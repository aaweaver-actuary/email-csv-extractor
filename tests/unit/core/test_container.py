"""Tests for the dependency injection container."""

import pytest
from unittest.mock import Mock

from email_csv_extractor.core.container import DependencyContainer
from email_csv_extractor.core.interfaces import Logger


class TestDependencyContainer:
    """Test cases for the dependency injection container."""
    
    def test_register_and_get_service(self):
        """Test registering and retrieving a service."""
        container = DependencyContainer()
        
        # Create a mock service
        mock_service = Mock()
        
        # Register the service
        container.register_service(Mock, mock_service)
        
        # Retrieve the service
        retrieved_service = container.get_service(Mock)
        
        assert retrieved_service is mock_service
    
    def test_register_and_get_factory(self):
        """Test registering and using a factory."""
        container = DependencyContainer()
        
        # Create a factory function
        mock_instance = Mock()
        factory = Mock(return_value=mock_instance)
        
        # Register the factory
        container.register_factory(Mock, factory)
        
        # Get service using factory
        retrieved_service = container.get_service(Mock)
        
        assert retrieved_service is mock_instance
        factory.assert_called_once()
        
        # Second call should return the same instance (singleton behavior)
        retrieved_service2 = container.get_service(Mock)
        assert retrieved_service2 is mock_instance
        factory.assert_called_once()  # Factory should only be called once
    
    def test_has_service(self):
        """Test checking if a service is registered."""
        container = DependencyContainer()
        
        # Should not have unregistered service
        assert not container.has_service(Mock)
        
        # Register service
        container.register_service(Mock, Mock())
        
        # Should have registered service
        assert container.has_service(Mock)
    
    def test_has_factory(self):
        """Test checking if a factory is registered."""
        container = DependencyContainer()
        
        # Should not have unregistered factory
        assert not container.has_service(Mock)
        
        # Register factory
        container.register_factory(Mock, Mock)
        
        # Should have registered factory
        assert container.has_service(Mock)
    
    def test_service_not_found(self):
        """Test retrieving a non-existent service raises error."""
        container = DependencyContainer()
        
        with pytest.raises(ValueError, match="No service registered for interface"):
            container.get_service(Mock)
    
    def test_default_logger_service(self):
        """Test that default logger service is registered."""
        container = DependencyContainer()
        
        # Should have default logger
        assert container.has_service(Logger)
        
        # Should be able to get logger
        logger = container.get_service(Logger)
        assert logger is not None
    
    def test_convenience_methods(self):
        """Test convenience methods for getting services."""
        container = DependencyContainer()
        
        # Mock services
        from email_csv_extractor.core.interfaces import (
            AuthenticationProvider, EmailPoller, MessageFilter,
            AttachmentDownloader, SharePointUploader, ConfigurationManager
        )
        
        mock_auth = Mock()
        mock_poller = Mock()
        mock_filter = Mock()
        mock_downloader = Mock()
        mock_uploader = Mock()
        mock_config = Mock()
        
        # Register services
        container.register_service(AuthenticationProvider, mock_auth)
        container.register_service(EmailPoller, mock_poller)
        container.register_service(MessageFilter, mock_filter)
        container.register_service(AttachmentDownloader, mock_downloader)
        container.register_service(SharePointUploader, mock_uploader)
        container.register_service(ConfigurationManager, mock_config)
        
        # Test convenience methods
        assert container.get_authentication_provider() is mock_auth
        assert container.get_email_poller() is mock_poller
        assert container.get_message_filter() is mock_filter
        assert container.get_attachment_downloader() is mock_downloader
        assert container.get_sharepoint_uploader() is mock_uploader
        assert container.get_configuration_manager() is mock_config
        assert container.get_logger() is not None