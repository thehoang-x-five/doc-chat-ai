"""
Document Parsers - Full Implementation

Provides document parsing using:
- MinerU parser (complex layouts, multimodal content, OCR)
- Docling parser (fast, Office documents, HTML)

Migrated from raganything/parser.py
"""

import asyncio
import base64
import json
import logging
import platform
import shutil
import subprocess
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from app.services.rag_patterns.pipeline.types import (
    DocStatus,
    ParserType,
    ProcessingResult,
)
from app.services.rag_patterns.pipeline.config import RAGConfig

logger = logging.getLogger(__name__)


class MineruExecutionError(Exception):
    """Exception for MinerU command execution failures."""
    
    def __init__(self, return_code: int, error_msg: Union[str, List[str]]):
        self.return_code = return_code
        self.error_msg = error_msg
        msg = error_msg if isinstance(error_msg, str) else "; ".join(error_msg)
        super().__init__(f"MinerU failed with code {return_code}: {msg}")


class BaseParser(ABC):
    """Base class for document parsers."""
    
    OFFICE_FORMATS = {".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx"}
    IMAGE_FORMATS = {".png", ".jpeg", ".jpg", ".bmp", ".tiff", ".tif", ".gif", ".webp"}
    TEXT_FORMATS = {".txt", ".md"}
    PDF_FORMATS = {".pdf"}
    
    def __init__(self, config: Optional[RAGConfig] = None):
        self.config = config or RAGConfig.from_server_settings()
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    async def parse(
        self,
        file_path: Union[str, Path],
        **kwargs
    ) -> ProcessingResult:
        """Parse a document file."""
        pass
    
    @abstractmethod
    def supports_format(self, file_path: Union[str, Path]) -> bool:
        """Check if parser supports this file format."""
        pass
    
    @abstractmethod
    def check_installation(self) -> bool:
        """Check if parser is properly installed."""
        pass
    
    def get_file_extension(self, file_path: Union[str, Path]) -> str:
        """Get lowercase file extension."""
        return Path(file_path).suffix.lower()
    
    @staticmethod
    def convert_office_to_pdf(
        doc_path: Union[str, Path],
        output_dir: Optional[str] = None
    ) -> Path:
        """
        Convert Office document to PDF using LibreOffice.
        
        Supports: .doc, .docx, .ppt, .pptx, .xls, .xlsx
        Requires LibreOffice to be installed.
        """
        doc_path = Path(doc_path)
        if not doc_path.exists():
            raise FileNotFoundError(f"Office document not found: {doc_path}")
        
        if output_dir:
            base_output_dir = Path(output_dir)
        else:
            base_output_dir = doc_path.parent / "libreoffice_output"
        
        base_output_dir.mkdir(parents=True, exist_ok=True)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            commands_to_try = ["libreoffice", "soffice"]
            conversion_successful = False
            
            for cmd in commands_to_try:
                try:
                    convert_cmd = [
                        cmd, "--headless", "--convert-to", "pdf",
                        "--outdir", str(temp_path), str(doc_path)
                    ]
                    
                    subprocess_kwargs = {
                        "capture_output": True,
                        "text": True,
                        "timeout": 60,
                        "encoding": "utf-8",
                        "errors": "ignore",
                    }
                    
                    if platform.system() == "Windows":
                        subprocess_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
                    
                    result = subprocess.run(convert_cmd, **subprocess_kwargs)
                    
                    if result.returncode == 0:
                        conversion_successful = True
                        logger.info(f"Converted {doc_path.name} to PDF using {cmd}")
                        break
                    else:
                        logger.warning(f"LibreOffice '{cmd}' failed: {result.stderr}")
                except FileNotFoundError:
                    logger.warning(f"LibreOffice command '{cmd}' not found")
                except subprocess.TimeoutExpired:
                    logger.warning(f"LibreOffice command '{cmd}' timed out")
                except Exception as e:
                    logger.error(f"LibreOffice '{cmd}' error: {e}")
            
            if not conversion_successful:
                raise RuntimeError(
                    f"LibreOffice conversion failed for {doc_path.name}. "
                    "Please ensure LibreOffice is installed."
                )
            
            pdf_files = list(temp_path.glob("*.pdf"))
            if not pdf_files:
                raise RuntimeError("No PDF file generated")
            
            pdf_path = pdf_files[0]
            if pdf_path.stat().st_size < 100:
                raise RuntimeError("Generated PDF is empty or corrupted")
            
            final_pdf_path = base_output_dir / f"{doc_path.stem}.pdf"
            shutil.copy2(pdf_path, final_pdf_path)
            
            return final_pdf_path
    
    @staticmethod
    def convert_text_to_pdf(
        text_path: Union[str, Path],
        output_dir: Optional[str] = None
    ) -> Path:
        """
        Convert text file to PDF using ReportLab.
        
        Supports: .txt, .md
        """
        text_path = Path(text_path)
        if not text_path.exists():
            raise FileNotFoundError(f"Text file not found: {text_path}")
        
        supported_formats = {".txt", ".md"}
        if text_path.suffix.lower() not in supported_formats:
            raise ValueError(f"Unsupported text format: {text_path.suffix}")
        
        try:
            with open(text_path, "r", encoding="utf-8") as f:
                text_content = f.read()
        except UnicodeDecodeError:
            for encoding in ["gbk", "latin-1", "cp1252"]:
                try:
                    with open(text_path, "r", encoding=encoding) as f:
                        text_content = f.read()
                    logger.info(f"Read file with {encoding} encoding")
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise RuntimeError(f"Could not decode {text_path.name}")
        
        if output_dir:
            base_output_dir = Path(output_dir)
        else:
            base_output_dir = text_path.parent / "reportlab_output"
        
        base_output_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = base_output_dir / f"{text_path.stem}.pdf"
        
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            
            doc = SimpleDocTemplate(
                str(pdf_path), pagesize=A4,
                leftMargin=inch, rightMargin=inch,
                topMargin=inch, bottomMargin=inch
            )
            
            styles = getSampleStyleSheet()
            normal_style = styles["Normal"]
            heading_style = styles["Heading1"]
            
            story = []
            
            if text_path.suffix.lower() == ".md":
                lines = text_content.split("\n")
                for line in lines:
                    line = line.strip()
                    if not line:
                        story.append(Spacer(1, 12))
                        continue
                    
                    if line.startswith("#"):
                        level = len(line) - len(line.lstrip("#"))
                        header_text = line.lstrip("#").strip()
                        if header_text:
                            header_style = ParagraphStyle(
                                name=f"Heading{level}",
                                parent=heading_style,
                                fontSize=max(16 - level, 10),
                                spaceAfter=8,
                                spaceBefore=16 if level <= 2 else 12,
                            )
                            story.append(Paragraph(header_text, header_style))
                    else:
                        story.append(Paragraph(line, normal_style))
                        story.append(Spacer(1, 6))
            else:
                lines = text_content.split("\n")
                for line in lines:
                    line = line.rstrip()
                    if not line.strip():
                        story.append(Spacer(1, 6))
                        continue
                    
                    safe_line = (
                        line.replace("&", "&amp;")
                        .replace("<", "&lt;")
                        .replace(">", "&gt;")
                    )
                    story.append(Paragraph(safe_line, normal_style))
                    story.append(Spacer(1, 3))
                
                if not story:
                    story.append(Paragraph("(Empty text file)", normal_style))
            
            doc.build(story)
            logger.info(f"Converted {text_path.name} to PDF")
            
        except ImportError:
            raise RuntimeError("reportlab required: pip install reportlab")
        
        if not pdf_path.exists() or pdf_path.stat().st_size < 100:
            raise RuntimeError(f"PDF conversion failed for {text_path.name}")
        
        return pdf_path
    
    @staticmethod
    def convert_image_format(
        image_path: Union[str, Path],
        output_format: str = "png"
    ) -> Path:
        """
        Convert image to a supported format.
        
        Args:
            image_path: Path to image file
            output_format: Target format (default: png)
        
        Returns:
            Path to converted image
        """
        try:
            from PIL import Image
        except ImportError:
            raise RuntimeError("Pillow required: pip install Pillow")
        
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        
        temp_dir = Path(tempfile.mkdtemp())
        output_path = temp_dir / f"{image_path.stem}_converted.{output_format}"
        
        try:
            with Image.open(image_path) as img:
                if img.mode in ("RGBA", "LA", "P"):
                    if img.mode == "P":
                        img = img.convert("RGBA")
                    
                    background = Image.new("RGB", img.size, (255, 255, 255))
                    if img.mode == "RGBA":
                        background.paste(img, mask=img.split()[-1])
                    else:
                        background.paste(img)
                    img = background
                elif img.mode not in ("RGB", "L"):
                    img = img.convert("RGB")
                
                img.save(output_path, output_format.upper(), optimize=True)
                logger.info(f"Converted {image_path.name} to {output_format}")
                
        except Exception as e:
            if output_path.exists():
                output_path.unlink()
            raise RuntimeError(f"Image conversion failed: {e}")
        
        return output_path


