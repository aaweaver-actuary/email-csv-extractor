"""Configuration settings using Pydantic for validation."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict
from pathlib import Path
import os
from dotenv import load_dotenv

from ..core.interfaces import FilterCriteria, ConfigurationManager
from ..core.exceptions import ConfigurationError

# Load environment variables from .env file
load_dotenv()


class AuthConfig(BaseModel):
    """Authentication configuration for MS Graph API."""
    
    client_id: str = Field(..., description="Azure AD Application Client ID")
    client_secret: str = Field(..., description="Azure AD Application Client Secret")
    tenant_id: str = Field(..., description="Azure AD Tenant ID")
    authority: str = Field(
        default="https://login.microsoftonline.com",
        description="Azure AD Authority URL"
    )
    scopes: List[str] = Field(
        default=["https://graph.microsoft.com/.default"],
        description="OAuth scopes for MS Graph API"
    )
    
    @field_validator('client_id', 'client_secret', 'tenant_id')
    @classmethod
    def validate_required_fields(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()


class EmailConfig(BaseModel):
    """Email polling configuration."""
    
    mailbox_address: str = Field(..., description="Email address to monitor")
    polling_interval_seconds: int = Field(
        default=300, 
        ge=60, 
        description="Polling interval in seconds (minimum 60)"
    )
    max_messages_per_poll: int = Field(
        default=50,
        ge=1,
        le=1000,
        description="Maximum messages to process per poll"
    )
    processed_messages_tracking_enabled: bool = Field(
        default=True,
        description="Track processed messages to avoid duplicates"
    )


class SharePointConfig(BaseModel):
    """SharePoint upload configuration."""
    
    team_id: str = Field(..., description="Microsoft Teams Team ID")
    channel_id: str = Field(..., description="Microsoft Teams Channel ID")
    target_folder_path: str = Field(
        default="Shared Documents/CSV Files",
        description="Target folder path in SharePoint"
    )
    large_file_threshold_mb: int = Field(
        default=4,
        ge=1,
        description="File size threshold for chunked upload (MB)"
    )
    chunk_size_mb: int = Field(
        default=5,
        ge=1,
        le=60,
        description="Chunk size for large file uploads (MB, max 60)"
    )
    max_retries: int = Field(
        default=3,
        ge=1,
        description="Maximum retry attempts for uploads"
    )


class FilterConfig(BaseModel):
    """Message filtering configuration."""
    
    sender_patterns: List[str] = Field(
        default_factory=list,
        description="Email sender patterns to match"
    )
    subject_patterns: List[str] = Field(
        default_factory=list, 
        description="Email subject patterns to match"
    )
    max_age_days: Optional[int] = Field(
        default=7,
        ge=1,
        description="Maximum age of messages to process (days)"
    )
    csv_file_extensions: List[str] = Field(
        default=[".csv", ".CSV"],
        description="File extensions to consider as CSV files"
    )
    min_file_size_bytes: int = Field(
        default=1,
        ge=0,
        description="Minimum file size to process (bytes)"
    )
    max_file_size_mb: int = Field(
        default=100,
        ge=1,
        description="Maximum file size to process (MB)"
    )


class ApplicationSettings(BaseModel):
    """Main application settings."""
    
    auth: AuthConfig
    email: EmailConfig
    sharepoint: SharePointConfig
    filtering: FilterConfig
    
    log_level: str = Field(
        default="INFO",
        description="Logging level"
    )
    temp_directory: Path = Field(
        default=Path("/tmp/email-csv-extractor"),
        description="Temporary directory for file processing"
    )
    
    @field_validator('log_level')
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {valid_levels}")
        return v.upper()
    
    model_config = ConfigDict(
        env_nested_delimiter="__",
        case_sensitive=False
    )


class EnvironmentConfigurationManager:
    """Configuration manager that loads settings from environment variables."""
    
    def __init__(self) -> None:
        self._settings: Optional[ApplicationSettings] = None
        self._load_settings()
    
    def _load_settings(self) -> None:
        """Load and validate settings from environment variables."""
        try:
            auth_config = AuthConfig(
                client_id=os.getenv("AZURE_CLIENT_ID", ""),
                client_secret=os.getenv("AZURE_CLIENT_SECRET", ""),
                tenant_id=os.getenv("AZURE_TENANT_ID", ""),
                authority=os.getenv("AZURE_AUTHORITY", "https://login.microsoftonline.com")
            )
            
            email_config = EmailConfig(
                mailbox_address=os.getenv("EMAIL_MAILBOX_ADDRESS", ""),
                polling_interval_seconds=int(os.getenv("EMAIL_POLLING_INTERVAL", "300")),
                max_messages_per_poll=int(os.getenv("EMAIL_MAX_MESSAGES_PER_POLL", "50"))
            )
            
            sharepoint_config = SharePointConfig(
                team_id=os.getenv("SHAREPOINT_TEAM_ID", ""),
                channel_id=os.getenv("SHAREPOINT_CHANNEL_ID", ""),
                target_folder_path=os.getenv("SHAREPOINT_TARGET_FOLDER", "Shared Documents/CSV Files")
            )
            
            filter_config = FilterConfig(
                sender_patterns=self._parse_list_env_var("FILTER_SENDER_PATTERNS"),
                subject_patterns=self._parse_list_env_var("FILTER_SUBJECT_PATTERNS"),
                max_age_days=self._parse_optional_int_env_var("FILTER_MAX_AGE_DAYS", 7)
            )
            
            self._settings = ApplicationSettings(
                auth=auth_config,
                email=email_config,
                sharepoint=sharepoint_config,
                filtering=filter_config,
                log_level=os.getenv("LOG_LEVEL", "INFO"),
                temp_directory=Path(os.getenv("TEMP_DIRECTORY", "/tmp/email-csv-extractor"))
            )
            
        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration: {str(e)}") from e
    
    def _parse_list_env_var(self, env_var: str) -> List[str]:
        """Parse a comma-separated environment variable into a list."""
        value = os.getenv(env_var, "")
        if not value:
            return []
        return [item.strip() for item in value.split(",") if item.strip()]
    
    def _parse_optional_int_env_var(self, env_var: str, default: int) -> int:
        """Parse an optional integer environment variable."""
        value = os.getenv(env_var)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            return default
    
    def get_auth_config(self) -> Dict[str, Any]:
        """Get authentication configuration."""
        if not self._settings:
            raise ConfigurationError("Settings not loaded")
        return self._settings.auth.model_dump()
    
    def get_email_config(self) -> Dict[str, Any]:
        """Get email polling configuration."""
        if not self._settings:
            raise ConfigurationError("Settings not loaded")
        return self._settings.email.model_dump()
    
    def get_sharepoint_config(self) -> Dict[str, Any]:
        """Get SharePoint upload configuration."""
        if not self._settings:
            raise ConfigurationError("Settings not loaded")
        return self._settings.sharepoint.model_dump()
    
    def get_filter_criteria(self) -> FilterCriteria:
        """Get message filtering criteria."""
        if not self._settings:
            raise ConfigurationError("Settings not loaded")
        
        filter_config = self._settings.filtering
        return FilterCriteria(
            sender_patterns=filter_config.sender_patterns,
            subject_patterns=filter_config.subject_patterns,
            max_age_days=filter_config.max_age_days
        )
    
    @property
    def settings(self) -> ApplicationSettings:
        """Get the loaded application settings."""
        if not self._settings:
            raise ConfigurationError("Settings not loaded")
        return self._settings