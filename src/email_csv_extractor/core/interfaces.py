"""Abstract base classes and interfaces following SOLID principles."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Protocol
from dataclasses import dataclass
from pathlib import Path


@dataclass
class EmailMessage:
    """Represents an email message with relevant metadata."""
    
    id: str
    sender: str
    subject: str
    received_datetime: str
    has_attachments: bool
    body_preview: str


@dataclass
class CsvAttachment:
    """Represents a CSV attachment from an email."""
    
    id: str
    name: str
    size: int
    content_type: str
    download_url: Optional[str] = None


@dataclass
class FilterCriteria:
    """Criteria for filtering email messages."""
    
    sender_patterns: List[str]
    subject_patterns: List[str]
    max_age_days: Optional[int] = None


class AuthenticationProvider(ABC):
    """Abstract base class for authentication providers."""
    
    @abstractmethod
    async def get_access_token(self) -> str:
        """Get a valid access token for MS Graph API."""
        pass
    
    @abstractmethod
    async def refresh_token_if_needed(self) -> None:
        """Refresh the access token if it's close to expiry."""
        pass


class EmailPoller(ABC):
    """Abstract base class for email polling services."""
    
    @abstractmethod
    async def poll_mailbox_for_new_messages(
        self, filter_criteria: FilterCriteria
    ) -> List[EmailMessage]:
        """Poll the mailbox for new messages matching criteria."""
        pass
    
    @abstractmethod
    async def get_message_attachments(self, message_id: str) -> List[CsvAttachment]:
        """Get CSV attachments from a specific message."""
        pass


class MessageFilter(ABC):
    """Abstract base class for message filtering services."""
    
    @abstractmethod
    def should_process_message(
        self, message: EmailMessage, criteria: FilterCriteria
    ) -> bool:
        """Determine if a message should be processed based on criteria."""
        pass
    
    @abstractmethod
    def extract_csv_attachments(
        self, attachments: List[CsvAttachment]
    ) -> List[CsvAttachment]:
        """Filter attachments to only include CSV files."""
        pass


class AttachmentDownloader(ABC):
    """Abstract base class for attachment download services."""
    
    @abstractmethod
    async def download_csv_attachment(
        self, attachment: CsvAttachment, local_path: Path
    ) -> Path:
        """Download a CSV attachment to a local file."""
        pass
    
    @abstractmethod
    async def validate_csv_content(self, file_path: Path) -> bool:
        """Validate that the downloaded file is a valid CSV."""
        pass


class SharePointUploader(ABC):
    """Abstract base class for SharePoint upload services."""
    
    @abstractmethod
    async def upload_file_to_sharepoint_folder(
        self, 
        file_path: Path, 
        target_folder: str,
        team_id: str,
        channel_id: str
    ) -> str:
        """Upload a file to a SharePoint folder in a Teams channel."""
        pass
    
    @abstractmethod
    async def upload_large_file_to_sharepoint_folder(
        self,
        file_path: Path,
        target_folder: str,
        team_id: str,
        channel_id: str,
        chunk_size: int = 1024 * 1024 * 5  # 5MB chunks
    ) -> str:
        """Upload a large file using chunked upload."""
        pass


class ConfigurationManager(Protocol):
    """Protocol for configuration management."""
    
    def get_auth_config(self) -> Dict[str, Any]:
        """Get authentication configuration."""
        ...
    
    def get_email_config(self) -> Dict[str, Any]:
        """Get email polling configuration."""
        ...
    
    def get_sharepoint_config(self) -> Dict[str, Any]:
        """Get SharePoint upload configuration."""
        ...
    
    def get_filter_criteria(self) -> FilterCriteria:
        """Get message filtering criteria."""
        ...


class Logger(Protocol):
    """Protocol for structured logging."""
    
    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message."""
        ...
    
    def error(self, message: str, **kwargs: Any) -> None:
        """Log error message."""
        ...
    
    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message."""
        ...
    
    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message."""
        ...