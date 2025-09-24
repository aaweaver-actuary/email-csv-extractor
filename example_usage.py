#!/usr/bin/env python3
"""
Example usage of the Email CSV Extractor system.

This script demonstrates how to use the email CSV extractor programmatically.
For production use, it's recommended to use the CLI interface instead.
"""

import asyncio
import os
from pathlib import Path
import structlog

# Set up basic environment for demo (normally these would be in .env file)
demo_env = {
    "AZURE_CLIENT_ID": "demo-client-id-replace-with-real",
    "AZURE_CLIENT_SECRET": "demo-client-secret-replace-with-real", 
    "AZURE_TENANT_ID": "demo-tenant-id-replace-with-real",
    "EMAIL_MAILBOX_ADDRESS": "reports@yourcompany.com",
    "SHAREPOINT_TEAM_ID": "demo-team-id-replace-with-real",
    "SHAREPOINT_CHANNEL_ID": "demo-channel-id-replace-with-real",
    "FILTER_SENDER_PATTERNS": "reports@company.com,automation@partner.com",
    "FILTER_SUBJECT_PATTERNS": "daily report,csv export",
    "LOG_LEVEL": "INFO"
}

# Apply demo environment (only if not already set)
for key, value in demo_env.items():
    if key not in os.environ:
        os.environ[key] = value

# Now import the system components
from email_csv_extractor.config.settings import EnvironmentConfigurationManager
from email_csv_extractor.core.container import DependencyContainer
from email_csv_extractor.auth.ms_graph_auth import MSGraphAuthenticationProvider
from email_csv_extractor.email.ms_graph_poller import MSGraphEmailPoller
from email_csv_extractor.filtering.message_filter import EmailMessageFilter
from email_csv_extractor.download.csv_downloader import MSGraphCsvDownloader
from email_csv_extractor.upload.sharepoint_uploader import MSGraphSharePointUploader
from email_csv_extractor.workflow.processor import EmailCsvProcessor


def setup_logging(log_level: str = "INFO") -> structlog.stdlib.BoundLogger:
    """Set up structured logging for the demo."""
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
    
    import logging
    logging.basicConfig(level=getattr(logging, log_level.upper()))
    
    return structlog.get_logger("email-csv-extractor-demo")


def setup_dependency_container(config_manager: EnvironmentConfigurationManager) -> DependencyContainer:
    """Set up the dependency injection container with all services."""
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


async def demo_health_check():
    """Demonstrate the health check functionality."""
    print("🔍 Running Health Check Demo")
    print("=" * 50)
    
    try:
        # Load configuration
        config_manager = EnvironmentConfigurationManager()
        
        # Setup container and processor
        container = setup_dependency_container(config_manager)
        logger = container.get_service(structlog.stdlib.BoundLogger)
        processor = EmailCsvProcessor(container, logger)
        
        # Run health check
        health_status = await processor.health_check()
        
        print(f"Overall Status: {health_status['overall_status']}")
        print(f"Timestamp: {health_status['timestamp']}")
        print("\nComponent Status:")
        
        for component, status in health_status['components'].items():
            status_icon = "✅" if status['status'] == 'healthy' else "❌"
            print(f"  {status_icon} {component}: {status['message']}")
        
        if health_status['overall_status'] == 'healthy':
            print("\n🎉 System is healthy and ready for operation!")
        else:
            print("\n⚠️  System has health issues that need attention.")
            
    except Exception as e:
        print(f"❌ Health check failed: {e}")


async def demo_dry_run():
    """Demonstrate a dry-run of the email processing."""
    print("\n🧪 Running Dry-Run Demo")
    print("=" * 50)
    
    try:
        # Load configuration
        config_manager = EnvironmentConfigurationManager()
        
        # Setup container and processor
        container = setup_dependency_container(config_manager)
        logger = container.get_service(structlog.stdlib.BoundLogger)
        processor = EmailCsvProcessor(container, logger)
        
        print("📧 Processing emails (dry-run mode)...")
        
        # Run single processing cycle in dry-run mode
        stats = await processor.process_emails_once(dry_run=True)
        
        print(f"\n📊 Processing Statistics:")
        print(f"  Messages found: {stats['messages_found']}")
        print(f"  Messages processed: {stats['messages_processed']}")
        print(f"  Attachments found: {stats['attachments_found']}")
        print(f"  Attachments downloaded: {stats['attachments_downloaded']}")
        print(f"  Files that would be uploaded: {stats['files_uploaded']}")
        
        if stats['errors']:
            print(f"  Errors encountered: {len(stats['errors'])}")
            for error in stats['errors']:
                print(f"    - {error}")
        
        print(f"\n⏱️  Processing time: {stats.get('start_time')} -> {stats.get('end_time')}")
        
        if stats['messages_found'] == 0:
            print("\n💡 No messages found. This could be because:")
            print("  - No new emails match the filter criteria")
            print("  - Authentication credentials are not valid")
            print("  - Mailbox address is incorrect")
            print("  - Filter patterns are too restrictive")
        
    except Exception as e:
        print(f"❌ Dry-run failed: {e}")
        print("💡 This is expected if you haven't set up real Azure credentials.")


def show_configuration_summary():
    """Show a summary of the current configuration."""
    print("\n⚙️  Configuration Summary")
    print("=" * 50)
    
    try:
        config_manager = EnvironmentConfigurationManager()
        settings = config_manager.settings
        
        print(f"📧 Email Configuration:")
        print(f"  Mailbox: {settings.email.mailbox_address}")
        print(f"  Polling interval: {settings.email.polling_interval_seconds}s")
        print(f"  Max messages per poll: {settings.email.max_messages_per_poll}")
        
        print(f"\n📁 SharePoint Configuration:")
        print(f"  Team ID: {settings.sharepoint.team_id}")
        print(f"  Channel ID: {settings.sharepoint.channel_id}")
        print(f"  Target folder: {settings.sharepoint.target_folder_path}")
        
        print(f"\n🔍 Filter Configuration:")
        filter_criteria = config_manager.get_filter_criteria()
        print(f"  Sender patterns: {filter_criteria.sender_patterns}")
        print(f"  Subject patterns: {filter_criteria.subject_patterns}")
        print(f"  Max age: {filter_criteria.max_age_days} days")
        
        print(f"\n🔧 System Configuration:")
        print(f"  Log level: {settings.log_level}")
        print(f"  Temp directory: {settings.temp_directory}")
        
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        print("💡 Make sure all required environment variables are set.")


async def main():
    """Main demo function."""
    print("🚀 Email CSV Extractor - Demo")
    print("=" * 50)
    print("This demo shows the capabilities of the email CSV extractor system.")
    print("For production use, configure real Azure AD credentials and use the CLI.\n")
    
    # Show configuration
    show_configuration_summary()
    
    # Run health check
    await demo_health_check()
    
    # Run dry-run demo
    await demo_dry_run()
    
    print("\n" + "=" * 50)
    print("📚 Next Steps:")
    print("1. Set up Azure AD app registration")
    print("2. Configure real credentials in .env file")
    print("3. Use CLI: email-csv-extractor run")
    print("4. Monitor logs for processing status")
    print("5. Connect PowerBI to SharePoint folder")
    print("\n🔗 For more info, see README.md")


if __name__ == "__main__":
    asyncio.run(main())