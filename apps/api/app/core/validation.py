"""Input validation and sanitization utilities for enterprise security."""

import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class EmailValidation(BaseModel):
    """Email validation model."""
    email: EmailStr


class PhoneValidation(BaseModel):
    """Phone number validation."""
    phone: str = Field(..., pattern=r'^\+?[1-9]\d{1,14}$')


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal attacks.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    # Remove path separators
    filename = filename.replace("/", "_").replace("\\", "_")
    
    # Remove potentially dangerous characters
    filename = re.sub(r'[^\w\s.-]', '', filename)
    
    # Limit length
    if len(filename) > 255:
        name, ext = filename.rsplit(".", 1) if "." in filename else (filename, "")
        filename = name[:250] + ("." + ext if ext else "")
    
    return filename


def sanitize_text(text: str, max_length: Optional[int] = None) -> str:
    """
    Sanitize text input to prevent injection attacks.
    
    Args:
        text: Input text
        max_length: Maximum allowed length
        
    Returns:
        Sanitized text
    """
    if not text:
        return ""
    
    # Remove null bytes
    text = text.replace("\x00", "")
    
    # Trim whitespace
    text = text.strip()
    
    # Limit length
    if max_length and len(text) > max_length:
        text = text[:max_length]
    
    return text


def validate_email(email: str) -> bool:
    """
    Validate email format.
    
    Args:
        email: Email address to validate
        
    Returns:
        True if valid, False otherwise
    """
    try:
        EmailValidation(email=email)
        return True
    except:
        return False


def validate_phone(phone: str) -> bool:
    """
    Validate phone number (E.164 format).
    
    Args:
        phone: Phone number to validate
        
    Returns:
        True if valid, False otherwise
    """
    try:
        PhoneValidation(phone=phone)
        return True
    except:
        return False


def validate_uuid(value: str) -> bool:
    """
    Validate UUID format.
    
    Args:
        value: String to validate as UUID
        
    Returns:
        True if valid UUID, False otherwise
    """
    import uuid
    try:
        uuid.UUID(value)
        return True
    except (ValueError, AttributeError):
        return False


class URLValidator:
    """URL validation with whitelist support."""
    
    ALLOWED_SCHEMES = ["http", "https"]
    BLOCKED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0", "internal"]
    
    @classmethod
    def validate(cls, url: str, allow_localhost: bool = False) -> bool:
        """
        Validate URL with security checks.
        
        Args:
            url: URL to validate
            allow_localhost: Whether to allow localhost URLs
            
        Returns:
            True if valid and safe, False otherwise
        """
        from urllib.parse import urlparse
        
        try:
            parsed = urlparse(url)
            
            # Check scheme
            if parsed.scheme not in cls.ALLOWED_SCHEMES:
                return False
            
            # Check for blocked hosts (SSRF prevention)
            if not allow_localhost:
                for blocked in cls.BLOCKED_HOSTS:
                    if blocked in parsed.netloc.lower():
                        return False
            
            return True
        
        except Exception:
            return False


class SQLInjectionValidator:
    """SQL injection prevention validator."""
    
    DANGEROUS_PATTERNS = [
        r"(\bUNION\b.*\bSELECT\b)",
        r"(\bSELECT\b.*\bFROM\b)",
        r"(\bINSERT\b.*\bINTO\b)",
        r"(\bUPDATE\b.*\bSET\b)",
        r"(\bDELETE\b.*\bFROM\b)",
        r"(\bDROP\b.*\bTABLE\b)",
        r"(--|\#|\/\*)",
        r"(\bOR\b.*=.*)",
        r"('.*OR.*'=')",
    ]
    
    @classmethod
    def validate(cls, text: str) -> bool:
        """
        Check if text contains SQL injection patterns.
        
        Args:
            text: Text to validate
            
        Returns:
            True if safe, False if suspicious patterns found
        """
        text_upper = text.upper()
        
        for pattern in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, text_upper, re.IGNORECASE):
                return False
        
        return True


class XSSValidator:
    """XSS prevention validator."""
    
    DANGEROUS_PATTERNS = [
        r"<script[^>]*>.*?</script>",
        r"javascript:",
        r"on\w+\s*=",  # onclick, onload, etc.
        r"<iframe",
        r"<object",
        r"<embed",
    ]
    
    @classmethod
    def validate(cls, text: str) -> bool:
        """
        Check if text contains XSS patterns.
        
        Args:
            text: Text to validate
            
        Returns:
            True if safe, False if suspicious patterns found
        """
        for pattern in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return False
        
        return True
    
    @classmethod
    def sanitize(cls, text: str) -> str:
        """
        Sanitize text by escaping HTML special characters.
        
        Args:
            text: Text to sanitize
            
        Returns:
            Sanitized text
        """
        import html
        return html.escape(text)


def validate_input_dict(
    data: Dict[str, Any],
    required_fields: List[str],
    optional_fields: Optional[List[str]] = None,
) -> Dict[str, str]:
    """
    Validate that dictionary contains required fields and no unexpected fields.
    
    Args:
        data: Input dictionary
        required_fields: List of required field names
        optional_fields: List of optional field names
        
    Returns:
        Dict of validation errors (empty if valid)
    """
    errors = {}
    
    # Check required fields
    for field in required_fields:
        if field not in data or data[field] is None:
            errors[field] = f"{field} is required"
    
    # Check for unexpected fields
    allowed_fields = set(required_fields + (optional_fields or []))
    for field in data.keys():
        if field not in allowed_fields:
            errors[field] = f"Unexpected field: {field}"
    
    return errors


class FileUploadValidator:
    """File upload validation."""
    
    ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt"}
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
    
    @classmethod
    def validate_extension(cls, filename: str) -> bool:
        """Check if file extension is allowed."""
        import os
        ext = os.path.splitext(filename)[1].lower()
        return ext in cls.ALLOWED_EXTENSIONS
    
    @classmethod
    def validate_size(cls, file_size: int) -> bool:
        """Check if file size is within limit."""
        return file_size <= cls.MAX_FILE_SIZE
    
    @classmethod
    def validate_mime_type(cls, content_type: str) -> bool:
        """Check if MIME type is allowed."""
        allowed_types = {
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "text/plain",
        }
        return content_type in allowed_types












