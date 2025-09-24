"""CSV attachment downloader for retrieving files from MS Graph API."""

import asyncio
import csv
import io
from pathlib import Path
from typing import Dict, Any
import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential

from ..core.interfaces import AttachmentDownloader, AuthenticationProvider, Logger, CsvAttachment
from ..core.exceptions import AttachmentDownloadError


class MSGraphCsvDownloader(AttachmentDownloader):
    """CSV attachment downloader using MS Graph API."""
    
    def __init__(
        self,
        auth_provider: AuthenticationProvider,
        config: Dict[str, Any],
        logger: Logger
    ) -> None:
        """Initialize the CSV downloader.
        
        Args:
            auth_provider: Authentication provider for MS Graph API
            config: Email configuration containing mailbox_address
            logger: Logger instance for structured logging
        """
        self._auth_provider = auth_provider
        self._config = config
        self._logger = logger
        self._mailbox_address = config["mailbox_address"]
        
        # MS Graph API endpoints
        self._base_url = "https://graph.microsoft.com/v1.0"
        self._messages_endpoint = f"{self._base_url}/users/{self._mailbox_address}/messages"
        
        self._logger.info(
            "Initialized MS Graph CSV downloader",
            mailbox_address=self._mailbox_address
        )
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    async def download_csv_attachment(
        self, attachment: CsvAttachment, local_path: Path
    ) -> Path:
        """Download a CSV attachment to a local file.
        
        Args:
            attachment: CSV attachment to download
            local_path: Local file path to save the attachment
            
        Returns:
            Path to the downloaded file
            
        Raises:
            AttachmentDownloadError: If download fails
        """
        try:
            self._logger.info(
                "Starting CSV attachment download",
                attachment_id=attachment.id,
                attachment_name=attachment.name,
                local_path=str(local_path),
                file_size=attachment.size
            )
            
            # Ensure parent directory exists
            local_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Get access token
            access_token = await self._auth_provider.get_access_token()
            
            # Download the attachment content
            attachment_content = await self._download_attachment_content(
                attachment, access_token
            )
            
            # Write content to local file
            await self._write_content_to_file(attachment_content, local_path)
            
            # Validate the downloaded file
            if not await self.validate_csv_content(local_path):
                raise AttachmentDownloadError(
                    f"Downloaded file is not a valid CSV: {local_path}"
                )
            
            self._logger.info(
                "Successfully downloaded CSV attachment",
                attachment_id=attachment.id,
                attachment_name=attachment.name,
                local_path=str(local_path),
                file_size_bytes=local_path.stat().st_size
            )
            
            return local_path
            
        except Exception as e:
            self._logger.error(
                "Failed to download CSV attachment",
                error=str(e),
                error_type=type(e).__name__,
                attachment_id=attachment.id,
                attachment_name=attachment.name,
                local_path=str(local_path)
            )
            
            # Clean up partial download
            if local_path.exists():
                try:
                    local_path.unlink()
                except Exception as cleanup_error:
                    self._logger.warning(
                        "Failed to clean up partial download",
                        cleanup_error=str(cleanup_error),
                        local_path=str(local_path)
                    )
            
            raise AttachmentDownloadError(f"CSV download failed: {str(e)}") from e
    
    async def validate_csv_content(self, file_path: Path) -> bool:
        """Validate that the downloaded file is a valid CSV.
        
        Args:
            file_path: Path to the file to validate
            
        Returns:
            True if file is a valid CSV, False otherwise
        """
        try:
            self._logger.debug(
                "Validating CSV content",
                file_path=str(file_path)
            )
            
            if not file_path.exists():
                self._logger.error(
                    "CSV validation failed: file does not exist",
                    file_path=str(file_path)
                )
                return False
            
            if file_path.stat().st_size == 0:
                self._logger.error(
                    "CSV validation failed: file is empty",
                    file_path=str(file_path)
                )
                return False
            
            # Try to parse the CSV file
            await self._validate_csv_format(file_path)
            
            self._logger.debug(
                "CSV validation successful",
                file_path=str(file_path)
            )
            return True
            
        except Exception as e:
            self._logger.error(
                "CSV validation failed",
                error=str(e),
                error_type=type(e).__name__,
                file_path=str(file_path)
            )
            return False
    
    async def _download_attachment_content(
        self, attachment: CsvAttachment, access_token: str
    ) -> bytes:
        """Download the raw content of an attachment.
        
        Args:
            attachment: Attachment to download
            access_token: Valid access token
            
        Returns:
            Raw attachment content as bytes
        """
        # Build the attachment URL - we need the message ID from the attachment ID
        # The attachment ID contains the message ID
        message_id = self._extract_message_id_from_attachment_id(attachment.id)
        attachment_url = f"{self._messages_endpoint}/{message_id}/attachments/{attachment.id}/$value"
        
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {access_token}",
            }
            
            self._logger.debug(
                "Downloading attachment from MS Graph",
                attachment_url=attachment_url,
                attachment_id=attachment.id
            )
            
            async with session.get(attachment_url, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise AttachmentDownloadError(
                        f"Failed to download attachment: {response.status} - {error_text}"
                    )
                
                # Read the content
                content = await response.read()
                
                self._logger.debug(
                    "Downloaded attachment content",
                    attachment_id=attachment.id,
                    content_size_bytes=len(content)
                )
                
                return content
    
    async def _write_content_to_file(self, content: bytes, file_path: Path) -> None:
        """Write attachment content to a local file.
        
        Args:
            content: Raw attachment content
            file_path: Path to write the file
        """
        loop = asyncio.get_event_loop()
        
        def _write_file() -> None:
            with open(file_path, 'wb') as f:
                f.write(content)
        
        await loop.run_in_executor(None, _write_file)
        
        self._logger.debug(
            "Wrote attachment content to file",
            file_path=str(file_path),
            file_size_bytes=len(content)
        )
    
    async def _validate_csv_format(self, file_path: Path) -> None:
        """Validate that a file has valid CSV format.
        
        Args:
            file_path: Path to the CSV file
            
        Raises:
            AttachmentDownloadError: If CSV format is invalid
        """
        loop = asyncio.get_event_loop()
        
        def _validate_csv() -> None:
            try:
                with open(file_path, 'r', encoding='utf-8', newline='') as f:
                    # Try to read the first few rows to validate format
                    csv_reader = csv.reader(f)
                    rows_read = 0
                    max_rows_to_check = 5
                    
                    for row in csv_reader:
                        rows_read += 1
                        if rows_read >= max_rows_to_check:
                            break
                    
                    if rows_read == 0:
                        raise AttachmentDownloadError("CSV file appears to be empty")
                
            except UnicodeDecodeError:
                # Try with different encoding
                try:
                    with open(file_path, 'r', encoding='latin-1', newline='') as f:
                        csv_reader = csv.reader(f)
                        # Just try to read one row to validate
                        next(csv_reader, None)
                except Exception as e:
                    raise AttachmentDownloadError(f"Cannot read CSV file with any encoding: {str(e)}")
            
            except csv.Error as e:
                raise AttachmentDownloadError(f"Invalid CSV format: {str(e)}")
            
            except Exception as e:
                raise AttachmentDownloadError(f"CSV validation error: {str(e)}")
        
        await loop.run_in_executor(None, _validate_csv)
    
    def _extract_message_id_from_attachment_id(self, attachment_id: str) -> str:
        """Extract message ID from attachment ID.
        
        MS Graph attachment IDs typically contain the message ID.
        This is a simplified implementation - in practice, you might need
        to store the message ID when retrieving attachments.
        
        Args:
            attachment_id: Full attachment ID from MS Graph
            
        Returns:
            Message ID extracted from attachment ID
        """
        # For now, we'll assume the attachment ID is structured in a way
        # that allows extraction of the message ID. In a real implementation,
        # you would need to track the message ID alongside the attachment.
        
        # This is a placeholder - in practice, you'd need to pass the message ID
        # along with the attachment or store it in the CsvAttachment object
        if hasattr(self, '_current_message_id'):
            return self._current_message_id
        
        # If we can't extract it, we'll need to handle this differently
        # For now, raise an error to indicate this needs to be implemented
        raise AttachmentDownloadError(
            "Message ID extraction not implemented - needs message ID tracking"
        )
    
    def set_current_message_id(self, message_id: str) -> None:
        """Set the current message ID for attachment downloads.
        
        This is a helper method to associate attachments with their message.
        
        Args:
            message_id: ID of the message containing attachments
        """
        self._current_message_id = message_id
        self._logger.debug(
            "Set current message ID for attachment downloads",
            message_id=message_id
        )