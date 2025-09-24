"""Dependency injection container for modular architecture."""

from typing import Any, Dict, Type, TypeVar, Generic, Callable
import structlog

from .interfaces import (
    AuthenticationProvider,
    EmailPoller,
    MessageFilter,
    AttachmentDownloader,
    SharePointUploader,
    ConfigurationManager,
    Logger,
)

T = TypeVar('T')


class DependencyContainer:
    """Simple dependency injection container following SOLID principles."""
    
    def __init__(self) -> None:
        self._services: Dict[Type[Any], Any] = {}
        self._factories: Dict[Type[Any], Callable[[], Any]] = {}
        self._setup_default_services()
    
    def register_service(self, interface: Type[T], implementation: T) -> None:
        """Register a service implementation for an interface."""
        self._services[interface] = implementation
    
    def register_factory(self, interface: Type[T], factory: Callable[[], T]) -> None:
        """Register a factory function for creating service instances."""
        self._factories[interface] = factory
    
    def get_service(self, interface: Type[T]) -> T:
        """Get a service instance by interface type."""
        if interface in self._services:
            return self._services[interface]
        
        if interface in self._factories:
            instance = self._factories[interface]()
            self._services[interface] = instance
            return instance
        
        raise ValueError(f"No service registered for interface: {interface}")
    
    def has_service(self, interface: Type[T]) -> bool:
        """Check if a service is registered for the given interface."""
        return interface in self._services or interface in self._factories
    
    def _setup_default_services(self) -> None:
        """Set up default services that don't require external dependencies."""
        # Register default logger
        default_logger = structlog.get_logger()
        self._services[Logger] = default_logger
    
    def get_authentication_provider(self) -> AuthenticationProvider:
        """Get the authentication provider service."""
        return self.get_service(AuthenticationProvider)
    
    def get_email_poller(self) -> EmailPoller:
        """Get the email poller service."""
        return self.get_service(EmailPoller)
    
    def get_message_filter(self) -> MessageFilter:
        """Get the message filter service."""
        return self.get_service(MessageFilter)
    
    def get_attachment_downloader(self) -> AttachmentDownloader:
        """Get the attachment downloader service."""
        return self.get_service(AttachmentDownloader)
    
    def get_sharepoint_uploader(self) -> SharePointUploader:
        """Get the SharePoint uploader service."""
        return self.get_service(SharePointUploader)
    
    def get_configuration_manager(self) -> ConfigurationManager:
        """Get the configuration manager service."""
        return self.get_service(ConfigurationManager)
    
    def get_logger(self) -> Logger:
        """Get the logger service."""
        return self.get_service(Logger)