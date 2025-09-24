"""Custom exceptions for the email CSV extractor."""


class EmailCsvExtractorError(Exception):
    """Base exception for all email CSV extractor errors."""
    
    pass


class AuthenticationError(EmailCsvExtractorError):
    """Raised when authentication fails."""
    
    pass


class EmailPollingError(EmailCsvExtractorError):
    """Raised when email polling encounters an error."""
    
    pass


class MessageFilteringError(EmailCsvExtractorError):
    """Raised when message filtering encounters an error."""
    
    pass


class AttachmentDownloadError(EmailCsvExtractorError):
    """Raised when CSV attachment download fails."""
    
    pass


class SharePointUploadError(EmailCsvExtractorError):
    """Raised when SharePoint upload fails."""
    
    pass


class ConfigurationError(EmailCsvExtractorError):
    """Raised when configuration is invalid."""
    
    pass