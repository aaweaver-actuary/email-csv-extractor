"""Tests for configuration settings."""

import pytest
import os
from pathlib import Path
from unittest.mock import patch, Mock
from pydantic import ValidationError

from email_csv_extractor.config.settings import (
    AuthConfig, EmailConfig, SharePointConfig, FilterConfig,
    ApplicationSettings, EnvironmentConfigurationManager
)
from email_csv_extractor.core.exceptions import ConfigurationError


class TestAuthConfig:
    """Test cases for AuthConfig."""
    
    def test_valid_auth_config(self):
        """Test creating valid auth configuration."""
        config = AuthConfig(
            client_id="test-client-id",
            client_secret="test-client-secret",
            tenant_id="test-tenant-id"
        )
        
        assert config.client_id == "test-client-id"
        assert config.client_secret == "test-client-secret"
        assert config.tenant_id == "test-tenant-id"
        assert config.authority == "https://login.microsoftonline.com"
        assert config.scopes == ["https://graph.microsoft.com/.default"]
    
    def test_auth_config_validation_empty_fields(self):
        """Test auth config validation with empty fields."""
        with pytest.raises(ValidationError):
            AuthConfig(
                client_id="",
                client_secret="test-secret",
                tenant_id="test-tenant"
            )
        
        with pytest.raises(ValidationError):
            AuthConfig(
                client_id="test-client",
                client_secret="",
                tenant_id="test-tenant"
            )
        
        with pytest.raises(ValidationError):
            AuthConfig(
                client_id="test-client",
                client_secret="test-secret",
                tenant_id=""
            )
    
    def test_auth_config_strips_whitespace(self):
        """Test that auth config strips whitespace."""
        config = AuthConfig(
            client_id="  test-client-id  ",
            client_secret="  test-client-secret  ",
            tenant_id="  test-tenant-id  "
        )
        
        assert config.client_id == "test-client-id"
        assert config.client_secret == "test-client-secret"
        assert config.tenant_id == "test-tenant-id"


class TestEmailConfig:
    """Test cases for EmailConfig."""
    
    def test_valid_email_config(self):
        """Test creating valid email configuration."""
        config = EmailConfig(
            mailbox_address="test@example.com",
            polling_interval_seconds=300,
            max_messages_per_poll=50
        )
        
        assert config.mailbox_address == "test@example.com"
        assert config.polling_interval_seconds == 300
        assert config.max_messages_per_poll == 50
        assert config.processed_messages_tracking_enabled is True
    
    def test_email_config_defaults(self):
        """Test email config with default values."""
        config = EmailConfig(mailbox_address="test@example.com")
        
        assert config.polling_interval_seconds == 300
        assert config.max_messages_per_poll == 50
        assert config.processed_messages_tracking_enabled is True
    
    def test_email_config_validation(self):
        """Test email config validation."""
        # Test minimum polling interval
        with pytest.raises(ValidationError):
            EmailConfig(
                mailbox_address="test@example.com",
                polling_interval_seconds=30  # Less than minimum 60
            )
        
        # Test maximum messages per poll
        with pytest.raises(ValidationError):
            EmailConfig(
                mailbox_address="test@example.com",
                max_messages_per_poll=1001  # More than maximum 1000
            )


class TestSharePointConfig:
    """Test cases for SharePointConfig."""
    
    def test_valid_sharepoint_config(self):
        """Test creating valid SharePoint configuration."""
        config = SharePointConfig(
            team_id="test-team-id",
            channel_id="test-channel-id"
        )
        
        assert config.team_id == "test-team-id"
        assert config.channel_id == "test-channel-id"
        assert config.target_folder_path == "Shared Documents/CSV Files"
        assert config.large_file_threshold_mb == 4
        assert config.chunk_size_mb == 5


class TestFilterConfig:
    """Test cases for FilterConfig."""
    
    def test_valid_filter_config(self):
        """Test creating valid filter configuration."""
        config = FilterConfig(
            sender_patterns=["test@example.com"],
            subject_patterns=["report"],
            max_age_days=5
        )
        
        assert config.sender_patterns == ["test@example.com"]
        assert config.subject_patterns == ["report"]
        assert config.max_age_days == 5
    
    def test_filter_config_defaults(self):
        """Test filter config with default values."""
        config = FilterConfig()
        
        assert config.sender_patterns == []
        assert config.subject_patterns == []
        assert config.max_age_days == 7
        assert config.csv_file_extensions == [".csv", ".CSV"]


class TestApplicationSettings:
    """Test cases for ApplicationSettings."""
    
    def test_valid_application_settings(self, auth_config, email_config, sharepoint_config, filter_config):
        """Test creating valid application settings."""
        settings = ApplicationSettings(
            auth=auth_config,
            email=email_config,
            sharepoint=sharepoint_config,
            filtering=filter_config
        )
        
        assert settings.auth == auth_config
        assert settings.email == email_config
        assert settings.sharepoint == sharepoint_config
        assert settings.filtering == filter_config
        assert settings.log_level == "INFO"
    
    def test_log_level_validation(self, auth_config, email_config, sharepoint_config, filter_config):
        """Test log level validation."""
        # Valid log level
        settings = ApplicationSettings(
            auth=auth_config,
            email=email_config,
            sharepoint=sharepoint_config,
            filtering=filter_config,
            log_level="DEBUG"
        )
        assert settings.log_level == "DEBUG"
        
        # Invalid log level
        with pytest.raises(ValidationError):
            ApplicationSettings(
                auth=auth_config,
                email=email_config,
                sharepoint=sharepoint_config,
                filtering=filter_config,
                log_level="INVALID"
            )


