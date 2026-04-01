"""
Text processing utilities
Enhanced with spell checking and query expansion
"""
import json
import re
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

# Try to import SymSpell for spell checking
try:
    from symspellpy import SymSpell, Verbosity
    SYMSPELL_AVAILABLE = True
except ImportError:
    SYMSPELL_AVAILABLE = False
    logger.warning("symspellpy not available. Install with: pip install symspellpy")


def clean_text(text: str) -> str:
    """Clean and normalize text"""
    if not text:
        return ""
        
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove leading/trailing whitespace
    text = text.strip()
    
    return text


def preserve_layout_text(text: str) -> str:
    """Preserve text layout with proper spacing"""
    if not text:
        return ""
        
    # Preserve line breaks and indentation
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        # Keep leading whitespace for indentation
        cleaned_line = line.rstrip()
        cleaned_lines.append(cleaned_line)
        
    return '\n'.join(cleaned_lines)


def text_to_markdown(text: str, title: Optional[str] = None) -> str:
    """Convert plain text to markdown format"""
    if not text:
        return ""
        
    markdown = ""
    
    if title:
        markdown += f"# {title}\n\n"
        
    # Split into paragraphs
    paragraphs = text.split('\n\n')
    
    for paragraph in paragraphs:
        if paragraph.strip():
            markdown += f"{paragraph.strip()}\n\n"
            
    return markdown.strip()


def extract_metadata_from_text(text: str) -> Dict[str, Any]:
    """Extract metadata from text content"""
    if not text:
        return {}
        
    word_count = len(text.split())
    char_count = len(text)
    line_count = len(text.split('\n'))
    
    # Detect language (simple heuristic)
    vietnamese_chars = len(re.findall(r'[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]', text.lower()))
    language = "vi" if vietnamese_chars > word_count * 0.1 else "en"
    
    return {
        "wordCount": word_count,
        "charCount": char_count,
        "lineCount": line_count,
        "detectedLanguage": language,
        "hasVietnamese": vietnamese_chars > 0
    }


def format_confidence_score(confidence: float) -> float:
    """Format confidence score to 2 decimal places"""
    return round(confidence, 2)


