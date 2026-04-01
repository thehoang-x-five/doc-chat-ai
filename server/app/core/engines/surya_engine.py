"""
Surya OCR Engine - High-precision Computer Vision based OCR
Uses Surya's Detection, Recognition, Layout analysis and Table Recognition
for processing scanned PDFs, images, and scientific documents.

Surya excels at:
- Scanned document OCR (90+ languages)
- Layout analysis (tables, figures, equations, headers, etc.)
- Reading order detection
- LaTeX OCR for mathematical formulas
- Character-level bounding box detection

This engine is used as a parallel alternative to Docling when:
1. The input is an image file (.jpg, .png, .webp, .tiff, .bmp)
2. The input is a scanned PDF (no embedded text layer)
3. The user explicitly requests "deep scan" / "scientific" mode
"""
import asyncio
import logging
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

from app.core.jobs import job_store, JobStatus, JobStep

logger = logging.getLogger(__name__)

# Try to import Surya components
SURYA_AVAILABLE = False
try:
    from surya.recognition import RecognitionPredictor
    from surya.detection import DetectionPredictor
    from surya.foundation import FoundationPredictor
    from surya.layout import LayoutPredictor
    from surya.table_rec import TableRecPredictor
    from surya.input.load import load_from_file
    from surya.common.util import rescale_bbox, expand_bbox
    from surya.settings import settings as surya_settings
    SURYA_AVAILABLE = True
    logger.info("Surya OCR engine loaded successfully")
except ImportError as e:
    logger.warning(f"Surya OCR not available: {e}. Install with: pip install surya-ocr")


# Layout labels from surya that represent text-bearing regions
TEXT_LABELS = {"Text", "ListItem", "Caption", "Footnote", "Form", "Code"}
HEADING_LABELS = {"SectionHeader", "PageHeader"}
TABLE_LABELS = {"Table"}
EQUATION_LABELS = {"Equation"}
FIGURE_LABELS = {"Picture", "Figure"}
SKIP_LABELS = {"PageFooter", "TableOfContents"}


