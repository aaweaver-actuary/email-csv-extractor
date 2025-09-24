"""Command-line interface for the email CSV extractor."""

import asyncio
import signal
import sys
from pathlib import Path
from typing import Optional
import click
import structlog

from .core.container import DependencyContainer
from .core.exceptions import EmailCsvExtractorError, ConfigurationError
from .config.settings import EnvironmentConfigurationManager
from .auth.ms_graph_auth import MSGraphAuthenticationProvider
from .email.ms_graph_poller import MSGraphEmailPoller
from .filtering.message_filter import EmailMessageFilter
from .download.csv_downloader import MSGraphCsvDownloader
from .upload.sharepoint_uploader import MSGraphSharePointUploader
from .workflow.processor import EmailCsvProcessor


def setup_logging(log_level: str) -> structlog.stdlib.BoundLogger:
    """Set up structured logging.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        
    Returns:
        Configured logger
    """
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Set log level
    import logging
    logging.basicConfig(level=getattr(logging, log_level.upper()))
    
    return structlog.get_logger("email-csv-extractor")


def setup_dependency_container(config_manager: EnvironmentConfigurationManager) -> DependencyContainer:
    """Set up the dependency injection container with all services.
    
    Args:
        config_manager: Configuration manager instance
        
    Returns:
        Configured dependency container
    """
    container = DependencyContainer()
    
    # Register configuration manager
    container.register_service(EnvironmentConfigurationManager, config_manager)
    
    # Register logger
    logger = setup_logging(config_manager.settings.log_level)
    container.register_service(structlog.stdlib.BoundLogger, logger)
    
    # Register authentication provider
    auth_config = config_manager.get_auth_config()
    auth_provider = MSGraphAuthenticationProvider(auth_config, logger)
    container.register_service(MSGraphAuthenticationProvider, auth_provider)
    
    # Register email poller
    email_config = config_manager.get_email_config()
    email_poller = MSGraphEmailPoller(auth_provider, email_config, logger)
    container.register_service(MSGraphEmailPoller, email_poller)
    
    # Register message filter
    filter_config = config_manager.settings.filtering.model_dump()
    message_filter = EmailMessageFilter(filter_config, logger)
    container.register_service(EmailMessageFilter, message_filter)
    
    # Register CSV downloader
    csv_downloader = MSGraphCsvDownloader(auth_provider, email_config, logger)
    container.register_service(MSGraphCsvDownloader, csv_downloader)
    
    # Register SharePoint uploader
    sharepoint_config = config_manager.get_sharepoint_config()
    sharepoint_uploader = MSGraphSharePointUploader(auth_provider, sharepoint_config, logger)
    container.register_service(MSGraphSharePointUploader, sharepoint_uploader)
    
    return container


class GracefulShutdown:
    """Handle graceful shutdown on SIGINT/SIGTERM."""
    
    def __init__(self) -> None:
        self.shutdown = False
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum: int, frame) -> None:
        """Handle shutdown signals."""
        print(f"\nReceived signal {signum}, initiating graceful shutdown...")
        self.shutdown = True


@click.group()
@click.version_option()
def cli() -> None:
    """Email CSV Extractor - Auto CSV log file ingestion from email to Microsoft Teams."""
    pass


@cli.command()
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Run in dry-run mode without uploading files"
)
@click.option(
    "--once",
    is_flag=True,
    default=False,
    help="Run once instead of continuous polling"
)
def run(dry_run: bool, once: bool) -> None:
    """Run the email CSV extractor."""
    asyncio.run(_run_async(dry_run, once))


async def _run_async(dry_run: bool, once: bool) -> None:
    """Async implementation of the run command."""
    logger = None
    
    try:
        # Load configuration
        config_manager = EnvironmentConfigurationManager()
        
        # Setup logging
        logger = setup_logging(config_manager.settings.log_level)
        
        logger.info(
            "Starting Email CSV Extractor",
            dry_run=dry_run,
            run_once=once,
            log_level=config_manager.settings.log_level
        )
        
        # Setup dependency container
        container = setup_dependency_container(config_manager)
        
        # Create processor
        processor = EmailCsvProcessor(container, logger)
        
        # Setup graceful shutdown
        shutdown_handler = GracefulShutdown()
        
        if once:
            # Run once
            await processor.process_emails_once(dry_run=dry_run)
            logger.info("Single processing run completed")
        else:
            # Continuous polling
            polling_interval = config_manager.settings.email.polling_interval_seconds
            logger.info(
                "Starting continuous polling",
                polling_interval_seconds=polling_interval
            )
            
            while not shutdown_handler.shutdown:
                try:
                    await processor.process_emails_once(dry_run=dry_run)
                    
                    # Wait for next poll or shutdown
                    for _ in range(polling_interval):
                        if shutdown_handler.shutdown:
                            break
                        await asyncio.sleep(1)
                        
                except Exception as e:
                    logger.error(
                        "Error during email processing cycle",
                        error=str(e),
                        error_type=type(e).__name__
                    )
                    # Wait a bit before retrying
                    await asyncio.sleep(30)
            
            logger.info("Graceful shutdown completed")
            
    except ConfigurationError as e:
        if logger:
            logger.error("Configuration error", error=str(e))
        else:
            print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)
        
    except Exception as e:
        if logger:
            logger.error(
                "Unexpected error",
                error=str(e),
                error_type=type(e).__name__
            )
        else:
            print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


