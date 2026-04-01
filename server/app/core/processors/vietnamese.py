"""
Vietnamese text processing utilities
Provides tone restoration and text normalization for Vietnamese
"""
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Try to import Vietnamese NLP libraries
try:
    from underthesea import word_tokenize
    UNDERTHESEA_AVAILABLE = True
except ImportError:
    UNDERTHESEA_AVAILABLE = False
    logger.warning("underthesea not available. Install with: pip install underthesea")

# Vietnamese tone marks mapping
VIETNAMESE_TONE_MAP = {
    # a family
    'a': ['à', 'á', 'ả', 'ã', 'ạ', 'ă', 'ằ', 'ắ', 'ẳ', 'ẵ', 'ặ', 'â', 'ầ', 'ấ', 'ẩ', 'ẫ', 'ậ'],
    'e': ['è', 'é', 'ẻ', 'ẽ', 'ẹ', 'ê', 'ề', 'ế', 'ể', 'ễ', 'ệ'],
    'i': ['ì', 'í', 'ỉ', 'ĩ', 'ị'],
    'o': ['ò', 'ó', 'ỏ', 'õ', 'ọ', 'ô', 'ồ', 'ố', 'ổ', 'ỗ', 'ộ', 'ơ', 'ờ', 'ớ', 'ở', 'ỡ', 'ợ'],
    'u': ['ù', 'ú', 'ủ', 'ũ', 'ụ', 'ư', 'ừ', 'ứ', 'ử', 'ữ', 'ự'],
    'y': ['ỳ', 'ý', 'ỷ', 'ỹ', 'ỵ'],
    'd': ['đ']
}

# Common Vietnamese words dictionary (for basic tone restoration)
COMMON_VIETNAMESE_WORDS = {
    'viet': 'việt',
    'nam': 'nam',
    'tieng': 'tiếng',
    'nguoi': 'người',
    'nha': 'nhà',
    'hoc': 'học',
    'sinh': 'sinh',
    'truong': 'trường',
    'lop': 'lớp',
    'giao': 'giáo',
    'vien': 'viên',
    'khoa': 'khoa',
    'hoc': 'học',
    'dai': 'đại',
    'cao': 'cao',
    'dang': 'đẳng',
    'thong': 'thông',
    'tin': 'tin',
    'cong': 'công',
    'nghe': 'nghệ',
    'ky': 'kỹ',
    'thuat': 'thuật',
    'kinh': 'kinh',
    'te': 'tế',
    'chinh': 'chính',
    'tri': 'trị',
    'xa': 'xã',
    'hoi': 'hội',
    'van': 'văn',
    'hoa': 'hóa',
    'lich': 'lịch',
    'su': 'sử',
    'dia': 'địa',
    'ly': 'lý',
    'toan': 'toán',
    'sinh': 'sinh',
    'vat': 'vật',
    'hoa': 'hóa',
    'anh': 'anh',
    'van': 'văn',
    'the': 'thể',
    'duc': 'dục',
    'am': 'âm',
    'nhac': 'nhạc',
    'my': 'mỹ',
    'thuat': 'thuật',
}


class VietnameseProcessor:
    """Vietnamese text processor with tone restoration"""
    
    def __init__(self):
        self.use_underthesea = UNDERTHESEA_AVAILABLE
        
    def has_vietnamese_chars(self, text: str) -> bool:
        """Check if text contains Vietnamese characters"""
        vietnamese_chars = set('àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ')
        return any(c in vietnamese_chars for c in text.lower())
    
    def is_vietnamese_text(self, text: str) -> bool:
        """Detect if text is likely Vietnamese"""
        # Check for Vietnamese-specific patterns
        vietnamese_patterns = [
            r'\b(việt|nam|tiếng|người|nhà|học|trường)\b',
            r'[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]'
        ]
        
        for pattern in vietnamese_patterns:
            if re.search(pattern, text.lower()):
                return True
        
        # Check if text has Vietnamese tone marks
        return self.has_vietnamese_chars(text)
    
    def restore_tones_basic(self, text: str) -> str:
        """
        Basic tone restoration using dictionary lookup
        This is a simple fallback method
        """
        words = text.lower().split()
        restored_words = []
        
        for word in words:
            # Remove punctuation for lookup
            clean_word = re.sub(r'[^\w]', '', word)
            
            # Look up in dictionary
            if clean_word in COMMON_VIETNAMESE_WORDS:
                restored = COMMON_VIETNAMESE_WORDS[clean_word]
                # Preserve original punctuation
                if word != clean_word:
                    restored = word.replace(clean_word, restored)
                restored_words.append(restored)
            else:
                restored_words.append(word)
        
        return ' '.join(restored_words)
    
    def normalize_vietnamese(self, text: str) -> str:
        """
        Normalize Vietnamese text
        - Fix common OCR errors
        - Standardize spacing
        - Fix tone marks
        """
        # Fix common OCR errors for Vietnamese
        replacements = {
            'đ': 'đ',  # Normalize đ character
            'Đ': 'Đ',
            '  ': ' ',  # Multiple spaces
            ' ,': ',',
            ' .': '.',
            ' ;': ';',
            ' :': ':',
            ' !': '!',
            ' ?': '?',
        }
        
        result = text
        for old, new in replacements.items():
            result = result.replace(old, new)
        
        return result.strip()
    
    def tokenize(self, text: str) -> list:
        """Tokenize Vietnamese text"""
        if self.use_underthesea:
            try:
                return word_tokenize(text)
            except Exception as e:
                logger.warning(f"Underthesea tokenization failed: {e}")
        
        # Fallback to simple split
        return text.split()
    
    def process_vietnamese_text(
        self, 
        text: str, 
        restore_tones: bool = True,
        normalize: bool = True
    ) -> str:
        """
        Process Vietnamese text with optional tone restoration
        
        Args:
            text: Input text
            restore_tones: Whether to attempt tone restoration
            normalize: Whether to normalize text
            
        Returns:
            Processed text
        """
        result = text
        
        # Normalize first
        if normalize:
            result = self.normalize_vietnamese(result)
        
        # Restore tones if requested and text doesn't have tones
        if restore_tones and not self.has_vietnamese_chars(result):
            result = self.restore_tones_basic(result)
        
        return result


# Global processor instance
vietnamese_processor = VietnameseProcessor()