class SuryaEngine:
    """
    High-precision OCR engine powered by Surya's vision models.
    
    Pipeline (matches official Surya library):
    1. Load PDF/image pages as PIL Images at DPI 96 (detection/layout)
    2. Load same pages at DPI 192 (highres for recognition accuracy)
    3. Run LayoutPredictor to classify each region (text, table, equation, etc.)
    4. Run RecognitionPredictor with highres_images for high quality text extraction
    5. Merge results in reading order into structured Markdown output
    """
    
    def __init__(self):
        """Initialize Surya predictors (lazy-loaded on first use)."""
        self._foundation_predictor = None
        self._detection_predictor = None
        self._recognition_predictor = None
        self._layout_foundation_predictor = None
        self._layout_predictor = None
        self._table_predictor = None
        self._initialized = False
    
    def _ensure_initialized(self, lightweight: bool = False):
        """Lazy-initialize the heavy ML models only when needed.
        
        Args:
            lightweight: If True, only load detection + recognition models
                        (skip layout + table_rec). Used for sub-OCR of embedded
                        images where layout analysis is unnecessary. Saves ~40% memory.
        
        Initialization pattern from official Surya CLI:
        - FoundationPredictor() → shared backbone for RecognitionPredictor
        - DetectionPredictor() → standalone text line detector
        - RecognitionPredictor(foundation) → text recognition
        - FoundationPredictor(checkpoint=LAYOUT) → separate backbone for Layout
        - LayoutPredictor(layout_foundation) → layout analysis
        """
        if self._initialized:
            return
        
        if not SURYA_AVAILABLE:
            raise ImportError(
                "Surya OCR is not installed. Install with: pip install surya-ocr"
            )
        
        mode_str = "lightweight (detect+recognize only)" if lightweight else "full"
        logger.info(f"Initializing Surya OCR models [{mode_str}] (this may take a moment)...")
        init_start = time.time()
        
        try:
            # 1. Foundation model (shared backbone for recognition)
            self._foundation_predictor = FoundationPredictor()
            
            # 2. Detection model (finds text line bounding boxes)
            self._detection_predictor = DetectionPredictor()
            
            # 3. Recognition model (reads text from detected lines)
            self._recognition_predictor = RecognitionPredictor(
                self._foundation_predictor
            )
            
            if not lightweight:
                # 4. Layout model (classifies regions: text, table, equation, etc.)
                self._layout_foundation_predictor = FoundationPredictor(
                    checkpoint=surya_settings.LAYOUT_MODEL_CHECKPOINT
                )
                self._layout_predictor = LayoutPredictor(
                    self._layout_foundation_predictor
                )
                
                # 5. Table Recognition model
                self._table_predictor = TableRecPredictor()
            
            self._initialized = True
            init_time = time.time() - init_start
            logger.info(f"Surya OCR models initialized [{mode_str}] in {init_time:.1f}s")
            
        except Exception as e:
            logger.error(f"Failed to initialize Surya models: {e}")
            raise
    
    async def process_document(
        self,
        job_id: str,
        file_path: Path,
        settings_dict: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process a document using Surya's vision-based OCR pipeline.
        
        Args:
            job_id: Job UUID string for progress tracking
            file_path: Path to the input file (PDF or image)
            settings_dict: Processing settings
            
        Returns:
            Dict with the standard result format compatible with DocumentEngine output
        """
        start_time = time.time()
        
        try:
            # Step 1: Update status
            job_store.update_job(
                job_id, status=JobStatus.RUNNING, step=JobStep.PREPROCESS,
                percent=5, message="Initializing Surya OCR engine..."
            )
            
            # Step 2: Initialize models (lazy)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._ensure_initialized)
            
            job_store.update_job(
                job_id, step=JobStep.PREPROCESS, percent=10,
                message="Loading document pages..."
            )
            
            # Step 3: Load pages at STANDARD DPI (96) for detection/layout
            images, names = await loop.run_in_executor(
                None, load_from_file, str(file_path)
            )
            
            if not images:
                raise ValueError(f"No pages could be loaded from {file_path}")
            
            logger.info(f"Loaded {len(images)} page(s) from {file_path.name} at DPI {surya_settings.IMAGE_DPI}")
            
            job_store.update_job(
                job_id, step=JobStep.PREPROCESS, percent=15,
                message="Preparing images for OCR..."
            )
            
            # Step 4: Batch processing configuration
            use_highres = settings_dict.get("surya_highres", False)
            
            # CHUNKING LOGIC: Process in batches of 5 pages to save memory
            CHUNK_SIZE = 5
            total_pages = len(images)
            layout_results = []
            ocr_results = []
            tables = []
            
            # Optional: Low-memory batch size for detection/layout
            import os
            # Use smaller internal batches to avoid CUDA OOM 
            os.environ["RECOGNITION_BATCH_SIZE"] = "2"
            os.environ["DETECTOR_BATCH_SIZE"] = "2"
            
            for start_idx in range(0, total_pages, CHUNK_SIZE):
                end_idx = min(start_idx + CHUNK_SIZE, total_pages)
                chunk_images = images[start_idx:end_idx]
                
                # Lazy load highres images for this specific chunk only to save massive amounts of RAM
                chunk_highres = None
                if use_highres:
                    if file_path.suffix.lower() == ".pdf":
                        import pypdfium2 as pdfium
                        pdf = pdfium.PdfDocument(str(file_path))
                        chunk_highres = []
                        for i in range(start_idx, end_idx):
                            page = pdf[i]
                            # Render at highres DPI
                            scale = surya_settings.IMAGE_DPI_HIGHRES / 72.0
                            pil_image = page.render(scale=scale).to_pil()
                            chunk_highres.append(pil_image)
                    else:
                        # For single image file, load directly
                        logger.info(f"Loading highres images (DPI={surya_settings.IMAGE_DPI_HIGHRES})")
                        hr_imgs, _ = await loop.run_in_executor(
                            None, load_from_file, str(file_path), None, surya_settings.IMAGE_DPI_HIGHRES
                        )
                        chunk_highres = hr_imgs[start_idx:end_idx]
                
                percent_base = 25 + int(50 * (start_idx / total_pages))
                job_store.update_job(
                    job_id, step=JobStep.PARSE, percent=percent_base,
                    message=f"Analyzing pages {start_idx+1}-{end_idx} of {total_pages}..."
                )
                
                # Run Layout Analysis for chunk
                def run_chunk_layout():
                    try:
                        return self._layout_predictor(chunk_images)
                    except Exception as e:
                        logger.warning(f"Batch layout failed ({e}). Proceeding one by one...")
                        res_list = []
                        for img in chunk_images:
                            try:
                                r = self._layout_predictor([img])
                                res_list.extend(r if r else [])
                            except Exception as sub_e:
                                logger.error(f"Single layout failed: {sub_e}")
                                from surya.schema import LayoutResult
                                res_list.append(LayoutResult(bboxes=[], image_bbox=[0,0,img.width,img.height]))
                        return res_list

                chunk_layout_res = await loop.run_in_executor(None, run_chunk_layout)
                layout_results.extend(chunk_layout_res)
                
                # Run Recognition for chunk
                def run_chunk_recognition():
                    try:
                        # Surya automatically uses highres_images as strict ROI crops based on low-res detection
                        return self._recognition_predictor(
                            chunk_images,
                            det_predictor=self._detection_predictor,
                            highres_images=chunk_highres,
                            sort_lines=True,
                            return_words=True,
                            math_mode=True,
                        )
                    except Exception as e:
                        logger.warning(f"Batch recognition failed ({e}). Proceeding one by one...")
                        res_list = []
                        for i, img in enumerate(chunk_images):
                            try:
                                hr = [chunk_highres[i]] if chunk_highres else None
                                r = self._recognition_predictor(
                                    [img],
                                    det_predictor=self._detection_predictor,
                                    highres_images=hr,
                                    sort_lines=True,
                                    return_words=True,
                                    math_mode=True,
                                )
                                res_list.extend(r if r else [])
                            except Exception as sub_e:
                                logger.error(f"Single recognition failed: {sub_e}")
                                from surya.schema import OCRResult
                                res_list.append(OCRResult(text_lines=[], image_bbox=[0,0,img.width,img.height]))
                        return res_list

                chunk_ocr_res = await loop.run_in_executor(None, run_chunk_recognition)
                
                # IMPLEMENT BOTTOM-STRIP FALLBACK CROP + RE-OCR CONSTRAINT
                for i, ocr_res in enumerate(chunk_ocr_res):
                    if not ocr_res.text_lines:
                        continue
                    
                    page_height = ocr_res.image_bbox[3]
                    last_line_y = max([l.bbox[3] for l in ocr_res.text_lines])
                    
                    # If the last recognized line is suspiciously close to the page edge but not at the very end
                    # (>92% but <99%), we do a fallback OCR on the bottom 15% strip.
                    if 0.92 * page_height < last_line_y < 0.99 * page_height:
                        logger.info(f"Page {start_idx+i+1}: Last line at {last_line_y}/{page_height}. Running bottom-strip fallback OCR.")
                        try:
                            # Crop bottom 15% strip
                            strip_top = int(page_height * 0.85)
                            strip_bbox = [0, strip_top, ocr_res.image_bbox[2], page_height]
                            
                            hr_img = chunk_highres[i] if chunk_highres else chunk_images[i]
                            # Scale strip_bbox to highres if needed
                            if chunk_highres:
                                strip_bbox = rescale_bbox(strip_bbox, chunk_images[i].size, hr_img.size)
                                
                            strip_crop = hr_img.crop(strip_bbox)
                            
                            # Re-OCR just the strip
                            strip_ocr = self._recognition_predictor(
                                [strip_crop],
                                det_predictor=self._detection_predictor,
                                highres_images=[strip_crop] if chunk_highres else None,
                            )[0]
                            
                            # Merge new lines if they are below the original last line
                            if strip_ocr.text_lines:
                                for line in strip_ocr.text_lines:
                                    # Adjust bbox back to original image space
                                    adjusted_bbox = [
                                        line.bbox[0],
                                        line.bbox[1] + strip_top,
                                        line.bbox[2],
                                        line.bbox[3] + strip_top
                                    ]
                                    if adjusted_bbox[1] > last_line_y - 5:  # Below existing lines
                                        line.bbox = adjusted_bbox
                                        ocr_res.text_lines.append(line)
                                        
                                # Re-sort lines
                                ocr_res.text_lines.sort(key=lambda x: x.bbox[1])
                        except Exception as e:
                            logger.error(f"Bottom-strip fallback failed for page {start_idx+i+1}: {e}")

                ocr_results.extend(chunk_ocr_res)
                
                # Process Tables locally per chunk
                table_crop_imgs = []
                table_page_idx = []
                
                for i, layout_pred in enumerate(chunk_layout_res):
                    img = chunk_images[i]
                    h_img = chunk_highres[i] if chunk_highres else img
                    for bbox_obj in layout_pred.bboxes:
                        if bbox_obj.label in TABLE_LABELS:
                            table_page_idx.append(start_idx + i)
                            bb = bbox_obj.bbox
                            if chunk_highres:
                                bb = rescale_bbox(bb, img.size, h_img.size)
                            bb = expand_bbox(bb)
                            table_crop_imgs.append(h_img.crop(bb))
                
                if table_crop_imgs:
                    def run_table_recognition():
                        try:
                            return self._table_predictor(table_crop_imgs)
                        except Exception as e:
                            logger.warning(f"Batch table rec failed ({e}).")
                            return [None]*len(table_crop_imgs)
                    
                    table_preds = await loop.run_in_executor(None, run_table_recognition)
                    
                    for idx, pred in enumerate(table_preds):
                        if not pred:
                            continue
                        out_pred = pred.model_dump()
                        out_pred["page_idx"] = table_page_idx[idx]
                        
                        html_table = "<table><tr>"
                        if hasattr(pred, "cols"):
                            for col in pred.cols:
                                html_table += "<th>Col</th>" if col.is_header else "<td>Col</td>"
                        html_table += "</tr></table>"
                        
                        tables.append({
                            "text": html_table,
                            "markdown": "",
                            "structured": out_pred,
                            "page_idx": table_page_idx[idx],
                            "caption": ""
                        })
                
                # Force garbage collection to free heavily unneeded inference memory
                import gc
                del chunk_images
                del chunk_highres
                del chunk_layout_res
                del chunk_ocr_res
                del table_crop_imgs
                gc.collect()
            
            logger.info(f"OCR recognition complete for {len(ocr_results)} pages")
            
            job_store.update_job(
                job_id, step=JobStep.POSTPROCESS, percent=75,
                message="Assembling structured output..."
            )
            
            # ==========================================================
            #  STEP 8: Merge Layout & Text into Markdown
            # ==========================================================
            full_text, markdown_text, pages, structured_images, equations = self._assemble_output(
                images, layout_results, ocr_results, tables
            )
            
            parse_time = int((time.time() - start_time) * 1000)
            
            # Calculate pseudo-confidence (average line confidence)
            avg_conf = None
            total_conf = 0
            conf_count = 0
            if ocr_results:
                for r in ocr_results:
                    if hasattr(r, "text_lines"):
                        for l in r.text_lines:
                            if hasattr(l, "confidence"):
                                total_conf += l.confidence
                                conf_count += 1
            if conf_count > 0:
                avg_conf = total_conf / conf_count

            layout_pages = self._build_layout_pages(layout_results, images)

            # Step 9: Build result in the same format as DocumentEngine
            result = {
                "jobId": job_id,
                "status": "done",
                "result": {
                    "fullText": full_text,
                    "markdownText": markdown_text,
                    "layoutText": full_text,
                    "pages": pages,
                    "structured": {
                        "tables": tables,
                        "equations": equations,
                        "images": structured_images
                    },
                    "layout": {
                        "pages": layout_pages
                    },
                    "meta": {
                        "parser": "surya",
                        "parse_method": settings_dict.get("parse_method", "auto"),
                        "language": settings_dict.get("language", "auto"),
                        "pageCount": total_pages,
                        "avgConfidence": avg_conf,
                        "highresEnabled": use_highres,
                        "highresDPI": surya_settings.IMAGE_DPI_HIGHRES if use_highres else None,
                        "timings": {
                            "parseMs": parse_time,
                            "postMs": 0
                        }
                    }
                },
                "error": None
            }
            
            job_store.update_job(
                job_id, status=JobStatus.DONE, step=JobStep.DONE,
                percent=100, message="Surya OCR processing complete",
                result=result
            )
            
            logger.info(
                f"Surya OCR completed for {file_path.name}: "
                f"{len(images)} pages, {len(full_text)} chars, "
                f"highres={'yes' if highres_images else 'no'}, "
                f"{parse_time}ms"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Surya OCR failed for job {job_id}: {e}", exc_info=True)
            job_store.update_job(
                job_id, status=JobStatus.ERROR,
                message=f"Surya OCR failed: {str(e)}", error=str(e)
            )
            raise
    
    def _assemble_output(
        self,
        images,
        layout_results,
        ocr_results,
        tables_data=None, # Added tables_data parameter
    ):
        """
        Merge layout analysis and OCR results into structured text.
        
        Strategy:
        - Use layout regions to classify content blocks
        - Map OCR text lines to their corresponding layout region
        - Generate Markdown with proper section headers, code blocks, 
          equation markers, and table indicators
        """
        all_full_text = []
        all_markdown = []
        pages = []
        all_tables = [] # This will now be populated from tables_data
        all_equations = []
        all_figures = []
        
        # Map table data to page for easier lookup
        tables_by_page = defaultdict(list)
        if tables_data:
            for table in tables_data:
                tables_by_page[table["page_idx"]].append(table)

        for page_idx, (image, layout, ocr) in enumerate(
            zip(images, layout_results, ocr_results)
        ):
            page_num = page_idx + 1
            page_text_parts = []
            page_md_parts = []
            
            # Get all OCR text lines for this page
            text_lines = ocr.text_lines if ocr.text_lines else []
            
            # Sort layout boxes by reading order (position field)
            layout_boxes = sorted(layout.bboxes, key=lambda b: b.position)
            
            if layout_boxes:
                # Track which lines are already assigned to avoid duplicates
                assigned_lines = set()
                
                # For each layout region, find OCR lines that fall within it
                for box in layout_boxes:
                    label = box.label
                    box_bbox = box.bbox  # [x1, y1, x2, y2]
                    
                    # Find text lines whose center falls within this layout box
                    region_lines = self._find_lines_in_region(
                        text_lines, box_bbox, assigned_lines
                    )
                    region_text = "\n".join(
                        [line.text for line in region_lines if line.text.strip()]
                    )
                    
                    if not region_text.strip():
                        if label in FIGURE_LABELS:
                            page_md_parts.append(
                                f"\n*[Figure on page {page_num}]*\n"
                            )
                            all_figures.append({
                                "id": f"fig-p{page_num}-{box.position}",
                                "page": page_num,
                                "bbox": list(box_bbox) if hasattr(box_bbox, '__iter__') else box_bbox,
                            })
                        continue
                    
                    # Format based on layout label
                    if label in HEADING_LABELS:
                        page_text_parts.append(region_text)
                        page_md_parts.append(f"## {region_text}")
                    elif label in TABLE_LABELS:
                        # Use the structured table data if available
                        page_tables = tables_by_page.get(page_idx, [])
                        current_table = next((t for t in page_tables if t["page_idx"] == page_idx and self._bbox_overlap(t["structured"]["bbox"], box_bbox)), None)
                        
                        if current_table:
                            # Use the HTML representation from table recognition
                            table_md = current_table["text"] # This is actually HTML
                            page_text_parts.append(region_text) # Keep OCR text for fullText
                            page_md_parts.append(
                                f"\n**[Table on page {page_num}]**\n\n{table_md}\n"
                            )
                            # Add to all_tables for structured output
                            all_tables.append({
                                "id": f"table-p{page_num}-{box.position}",
                                "name": f"Table (Page {page_num})",
                                "data": current_table["structured"], # Store the full structured data
                                "page": page_num,
                                "text": region_text # Keep OCR text for context
                            })
                        else:
                            # Fallback to just OCR text if no structured table data
                            page_text_parts.append(region_text)
                            page_md_parts.append(
                                f"\n**[Table on page {page_num}]**\n\n{region_text}\n"
                            )
                            all_tables.append({
                                "id": f"table-p{page_num}-{box.position}",
                                "name": f"Table (Page {page_num})",
                                "data": region_text, # Store plain text
                                "page": page_num
                            })
                    elif label in EQUATION_LABELS:
                        page_text_parts.append(region_text)
                        page_md_parts.append(f"\n$$\n{region_text}\n$$\n")
                        all_equations.append({
                            "id": f"eq-p{page_num}-{box.position}",
                            "latex": region_text,
                            "page": page_num
                        })
                    elif label in FIGURE_LABELS:
                        # Figure with detected text (e.g., captions within figures)
                        page_text_parts.append(region_text)
                        page_md_parts.append(
                            f"\n*[Figure on page {page_num}]*\n{region_text}\n"
                        )
                        all_figures.append({
                            "id": f"fig-p{page_num}-{box.position}",
                            "page": page_num,
                            "text": region_text,
                            "bbox": list(box_bbox) if hasattr(box_bbox, '__iter__') else box_bbox,
                        })
                    elif label == "Code":
                        page_text_parts.append(region_text)
                        page_md_parts.append(f"\n```\n{region_text}\n```\n")
                    elif label in SKIP_LABELS:
                        # Skip page footers, TOC in main text
                        continue
                    else:
                        # Normal text, list items, captions, footnotes, forms
                        page_text_parts.append(region_text)
                        page_md_parts.append(region_text)
            else:
                # No layout info - just use OCR lines directly
                for line in text_lines:
                    if line.text.strip():
                        page_text_parts.append(line.text)
                        page_md_parts.append(line.text)
            
            page_full = "\n".join(page_text_parts)
            page_md = "\n\n".join(page_md_parts)
            
            all_full_text.append(page_full)
            all_markdown.append(page_md)
            
            # Calculate page confidence
            page_confidence = 0.0
            if text_lines:
                page_confidence = sum(
                    l.confidence for l in text_lines
                ) / len(text_lines)
            
            pages.append({
                "page": page_num,
                "text": page_full,
                "confidence": round(page_confidence, 3)
            })
        
        full_text = "\n\n".join(all_full_text)
        markdown_text = "\n\n---\n\n".join(all_markdown)  # Page separator
        
        # structured = { # This is now handled directly in process_document
        #     "tables": all_tables,
        #     "equations": all_equations,
        #     "images": all_figures,
        # }
        
        return full_text, markdown_text, pages, all_figures, all_equations # Return all_figures and all_equations
    
    def _find_lines_in_region(self, text_lines, region_bbox, assigned_lines=None):
        """
        Find OCR text lines whose center point falls within a layout region bbox.
        
        Args:
            text_lines: List of TextLine objects from OCR
            region_bbox: [x1, y1, x2, y2] of the layout region
            assigned_lines: Set of already-assigned line indices to avoid duplicates
            
        Returns:
            List of TextLine objects within the region
        """
        rx1, ry1, rx2, ry2 = region_bbox
        matched = []
        if assigned_lines is None:
            assigned_lines = set()
        
        for idx, line in enumerate(text_lines):
            if idx in assigned_lines:
                continue
                
            # Get line center from its polygon
            if hasattr(line, 'polygon') and line.polygon:
                poly = line.polygon
                cx = sum(p[0] for p in poly) / len(poly)
                cy = sum(p[1] for p in poly) / len(poly)
            elif hasattr(line, 'bbox') and line.bbox:
                bx1, by1, bx2, by2 = line.bbox
                cx = (bx1 + bx2) / 2
                cy = (by1 + by2) / 2
            else:
                continue
            
            # Check if center is within region (with small tolerance)
            tolerance = 5  # pixels
            if (rx1 - tolerance <= cx <= rx2 + tolerance and
                ry1 - tolerance <= cy <= ry2 + tolerance):
                matched.append(line)
                assigned_lines.add(idx)
        
        return matched
    
    def _build_layout_pages(self, layout_results, images):
        """Build layout page info compatible with DocumentEngine format."""
        layout_pages = []
        
        for page_idx, (layout, image) in enumerate(
            zip(layout_results, images)
        ):
            blocks = []
            for box in layout.bboxes:
                block_type = "text"
                label = box.label
                
                if label in TABLE_LABELS:
                    block_type = "table"
                elif label in FIGURE_LABELS:
                    block_type = "image"
                elif label in HEADING_LABELS:
                    block_type = "heading"
                elif label in EQUATION_LABELS:
                    block_type = "formula"
                elif label == "Code":
                    block_type = "code"
                
                blocks.append({
                    "id": f"block-p{page_idx+1}-{box.position}",
                    "type": block_type,
                    "label": label,
                    "bbox": {
                        "x": box.bbox[0] / image.size[0],
                        "y": box.bbox[1] / image.size[1],
                        "width": (box.bbox[2] - box.bbox[0]) / image.size[0],
                        "height": (box.bbox[3] - box.bbox[1]) / image.size[1],
                    },
                    "confidence": round(box.confidence, 3),
                    "position": box.position,
                })
            
            layout_pages.append({
                "page": page_idx + 1,
                "width": image.size[0],
                "height": image.size[1],
                "blocks": blocks
            })
        
        return layout_pages
    
    def _calc_avg_confidence(self, ocr_results):
        """Calculate average OCR confidence across all pages."""
        total_conf = 0.0
        total_lines = 0
        
        for result in ocr_results:
            for line in result.text_lines:
                total_conf += line.confidence
                total_lines += 1
        
        return round(total_conf / max(total_lines, 1), 3)

    def _bbox_overlap(self, bbox1, bbox2, threshold=0.5):
        """Check if two bounding boxes overlap by a certain threshold (IOU)."""
        # Ensure bboxes are in [x1, y1, x2, y2] format
        if len(bbox1) == 8: # Polygon
            from surya.schema import Bbox
            bbox1 = Bbox(bbox1).bbox
        if len(bbox2) == 8: # Polygon
            from surya.schema import Bbox
            bbox2 = Bbox(bbox2).bbox

        x1_a, y1_a, x2_a, y2_a = bbox1
        x1_b, y1_b, x2_b, y2_b = bbox2

        # Calculate intersection coordinates
        x_overlap_start = max(x1_a, x1_b)
        y_overlap_start = max(y1_a, y1_b)
        x_overlap_end = min(x2_a, x2_b)
        y_overlap_end = min(y2_a, y2_b)

        # Calculate intersection area
        intersection_width = max(0, x_overlap_end - x_overlap_start)
        intersection_height = max(0, y_overlap_end - y_overlap_start)
        intersection_area = intersection_width * intersection_height

        # Calculate union area
        area_a = (x2_a - x1_a) * (y2_a - y1_a)
        area_b = (x2_b - x1_b) * (y2_b - y1_b)
        union_area = area_a + area_b - intersection_area

        if union_area == 0:
            return False

        iou = intersection_area / union_area
        return iou >= threshold

    async def process_crops(
        self,
        crops: List[Any],
        page_image: Any,
    ) -> str:
        """
        Process cropped image regions using Surya OCR.
        Used for nested sub-OCR when Docling detects embedded images in PDFs.
        
        Args:
            crops: List of dicts with 'bbox' key [x1, y1, x2, y2]
            page_image: PIL Image of the full page
            
        Returns:
            Combined OCR text from all cropped regions
        """
        if not SURYA_AVAILABLE:
            return ""
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._ensure_initialized)
        
        crop_images = []
        for crop_info in crops:
            bbox = crop_info.get('bbox', crop_info.get('polygon'))
            if not bbox:
                continue
            
            # Handle both [x1,y1,x2,y2] and polygon formats
            if isinstance(bbox[0], (list, tuple)):
                # Polygon format - get bounding box
                xs = [p[0] for p in bbox]
                ys = [p[1] for p in bbox]
                x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
            else:
                x1, y1, x2, y2 = bbox[:4]
            
            # Crop the image region
            try:
                cropped = page_image.crop((int(x1), int(y1), int(x2), int(y2)))
                if cropped.size[0] > 10 and cropped.size[1] > 10:
                    crop_images.append(cropped.convert("RGB"))
            except Exception as e:
                logger.warning(f"Failed to crop image region: {e}")
                continue
        
        if not crop_images:
            return ""
        
        # Run OCR on all crop images
        def run_crop_ocr():
            try:
                return self._recognition_predictor(
                    crop_images,
                    det_predictor=self._detection_predictor,
                    sort_lines=True,
                    math_mode=True,
                )
            except Exception as e:
                logger.warning(f"Batch crop OCR failed ({str(e)}). Processing crops one by one...")
                results = []
                for crop_img in crop_images:
                    try:
                        res = self._recognition_predictor(
                            [crop_img],
                            det_predictor=self._detection_predictor,
                            sort_lines=True,
                            math_mode=True,
                        )
                        if res:
                            results.extend(res)
                    except Exception as sub_e:
                        logger.error(f"Failed to OCR a single crop: {sub_e}")
                        # Append empty result to keep list length consistent if needed, 
                        # but _recognition_predictor returns an OCRResult per image.
                        # Surya's OCRResult has text_lines
                        from surya.schema import OCRResult
                        results.append(OCRResult(text_lines=[], image_bbox=[0,0,crop_img.width,crop_img.height]))
                return results

        try:
            ocr_results = await loop.run_in_executor(
                None,
                run_crop_ocr
            )
            
            all_text = []
            for result in ocr_results:
                for line in result.text_lines:
                    if line.text.strip():
                        all_text.append(line.text)
            
            return "\n".join(all_text)
            
        except Exception as e:
            logger.error(f"Crop OCR failed: {e}")
            return ""


# ============================================================================
# Utility: Determine if a file should use Surya instead of Docling
# ============================================================================
SURYA_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.tiff', '.tif', '.bmp'}
SURYA_PREFERRED_EXTENSIONS = SURYA_IMAGE_EXTENSIONS  # Images always go to Surya


def should_use_surya(file_path: Path, config: dict = None) -> bool:
    """
    Determine whether the SuryaEngine should be used for this file.
    
    Rules:
    1. Image files (.jpg, .png, .webp, .tiff, .bmp) → Always Surya
    2. If config explicitly requests surya parser → Surya 
    3. If USE_SURYA_FOR_PDF env is set and file is PDF → Surya
    4. Otherwise → Docling (default)
    
    Args:
        file_path: Path to the input file
        config: Optional processing config dict
        
    Returns:
        True if SuryaEngine should handle this file
    """
    if not SURYA_AVAILABLE:
        return False
    
    ext = file_path.suffix.lower()
    config = config or {}
    
    # Rule 1: Image files always use Surya
    if ext in SURYA_PREFERRED_EXTENSIONS:
        return True
    
    # Rule 2: Explicit parser request
    if config.get("parser") == "surya":
        return True
    
    # Rule 3: Environment variable for PDF
    import os
    if ext == '.pdf' and os.environ.get("USE_SURYA_FOR_PDF", "").lower() in ("true", "1", "yes"):
        return True
    
    return False
