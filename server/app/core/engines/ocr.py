"""
Document processing engine using Docling
"""
import asyncio
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional, List

from app.core.config import settings
from app.core.jobs import job_store, JobStatus, JobStep

logger = logging.getLogger(__name__)

# Try to import docling
try:
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions, OcrAutoOptions
    from docling_core.types.doc import PictureItem, DocItemLabel
    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False
    PictureItem = None
    DocItemLabel = None
    logger.warning("Docling not available. Using simulation mode.")

# Try to import AI provider manager
try:
    from app.services.infrastructure.ai_providers.manager import AIProviderManager
    AI_ENHANCEMENT_AVAILABLE = True
except ImportError:
    AI_ENHANCEMENT_AVAILABLE = False
    logger.warning("AI enhancement not available")

# Try to import Vietnamese processor
try:
    from app.core.processors.vietnamese import vietnamese_processor
    VIETNAMESE_PROCESSOR_AVAILABLE = True
except ImportError:
    VIETNAMESE_PROCESSOR_AVAILABLE = False
    logger.warning("Vietnamese processor not available")


class DocumentEngine:
    def __init__(self):
        self.converter = None
        self.ai_manager = None
        
        if DOCLING_AVAILABLE:
            try:
                # Configure Docling pipeline options for full extraction
                # D3: Handle mixed text layer + scanned layer (do_ocr=True)
                pipeline_options = PdfPipelineOptions()
                pipeline_options.do_ocr = True
                pipeline_options.do_table_structure = True
                pipeline_options.generate_page_images = True
                pipeline_options.generate_picture_images = True
                pipeline_options.ocr_options = OcrAutoOptions()
                
                self.converter = DocumentConverter(
                    allowed_formats=[
                        InputFormat.PDF, InputFormat.IMAGE, InputFormat.DOCX, 
                        InputFormat.HTML, InputFormat.PPTX, InputFormat.XLSX,
                        InputFormat.ASCIIDOC, InputFormat.MD
                    ],
                    format_options={
                        InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
                    }
                )
                logger.info("Docling converter initialized with OCR and image extraction enabled")
            except Exception as e:
                logger.error(f"Failed to initialize Docling converter: {e}")
                self.converter = None
        
        # Initialize AI provider manager if enabled
        if settings.AI_ENHANCEMENT_ENABLED and AI_ENHANCEMENT_AVAILABLE:
            try:
                self.ai_manager = AIProviderManager()
                logger.info("AI Provider Manager initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize AI Provider Manager: {e}")
                self.ai_manager = None

        
    async def process_document(
        self,
        job_id: str,
        file_path: Path,
        settings_dict: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process document with Docling or simulation"""
        start_time = time.time()
        
        try:
            # Update job status
            job_store.update_job(job_id, status=JobStatus.RUNNING, step=JobStep.PREPROCESS, 
                               percent=10, message="Preprocessing document...")
            
            parser = settings_dict.get("parser", settings.DEFAULT_PARSER)
            
            # Update job status
            job_store.update_job(job_id, step=JobStep.PARSE, percent=30, 
                               message=f"Parsing with {parser}...")
            
            parse_time_start = time.time()
            
            # Check file type
            file_ext = file_path.suffix.lower()
            text_extensions = ['.txt', '.md', '.csv', '.json', '.rtf', '.odt', '.xml', '.html', '.xhtml']
            
            # Try to use Docling if available for non-text files
            if file_ext in text_extensions:
                # Direct text file processing
                result = await self._process_text_file(job_id, file_path, settings_dict)
            elif DOCLING_AVAILABLE and self.converter:
                try:
                    result = await self._process_with_docling(job_id, file_path, settings_dict)
                except Exception as e:
                    logger.error(f"Docling processing failed: {e}")
                    # For text files, try direct reading as fallback
                    if file_ext in text_extensions:
                        result = await self._process_text_file(job_id, file_path, settings_dict)
                    else:
                        raise ValueError(f"OCR processing failed: {str(e)}")
            else:
                raise ValueError(
                    f"Cannot process {file_ext} files. Docling OCR engine is not available. "
                    f"Please install Docling: pip install docling"
                )
            
            parse_time = int((time.time() - parse_time_start) * 1000)
            
            # Update timings
            if "result" in result and "meta" in result["result"]:
                result["result"]["meta"]["timings"]["parseMs"] = parse_time
            
            # AI Enhancement step (if enabled)
            # Skip if already enhanced (e.g., from _process_text_file)
            logger.info(f"Checking AI enhancement: enabled={settings.AI_ENHANCEMENT_ENABLED}, manager={self.ai_manager is not None}")
            already_enhanced = "result" in result and "enhancedText" in result.get("result", {})
            logger.info(f"Already enhanced: {already_enhanced}")
            
            if settings.AI_ENHANCEMENT_ENABLED and self.ai_manager and not already_enhanced:
                try:
                    logger.info("Starting AI enhancement...")
                    job_store.update_job(job_id, step=JobStep.POSTPROCESS, percent=85, 
                                       message="Enhancing text with AI...")
                    
                    logger.info(f"Result keys: {result.keys()}")
                    full_text = result.get("result", {}).get("fullText", "")
                    target_language = settings_dict.get("language", "auto")
                    logger.info(f"Full text length: {len(full_text)}, target_language: {target_language}")
                    
                    if full_text:
                        # Vietnamese processing (if requested)
                        if VIETNAMESE_PROCESSOR_AVAILABLE and target_language == "vi":
                            logger.info("Applying Vietnamese text processing...")
                            full_text = vietnamese_processor.process_vietnamese_text(
                                full_text,
                                restore_tones=True,
                                normalize=True
                            )
                            # Update result with processed text
                            result["result"]["fullText"] = full_text
                        
                        # Determine document type
                        document_type = self._detect_document_type(file_path, full_text)
                        
                        # Read image data for vision enhancement if available
                        image_data = None
                        if settings.AI_USE_VISION_WHEN_AVAILABLE and file_ext in ['.jpg', '.jpeg', '.png', '.webp']:
                            try:
                                with open(file_path, 'rb') as f:
                                    image_data = f.read()
                            except Exception as e:
                                logger.warning(f"Could not read image for vision enhancement: {e}")
                        
                        # Enhance text with AI (includes language translation if needed)
                        enhancement_result = await self.ai_manager.enhance_text(
                            text=full_text,
                            document_type=document_type,
                            image_data=image_data,
                            target_language=target_language
                        )
                        
                        logger.info(f"Got enhancement result: {enhancement_result}")
                        logger.info(f"Enhanced text: {enhancement_result.enhanced_text[:100]}")
                        
                        # Add enhanced text to result
                        logger.info(f"Result structure: {result.keys()}")
                        if "result" in result:
                            logger.info(f"Adding enhancedText to result...")
                            result["result"]["enhancedText"] = enhancement_result.enhanced_text
                            result["result"]["aiMetadata"] = {
                                "provider": enhancement_result.provider_used,
                                "model": enhancement_result.model_used,
                                "processingTimeMs": enhancement_result.processing_time_ms,
                                "improvements": enhancement_result.improvements,
                                "fallbackOccurred": enhancement_result.fallback_occurred,
                                "targetLanguage": target_language
                            }
                            
                            logger.info(f"AI enhancement completed with {enhancement_result.provider_used}")
                            logger.info(f"Enhanced text length: {len(enhancement_result.enhanced_text)}")
                            logger.info(f"Enhanced text preview: {enhancement_result.enhanced_text[:200]}")
                            logger.info(f"Result now has enhancedText: {'enhancedText' in result['result']}")
                        else:
                            logger.error("No 'result' key in result dict!")
                    
                except Exception as e:
                    logger.error(f"AI enhancement failed: {e}")
                    logger.exception("Full traceback:")
                    # Continue without enhancement - don't fail the whole job
            
            # Update job as done
            job_store.update_job(job_id, status=JobStatus.DONE, step=JobStep.DONE, 
                               percent=100, message="Processing complete", result=result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing document for job {job_id}: {e}", exc_info=True)
            job_store.update_job(job_id, status=JobStatus.ERROR, 
                               message=f"Processing failed: {str(e)}", error=str(e))
            raise

    async def _process_with_docling(
        self,
        job_id: str,
        file_path: Path,
        settings_dict: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process document using Docling"""
        
        # Update progress
        job_store.update_job(job_id, step=JobStep.PARSE, percent=40, 
                           message="Converting document with Docling...")
        
        logger.info(f"Starting Docling conversion for: {file_path}")
        
        # Run Docling conversion in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, 
            lambda: self.converter.convert(str(file_path))
        )
        
        logger.info(f"Docling conversion completed, extracting content...")
        
        # Update progress
        job_store.update_job(job_id, step=JobStep.POSTPROCESS, percent=80, 
                           message="Building output...")
        
        # Extract text and structure from Docling result
        doc = result.document
        
        # Get full text - try multiple methods to ensure we get EVERYTHING
        full_text = ""
        if hasattr(doc, 'export_to_text'):
            full_text = doc.export_to_text()
        elif hasattr(doc, 'text'):
            full_text = doc.text
        else:
            full_text = str(doc)
        
        # Export DoclingDocument as structured JSON (lossless, preserves page/bbox/provenance)
        docling_json = None
        try:
            if hasattr(doc, 'model_dump'):
                docling_json = doc.model_dump(mode='python')
            elif hasattr(doc, 'export_to_dict'):
                docling_json = doc.export_to_dict()
        except Exception as e:
            logger.warning(f"Could not export DoclingDocument JSON: {e}")
        
        # Also try to get text from all items (including headers/footers)
        # AND collect embedded images (PictureItem) with their bounding boxes
        embedded_images = []
        if hasattr(doc, 'iterate_items'):
            try:
                all_text_parts = []
                for item, level in doc.iterate_items():
                    if hasattr(item, 'text') and item.text:
                        all_text_parts.append(item.text)
                    
                    # Detect PictureItem (embedded images/figures)
                    if PictureItem is not None and isinstance(item, PictureItem):
                        img_info = self._extract_picture_info(item, doc)
                        if img_info:
                            embedded_images.append(img_info)
                    elif hasattr(item, 'label') and str(item.label) in (
                        'picture', 'DocItemLabel.PICTURE', 'figure'
                    ):
                        img_info = self._extract_picture_info(item, doc)
                        if img_info:
                            embedded_images.append(img_info)
                
                # If we got more text from items, use that
                items_text = '\n'.join(all_text_parts)
                if len(items_text) > len(full_text):
                    logger.info(f"Using items text ({len(items_text)} chars) instead of export ({len(full_text)} chars)")
                    full_text = items_text
            except Exception as e:
                logger.warning(f"Could not iterate items: {e}")
        
        if embedded_images:
            logger.info(f"Found {len(embedded_images)} embedded images in document")
        
        logger.info(f"Extracted text length: {len(full_text)} chars")
        
        # Get markdown
        markdown_text = ""
        if hasattr(doc, 'export_to_markdown'):
            markdown_text = doc.export_to_markdown()
        else:
            markdown_text = full_text
        
        # Build pages - try to get page-level content
        pages = []
        page_count = 1
        
        # Try different ways to get pages
        if hasattr(doc, 'pages') and doc.pages:
            page_count = len(doc.pages)
            for i, page in enumerate(doc.pages):
                page_text = ""
                if hasattr(page, 'export_to_text'):
                    page_text = page.export_to_text()
                elif hasattr(page, 'text'):
                    page_text = page.text
                else:
                    page_text = str(page)
                pages.append({
                    "page": i + 1,
                    "text": page_text,
                    "confidence": 0.95
                })
        elif hasattr(doc, 'num_pages'):
            page_count = doc.num_pages() if callable(doc.num_pages) else doc.num_pages
            # Split text evenly across pages as fallback
            if page_count and page_count > 1:
                lines = full_text.split('\n')
                lines_per_page = max(1, len(lines) // page_count)
                for i in range(page_count):
                    start = i * lines_per_page
                    end = start + lines_per_page if i < page_count - 1 else len(lines)
                    page_text = '\n'.join(lines[start:end])
                    pages.append({
                        "page": i + 1,
                        "text": page_text,
                        "confidence": 0.95
                    })
            else:
                pages = [{"page": 1, "text": full_text, "confidence": 0.95}]
        else:
            pages = [{"page": 1, "text": full_text, "confidence": 0.95}]
        
        logger.info(f"Extracted {len(pages)} pages")
        
        # Build structured data
        tables = []
        if hasattr(doc, 'tables') and doc.tables:
            for i, table in enumerate(doc.tables):
                table_data = str(table)
                if hasattr(table, 'export_to_dataframe'):
                    try:
                        df = table.export_to_dataframe()
                        table_data = df.to_string()
                    except:
                        pass
                tables.append({
                    "id": f"table-{i+1}",
                    "name": f"Table {i+1}",
                    "data": table_data
                })
        
        # Build layout with actual bounding boxes from Docling
        layout_pages = self._extract_layout_from_docling(doc, pages, full_text)
        
        return {
            "jobId": job_id,
            "status": "done",
            "result": {
                "fullText": full_text,
                "markdownText": markdown_text,
                "layoutText": full_text,
                "pages": pages,
                "structured": {
                    "tables": tables,
                    "equations": [],
                    "images": embedded_images,
                    "docling_document": docling_json,  # Full DoclingDocument for metadata
                },
                "layout": {
                    "pages": layout_pages
                },
                "meta": {
                    "parser": "docling",
                    "parse_method": settings_dict.get("parse_method", "auto"),
                    "language": settings_dict.get("language", "auto"),
                    "pageCount": len(pages),
                    "avgConfidence": None,  # Docling is a structural parser, not OCR — no confidence score
                    "timings": {
                        "parseMs": 0,
                        "postMs": 100
                    }
                }
            },
            "error": None
        }

    def _extract_layout_from_docling(
        self,
        doc: Any,
        pages: List[Dict],
        full_text: str
    ) -> List[Dict[str, Any]]:
        """Extract detailed layout with bounding boxes from Docling document"""
        layout_pages = []
        
        try:
            # Try to get document items with bounding boxes
            doc_items = []
            page_dimensions = {}
            
            # Method 1: Try to get items from document body
            if hasattr(doc, 'body') and doc.body:
                for item in doc.body:
                    doc_items.append(item)
            
            # Method 2: Try iterate_items method
            if not doc_items and hasattr(doc, 'iterate_items'):
                try:
                    for item, level in doc.iterate_items():
                        doc_items.append(item)
                except:
                    pass
            
            # Method 3: Try to get from pages directly
            if hasattr(doc, 'pages') and doc.pages:
                for page_no, page in enumerate(doc.pages):
                    page_num = page_no + 1
                    page_width = getattr(page, 'width', 1.0) or 1.0
                    page_height = getattr(page, 'height', 1.414) or 1.414
                    page_dimensions[page_num] = (page_width, page_height)
                    
                    # Try to get items from page
                    if hasattr(page, 'items'):
                        for item in page.items:
                            if not hasattr(item, 'page_no'):
                                item.page_no = page_num
                            doc_items.append(item)
            
            # Group items by page
            items_by_page = {}
            for item in doc_items:
                page_no = getattr(item, 'page_no', 1) or 1
                if page_no not in items_by_page:
                    items_by_page[page_no] = []
                items_by_page[page_no].append(item)
            
            # Build layout pages
            num_pages = max(len(pages), max(items_by_page.keys()) if items_by_page else 1)
            
            for page_num in range(1, num_pages + 1):
                page_width, page_height = page_dimensions.get(page_num, (1.0, 1.414))
                
                blocks = []
                page_items = items_by_page.get(page_num, [])
                
                for idx, item in enumerate(page_items):
                    # Extract text
                    item_text = ""
                    if hasattr(item, 'text'):
                        item_text = item.text
                    elif hasattr(item, 'export_to_text'):
                        item_text = item.export_to_text()
                    else:
                        item_text = str(item)
                    
                    # Determine block type
                    block_type = "text"
                    is_image = False
                    if hasattr(item, 'label'):
                        label = str(item.label).lower()
                        if 'table' in label:
                            block_type = "table"
                        elif 'figure' in label or 'image' in label or 'picture' in label:
                            block_type = "image"
                            is_image = True
                        elif 'title' in label or 'heading' in label:
                            block_type = "heading"
                        elif 'list' in label:
                            block_type = "list"
                    if PictureItem is not None and isinstance(item, PictureItem):
                        block_type = "image"
                        is_image = True
                    
                    # Skip items with no text UNLESS they are images
                    if (not item_text or not item_text.strip()) and not is_image:
                        continue
                    
                    # Extract bounding box
                    bbox = self._extract_bbox(item, page_width, page_height)
                    
                    # Build lines from text
                    lines = self._build_lines_from_text(item_text, bbox) if item_text.strip() else []
                    
                    blocks.append({
                        "type": block_type,
                        "text": item_text,
                        "bbox": bbox,
                        "confidence": 0.95,
                        "lines": lines
                    })
                
                # If no blocks extracted, create from page text
                if not blocks and page_num <= len(pages):
                    page_text = pages[page_num - 1].get("text", "")
                    if page_text:
                        lines = self._build_lines_from_text(page_text, {"x": 0.05, "y": 0.05, "w": 0.9, "h": 0.9})
                        blocks.append({
                            "type": "text",
                            "text": page_text,
                            "bbox": {"x": 0.05, "y": 0.05, "w": 0.9, "h": 0.9},
                            "confidence": 0.95,
                            "lines": lines
                        })
                
                layout_pages.append({
                    "page": page_num,
                    "width": 1.0,
                    "height": page_height / page_width if page_width else 1.414,
                    "blocks": blocks
                })
            
            logger.info(f"Extracted layout: {len(layout_pages)} pages, {sum(len(p['blocks']) for p in layout_pages)} blocks")
            
        except Exception as e:
            logger.warning(f"Failed to extract detailed layout: {e}, using fallback")
            # Fallback to simple layout
            for i, page_data in enumerate(pages):
                page_text = page_data.get("text", "")
                lines = self._build_lines_from_text(page_text, {"x": 0.05, "y": 0.05, "w": 0.9, "h": 0.9})
                layout_pages.append({
                    "page": i + 1,
                    "width": 1.0,
                    "height": 1.414,
                    "blocks": [{
                        "type": "text",
                        "text": page_text,
                        "bbox": {"x": 0.05, "y": 0.05, "w": 0.9, "h": 0.9},
                        "confidence": 0.95,
                        "lines": lines
                    }]
                })
        
        return layout_pages
    
    def _extract_bbox(self, item: Any, page_width: float, page_height: float) -> Dict[str, float]:
        """Extract normalized bounding box from Docling item"""
        try:
            # Try different bbox attributes
            bbox = None
            
            if hasattr(item, 'prov') and item.prov:
                # Docling provenance contains bbox info
                for prov in item.prov:
                    if hasattr(prov, 'bbox'):
                        bbox = prov.bbox
                        break
            
            if not bbox and hasattr(item, 'bbox'):
                bbox = item.bbox
            
            if not bbox and hasattr(item, 'bounding_box'):
                bbox = item.bounding_box
            
            if bbox:
                # Normalize coordinates to 0-1 range
                if hasattr(bbox, 'l'):  # Docling BoundingBox format
                    x = bbox.l / page_width if page_width else bbox.l
                    y = bbox.t / page_height if page_height else bbox.t
                    w = (bbox.r - bbox.l) / page_width if page_width else (bbox.r - bbox.l)
                    h = (bbox.b - bbox.t) / page_height if page_height else (bbox.b - bbox.t)
                elif isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
                    x = bbox[0] / page_width if page_width else bbox[0]
                    y = bbox[1] / page_height if page_height else bbox[1]
                    w = (bbox[2] - bbox[0]) / page_width if page_width else (bbox[2] - bbox[0])
                    h = (bbox[3] - bbox[1]) / page_height if page_height else (bbox[3] - bbox[1])
                elif hasattr(bbox, 'x'):
                    x = bbox.x / page_width if page_width else bbox.x
                    y = bbox.y / page_height if page_height else bbox.y
                    w = bbox.width / page_width if page_width and hasattr(bbox, 'width') else 0.9
                    h = bbox.height / page_height if page_height and hasattr(bbox, 'height') else 0.05
                else:
                    return {"x": 0.05, "y": 0.05, "w": 0.9, "h": 0.1}
                
                # Clamp values to valid range
                x = max(0, min(1, x))
                y = max(0, min(1, y))
                w = max(0.01, min(1 - x, w))
                h = max(0.01, min(1 - y, h))
                
                return {"x": x, "y": y, "w": w, "h": h}
        except Exception as e:
            logger.debug(f"Failed to extract bbox: {e}")
        
        return {"x": 0.05, "y": 0.05, "w": 0.9, "h": 0.1}
    
    def _build_lines_from_text(self, text: str, parent_bbox: Dict[str, float]) -> List[Dict[str, Any]]:
        """Build line-level layout from text content"""
        lines = []
        text_lines = text.split('\n')
        
        if not text_lines:
            return lines
        
        line_height = min(0.04, parent_bbox["h"] / max(len(text_lines), 1))
        line_gap = 0.01
        
        for idx, line_text in enumerate(text_lines):
            if not line_text.strip():
                continue
            
            y = parent_bbox["y"] + idx * (line_height + line_gap)
            if y + line_height > parent_bbox["y"] + parent_bbox["h"]:
                break
            
            # Build words
            words = []
            word_list = line_text.split()
            if word_list:
                word_width = min(0.15, parent_bbox["w"] / max(len(word_list), 1))
                x_cursor = parent_bbox["x"]
                
                for word_text in word_list:
                    # Estimate word width based on character count
                    estimated_width = min(word_width * (len(word_text) / 5), parent_bbox["w"] - (x_cursor - parent_bbox["x"]))
                    
                    words.append({
                        "text": word_text,
                        "bbox": {
                            "x": x_cursor,
                            "y": y,
                            "w": estimated_width,
                            "h": line_height
                        },
                        "confidence": 0.95
                    })
                    x_cursor += estimated_width + 0.01
            
            lines.append({
                "text": line_text,
                "confidence": 0.95,
                "bbox": {
                    "x": parent_bbox["x"],
                    "y": y,
                    "w": parent_bbox["w"],
                    "h": line_height
                },
                "words": words
            })
        
        return lines

    @staticmethod
    def _decode_text_bytes(file_content: bytes) -> str:
        try:
            return file_content.decode("utf-8-sig")
        except UnicodeDecodeError:
            return file_content.decode("latin-1", errors="ignore")

    @classmethod
    def _extract_rtf_text(cls, file_content: bytes) -> str:
        import re

        text = cls._decode_text_bytes(file_content)
        text = re.sub(r"\\par[d]?", "\n", text)
        text = re.sub(r"\\tab", "\t", text)
        text = re.sub(r"\\'[0-9a-fA-F]{2}", " ", text)
        text = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", text)
        text = re.sub(r"[{}]", "", text)
        return re.sub(r"\n{3,}", "\n\n", text).strip()

    @staticmethod
    def _extract_odt_text(file_content: bytes) -> str:
        import io
        import zipfile
        import xml.etree.ElementTree as ET

        with zipfile.ZipFile(io.BytesIO(file_content)) as archive:
            xml_data = archive.read("content.xml")

        root = ET.fromstring(xml_data)
        paragraphs = []
        for elem in root.iter():
            if elem.tag.endswith("}p") or elem.tag.endswith("}h"):
                text = "".join(elem.itertext()).strip()
                if text:
                    paragraphs.append(text)
        return "\n\n".join(paragraphs).strip()

    @classmethod
    def _extract_text_like_file(cls, file_path: Path) -> str:
        file_content = file_path.read_bytes()
        file_ext = file_path.suffix.lower()

        if file_ext == ".rtf":
            return cls._extract_rtf_text(file_content)
        if file_ext == ".odt":
            return cls._extract_odt_text(file_content)

        text = cls._decode_text_bytes(file_content)
        if file_ext == ".json":
            try:
                import json

                return json.dumps(json.loads(text), ensure_ascii=False, indent=2)
            except Exception:
                return text
        return text

    async def _process_text_file(
        self,
        job_id: str,
        file_path: Path,
        settings_dict: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process plain text files directly"""
        
        # Update progress
        job_store.update_job(job_id, step=JobStep.PARSE, percent=50, 
                           message="Reading text file...")
        
        # Read file content
        full_text = ""
        file_ext = file_path.suffix.lower()
        
        if file_ext in ['.txt', '.md', '.csv', '.json', '.rtf', '.odt', '.xml', '.html', '.xhtml']:
            try:
                full_text = self._extract_text_like_file(file_path)
            except Exception as e:
                logger.error(f"Could not read text file: {e}")
                raise ValueError(f"Could not read file: {file_path.name}")
        else:
            # For non-text files without Docling, raise error
            raise ValueError(
                f"Cannot process {file_ext} files. Docling OCR engine failed or is not available. "
                f"Please ensure Docling is properly installed: pip install docling"
            )
        
        # Update progress
        job_store.update_job(job_id, step=JobStep.POSTPROCESS, percent=80, 
                           message="Building output...")
        
        markdown_text = f"# {file_path.stem}\n\n{full_text}"
        
        pages = [{
            "page": 1,
            "text": full_text,
            "confidence": 1.0
        }]
        
        # Build layout with lines for text files
        block_bbox = {"x": 0.05, "y": 0.05, "w": 0.9, "h": 0.9}
        lines = self._build_lines_from_text(full_text, block_bbox)
        
        # AI Enhancement (if enabled)
        enhanced_text = None
        ai_metadata = None
        target_language = settings_dict.get("language", "auto")
        
        if settings.AI_ENHANCEMENT_ENABLED and self.ai_manager and full_text:
            try:
                logger.info(f"Running AI enhancement for text file, target_language={target_language}")
                
                # Determine document type
                document_type = self._detect_document_type(file_path, full_text)
                
                # Enhance text
                enhancement_result = await self.ai_manager.enhance_text(
                    text=full_text,
                    document_type=document_type,
                    image_data=None,
                    target_language=target_language
                )
                
                enhanced_text = enhancement_result.enhanced_text
                ai_metadata = {
                    "provider": enhancement_result.provider_used,
                    "model": enhancement_result.model_used,
                    "processingTimeMs": enhancement_result.processing_time_ms,
                    "improvements": enhancement_result.improvements,
                    "fallbackOccurred": enhancement_result.fallback_occurred,
                    "targetLanguage": target_language
                }
                
                logger.info(f"AI enhancement completed: {len(enhanced_text)} chars")
                logger.info(f"Enhanced text value: {enhanced_text[:200]}")
                logger.info(f"Enhanced text is None: {enhanced_text is None}")
                logger.info(f"Enhanced text is empty: {not enhanced_text}")
            except Exception as e:
                logger.error(f"AI enhancement failed: {e}")
        
        result_dict = {
            "fullText": full_text,
            "markdownText": markdown_text,
            "layoutText": full_text,
            "pages": pages,
            "structured": {
                "tables": [],
                "equations": [],
                "images": []
            },
            "layout": {
                "pages": [{
                    "page": 1,
                    "width": 1.0,
                    "height": 1.414,
                    "blocks": [{
                        "type": "text",
                        "text": full_text,
                        "bbox": block_bbox,
                        "confidence": 1.0,
                        "lines": lines
                    }]
                }]
            },
            "meta": {
                "parser": "text-reader",
                "parse_method": "direct",
                "language": settings_dict.get("language", "auto"),
                "pageCount": 1,
                "avgConfidence": 1.0,
                "timings": {
                    "parseMs": 10,
                    "postMs": 10
                }
            }
        }
        
        # Add enhanced text if available
        if enhanced_text:
            logger.info(f"Adding enhancedText to result_dict: {enhanced_text[:100]}")
            result_dict["enhancedText"] = enhanced_text
        else:
            logger.warning("No enhanced_text to add to result_dict")
            
        if ai_metadata:
            result_dict["aiMetadata"] = ai_metadata
        
        logger.info(f"result_dict keys before return: {result_dict.keys()}")
        logger.info(f"Has enhancedText in result_dict: {'enhancedText' in result_dict}")
        
        return {
            "jobId": job_id,
            "status": "done",
            "result": result_dict,
            "error": None
        }

    def _extract_picture_info(self, item: Any, doc: Any) -> Optional[Dict[str, Any]]:
        """
        Extract picture/image info from a Docling PictureItem or figure element.
        
        Returns a dict with id, page, bbox suitable for sub-OCR cropping,
        or None if no valid bbox can be extracted.
        """
        try:
            page_no = 1
            bbox_dict = None
            
            # Get page number and bbox from provenance (prov)
            if hasattr(item, 'prov') and item.prov:
                prov = item.prov[0]
                if hasattr(prov, 'page_no'):
                    page_no = prov.page_no
                if hasattr(prov, 'bbox') and prov.bbox:
                    bbox = prov.bbox
                    # Docling BoundingBox has l, t, r, b (left, top, right, bottom)
                    if hasattr(bbox, 'l'):
                        bbox_dict = {
                            "x1": float(bbox.l),
                            "y1": float(bbox.t),
                            "x2": float(bbox.r),
                            "y2": float(bbox.b),
                        }
                    elif isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
                        bbox_dict = {
                            "x1": float(bbox[0]),
                            "y1": float(bbox[1]),
                            "x2": float(bbox[2]),
                            "y2": float(bbox[3]),
                        }
            
            if not bbox_dict:
                # Can't crop without a bounding box
                return None
            
            # Get caption text if available
            caption = ""
            if hasattr(item, 'caption_text'):
                caption = item.caption_text(doc) if callable(item.caption_text) else str(item.caption_text)
            elif hasattr(item, 'caption') and item.caption:
                if hasattr(item.caption, 'text'):
                    caption = item.caption.text
                else:
                    caption = str(item.caption)
            
            return {
                "id": f"img-p{page_no}-{id(item)}",
                "page": page_no,
                "bbox": bbox_dict,  # Absolute pixel coordinates
                "caption": caption,
                "label": str(getattr(item, 'label', 'picture')),
            }
            
        except Exception as e:
            logger.debug(f"Could not extract picture info: {e}")
            return None

    def _detect_document_type(self, file_path: Path, text: str) -> str:
        """
        Detect document type for appropriate prompt selection
        
        Args:
            file_path: Path to the document
            text: Extracted text content
            
        Returns:
            Document type (general, code, invoice, form, handwritten)
        """
        filename = file_path.name.lower()
        text_lower = text.lower()
        
        # Check for code documents
        code_indicators = ['def ', 'function ', 'class ', 'import ', 'const ', 'var ', 'let ', '#!/']
        code_extensions = ['.py', '.js', '.ts', '.java', '.cpp', '.c', '.go', '.rs']
        
        if any(ext in filename for ext in code_extensions) or any(ind in text for ind in code_indicators):
            return "code"
        
        # Check for invoices/receipts
        invoice_indicators = ['invoice', 'receipt', 'total', 'tax', 'amount', 'payment']
        if any(ind in text_lower for ind in invoice_indicators) and any(ind in filename for ind in ['invoice', 'receipt']):
            return "invoice"
        
        # Check for forms
        form_indicators = ['form', 'application', 'name:', 'date:', 'signature']
        if any(ind in text_lower for ind in form_indicators) and 'form' in filename:
            return "form"
        
        # Check for handwritten (usually from image files with certain patterns)
        if file_path.suffix.lower() in ['.jpg', '.jpeg', '.png'] and len(text) < 500:
            return "handwritten"
        
        return "general"


# Global engine instance
rag_engine = DocumentEngine()

# Alias for backward compatibility
RAGAnythingEngine = DocumentEngine
