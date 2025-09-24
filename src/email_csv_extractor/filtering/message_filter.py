"""Message filtering service for email messages and CSV attachments."""

import re
from typing import List, Dict, Any
from datetime import datetime, timedelta

from ..core.interfaces import MessageFilter, Logger, EmailMessage, CsvAttachment, FilterCriteria
from ..core.exceptions import MessageFilteringError


class EmailMessageFilter(MessageFilter):
    """Message filter for determining which emails and attachments to process."""
    
    def __init__(self, config: Dict[str, Any], logger: Logger) -> None:
        """Initialize the message filter.
        
        Args:
            config: Filtering configuration containing:
                - csv_file_extensions: List of CSV file extensions
                - min_file_size_bytes: Minimum file size to process
                - max_file_size_mb: Maximum file size to process
            logger: Logger instance for structured logging
        """
        self._config = config
        self._logger = logger
        
        self._csv_extensions = config.get("csv_file_extensions", [".csv", ".CSV"])
        self._min_file_size = config.get("min_file_size_bytes", 1)
        self._max_file_size_bytes = config.get("max_file_size_mb", 100) * 1024 * 1024
        
        self._logger.info(
            "Initialized email message filter",
            csv_extensions=self._csv_extensions,
            min_file_size_bytes=self._min_file_size,
            max_file_size_mb=config.get("max_file_size_mb", 100)
        )
    
    def should_process_message(
        self, message: EmailMessage, criteria: FilterCriteria
    ) -> bool:
        """Determine if a message should be processed based on criteria.
        
        Args:
            message: Email message to evaluate
            criteria: Filter criteria to apply
            
        Returns:
            True if message should be processed, False otherwise
        """
        try:
            self._logger.debug(
                "Evaluating message for processing",
                message_id=message.id,
                sender=message.sender,
                subject=message.subject
            )
            
            # Check if message has attachments
            if not message.has_attachments:
                self._logger.debug(
                    "Message rejected: no attachments",
                    message_id=message.id
                )
                return False
            
            # Check sender patterns
            if criteria.sender_patterns and not self._matches_sender_patterns(
                message.sender, criteria.sender_patterns
            ):
                self._logger.debug(
                    "Message rejected: sender doesn't match patterns",
                    message_id=message.id,
                    sender=message.sender,
                    patterns=criteria.sender_patterns
                )
                return False
            
            # Check subject patterns
            if criteria.subject_patterns and not self._matches_subject_patterns(
                message.subject, criteria.subject_patterns
            ):
                self._logger.debug(
                    "Message rejected: subject doesn't match patterns",
                    message_id=message.id,
                    subject=message.subject,
                    patterns=criteria.subject_patterns
                )
                return False
            
            # Check message age
            if criteria.max_age_days and not self._is_message_within_age_limit(
                message.received_datetime, criteria.max_age_days
            ):
                self._logger.debug(
                    "Message rejected: too old",
                    message_id=message.id,
                    received_datetime=message.received_datetime,
                    max_age_days=criteria.max_age_days
                )
                return False
            
            self._logger.debug(
                "Message approved for processing",
                message_id=message.id,
                sender=message.sender,
                subject=message.subject
            )
            return True
            
        except Exception as e:
            self._logger.error(
                "Error evaluating message for processing",
                error=str(e),
                error_type=type(e).__name__,
                message_id=message.id
            )
            raise MessageFilteringError(f"Message evaluation failed: {str(e)}") from e
    
    def extract_csv_attachments(
        self, attachments: List[CsvAttachment]
    ) -> List[CsvAttachment]:
        """Filter attachments to only include valid CSV files.
        
        Args:
            attachments: List of all attachments
            
        Returns:
            List of CSV attachments that pass validation
        """
        try:
            self._logger.debug(
                "Filtering attachments for CSV files",
                total_attachments=len(attachments)
            )
            
            csv_attachments = []
            
            for attachment in attachments:
                if self._is_valid_csv_attachment(attachment):
                    csv_attachments.append(attachment)
                    self._logger.debug(
                        "CSV attachment approved",
                        attachment_id=attachment.id,
                        name=attachment.name,
                        size=attachment.size
                    )
                else:
                    self._logger.debug(
                        "Attachment rejected",
                        attachment_id=attachment.id,
                        name=attachment.name,
                        size=attachment.size,
                        content_type=attachment.content_type
                    )
            
            self._logger.info(
                "Completed CSV attachment filtering",
                total_attachments=len(attachments),
                csv_attachments_count=len(csv_attachments)
            )
            
            return csv_attachments
            
        except Exception as e:
            self._logger.error(
                "Error filtering CSV attachments",
                error=str(e),
                error_type=type(e).__name__,
                total_attachments=len(attachments)
            )
            raise MessageFilteringError(f"Attachment filtering failed: {str(e)}") from e
    
    def _matches_sender_patterns(self, sender: str, patterns: List[str]) -> bool:
        """Check if sender matches any of the provided patterns.
        
        Args:
            sender: Sender email address
            patterns: List of patterns to match against
            
        Returns:
            True if sender matches any pattern
        """
        if not sender or not patterns:
            return True  # No patterns means match all
        
        sender_lower = sender.lower()
        
        for pattern in patterns:
            pattern_lower = pattern.lower()
            
            # Support both regex and simple substring matching
            try:
                if re.search(pattern_lower, sender_lower):
                    return True
            except re.error:
                # If regex fails, fall back to substring matching
                if pattern_lower in sender_lower:
                    return True
        
        return False
    
    def _matches_subject_patterns(self, subject: str, patterns: List[str]) -> bool:
        """Check if subject matches any of the provided patterns.
        
        Args:
            subject: Email subject
            patterns: List of patterns to match against
            
        Returns:
            True if subject matches any pattern
        """
        if not subject or not patterns:
            return True  # No patterns means match all
        
        subject_lower = subject.lower()
        
        for pattern in patterns:
            pattern_lower = pattern.lower()
            
            # Support both regex and simple substring matching
            try:
                if re.search(pattern_lower, subject_lower):
                    return True
            except re.error:
                # If regex fails, fall back to substring matching
                if pattern_lower in subject_lower:
                    return True
        
        return False
    
    def _is_message_within_age_limit(self, received_datetime: str, max_age_days: int) -> bool:
        """Check if message is within the age limit.
        
        Args:
            received_datetime: ISO 8601 datetime string when message was received
            max_age_days: Maximum age in days
            
        Returns:
            True if message is within age limit
        """
        try:
            # Parse the datetime string (MS Graph returns ISO 8601 format)
            received_dt = datetime.fromisoformat(received_datetime.replace('Z', '+00:00'))
            
            # Convert to UTC for comparison
            if received_dt.tzinfo is not None:
                received_dt = received_dt.replace(tzinfo=None)
            
            # Check if within age limit
            cutoff_date = datetime.utcnow() - timedelta(days=max_age_days)
            return received_dt >= cutoff_date
            
        except (ValueError, TypeError) as e:
            self._logger.warning(
                "Failed to parse message datetime, assuming within age limit",
                received_datetime=received_datetime,
                error=str(e)
            )
            return True  # Assume within limit if parsing fails
    
    def _is_valid_csv_attachment(self, attachment: CsvAttachment) -> bool:
        """Check if an attachment is a valid CSV file to process.
        
        Args:
            attachment: Attachment to validate
            
        Returns:
            True if attachment is valid for processing
        """
        # Check file extension
        if not self._has_csv_extension(attachment.name):
            return False
        
        # Check file size
        if attachment.size < self._min_file_size:
            return False
        
        if attachment.size > self._max_file_size_bytes:
            return False
        
        # Check content type (if available)
        if attachment.content_type and not self._has_csv_content_type(attachment.content_type):
            # Don't reject based on content type alone, as it can be unreliable
            self._logger.debug(
                "Attachment has non-CSV content type but will proceed based on extension",
                attachment_name=attachment.name,
                content_type=attachment.content_type
            )
        
        return True
    
    def _has_csv_extension(self, filename: str) -> bool:
        """Check if filename has a CSV extension.
        
        Args:
            filename: Name of the file
            
        Returns:
            True if file has CSV extension
        """
        if not filename:
            return False
        
        filename_lower = filename.lower()
        return any(filename_lower.endswith(ext.lower()) for ext in self._csv_extensions)
    
    def _has_csv_content_type(self, content_type: str) -> bool:
        """Check if content type indicates CSV file.
        
        Args:
            content_type: MIME content type
            
        Returns:
            True if content type indicates CSV
        """
        if not content_type:
            return False
        
        csv_content_types = [
            "text/csv",
            "application/csv",
            "text/comma-separated-values",
            "text/plain"  # CSV files are sometimes served as plain text
        ]
        
        content_type_lower = content_type.lower()
        return any(csv_type in content_type_lower for csv_type in csv_content_types)
    
    def get_filter_statistics(self) -> Dict[str, Any]:
        """Get statistics about the current filter configuration.
        
        Returns:
            Dictionary with filter statistics
        """
        return {
            "csv_extensions": self._csv_extensions,
            "min_file_size_bytes": self._min_file_size,
            "max_file_size_bytes": self._max_file_size_bytes,
            "max_file_size_mb": self._max_file_size_bytes / (1024 * 1024)
        }