"""Main workflow processor that orchestrates the email CSV extraction process."""

import asyncio
from pathlib import Path
from typing import List, Dict, Any
import uuid
from datetime import datetime

from ..core.container import DependencyContainer
from ..core.interfaces import Logger, EmailMessage, CsvAttachment
from ..core.exceptions import EmailCsvExtractorError
from ..auth.ms_graph_auth import MSGraphAuthenticationProvider
from ..email.ms_graph_poller import MSGraphEmailPoller
from ..filtering.message_filter import EmailMessageFilter
from ..download.csv_downloader import MSGraphCsvDownloader
from ..upload.sharepoint_uploader import MSGraphSharePointUploader
from ..config.settings import EnvironmentConfigurationManager


class EmailCsvProcessor:
    """Main processor that orchestrates the email CSV extraction workflow."""
    
    def __init__(self, container: DependencyContainer, logger: Logger) -> None:
        """Initialize the email CSV processor.
        
        Args:
            container: Dependency injection container
            logger: Logger instance for structured logging
        """
        self._container = container
        self._logger = logger
        
        # Get services from container
        self._config_manager = container.get_service(EnvironmentConfigurationManager)
        self._auth_provider = container.get_service(MSGraphAuthenticationProvider)
        self._email_poller = container.get_service(MSGraphEmailPoller)
        self._message_filter = container.get_service(EmailMessageFilter)
        self._csv_downloader = container.get_service(MSGraphCsvDownloader)
        self._sharepoint_uploader = container.get_service(MSGraphSharePointUploader)
        
        # Setup temp directory
        self._temp_dir = self._config_manager.settings.temp_directory
        self._temp_dir.mkdir(parents=True, exist_ok=True)
        
        self._logger.info(
            "Initialized email CSV processor",
            temp_directory=str(self._temp_dir)
        )
    
    async def process_emails_once(self, dry_run: bool = False) -> Dict[str, Any]:
        """Process emails once and return processing statistics.
        
        Args:
            dry_run: If True, don't actually upload files to SharePoint
            
        Returns:
            Dictionary with processing statistics
            
        Raises:
            EmailCsvExtractorError: If processing fails
        """
        stats = {
            "start_time": datetime.utcnow().isoformat(),
            "messages_found": 0,
            "messages_processed": 0,
            "attachments_found": 0,
            "attachments_downloaded": 0,
            "files_uploaded": 0,
            "errors": [],
            "dry_run": dry_run
        }
        
        try:
            self._logger.info(
                "Starting email processing cycle",
                dry_run=dry_run
            )
            
            # Refresh authentication token if needed
            await self._auth_provider.refresh_token_if_needed()
            
            # Get filter criteria
            filter_criteria = self._config_manager.get_filter_criteria()
            
            # Poll for new messages
            self._logger.info("Polling mailbox for new messages")
            messages = await self._email_poller.poll_mailbox_for_new_messages(filter_criteria)
            stats["messages_found"] = len(messages)
            
            if not messages:
                self._logger.info("No new messages found")
                stats["end_time"] = datetime.utcnow().isoformat()
                return stats
            
            self._logger.info(
                "Found messages to process",
                message_count=len(messages)
            )
            
            # Process each message
            for message in messages:
                try:
                    message_stats = await self._process_single_message(message, dry_run)
                    
                    # Update overall stats
                    stats["messages_processed"] += 1
                    stats["attachments_found"] += message_stats["attachments_found"]
                    stats["attachments_downloaded"] += message_stats["attachments_downloaded"]
                    stats["files_uploaded"] += message_stats["files_uploaded"]
                    
                    if message_stats["errors"]:
                        stats["errors"].extend(message_stats["errors"])
                    
                except Exception as e:
                    error_msg = f"Failed to process message {message.id}: {str(e)}"
                    self._logger.error(
                        "Failed to process message",
                        error=str(e),
                        error_type=type(e).__name__,
                        message_id=message.id,
                        message_subject=message.subject
                    )
                    stats["errors"].append(error_msg)
            
            stats["end_time"] = datetime.utcnow().isoformat()
            
            self._logger.info(
                "Completed email processing cycle",
                **{k: v for k, v in stats.items() if k not in ["errors", "start_time", "end_time"]}
            )
            
            return stats
            
        except Exception as e:
            error_msg = f"Email processing cycle failed: {str(e)}"
            self._logger.error(
                "Email processing cycle failed",
                error=str(e),
                error_type=type(e).__name__
            )
            stats["errors"].append(error_msg)
            stats["end_time"] = datetime.utcnow().isoformat()
            raise EmailCsvExtractorError(error_msg) from e
    
    async def _process_single_message(
        self, message: EmailMessage, dry_run: bool
    ) -> Dict[str, Any]:
        """Process a single email message.
        
        Args:
            message: Email message to process
            dry_run: If True, don't upload files
            
        Returns:
            Dictionary with processing statistics for this message
        """
        message_stats = {
            "attachments_found": 0,
            "attachments_downloaded": 0,
            "files_uploaded": 0,
            "errors": []
        }
        
        try:
            self._logger.info(
                "Processing message",
                message_id=message.id,
                sender=message.sender,
                subject=message.subject
            )
            
            # Check if message should be processed
            filter_criteria = self._config_manager.get_filter_criteria()
            if not self._message_filter.should_process_message(message, filter_criteria):
                self._logger.info(
                    "Message skipped by filter",
                    message_id=message.id
                )
                return message_stats
            
            # Get message attachments
            attachments = await self._email_poller.get_message_attachments(message.id)
            message_stats["attachments_found"] = len(attachments)
            
            if not attachments:
                self._logger.info(
                    "No attachments found in message",
                    message_id=message.id
                )
                return message_stats
            
            # Filter for CSV attachments
            csv_attachments = self._message_filter.extract_csv_attachments(attachments)
            
            if not csv_attachments:
                self._logger.info(
                    "No CSV attachments found in message",
                    message_id=message.id,
                    total_attachments=len(attachments)
                )
                return message_stats
            
            # Set current message ID for downloader
            self._csv_downloader.set_current_message_id(message.id)
            
            # Process each CSV attachment
            for attachment in csv_attachments:
                try:
                    await self._process_csv_attachment(
                        attachment, message, dry_run, message_stats
                    )
                except Exception as e:
                    error_msg = f"Failed to process attachment {attachment.name}: {str(e)}"
                    self._logger.error(
                        "Failed to process attachment",
                        error=str(e),
                        error_type=type(e).__name__,
                        attachment_id=attachment.id,
                        attachment_name=attachment.name,
                        message_id=message.id
                    )
                    message_stats["errors"].append(error_msg)
            
            return message_stats
            
        except Exception as e:
            error_msg = f"Failed to process message {message.id}: {str(e)}"
            message_stats["errors"].append(error_msg)
            raise
    
    async def _process_csv_attachment(
        self,
        attachment: CsvAttachment,
        message: EmailMessage,
        dry_run: bool,
        stats: Dict[str, Any]
    ) -> None:
        """Process a single CSV attachment.
        
        Args:
            attachment: CSV attachment to process
            message: Parent email message
            dry_run: If True, don't upload file
            stats: Statistics dictionary to update
        """
        temp_file_path = None
        
        try:
            self._logger.info(
                "Processing CSV attachment",
                attachment_id=attachment.id,
                attachment_name=attachment.name,
                attachment_size=attachment.size,
                message_id=message.id
            )
            
            # Generate unique filename for temp file
            unique_id = str(uuid.uuid4())[:8]
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            safe_filename = self._sanitize_filename(attachment.name)
            temp_filename = f"{timestamp}_{unique_id}_{safe_filename}"
            temp_file_path = self._temp_dir / temp_filename
            
            # Download the CSV attachment
            downloaded_path = await self._csv_downloader.download_csv_attachment(
                attachment, temp_file_path
            )
            stats["attachments_downloaded"] += 1
            
            self._logger.info(
                "Downloaded CSV attachment",
                attachment_name=attachment.name,
                local_path=str(downloaded_path),
                file_size_bytes=downloaded_path.stat().st_size
            )
            
            if not dry_run:
                # Upload to SharePoint
                await self._upload_csv_to_sharepoint(
                    downloaded_path, attachment, message
                )
                stats["files_uploaded"] += 1
                
                self._logger.info(
                    "Uploaded CSV to SharePoint",
                    attachment_name=attachment.name,
                    local_path=str(downloaded_path)
                )
            else:
                self._logger.info(
                    "Dry run: would upload CSV to SharePoint",
                    attachment_name=attachment.name,
                    local_path=str(downloaded_path)
                )
            
        finally:
            # Clean up temp file
            if temp_file_path and temp_file_path.exists():
                try:
                    temp_file_path.unlink()
                    self._logger.debug(
                        "Cleaned up temp file",
                        temp_file_path=str(temp_file_path)
                    )
                except Exception as cleanup_error:
                    self._logger.warning(
                        "Failed to clean up temp file",
                        error=str(cleanup_error),
                        temp_file_path=str(temp_file_path)
                    )
    
    async def _upload_csv_to_sharepoint(
        self,
        file_path: Path,
        attachment: CsvAttachment,
        message: EmailMessage
    ) -> str:
        """Upload a CSV file to SharePoint.
        
        Args:
            file_path: Path to the local CSV file
            attachment: Original attachment information
            message: Parent email message
            
        Returns:
            SharePoint file URL
        """
        config = self._config_manager.settings.sharepoint
        
        # Create a descriptive filename with metadata
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        sender_safe = self._sanitize_filename(message.sender.split('@')[0])
        original_name = Path(attachment.name).stem
        extension = Path(attachment.name).suffix
        
        new_filename = f"{timestamp}_{sender_safe}_{original_name}{extension}"
        
        # Create a temporary file with the new name
        new_file_path = file_path.parent / new_filename
        file_path.rename(new_file_path)
        
        try:
            # Determine target folder (could be enhanced with date-based folders)
            target_folder = config.target_folder_path
            
            # Upload the file
            upload_url = await self._sharepoint_uploader.upload_file_to_sharepoint_folder(
                new_file_path,
                target_folder,
                config.team_id,
                config.channel_id
            )
            
            self._logger.info(
                "Successfully uploaded CSV to SharePoint",
                original_filename=attachment.name,
                new_filename=new_filename,
                upload_url=upload_url,
                sender=message.sender,
                subject=message.subject
            )
            
            return upload_url
            
        finally:
            # Rename back for cleanup
            if new_file_path.exists():
                try:
                    new_file_path.rename(file_path)
                except Exception:
                    pass  # File will be cleaned up by caller
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize a filename for safe filesystem usage.
        
        Args:
            filename: Original filename
            
        Returns:
            Sanitized filename
        """
        # Remove or replace problematic characters
        import re
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
        sanitized = re.sub(r'\s+', '_', sanitized)  # Replace spaces with underscores
        sanitized = sanitized.strip('._-')  # Remove leading/trailing special chars
        
        # Ensure it's not empty
        if not sanitized:
            sanitized = "file"
        
        # Limit length
        if len(sanitized) > 100:
            name_part = Path(sanitized).stem[:80]  # Keep extension
            ext_part = Path(sanitized).suffix[:20]
            sanitized = f"{name_part}{ext_part}"
        
        return sanitized
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform a health check of all system components.
        
        Returns:
            Dictionary with health check results
        """
        health_status = {
            "overall_status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "components": {}
        }
        
        try:
            # Check authentication
            try:
                await self._auth_provider.get_access_token()
                health_status["components"]["authentication"] = {
                    "status": "healthy",
                    "message": "Authentication successful"
                }
            except Exception as e:
                health_status["components"]["authentication"] = {
                    "status": "unhealthy", 
                    "message": f"Authentication failed: {str(e)}"
                }
                health_status["overall_status"] = "unhealthy"
            
            # Check configuration
            try:
                self._config_manager.get_auth_config()
                self._config_manager.get_email_config()
                self._config_manager.get_sharepoint_config()
                health_status["components"]["configuration"] = {
                    "status": "healthy",
                    "message": "Configuration valid"
                }
            except Exception as e:
                health_status["components"]["configuration"] = {
                    "status": "unhealthy",
                    "message": f"Configuration error: {str(e)}"
                }
                health_status["overall_status"] = "unhealthy"
            
            # Check temp directory
            try:
                self._temp_dir.mkdir(parents=True, exist_ok=True)
                test_file = self._temp_dir / "health_check.tmp"
                test_file.write_text("test")
                test_file.unlink()
                health_status["components"]["temp_directory"] = {
                    "status": "healthy",
                    "message": f"Temp directory accessible: {self._temp_dir}"
                }
            except Exception as e:
                health_status["components"]["temp_directory"] = {
                    "status": "unhealthy",
                    "message": f"Temp directory error: {str(e)}"
                }
                health_status["overall_status"] = "unhealthy"
            
            return health_status
            
        except Exception as e:
            health_status["overall_status"] = "unhealthy"
            health_status["error"] = str(e)
            return health_status