@cli.command()
def test_auth() -> None:
    """Test authentication with MS Graph API."""
    asyncio.run(_test_auth_async())


async def _test_auth_async() -> None:
    """Async implementation of auth test."""
    try:
        config_manager = EnvironmentConfigurationManager()
        logger = setup_logging(config_manager.settings.log_level)
        
        logger.info("Testing MS Graph authentication")
        
        auth_config = config_manager.get_auth_config()
        auth_provider = MSGraphAuthenticationProvider(auth_config, logger)
        
        # Test token acquisition
        token = await auth_provider.get_access_token()
        logger.info("Authentication successful", token_length=len(token))
        
        # Get token info
        token_info = auth_provider.get_token_info()
        logger.info("Token information", **token_info)
        
        print("✅ Authentication test successful!")
        
    except Exception as e:
        print(f"❌ Authentication test failed: {e}", file=sys.stderr)
        sys.exit(1)


@cli.command()
@click.option(
    "--max-messages",
    type=int,
    default=5,
    help="Maximum number of messages to test"
)
def test_email() -> None:
    """Test email polling functionality."""
    asyncio.run(_test_email_async())


async def _test_email_async() -> None:
    """Async implementation of email test."""
    try:
        config_manager = EnvironmentConfigurationManager()
        logger = setup_logging(config_manager.settings.log_level)
        
        logger.info("Testing email polling")
        
        # Setup auth
        auth_config = config_manager.get_auth_config()
        auth_provider = MSGraphAuthenticationProvider(auth_config, logger)
        
        # Setup email poller
        email_config = config_manager.get_email_config()
        email_poller = MSGraphEmailPoller(auth_provider, email_config, logger)
        
        # Test polling
        filter_criteria = config_manager.get_filter_criteria()
        messages = await email_poller.poll_mailbox_for_new_messages(filter_criteria)
        
        logger.info("Email polling successful", message_count=len(messages))
        
        for i, message in enumerate(messages[:5]):  # Show first 5
            print(f"Message {i+1}:")
            print(f"  ID: {message.id}")
            print(f"  From: {message.sender}")
            print(f"  Subject: {message.subject}")
            print(f"  Has Attachments: {message.has_attachments}")
            print()
        
        print(f"✅ Email polling test successful! Found {len(messages)} messages")
        
    except Exception as e:
        print(f"❌ Email polling test failed: {e}", file=sys.stderr)
        sys.exit(1)


@cli.command()
def validate_config() -> None:
    """Validate configuration settings."""
    try:
        config_manager = EnvironmentConfigurationManager()
        logger = setup_logging(config_manager.settings.log_level)
        
        logger.info("Validating configuration")
        
        # Print configuration summary (without secrets)
        settings = config_manager.settings
        
        print("✅ Configuration validation successful!")
        print()
        print("Configuration Summary:")
        print(f"  Email Address: {settings.email.mailbox_address}")
        print(f"  Polling Interval: {settings.email.polling_interval_seconds}s")
        print(f"  Team ID: {settings.sharepoint.team_id}")
        print(f"  Channel ID: {settings.sharepoint.channel_id}")
        print(f"  Target Folder: {settings.sharepoint.target_folder_path}")
        print(f"  Log Level: {settings.log_level}")
        print(f"  Temp Directory: {settings.temp_directory}")
        
        filter_criteria = config_manager.get_filter_criteria()
        print(f"  Sender Patterns: {filter_criteria.sender_patterns}")
        print(f"  Subject Patterns: {filter_criteria.subject_patterns}")
        print(f"  Max Age Days: {filter_criteria.max_age_days}")
        
    except Exception as e:
        print(f"❌ Configuration validation failed: {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()