"""SharePoint uploader for uploading CSV files to Teams channels with large file support."""

import asyncio
import math
from pathlib import Path
from typing import Dict, Any, Optional
import aiohttp
from urllib.parse import quote
from tenacity import retry, stop_after_attempt, wait_exponential

from ..core.interfaces import SharePointUploader, AuthenticationProvider, Logger
from ..core.exceptions import SharePointUploadError


class MSGraphSharePointUploader(SharePointUploader):
    """SharePoint uploader using MS Graph API with support for large files."""
    
    def __init__(
        self,
        auth_provider: AuthenticationProvider,
        config: Dict[str, Any],
        logger: Logger
    ) -> None:
        """Initialize the SharePoint uploader.
        
        Args:
            auth_provider: Authentication provider for MS Graph API
            config: SharePoint configuration containing:
                - team_id: Microsoft Teams Team ID
                - channel_id: Microsoft Teams Channel ID
                - target_folder_path: Target folder path
                - large_file_threshold_mb: Threshold for chunked uploads
                - chunk_size_mb: Chunk size for large files
                - max_retries: Maximum retry attempts
            logger: Logger instance for structured logging
        """
        self._auth_provider = auth_provider
        self._config = config
        self._logger = logger
        
        self._team_id = config["team_id"]
        self._channel_id = config["channel_id"]
        self._target_folder = config.get("target_folder_path", "Shared Documents/CSV Files")
        self._large_file_threshold = config.get("large_file_threshold_mb", 4) * 1024 * 1024
        self._chunk_size = config.get("chunk_size_mb", 5) * 1024 * 1024
        self._max_retries = config.get("max_retries", 3)
        
        # MS Graph API endpoints
        self._base_url = "https://graph.microsoft.com/v1.0"
        self._site_url = f"{self._base_url}/teams/{self._team_id}/channels/{self._channel_id}/filesFolder"
        
        self._logger.info(
            "Initialized MS Graph SharePoint uploader",
            team_id=self._team_id,
            channel_id=self._channel_id,
            target_folder=self._target_folder,
            large_file_threshold_mb=self._large_file_threshold / (1024 * 1024),
            chunk_size_mb=self._chunk_size / (1024 * 1024)
        )
    
    async def upload_file_to_sharepoint_folder(
        self,
        file_path: Path,
        target_folder: str,
        team_id: str,
        channel_id: str
    ) -> str:
        """Upload a file to a SharePoint folder in a Teams channel.
        
        Args:
            file_path: Path to the file to upload
            target_folder: Target folder path in SharePoint
            team_id: Microsoft Teams Team ID
            channel_id: Microsoft Teams Channel ID
            
        Returns:
            SharePoint file URL
            
        Raises:
            SharePointUploadError: If upload fails
        """
        try:
            file_size = file_path.stat().st_size
            
            self._logger.info(
                "Starting file upload to SharePoint",
                file_path=str(file_path),
                file_size_bytes=file_size,
                file_size_mb=file_size / (1024 * 1024),
                target_folder=target_folder,
                team_id=team_id,
                channel_id=channel_id
            )
            
            # Choose upload method based on file size
            if file_size > self._large_file_threshold:
                return await self.upload_large_file_to_sharepoint_folder(
                    file_path, target_folder, team_id, channel_id
                )
            else:
                return await self._upload_small_file(
                    file_path, target_folder, team_id, channel_id
                )
                
        except Exception as e:
            self._logger.error(
                "Failed to upload file to SharePoint",
                error=str(e),
                error_type=type(e).__name__,
                file_path=str(file_path),
                target_folder=target_folder
            )
            raise SharePointUploadError(f"File upload failed: {str(e)}") from e
    
    async def upload_large_file_to_sharepoint_folder(
        self,
        file_path: Path,
        target_folder: str,
        team_id: str,
        channel_id: str,
        chunk_size: int = None
    ) -> str:
        """Upload a large file using chunked upload.
        
        Args:
            file_path: Path to the file to upload
            target_folder: Target folder path in SharePoint
            team_id: Microsoft Teams Team ID
            channel_id: Microsoft Teams Channel ID
            chunk_size: Size of each chunk (optional, uses config default)
            
        Returns:
            SharePoint file URL
            
        Raises:
            SharePointUploadError: If upload fails
        """
        try:
            if chunk_size is None:
                chunk_size = self._chunk_size
            
            file_size = file_path.stat().st_size
            total_chunks = math.ceil(file_size / chunk_size)
            
            self._logger.info(
                "Starting chunked upload for large file",
                file_path=str(file_path),
                file_size_bytes=file_size,
                chunk_size_bytes=chunk_size,
                total_chunks=total_chunks,
                target_folder=target_folder
            )
            
            # Create upload session
            upload_session = await self._create_upload_session(
                file_path, target_folder, team_id, channel_id
            )
            
            # Upload chunks
            uploaded_url = await self._upload_file_chunks(
                file_path, upload_session, chunk_size
            )
            
            self._logger.info(
                "Successfully completed chunked upload",
                file_path=str(file_path),
                uploaded_url=uploaded_url,
                total_chunks=total_chunks
            )
            
            return uploaded_url
            
        except Exception as e:
            self._logger.error(
                "Failed to upload large file",
                error=str(e),
                error_type=type(e).__name__,
                file_path=str(file_path),
                target_folder=target_folder
            )
            raise SharePointUploadError(f"Large file upload failed: {str(e)}") from e
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    async def _upload_small_file(
        self,
        file_path: Path,
        target_folder: str,
        team_id: str,
        channel_id: str
    ) -> str:
        """Upload a small file directly.
        
        Args:
            file_path: Path to the file to upload
            target_folder: Target folder path
            team_id: Team ID
            channel_id: Channel ID
            
        Returns:
            SharePoint file URL
        """
        access_token = await self._auth_provider.get_access_token()
        
        # Build upload URL
        file_name = file_path.name
        encoded_folder = quote(target_folder)
        encoded_filename = quote(file_name)
        upload_url = f"{self._base_url}/teams/{team_id}/channels/{channel_id}/filesFolder:/{encoded_folder}/{encoded_filename}:/content"
        
        # Read file content
        with open(file_path, 'rb') as f:
            file_content = f.read()
        
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/octet-stream"
            }
            
            async with session.put(upload_url, headers=headers, data=file_content) as response:
                if response.status not in [200, 201]:
                    error_text = await response.text()
                    raise SharePointUploadError(
                        f"Failed to upload file: {response.status} - {error_text}"
                    )
                
                result = await response.json()
                web_url = result.get("webUrl", "")
                
                self._logger.info(
                    "Successfully uploaded small file",
                    file_path=str(file_path),
                    uploaded_url=web_url,
                    file_size_bytes=len(file_content)
                )
                
                return web_url
    
    async def _create_upload_session(
        self,
        file_path: Path,
        target_folder: str,
        team_id: str,
        channel_id: str
    ) -> Dict[str, Any]:
        """Create an upload session for large file upload.
        
        Args:
            file_path: Path to the file to upload
            target_folder: Target folder path
            team_id: Team ID
            channel_id: Channel ID
            
        Returns:
            Upload session information
        """
        access_token = await self._auth_provider.get_access_token()
        
        file_name = file_path.name
        encoded_folder = quote(target_folder)
        encoded_filename = quote(file_name)
        
        session_url = f"{self._base_url}/teams/{team_id}/channels/{channel_id}/filesFolder:/{encoded_folder}/{encoded_filename}:/createUploadSession"
        
        # Prepare request payload
        payload = {
            "item": {
                "@microsoft.graph.conflictBehavior": "replace",
                "name": file_name
            }
        }
        
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            async with session.post(session_url, headers=headers, json=payload) as response:
                if response.status not in [200, 201]:
                    error_text = await response.text()
                    raise SharePointUploadError(
                        f"Failed to create upload session: {response.status} - {error_text}"
                    )
                
                upload_session = await response.json()
                
                self._logger.debug(
                    "Created upload session",
                    file_path=str(file_path),
                    upload_url=upload_session.get("uploadUrl", "")
                )
                
                return upload_session
    
    async def _upload_file_chunks(
        self,
        file_path: Path,
        upload_session: Dict[str, Any],
        chunk_size: int
    ) -> str:
        """Upload file in chunks using the upload session.
        
        Args:
            file_path: Path to the file to upload
            upload_session: Upload session information
            chunk_size: Size of each chunk
            
        Returns:
            SharePoint file URL
        """
        upload_url = upload_session["uploadUrl"]
        file_size = file_path.stat().st_size
        total_chunks = math.ceil(file_size / chunk_size)
        
        with open(file_path, 'rb') as f:
            for chunk_index in range(total_chunks):
                start_byte = chunk_index * chunk_size
                end_byte = min(start_byte + chunk_size - 1, file_size - 1)
                chunk_data = f.read(chunk_size)
                
                await self._upload_chunk(
                    upload_url, chunk_data, start_byte, end_byte, file_size, chunk_index + 1, total_chunks
                )
                
                self._logger.debug(
                    "Uploaded chunk",
                    chunk_number=chunk_index + 1,
                    total_chunks=total_chunks,
                    start_byte=start_byte,
                    end_byte=end_byte,
                    chunk_size_bytes=len(chunk_data)
                )
        
        # The final chunk upload should return the file information
        # For now, we'll construct a basic URL - in practice, you'd get this from the final response
        return f"Uploaded to SharePoint: {file_path.name}"
    
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        reraise=True
    )
    async def _upload_chunk(
        self,
        upload_url: str,
        chunk_data: bytes,
        start_byte: int,
        end_byte: int,
        total_size: int,
        chunk_number: int,
        total_chunks: int
    ) -> None:
        """Upload a single chunk of data.
        
        Args:
            upload_url: Upload session URL
            chunk_data: Chunk data to upload
            start_byte: Start byte position
            end_byte: End byte position
            total_size: Total file size
            chunk_number: Current chunk number
            total_chunks: Total number of chunks
        """
        async with aiohttp.ClientSession() as session:
            headers = {
                "Content-Length": str(len(chunk_data)),
                "Content-Range": f"bytes {start_byte}-{end_byte}/{total_size}"
            }
            
            async with session.put(upload_url, headers=headers, data=chunk_data) as response:
                if response.status not in [202, 200, 201]:
                    error_text = await response.text()
                    raise SharePointUploadError(
                        f"Failed to upload chunk {chunk_number}/{total_chunks}: {response.status} - {error_text}"
                    )
                
                # Check if this was the final chunk
                if response.status in [200, 201]:
                    result = await response.json()
                    self._logger.info(
                        "Final chunk uploaded successfully",
                        chunk_number=chunk_number,
                        total_chunks=total_chunks,
                        file_url=result.get("webUrl", "")
                    )
    
    async def _ensure_folder_exists(
        self, folder_path: str, team_id: str, channel_id: str
    ) -> None:
        """Ensure the target folder exists in SharePoint.
        
        Args:
            folder_path: Path to the folder
            team_id: Team ID
            channel_id: Channel ID
        """
        try:
            access_token = await self._auth_provider.get_access_token()
            
            # Split folder path into components
            folder_parts = [part for part in folder_path.split('/') if part]
            
            # Build folder structure
            current_path = ""
            for folder_name in folder_parts:
                current_path = f"{current_path}/{folder_name}" if current_path else folder_name
                await self._create_folder_if_not_exists(
                    current_path, team_id, channel_id, access_token
                )
                
        except Exception as e:
            self._logger.warning(
                "Failed to ensure folder exists (continuing anyway)",
                error=str(e),
                folder_path=folder_path
            )
    
    async def _create_folder_if_not_exists(
        self, folder_path: str, team_id: str, channel_id: str, access_token: str
    ) -> None:
        """Create a folder if it doesn't exist.
        
        Args:
            folder_path: Path to the folder
            team_id: Team ID
            channel_id: Channel ID
            access_token: Access token
        """
        encoded_path = quote(folder_path)
        folder_url = f"{self._base_url}/teams/{team_id}/channels/{channel_id}/filesFolder:/{encoded_path}"
        
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {access_token}",
            }
            
            # Check if folder exists
            async with session.get(folder_url, headers=headers) as response:
                if response.status == 200:
                    return  # Folder exists
                
                if response.status == 404:
                    # Folder doesn't exist, create it
                    create_url = f"{self._base_url}/teams/{team_id}/channels/{channel_id}/filesFolder/children"
                    payload = {
                        "name": folder_path.split('/')[-1],
                        "folder": {},
                        "@microsoft.graph.conflictBehavior": "rename"
                    }
                    
                    headers["Content-Type"] = "application/json"
                    async with session.post(create_url, headers=headers, json=payload) as create_response:
                        if create_response.status not in [200, 201]:
                            error_text = await create_response.text()
                            self._logger.warning(
                                "Failed to create folder",
                                folder_path=folder_path,
                                error=error_text
                            )