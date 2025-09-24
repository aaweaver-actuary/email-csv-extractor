"""Pytest configuration and fixtures for the email CSV extractor tests."""

import pytest
import asyncio
from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import Mock, AsyncMock
import tempfile
import shutil

from email_csv_extractor.core.interfaces import (
    EmailMessage, CsvAttachment, FilterCriteria, Logger
)
from email_csv_extractor.config.settings import (
    AuthConfig, EmailConfig, SharePointConfig, FilterConfig, ApplicationSettings
)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_logger():
    """Create a mock logger for testing."""
    logger = Mock(spec=Logger)
    logger.info = Mock()
    logger.error = Mock()
    logger.debug = Mock()
    logger.warning = Mock()
    return logger


@pytest.fixture
def sample_email_message():
    """Create a sample email message for testing."""
    return EmailMessage(
        id="test-message-id",
        sender="test@example.com",
        subject="Test CSV Report",
        received_datetime="2024-01-01T12:00:00Z",
        has_attachments=True,
        body_preview="This is a test email with CSV attachment"
    )


@pytest.fixture
def sample_csv_attachment():
    """Create a sample CSV attachment for testing."""
    return CsvAttachment(
        id="test-attachment-id",
        name="test_report.csv",
        size=1024,
        content_type="text/csv"
    )


@pytest.fixture
def sample_filter_criteria():
    """Create sample filter criteria for testing."""
    return FilterCriteria(
        sender_patterns=["test@example.com", "report@company.com"],
        subject_patterns=["report", "csv"],
        max_age_days=7
    )


@pytest.fixture
def temp_directory():
    """Create a temporary directory for testing."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_csv_content():
    """Create sample CSV content for testing."""
    return """Name,Age,City
John Doe,30,New York
Jane Smith,25,Los Angeles
Bob Johnson,35,Chicago"""


@pytest.fixture
def sample_csv_file(temp_directory, sample_csv_content):
    """Create a sample CSV file for testing."""
    csv_file = temp_directory / "test.csv"
    csv_file.write_text(sample_csv_content)
    return csv_file


@pytest.fixture
def auth_config():
    """Create sample auth configuration."""
    return AuthConfig(
        client_id="test-client-id",
        client_secret="test-client-secret",
        tenant_id="test-tenant-id"
    )


@pytest.fixture
def email_config():
    """Create sample email configuration."""
    return EmailConfig(
        mailbox_address="test@example.com",
        polling_interval_seconds=300,
        max_messages_per_poll=50
    )


@pytest.fixture
def sharepoint_config():
    """Create sample SharePoint configuration."""
    return SharePointConfig(
        team_id="test-team-id",
        channel_id="test-channel-id",
        target_folder_path="Shared Documents/CSV Files"
    )


@pytest.fixture
def filter_config():
    """Create sample filter configuration."""
    return FilterConfig(
        sender_patterns=["test@example.com"],
        subject_patterns=["report"],
        max_age_days=7
    )


@pytest.fixture
def application_settings(auth_config, email_config, sharepoint_config, filter_config, temp_directory):
    """Create sample application settings."""
    return ApplicationSettings(
        auth=auth_config,
        email=email_config,
        sharepoint=sharepoint_config,
        filtering=filter_config,
        temp_directory=temp_directory
    )


@pytest.fixture
def mock_auth_provider():
    """Create a mock authentication provider."""
    provider = AsyncMock()
    provider.get_access_token.return_value = "mock-access-token"
    provider.refresh_token_if_needed.return_value = None
    provider.get_token_info.return_value = {
        "has_token": True,
        "is_valid": True,
        "client_id": "test-client-id"
    }
    return provider


@pytest.fixture
def mock_email_poller():
    """Create a mock email poller."""
    poller = AsyncMock()
    poller.poll_mailbox_for_new_messages.return_value = []
    poller.get_message_attachments.return_value = []
    return poller


@pytest.fixture
def mock_message_filter():
    """Create a mock message filter."""
    filter_mock = Mock()
    filter_mock.should_process_message.return_value = True
    filter_mock.extract_csv_attachments.return_value = []
    return filter_mock


@pytest.fixture
def mock_csv_downloader():
    """Create a mock CSV downloader."""
    downloader = AsyncMock()
    downloader.download_csv_attachment.return_value = Path("/tmp/test.csv")
    downloader.validate_csv_content.return_value = True
    downloader.set_current_message_id.return_value = None
    return downloader


@pytest.fixture
def mock_sharepoint_uploader():
    """Create a mock SharePoint uploader."""
    uploader = AsyncMock()
    uploader.upload_file_to_sharepoint_folder.return_value = "https://sharepoint.com/test.csv"
    uploader.upload_large_file_to_sharepoint_folder.return_value = "https://sharepoint.com/test.csv"
    return uploader


@pytest.fixture
def mock_aiohttp_session():
    """Create a mock aiohttp session for testing."""
    session = AsyncMock()
    response = AsyncMock()
    response.status = 200
    response.json.return_value = {"value": []}
    response.text.return_value = "OK"
    response.read.return_value = b"test,data\n1,2"
    
    session.get.return_value.__aenter__.return_value = response
    session.post.return_value.__aenter__.return_value = response
    session.put.return_value.__aenter__.return_value = response
    
    return session


class MockMSALApp:
    """Mock MSAL confidential client application."""
    
    def __init__(self, client_id, client_credential, authority):
        self.client_id = client_id
        self.client_credential = client_credential
        self.authority = authority
    
    def acquire_token_for_client(self, scopes):
        """Mock token acquisition."""
        return {
            "access_token": "mock-access-token",
            "expires_in": 3600,
            "token_type": "Bearer"
        }


@pytest.fixture
def mock_msal_app():
    """Create a mock MSAL application."""
    return MockMSALApp(
        client_id="test-client-id",
        client_credential="test-client-secret",
        authority="https://login.microsoftonline.com/test-tenant-id"
    )