"""PII redaction utilities for logs and audit trails."""

import re
from typing import Any, Dict, List, Optional, Pattern

# Patterns for common PII
EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
PHONE_PATTERN = re.compile(r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}')
SSN_PATTERN = re.compile(r'\b\d{3}-\d{2}-\d{4}\b')
CREDIT_CARD_PATTERN = re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b')
IP_ADDRESS_PATTERN = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')
DATE_OF_BIRTH_PATTERN = re.compile(r'\b\d{2}/\d{2}/\d{4}\b|\b\d{4}-\d{2}-\d{2}\b')

# Sensitive field names to redact
SENSITIVE_FIELDS = {
    'password', 'token', 'secret', 'api_key', 'ssn', 'social_security',
    'credit_card', 'cvv', 'pin', 'passport', 'drivers_license',
    'date_of_birth', 'dob', 'birth_date', 'salary', 'compensation',
}


class PIIRedactor:
    """Utility for redacting PII from logs and data structures."""
    
    @staticmethod
    def redact_text(text: str, replacement: str = "[REDACTED]") -> str:
        """
        Redact PII patterns from text.
        
        Args:
            text: Text potentially containing PII
            replacement: String to replace PII with
            
        Returns:
            Text with PII redacted
        """
        if not text:
            return text
        
        # Redact email addresses
        text = EMAIL_PATTERN.sub(f"[EMAIL_{replacement}]", text)
        
        # Redact phone numbers
        text = PHONE_PATTERN.sub(f"[PHONE_{replacement}]", text)
        
        # Redact SSN
        text = SSN_PATTERN.sub(f"[SSN_{replacement}]", text)
        
        # Redact credit cards
        text = CREDIT_CARD_PATTERN.sub(f"[CC_{replacement}]", text)
        
        # Redact IP addresses (partially)
        text = IP_ADDRESS_PATTERN.sub(lambda m: PIIRedactor._redact_ip(m.group()), text)
        
        # Redact DOB
        text = DATE_OF_BIRTH_PATTERN.sub(f"[DOB_{replacement}]", text)
        
        return text
    
    @staticmethod
    def _redact_ip(ip: str) -> str:
        """Partially redact IP address (keep first two octets)."""
        parts = ip.split('.')
        if len(parts) == 4:
            return f"{parts[0]}.{parts[1]}.xxx.xxx"
        return "[IP_REDACTED]"
    
    @staticmethod
    def redact_dict(data: Dict[str, Any], deep: bool = True) -> Dict[str, Any]:
        """
        Redact PII from dictionary (for logging structured data).
        
        Args:
            data: Dictionary potentially containing PII
            deep: Whether to recursively redact nested structures
            
        Returns:
            Dictionary with sensitive fields redacted
        """
        if not isinstance(data, dict):
            return data
        
        redacted = {}
        for key, value in data.items():
            key_lower = key.lower()
            
            # Check if field name is sensitive
            if any(sensitive in key_lower for sensitive in SENSITIVE_FIELDS):
                redacted[key] = "[REDACTED]"
            
            # Recursively process nested dicts
            elif deep and isinstance(value, dict):
                redacted[key] = PIIRedactor.redact_dict(value, deep=True)
            
            # Process lists
            elif deep and isinstance(value, list):
                redacted[key] = [
                    PIIRedactor.redact_dict(item, deep=True) if isinstance(item, dict)
                    else PIIRedactor.redact_text(str(item)) if isinstance(item, str)
                    else item
                    for item in value
                ]
            
            # Redact string values
            elif isinstance(value, str):
                redacted[key] = PIIRedactor.redact_text(value)
            
            # Keep other types as-is
            else:
                redacted[key] = value
        
        return redacted
    
    @staticmethod
    def redact_candidate_name(name: str) -> str:
        """
        Redact candidate name for anonymized logs.
        
        Returns: "Candidate-XXXX" where XXXX is hash of name
        """
        import hashlib
        name_hash = hashlib.md5(name.encode()).hexdigest()[:8]
        return f"Candidate-{name_hash}"
    
    @staticmethod
    def anonymize_for_analytics(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Anonymize data for analytics/reporting.
        
        Keeps statistical value while removing PII.
        """
        anonymized = {}
        
        for key, value in data.items():
            key_lower = key.lower()
            
            # Replace identifiable fields with anonymous IDs
            if 'email' in key_lower:
                anonymized[key] = PIIRedactor._hash_value(value)
            elif 'name' in key_lower:
                anonymized[key] = PIIRedactor._hash_value(value)
            elif 'phone' in key_lower:
                anonymized[key] = "[PHONE_HASHED]"
            elif 'ip' in key_lower or 'address' in key_lower:
                anonymized[key] = PIIRedactor._redact_ip(value) if isinstance(value, str) else value
            
            # Keep aggregate/statistical data
            elif key_lower in ['count', 'total', 'average', 'score', 'rating', 'status']:
                anonymized[key] = value
            
            # Recursively handle nested structures
            elif isinstance(value, dict):
                anonymized[key] = PIIRedactor.anonymize_for_analytics(value)
            elif isinstance(value, list) and value and isinstance(value[0], dict):
                anonymized[key] = [PIIRedactor.anonymize_for_analytics(item) for item in value]
            
            else:
                anonymized[key] = value
        
        return anonymized
    
    @staticmethod
    def _hash_value(value: str) -> str:
        """Generate consistent hash for value."""
        import hashlib
        return hashlib.sha256(value.encode()).hexdigest()[:16]
    
    @staticmethod
    def redact_for_audit_log(log_entry: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare log entry for audit trail.
        
        Balances between auditability and privacy.
        """
        redacted = log_entry.copy()
        
        # Redact sensitive fields but keep metadata
        if 'user_email' in redacted:
            # Keep domain for audit, redact local part
            email = redacted['user_email']
            if '@' in email:
                local, domain = email.split('@')
                redacted['user_email'] = f"{local[:2]}***@{domain}"
        
        if 'ip_address' in redacted:
            redacted['ip_address'] = PIIRedactor._redact_ip(redacted['ip_address'])
        
        # Redact request/response bodies
        if 'request_body' in redacted:
            redacted['request_body'] = PIIRedactor.redact_dict(redacted['request_body'])
        
        if 'response_body' in redacted:
            redacted['response_body'] = PIIRedactor.redact_dict(redacted['response_body'])
        
        return redacted


class AuditLogger:
    """Enhanced audit logging with PII protection."""
    
    @staticmethod
    async def log_action(
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        details: Optional[Dict[str, Any]] = None,
        result: str = "success",
        ip_address: Optional[str] = None,
    ):
        """
        Log user action with PII redaction.
        
        Stores in audit_logs table with proper redaction.
        """
        log_entry = {
            "timestamp": "datetime.utcnow().isoformat()",
            "user_id": user_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "result": result,
            "ip_address": ip_address,
            "details": details or {},
        }
        
        # Redact PII from details
        log_entry["details"] = PIIRedactor.redact_dict(log_entry["details"])
        
        # Partially redact IP
        if log_entry["ip_address"]:
            log_entry["ip_address"] = PIIRedactor._redact_ip(log_entry["ip_address"])
        
        # TODO: Store in database
        # await db.execute(INSERT INTO audit_logs ...)
        
        # Also log to structured logger
        import logging
        logger = logging.getLogger("audit")
        logger.info(f"Audit: {log_entry}")
    
    @staticmethod
    async def log_data_access(
        user_id: str,
        accessed_user_id: str,
        data_type: str,
        reason: Optional[str] = None,
    ):
        """
        Log access to candidate PII.
        
        Required for GDPR transparency.
        """
        await AuditLogger.log_action(
            user_id=user_id,
            action="data_access",
            resource_type=data_type,
            resource_id=accessed_user_id,
            details={"reason": reason} if reason else {},
        )
    
    @staticmethod
    async def log_sensitive_operation(
        user_id: str,
        operation: str,
        resource_id: str,
        justification: str,
    ):
        """
        Log highly sensitive operations.
        
        Examples: data deletion, role changes, permission grants.
        """
        await AuditLogger.log_action(
            user_id=user_id,
            action=f"SENSITIVE_{operation}",
            resource_type="system",
            resource_id=resource_id,
            details={"justification": justification},
        )
        
        # TODO: Send alert to security team
        import logging
        logging.getLogger("security").warning(
            f"Sensitive operation: {operation} by {user_id}"
        )


# Example usage in logging configuration
def configure_pii_safe_logging():
    """
    Configure logging to automatically redact PII.
    
    Add this to app startup.
    """
    import logging
    
    class PIIRedactingFormatter(logging.Formatter):
        """Custom formatter that redacts PII from log messages."""
        
        def format(self, record: logging.LogRecord) -> str:
            # Redact PII from message
            if isinstance(record.msg, str):
                record.msg = PIIRedactor.redact_text(record.msg)
            
            # Redact PII from args
            if record.args:
                record.args = tuple(
                    PIIRedactor.redact_text(str(arg)) if isinstance(arg, str) else arg
                    for arg in record.args
                )
            
            return super().format(record)
    
    # Apply to all handlers
    for handler in logging.root.handlers:
        handler.setFormatter(PIIRedactingFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))












