"""PDF and document parsing utilities."""

import re
from typing import Optional

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

try:
    import docx
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False


class DocumentParser:
    """Parser for extracting text from various document formats."""
    
    @staticmethod
    def _clean_garbled_text(text: str) -> str:
        """Clean garbled text with spaces/ampersands between characters.
        
        Fixes issues like "D o c u m e n t a t i o n" or "D&o&c&u&m&e&n&t&a&t&i&o&n"
        by removing spaces/ampersands between consecutive characters.
        
        Args:
            text: Raw extracted text with potential garbling
            
        Returns:
            Cleaned text with normal spacing
        """
        if not text:
            return text
        
        # First, normalize multiple spaces to single space
        text = re.sub(r' +', ' ', text)
        
        # Handle ampersands between characters: "D&o&c&u&m&e&n&t&a&t&i&o&n" → "Documentation"
        text = re.sub(r'([a-zA-Z0-9])&+([a-zA-Z0-9])', r'\1\2', text)
        
        # Handle spaces between single characters that form words
        # Pattern: "D o c u m e n t a t i o n" → "Documentation"
        # Strategy: Find sequences of single letters/numbers separated by single spaces
        # and combine them if they appear to form a word
        
        # Pattern to find sequences like "X Y Z" (single chars separated by spaces)
        # We'll process lines separately to avoid breaking across words
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Split line by spaces to identify word boundaries
            # If we see a pattern like single char + space + single char repeatedly,
            # it's likely garbled text
            words = line.split()
            cleaned_words = []
            
            i = 0
            while i < len(words):
                # Check if this starts a garbled sequence (multiple single-char "words")
                if len(words[i]) == 1 and i + 1 < len(words) and len(words[i + 1]) == 1:
                    # Found start of garbled sequence - collect consecutive single chars
                    garbled_seq = [words[i]]
                    i += 1
                    while i < len(words) and len(words[i]) == 1:
                        garbled_seq.append(words[i])
                        i += 1
                    # Combine into single word
                    cleaned_words.append(''.join(garbled_seq))
                else:
                    # Normal word - keep as is
                    cleaned_words.append(words[i])
                    i += 1
            
            cleaned_lines.append(' '.join(cleaned_words))
        
        text = '\n'.join(cleaned_lines)
        
        # Also handle patterns with mixed spaces and ampersands: "D o & c u m e n t"
        text = re.sub(r'([a-zA-Z0-9])\s*&\s*([a-zA-Z0-9])', r'\1\2', text)
        
        # Clean up multiple spaces that might remain
        text = re.sub(r' {2,}', ' ', text)
        
        # Normalize line breaks
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text.strip()

    @staticmethod
    def extract_text_from_pdf(file_bytes: bytes) -> str:
        """Extract text from PDF file (Azure DI primary when configured)."""
        try:
            from app.services.pdf_extraction import extract_pdf_text

            text, _method = extract_pdf_text(file_bytes)
            return DocumentParser._clean_garbled_text(text)
        except Exception:
            pass

        if not PDFPLUMBER_AVAILABLE:
            raise ImportError("pdfplumber not installed. Install with: pip install pdfplumber")
        
        import io
        text_parts = []
        
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    # Clean garbled text (spaces/ampersands between characters)
                    text = DocumentParser._clean_garbled_text(text)
                    text_parts.append(text)
        
        return "\n".join(text_parts)

    @staticmethod
    def extract_text_from_docx(file_bytes: bytes) -> str:
        """Extract text from DOCX file.
        
        Args:
            file_bytes: DOCX file bytes
            
        Returns:
            Extracted text
        """
        if not DOCX_AVAILABLE:
            raise ImportError("python-docx not installed. Install with: pip install python-docx")
        
        import io
        doc = docx.Document(io.BytesIO(file_bytes))
        
        text_parts = []
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text_parts.append(paragraph.text)
        
        return "\n".join(text_parts)

    @staticmethod
    def extract_text(file_bytes: bytes, filename: str) -> str:
        """Extract text from document based on file extension.
        
        Args:
            file_bytes: File bytes
            filename: Original filename
            
        Returns:
            Extracted text
        """
        filename_lower = filename.lower()
        
        if filename_lower.endswith('.pdf'):
            return DocumentParser.extract_text_from_pdf(file_bytes)
        elif filename_lower.endswith('.docx'):
            return DocumentParser.extract_text_from_docx(file_bytes)
        elif filename_lower.endswith('.txt'):
            return file_bytes.decode('utf-8', errors='ignore')
        else:
            # Try to decode as text
            try:
                return file_bytes.decode('utf-8', errors='ignore')
            except:
                raise ValueError(f"Unsupported file type: {filename}")