def split_text_by_pages(text: str, max_chars_per_page: int = 2000) -> list:
    """Split text into pages based on character count"""
    if not text:
        return []
        
    pages = []
    current_page = ""
    
    paragraphs = text.split('\n\n')
    
    for paragraph in paragraphs:
        if len(current_page) + len(paragraph) > max_chars_per_page and current_page:
            pages.append(current_page.strip())
            current_page = paragraph
        else:
            if current_page:
                current_page += '\n\n' + paragraph
            else:
                current_page = paragraph
                
    if current_page:
        pages.append(current_page.strip())
        
    return pages


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage"""
    # Remove or replace unsafe characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Remove leading/trailing dots and spaces
    filename = filename.strip('. ')
    
    # Ensure filename is not empty
    if not filename:
        filename = "untitled"
        
    return filename


def create_text_summary(text: str, max_length: int = 200) -> str:
    """Create a summary of text content"""
    if not text:
        return ""
        
    if len(text) <= max_length:
        return text
        
    # Find a good breaking point
    truncated = text[:max_length]
    last_space = truncated.rfind(' ')
    
    if last_space > max_length * 0.8:  # If we can find a space in the last 20%
        truncated = truncated[:last_space]
        
    return truncated + "..."


# Vietnamese synonym dictionary for query expansion
VIETNAMESE_SYNONYMS = {
    "học": ["học tập", "nghiên cứu"],
    "sinh viên": ["học sinh", "người học"],
    "giáo viên": ["thầy cô", "người dạy"],
    "trường": ["trường học", "cơ sở giáo dục"],
    "tài liệu": ["tư liệu", "tài liệu học tập"],
    "liệu": [],  # Part of "tài liệu", no expansion
    "bài giảng": ["bài học", "giảng bài"],
    "kiểm tra": ["thi", "đánh giá"],
    "điểm": ["điểm số", "kết quả"],
    "lớp": ["lớp học", "khóa học"],
    "môn": ["môn học", "học phần"],
    "đại học": ["trường đại học", "cao đẳng"],
    "nghiên cứu": ["học tập", "tìm hiểu"],
    "phát triển": ["cải thiện", "nâng cao"],
    "công nghệ": ["kỹ thuật", "technology"],
    "thông tin": ["dữ liệu", "tin tức"],
    "hệ thống": ["system", "cơ chế"],
    "quản lý": ["điều hành", "management"],
    "dự án": ["project", "công trình"],
    "phần mềm": ["software", "ứng dụng"],
    "dữ liệu": ["data", "thông tin"],
}

# Technical terms that should be preserved (not expanded or spell-checked)
TECHNICAL_TERMS = {
    "API", "REST", "HTTP", "HTTPS", "JSON", "XML", "SQL", "NoSQL",
    "Python", "JavaScript", "TypeScript", "Java", "C++", "C#",
    "Docker", "Kubernetes", "AWS", "Azure", "GCP",
    "Git", "GitHub", "GitLab", "CI/CD",
    "AI", "ML", "NLP", "LLM", "RAG", "OCR",
    "FastAPI", "Django", "Flask", "React", "Vue", "Angular",
    "MongoDB", "PostgreSQL", "MySQL", "Redis",
    "OAuth", "JWT", "SSL", "TLS",
}


@dataclass
class QueryExpansion:
    """Result of query expansion"""
    original: str
    expanded_terms: List[str]
    synonyms_used: Dict[str, List[str]]
    preserved_terms: List[str]


@dataclass
class ProcessingQuality:
    """Quality metrics for text processing"""
    original_text: str
    processed_text: str
    corrections_made: int
    terms_expanded: int
    terms_preserved: int


class EnhancedTextProcessor:
    """Enhanced text processor with spell checking and query expansion"""
    
    def __init__(self):
        self.symspell = None
        if SYMSPELL_AVAILABLE:
            try:
                self.symspell = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
                # Note: In production, load a proper Vietnamese dictionary
                # For now, we'll use basic functionality
                logger.info("SymSpell initialized for spell checking")
            except Exception as e:
                logger.warning(f"Failed to initialize SymSpell: {e}")
                self.symspell = None
    
    def spell_check(self, text: str, language: str = "vi") -> str:
        """
        Correct spelling errors in text
        
        Args:
            text: Input text
            language: Language code (vi for Vietnamese, en for English)
            
        Returns:
            Spell-checked text
        """
        if not self.symspell:
            logger.debug("SymSpell not available, returning original text")
            return text
        
        # For now, return original text as we need a proper dictionary
        # In production, load Vietnamese dictionary and use:
        # suggestions = self.symspell.lookup_compound(text, max_edit_distance=2)
        # return suggestions[0].term if suggestions else text
        
        return text
    
    def preserve_technical_terms(self, text: str) -> List[str]:
        """
        Identify and preserve technical terms in text
        
        Args:
            text: Input text
            
        Returns:
            List of technical terms found
        """
        words = text.split()
        preserved = []
        
        for word in words:
            # Remove punctuation for checking
            clean_word = re.sub(r'[^\w]', '', word)
            if clean_word.upper() in TECHNICAL_TERMS or clean_word in TECHNICAL_TERMS:
                preserved.append(clean_word)
        
        return preserved
    
    def expand_query(
        self, 
        query: str, 
        max_synonyms: int = 3
    ) -> QueryExpansion:
        """
        Expand query with synonyms
        
        Args:
            query: Original query
            max_synonyms: Maximum number of synonyms per term (default: 3)
            
        Returns:
            QueryExpansion with expanded terms
        """
        # Preserve technical terms
        preserved_terms = self.preserve_technical_terms(query)
        
        # Split query into words
        words = query.split()
        expanded_terms = []
        synonyms_used = {}
        
        for word in words:
            # Skip technical terms
            clean_word = re.sub(r'[^\w]', '', word)
            if clean_word.upper() in TECHNICAL_TERMS or clean_word in TECHNICAL_TERMS:
                expanded_terms.append(word)
                continue
            
            # Add original word
            expanded_terms.append(word)
            
            # Look for synonyms (case-insensitive)
            word_lower = clean_word.lower()
            if word_lower in VIETNAMESE_SYNONYMS:
                synonyms = VIETNAMESE_SYNONYMS[word_lower][:max_synonyms]
                synonyms_used[word_lower] = synonyms
                expanded_terms.extend(synonyms)
        
        return QueryExpansion(
            original=query,
            expanded_terms=expanded_terms,
            synonyms_used=synonyms_used,
            preserved_terms=preserved_terms
        )
    
    def process_query(
        self,
        query: str,
        spell_check: bool = True,
        expand: bool = True,
        max_synonyms: int = 3
    ) -> Tuple[str, ProcessingQuality]:
        """
        Process query with spell checking and expansion
        
        Args:
            query: Original query
            spell_check: Whether to apply spell checking
            expand: Whether to expand with synonyms
            max_synonyms: Maximum synonyms per term
            
        Returns:
            Tuple of (processed_query, quality_metrics)
        """
        original = query
        processed = query
        corrections_made = 0
        terms_expanded = 0
        terms_preserved = 0
        
        # Spell check
        if spell_check:
            checked = self.spell_check(processed)
            if checked != processed:
                corrections_made += 1
            processed = checked
        
        # Expand query
        if expand:
            expansion = self.expand_query(processed, max_synonyms)
            terms_expanded = len(expansion.synonyms_used)
            terms_preserved = len(expansion.preserved_terms)
            # Join expanded terms
            processed = " ".join(expansion.expanded_terms)
        
        quality = ProcessingQuality(
            original_text=original,
            processed_text=processed,
            corrections_made=corrections_made,
            terms_expanded=terms_expanded,
            terms_preserved=terms_preserved
        )
        
        return processed, quality


# Global instance
text_processor = EnhancedTextProcessor()