class MineruParser(BaseParser):
    """
    MinerU parser for complex documents.
    
    Strengths:
    - Excellent multimodal content extraction
    - Complex layout handling
    - Table and equation recognition
    - OCR support
    """
    
    MINERU_SUPPORTED_FORMATS = {".png", ".jpeg", ".jpg"}
    
    async def parse(
        self,
        file_path: Union[str, Path],
        **kwargs
    ) -> ProcessingResult:
        """Parse document using MinerU."""
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                return ProcessingResult(
                    status=DocStatus.FAILED,
                    error=f"File not found: {file_path}"
                )
            
            ext = self.get_file_extension(file_path)
            
            if ext in self.PDF_FORMATS:
                content_list = await self._parse_pdf(file_path, **kwargs)
            elif ext in self.IMAGE_FORMATS:
                content_list = await self._parse_image(file_path, **kwargs)
            elif ext in self.OFFICE_FORMATS:
                content_list = await self._parse_office_doc(file_path, **kwargs)
            elif ext in self.TEXT_FORMATS:
                content_list = await self._parse_text_file(file_path, **kwargs)
            else:
                return ProcessingResult(
                    status=DocStatus.FAILED,
                    error=f"Unsupported format: {ext}"
                )
            
            return ProcessingResult(
                status=DocStatus.COMPLETED,
                content=content_list,
                metadata={
                    "parser": "mineru",
                    "file_path": str(file_path),
                    "file_type": ext
                }
            )
            
        except MineruExecutionError as e:
            self.logger.error(f"MinerU execution failed: {e}")
            return ProcessingResult(
                status=DocStatus.FAILED,
                error=str(e)
            )
        except Exception as e:
            self.logger.error(f"MinerU parsing failed: {e}", exc_info=True)
            return ProcessingResult(
                status=DocStatus.FAILED,
                error=str(e)
            )
    
    async def _parse_pdf(
        self,
        pdf_path: Path,
        method: str = "auto",
        lang: Optional[str] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Parse PDF using MinerU."""
        output_dir = kwargs.get("output_dir")
        if output_dir:
            base_output_dir = Path(output_dir)
        else:
            base_output_dir = pdf_path.parent / "mineru_output"
        
        base_output_dir.mkdir(parents=True, exist_ok=True)
        
        await self._run_mineru_command(
            input_path=pdf_path,
            output_dir=base_output_dir,
            method=method,
            lang=lang,
            **kwargs
        )
        
        backend = kwargs.get("backend", "")
        if backend.startswith("vlm-"):
            method = "vlm"
        
        content_list, _ = self._read_output_files(
            base_output_dir, pdf_path.stem, method
        )
        return content_list
    
    async def _parse_image(
        self,
        image_path: Path,
        lang: Optional[str] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Parse image using MinerU."""
        ext = image_path.suffix.lower()
        actual_image_path = image_path
        temp_converted_file = None
        
        if ext not in self.MINERU_SUPPORTED_FORMATS:
            self.logger.info(f"Converting {ext} to PNG for MinerU compatibility")
            temp_converted_file = self.convert_image_format(image_path, "png")
            actual_image_path = temp_converted_file
        
        try:
            output_dir = kwargs.get("output_dir")
            if output_dir:
                base_output_dir = Path(output_dir)
            else:
                base_output_dir = image_path.parent / "mineru_output"
            
            base_output_dir.mkdir(parents=True, exist_ok=True)
            
            await self._run_mineru_command(
                input_path=actual_image_path,
                output_dir=base_output_dir,
                method="ocr",
                lang=lang,
                **kwargs
            )
            
            content_list, _ = self._read_output_files(
                base_output_dir, image_path.stem, "ocr"
            )
            return content_list
            
        finally:
            if temp_converted_file and temp_converted_file.exists():
                try:
                    temp_converted_file.unlink()
                    temp_converted_file.parent.rmdir()
                except Exception:
                    pass
    
    async def _parse_office_doc(
        self,
        doc_path: Path,
        lang: Optional[str] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Parse Office document by converting to PDF first."""
        self.logger.info(f"Converting Office document {doc_path.name} to PDF")
        output_dir = kwargs.get("output_dir")
        pdf_path = self.convert_office_to_pdf(doc_path, output_dir)
        return await self._parse_pdf(pdf_path, lang=lang, **kwargs)
    
    async def _parse_text_file(
        self,
        text_path: Path,
        lang: Optional[str] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Parse text file by converting to PDF first."""
        self.logger.info(f"Converting text file {text_path.name} to PDF")
        output_dir = kwargs.get("output_dir")
        pdf_path = self.convert_text_to_pdf(text_path, output_dir)
        return await self._parse_pdf(pdf_path, lang=lang, **kwargs)
    
    async def _run_mineru_command(
        self,
        input_path: Path,
        output_dir: Path,
        method: str = "auto",
        lang: Optional[str] = None,
        **kwargs
    ) -> None:
        """Run mineru command line tool."""
        cmd = [
            "mineru",
            "-p", str(input_path),
            "-o", str(output_dir),
            "-m", method,
        ]
        
        if kwargs.get("backend"):
            cmd.extend(["-b", kwargs["backend"]])
        if kwargs.get("source"):
            cmd.extend(["--source", kwargs["source"]])
        if lang:
            cmd.extend(["-l", lang])
        if kwargs.get("start_page") is not None:
            cmd.extend(["-s", str(kwargs["start_page"])])
        if kwargs.get("end_page") is not None:
            cmd.extend(["-e", str(kwargs["end_page"])])
        if not kwargs.get("formula", True):
            cmd.extend(["-f", "false"])
        if not kwargs.get("table", True):
            cmd.extend(["-t", "false"])
        if kwargs.get("device"):
            cmd.extend(["-d", kwargs["device"]])
        if kwargs.get("vlm_url"):
            cmd.extend(["-u", kwargs["vlm_url"]])
        
        self.logger.info(f"Executing: {' '.join(cmd)}")
        
        subprocess_kwargs = {
            "stdout": asyncio.subprocess.PIPE,
            "stderr": asyncio.subprocess.PIPE,
        }
        
        if platform.system() == "Windows":
            subprocess_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd, **subprocess_kwargs
            )
            
            stdout, stderr = await process.communicate()
            
            if stdout:
                for line in stdout.decode("utf-8", errors="ignore").splitlines():
                    if line.strip():
                        self.logger.info(f"[MinerU] {line}")
            
            error_lines = []
            if stderr:
                for line in stderr.decode("utf-8", errors="ignore").splitlines():
                    if line.strip():
                        if "error" in line.lower():
                            self.logger.error(f"[MinerU] {line}")
                            error_lines.append(line)
                        elif "warning" in line.lower():
                            self.logger.warning(f"[MinerU] {line}")
                        else:
                            self.logger.info(f"[MinerU] {line}")
            
            if process.returncode != 0 or error_lines:
                raise MineruExecutionError(process.returncode or 1, error_lines)
            
            self.logger.info("[MinerU] Command completed successfully")
            
        except FileNotFoundError:
            raise RuntimeError(
                "mineru command not found. Please install: pip install -U 'mineru[core]'"
            )
    
    def _read_output_files(
        self,
        output_dir: Path,
        file_stem: str,
        method: str = "auto"
    ) -> Tuple[List[Dict[str, Any]], str]:
        """Read output files generated by mineru."""
        md_file = output_dir / f"{file_stem}.md"
        json_file = output_dir / f"{file_stem}_content_list.json"
        images_base_dir = output_dir
        
        file_stem_subdir = output_dir / file_stem
        if file_stem_subdir.exists():
            md_file = file_stem_subdir / method / f"{file_stem}.md"
            json_file = file_stem_subdir / method / f"{file_stem}_content_list.json"
            images_base_dir = file_stem_subdir / method
        
        md_content = ""
        if md_file.exists():
            try:
                with open(md_file, "r", encoding="utf-8") as f:
                    md_content = f.read()
            except Exception as e:
                self.logger.warning(f"Could not read markdown: {e}")
        
        content_list = []
        if json_file.exists():
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    content_list = json.load(f)
                
                for item in content_list:
                    if isinstance(item, dict):
                        for field in ["img_path", "table_img_path", "equation_img_path"]:
                            if field in item and item[field]:
                                absolute_path = (images_base_dir / item[field]).resolve()
                                item[field] = str(absolute_path)
                
            except Exception as e:
                self.logger.warning(f"Could not read JSON: {e}")
        
        return content_list, md_content
    
    def supports_format(self, file_path: Union[str, Path]) -> bool:
        """Check if MinerU supports this format."""
        ext = self.get_file_extension(file_path)
        return ext in (
            self.PDF_FORMATS | self.IMAGE_FORMATS |
            self.OFFICE_FORMATS | self.TEXT_FORMATS
        )
    
    def check_installation(self) -> bool:
        """Check if MinerU is properly installed."""
        try:
            subprocess_kwargs = {
                "capture_output": True,
                "text": True,
                "check": True,
                "encoding": "utf-8",
                "errors": "ignore",
            }
            
            if platform.system() == "Windows":
                subprocess_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            
            result = subprocess.run(["mineru", "--version"], **subprocess_kwargs)
            self.logger.debug(f"MinerU version: {result.stdout.strip()}")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.logger.debug("MinerU not installed: pip install -U 'mineru[core]'")
            return False


class DoclingParser(BaseParser):
    """
    Docling parser for standard documents.
    
    Strengths:
    - Fast processing
    - Native Office document support
    - HTML support
    - Good text extraction
    """
    
    HTML_FORMATS = {".html", ".htm", ".xhtml"}
    
    async def parse(
        self,
        file_path: Union[str, Path],
        **kwargs
    ) -> ProcessingResult:
        """Parse document using Docling."""
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                return ProcessingResult(
                    status=DocStatus.FAILED,
                    error=f"File not found: {file_path}"
                )
            
            ext = self.get_file_extension(file_path)
            
            if ext in self.PDF_FORMATS:
                content_list = await self._parse_pdf(file_path, **kwargs)
            elif ext in self.OFFICE_FORMATS:
                content_list = await self._parse_office_doc(file_path, **kwargs)
            elif ext in self.HTML_FORMATS:
                content_list = await self._parse_html(file_path, **kwargs)
            else:
                return ProcessingResult(
                    status=DocStatus.FAILED,
                    error=f"Unsupported format: {ext}. "
                          f"Docling supports: PDF, Office ({', '.join(self.OFFICE_FORMATS)}), "
                          f"HTML ({', '.join(self.HTML_FORMATS)})"
                )
            
            return ProcessingResult(
                status=DocStatus.COMPLETED,
                content=content_list,
                metadata={
                    "parser": "docling",
                    "file_path": str(file_path),
                    "file_type": ext
                }
            )
            
        except Exception as e:
            self.logger.error(f"Docling parsing failed: {e}", exc_info=True)
            return ProcessingResult(
                status=DocStatus.FAILED,
                error=str(e)
            )
    
    async def _parse_pdf(
        self,
        pdf_path: Path,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Parse PDF using Docling."""
        output_dir = kwargs.get("output_dir")
        if output_dir:
            base_output_dir = Path(output_dir)
        else:
            base_output_dir = pdf_path.parent / "docling_output"
        
        base_output_dir.mkdir(parents=True, exist_ok=True)
        
        await self._run_docling_command(
            input_path=pdf_path,
            output_dir=base_output_dir,
            file_stem=pdf_path.stem,
            **kwargs
        )
        
        content_list, _ = self._read_output_files(base_output_dir, pdf_path.stem)
        return content_list
    
    async def _parse_office_doc(
        self,
        doc_path: Path,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Parse Office document using Docling."""
        if doc_path.suffix.lower() not in self.OFFICE_FORMATS:
            raise ValueError(f"Unsupported Office format: {doc_path.suffix}")
        
        output_dir = kwargs.get("output_dir")
        if output_dir:
            base_output_dir = Path(output_dir)
        else:
            base_output_dir = doc_path.parent / "docling_output"
        
        base_output_dir.mkdir(parents=True, exist_ok=True)
        
        await self._run_docling_command(
            input_path=doc_path,
            output_dir=base_output_dir,
            file_stem=doc_path.stem,
            **kwargs
        )
        
        content_list, _ = self._read_output_files(base_output_dir, doc_path.stem)
        return content_list
    
    async def _parse_html(
        self,
        html_path: Path,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Parse HTML using Docling."""
        if html_path.suffix.lower() not in self.HTML_FORMATS:
            raise ValueError(f"Unsupported HTML format: {html_path.suffix}")
        
        output_dir = kwargs.get("output_dir")
        if output_dir:
            base_output_dir = Path(output_dir)
        else:
            base_output_dir = html_path.parent / "docling_output"
        
        base_output_dir.mkdir(parents=True, exist_ok=True)
        
        await self._run_docling_command(
            input_path=html_path,
            output_dir=base_output_dir,
            file_stem=html_path.stem,
            **kwargs
        )
        
        content_list, _ = self._read_output_files(base_output_dir, html_path.stem)
        return content_list
    
    async def _run_docling_command(
        self,
        input_path: Path,
        output_dir: Path,
        file_stem: str,
        **kwargs
    ) -> None:
        """Run docling command line tool."""
        file_output_dir = output_dir / file_stem / "docling"
        file_output_dir.mkdir(parents=True, exist_ok=True)
        
        cmd_json = [
            "docling",
            "--output", str(file_output_dir),
            "--to", "json",
            str(input_path),
        ]
        cmd_md = [
            "docling",
            "--output", str(file_output_dir),
            "--to", "md",
            str(input_path),
        ]
        
        self.logger.info(f"Executing: {' '.join(cmd_json)}")
        
        subprocess_kwargs = {
            "stdout": asyncio.subprocess.PIPE,
            "stderr": asyncio.subprocess.PIPE,
        }
        
        if platform.system() == "Windows":
            subprocess_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        
        try:
            process_json = await asyncio.create_subprocess_exec(
                *cmd_json, **subprocess_kwargs
            )
            stdout_json, stderr_json = await process_json.communicate()
            
            if process_json.returncode != 0:
                error = stderr_json.decode("utf-8", errors="ignore")
                raise RuntimeError(f"Docling JSON command failed: {error}")
            
            process_md = await asyncio.create_subprocess_exec(
                *cmd_md, **subprocess_kwargs
            )
            stdout_md, stderr_md = await process_md.communicate()
            
            if process_md.returncode != 0:
                error = stderr_md.decode("utf-8", errors="ignore")
                raise RuntimeError(f"Docling MD command failed: {error}")
            
            self.logger.info("[Docling] Command completed successfully")
            
        except FileNotFoundError:
            raise RuntimeError("docling command not found. Please install Docling.")
    
    def _read_output_files(
        self,
        output_dir: Path,
        file_stem: str
    ) -> Tuple[List[Dict[str, Any]], str]:
        """Read output files generated by docling."""
        file_subdir = output_dir / file_stem / "docling"
        md_file = file_subdir / f"{file_stem}.md"
        json_file = file_subdir / f"{file_stem}.json"
        
        md_content = ""
        if md_file.exists():
            try:
                with open(md_file, "r", encoding="utf-8") as f:
                    md_content = f.read()
            except Exception as e:
                self.logger.warning(f"Could not read markdown: {e}")
        
        content_list = []
        if json_file.exists():
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    docling_content = json.load(f)
                
                if "body" in docling_content:
                    content_list = self._read_from_block_recursive(
                        docling_content["body"],
                        "body",
                        file_subdir,
                        0,
                        "0",
                        docling_content
                    )
            except Exception as e:
                self.logger.warning(f"Could not read JSON: {e}")
        
        return content_list, md_content
    
    def _read_from_block_recursive(
        self,
        block: Dict[str, Any],
        block_type: str,
        output_dir: Path,
        cnt: int,
        num: str,
        docling_content: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Recursively read blocks from Docling output."""
        content_list = []
        
        if not block.get("children"):
            cnt += 1
            content_list.append(
                self._read_from_block(block, block_type, output_dir, cnt, num)
            )
        else:
            if block_type not in ["groups", "body"]:
                cnt += 1
                content_list.append(
                    self._read_from_block(block, block_type, output_dir, cnt, num)
                )
            
            for member in block["children"]:
                cnt += 1
                member_tag = member["$ref"]
                member_type = member_tag.split("/")[1]
                member_num = member_tag.split("/")[2]
                member_block = docling_content[member_type][int(member_num)]
                content_list.extend(
                    self._read_from_block_recursive(
                        member_block,
                        member_type,
                        output_dir,
                        cnt,
                        member_num,
                        docling_content
                    )
                )
        
        return content_list
    
    def _read_from_block(
        self,
        block: Dict[str, Any],
        block_type: str,
        output_dir: Path,
        cnt: int,
        num: str
    ) -> Dict[str, Any]:
        """Read a single block from Docling output."""
        if block_type == "texts":
            if block.get("label") == "formula":
                return {
                    "type": "equation",
                    "img_path": "",
                    "text": block.get("orig", ""),
                    "text_format": "unknown",
                    "page_idx": cnt // 10,
                }
            else:
                return {
                    "type": "text",
                    "text": block.get("orig", ""),
                    "page_idx": cnt // 10,
                }
        
        elif block_type == "pictures":
            try:
                base64_uri = block["image"]["uri"]
                base64_str = base64_uri.split(",")[1]
                
                image_dir = output_dir / "images"
                image_dir.mkdir(parents=True, exist_ok=True)
                image_path = image_dir / f"image_{num}.png"
                
                with open(image_path, "wb") as f:
                    f.write(base64.b64decode(base64_str))
                
                return {
                    "type": "image",
                    "img_path": str(image_path.resolve()),
                    "image_caption": block.get("caption", ""),
                    "image_footnote": block.get("footnote", ""),
                    "page_idx": cnt // 10,
                }
            except Exception as e:
                self.logger.warning(f"Failed to process image {num}: {e}")
                return {
                    "type": "text",
                    "text": f"[Image processing failed: {block.get('caption', '')}]",
                    "page_idx": cnt // 10,
                }
        
        else:
            try:
                return {
                    "type": "table",
                    "img_path": "",
                    "table_caption": block.get("caption", ""),
                    "table_footnote": block.get("footnote", ""),
                    "table_body": block.get("data", []),
                    "page_idx": cnt // 10,
                }
            except Exception as e:
                self.logger.warning(f"Failed to process table {num}: {e}")
                return {
                    "type": "text",
                    "text": f"[Table processing failed: {block.get('caption', '')}]",
                    "page_idx": cnt // 10,
                }
    
    def supports_format(self, file_path: Union[str, Path]) -> bool:
        """Check if Docling supports this format."""
        ext = self.get_file_extension(file_path)
        return ext in (
            self.PDF_FORMATS | self.OFFICE_FORMATS |
            self.TEXT_FORMATS | self.HTML_FORMATS
        )
    
    def check_installation(self) -> bool:
        """Check if Docling is properly installed."""
        try:
            subprocess_kwargs = {
                "capture_output": True,
                "text": True,
                "check": True,
                "encoding": "utf-8",
                "errors": "ignore",
            }
            
            if platform.system() == "Windows":
                subprocess_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            
            result = subprocess.run(["docling", "--version"], **subprocess_kwargs)
            self.logger.debug(f"Docling version: {result.stdout.strip()}")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.logger.debug("Docling not installed. Please install it.")
            return False


class ParserFactory:
    """Factory for creating parser instances."""
    
    @staticmethod
    def create_parser(
        parser_type: Union[str, ParserType],
        config: Optional[RAGConfig] = None
    ) -> BaseParser:
        """
        Create a parser instance.
        
        Args:
            parser_type: Type of parser (mineru, docling, auto)
            config: RAG configuration
        
        Returns:
            Parser instance
        """
        if isinstance(parser_type, ParserType):
            parser_type = parser_type.value
        
        parser_type = parser_type.lower()
        
        if parser_type == "mineru":
            return MineruParser(config)
        elif parser_type == "docling":
            return DoclingParser(config)
        elif parser_type == "auto":
            config = config or RAGConfig.from_server_settings()
            return ParserFactory.create_parser(config.parser, config)
        else:
            raise ValueError(f"Unknown parser type: {parser_type}")
    
    @staticmethod
    def get_best_parser_for_file(
        file_path: Union[str, Path],
        config: Optional[RAGConfig] = None
    ) -> BaseParser:
        """
        Get the best parser for a specific file.
        
        Args:
            file_path: Path to the file
            config: RAG configuration
        
        Returns:
            Best parser for this file type
        """
        config = config or RAGConfig.from_server_settings()
        ext = Path(file_path).suffix.lower()
        
        if ext in {".pdf"} | BaseParser.IMAGE_FORMATS:
            return MineruParser(config)
        elif ext in BaseParser.OFFICE_FORMATS | DoclingParser.HTML_FORMATS:
            return DoclingParser(config)
        else:
            return ParserFactory.create_parser(config.parser, config)


__all__ = [
    "BaseParser",
    "MineruParser",
    "DoclingParser",
    "ParserFactory",
    "MineruExecutionError",
]