class TestEnvironmentConfigurationManager:
    """Test cases for EnvironmentConfigurationManager."""
    
    @patch.dict(os.environ, {
        "AZURE_CLIENT_ID": "test-client-id",
        "AZURE_CLIENT_SECRET": "test-client-secret",
        "AZURE_TENANT_ID": "test-tenant-id",
        "EMAIL_MAILBOX_ADDRESS": "test@example.com",
        "SHAREPOINT_TEAM_ID": "test-team-id",
        "SHAREPOINT_CHANNEL_ID": "test-channel-id",
        "FILTER_SENDER_PATTERNS": "test@example.com,report@company.com",
        "FILTER_SUBJECT_PATTERNS": "report,csv"
    })
    def test_load_from_environment(self):
        """Test loading configuration from environment variables."""
        config_manager = EnvironmentConfigurationManager()
        
        # Test auth config
        auth_config = config_manager.get_auth_config()
        assert auth_config["client_id"] == "test-client-id"
        assert auth_config["client_secret"] == "test-client-secret"
        assert auth_config["tenant_id"] == "test-tenant-id"
        
        # Test email config
        email_config = config_manager.get_email_config()
        assert email_config["mailbox_address"] == "test@example.com"
        
        # Test SharePoint config
        sharepoint_config = config_manager.get_sharepoint_config()
        assert sharepoint_config["team_id"] == "test-team-id"
        assert sharepoint_config["channel_id"] == "test-channel-id"
        
        # Test filter criteria
        filter_criteria = config_manager.get_filter_criteria()
        assert "test@example.com" in filter_criteria.sender_patterns
        assert "report@company.com" in filter_criteria.sender_patterns
        assert "report" in filter_criteria.subject_patterns
        assert "csv" in filter_criteria.subject_patterns
    
    def test_missing_required_config(self):
        """Test handling of missing required configuration."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ConfigurationError):
                EnvironmentConfigurationManager()
    
    def test_parse_list_env_var(self):
        """Test parsing comma-separated environment variables."""
        config_manager = EnvironmentConfigurationManager.__new__(EnvironmentConfigurationManager)
        
        # Test with comma-separated values
        with patch.dict(os.environ, {"TEST_LIST": "a,b,c"}):
            result = config_manager._parse_list_env_var("TEST_LIST")
            assert result == ["a", "b", "c"]
        
        # Test with empty value
        with patch.dict(os.environ, {"TEST_LIST": ""}):
            result = config_manager._parse_list_env_var("TEST_LIST")
            assert result == []
        
        # Test with missing env var
        result = config_manager._parse_list_env_var("MISSING_VAR")
        assert result == []
    
    def test_parse_optional_int_env_var(self):
        """Test parsing optional integer environment variables."""
        config_manager = EnvironmentConfigurationManager.__new__(EnvironmentConfigurationManager)
        
        # Test with valid integer
        with patch.dict(os.environ, {"TEST_INT": "42"}):
            result = config_manager._parse_optional_int_env_var("TEST_INT", 10)
            assert result == 42
        
        # Test with invalid integer (should return default)
        with patch.dict(os.environ, {"TEST_INT": "invalid"}):
            result = config_manager._parse_optional_int_env_var("TEST_INT", 10)
            assert result == 10
        
        # Test with missing env var (should return default)
        result = config_manager._parse_optional_int_env_var("MISSING_INT", 10)
        assert result == 10
    
    def test_configuration_error_handling(self):
        """Test configuration error handling."""
        # Mock the init method to raise an exception during loading
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(EnvironmentConfigurationManager, '__init__', side_effect=ConfigurationError("Test error")):
                with pytest.raises(ConfigurationError, match="Test error"):
                    EnvironmentConfigurationManager()
    
    @patch.dict(os.environ, {
        "AZURE_CLIENT_ID": "test-client-id",
        "AZURE_CLIENT_SECRET": "test-client-secret", 
        "AZURE_TENANT_ID": "test-tenant-id",
        "EMAIL_MAILBOX_ADDRESS": "test@example.com",
        "SHAREPOINT_TEAM_ID": "test-team-id",
        "SHAREPOINT_CHANNEL_ID": "test-channel-id"
    })
    def test_settings_property(self):
        """Test accessing settings property."""
        config_manager = EnvironmentConfigurationManager()
        settings = config_manager.settings
        
        assert isinstance(settings, ApplicationSettings)
        assert settings.auth.client_id == "test-client-id"
        assert settings.email.mailbox_address == "test@example.com"
    
    def test_settings_not_loaded_error(self):
        """Test error when settings are not loaded."""
        config_manager = EnvironmentConfigurationManager.__new__(EnvironmentConfigurationManager)
        config_manager._settings = None
        
        with pytest.raises(ConfigurationError, match="Settings not loaded"):
            config_manager.get_auth_config()
        
        with pytest.raises(ConfigurationError, match="Settings not loaded"):
            config_manager.settings