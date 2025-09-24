"""MS Graph email poller for monitoring mailbox messages."""

import asyncio
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timedelta
import aiohttp
from urllib.parse import quote
import json

from ..core.interfaces import EmailPoller, AuthenticationProvider, Logger, EmailMessage, CsvAttachment, FilterCriteria
from ..core.exceptions import EmailPollingError


class MSGraphEmailPoller(EmailPoller):
    """Email poller using MS Graph API to monitor mailbox for new messages."""
    
    def __init__(
        self,
        auth_provider: AuthenticationProvider,
        config: Dict[str, Any],
        logger: Logger
    ) -> None:
        """Initialize the email poller.
        
        Args:
            auth_provider: Authentication provider for MS Graph API
            config: Email configuration containing:
                - mailbox_address: Email address to monitor
                - polling_interval_seconds: Polling interval
                - max_messages_per_poll: Max messages per poll
            logger: Logger instance for structured logging
        """
        self._auth_provider = auth_provider
        self._config = config
        self._logger = logger
        self._mailbox_address = config["mailbox_address"]
        self._max_messages = config.get("max_messages_per_poll", 50)
        self._processed_messages: Set[str] = set()
        
        # MS Graph API endpoints
        self._base_url = "https://graph.microsoft.com/v1.0"
        self._messages_endpoint = f"{self._base_url}/users/{quote(self._mailbox_address)}/messages"
        
        self._logger.info(
            "Initialized MS Graph email poller",
            mailbox_address=self._mailbox_address,
            max_messages_per_poll=self._max_messages
        )
    
    async def poll_mailbox_for_new_messages(
        self, filter_criteria: FilterCriteria
    ) -> List[EmailMessage]:
        """Poll the mailbox for new messages matching criteria.
        
        Args:
            filter_criteria: Criteria for filtering messages
            
        Returns:
            List of email messages matching the criteria
            
        Raises:
            EmailPollingError: If polling fails
        """
        try:
            self._logger.debug(
                "Starting mailbox poll",
                sender_patterns=filter_criteria.sender_patterns,
                subject_patterns=filter_criteria.subject_patterns,
                max_age_days=filter_criteria.max_age_days
            )
            
            # Build OData filter query
            odata_filter = self._build_odata_filter(filter_criteria)
            
            # Get access token
            access_token = await self._auth_provider.get_access_token()
            
            # Query messages from MS Graph
            messages = await self._query_messages(access_token, odata_filter)
            
            # Filter out already processed messages
            new_messages = [
                msg for msg in messages 
                if msg.id not in self._processed_messages
            ]
            
            # Track processed messages
            for msg in new_messages:
                self._processed_messages.add(msg.id)
            
            self._logger.info(
                "Completed mailbox poll",
                total_messages_found=len(messages),
                new_messages_count=len(new_messages),
                processed_messages_count=len(self._processed_messages)
            )
            
            return new_messages
            
        except Exception as e:
            self._logger.error(
                "Failed to poll mailbox",
                error=str(e),
                error_type=type(e).__name__,
                mailbox_address=self._mailbox_address
            )
            raise EmailPollingError(f"Mailbox polling failed: {str(e)}") from e
    
    async def get_message_attachments(self, message_id: str) -> List[CsvAttachment]:
        """Get CSV attachments from a specific message.
        
        Args:
            message_id: ID of the message to get attachments from
            
        Returns:
            List of CSV attachments
            
        Raises:
            EmailPollingError: If getting attachments fails
        """
        try:
            self._logger.debug(
                "Getting message attachments",
                message_id=message_id
            )
            
            # Get access token
            access_token = await self._auth_provider.get_access_token()
            
            # Query attachments
            attachments_url = f"{self._messages_endpoint}/{message_id}/attachments"
            
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                }
                
                async with session.get(attachments_url, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise EmailPollingError(
                            f"Failed to get attachments: {response.status} - {error_text}"
                        )
                    
                    data = await response.json()
                    attachments_data = data.get("value", [])
            
            # Parse attachments and filter for CSV files
            csv_attachments = []
            for attachment_data in attachments_data:
                if self._is_csv_attachment(attachment_data):
                    csv_attachment = self._parse_attachment_data(attachment_data)
                    csv_attachments.append(csv_attachment)
            
            self._logger.info(
                "Retrieved message attachments",
                message_id=message_id,
                total_attachments=len(attachments_data),
                csv_attachments_count=len(csv_attachments)
            )
            
            return csv_attachments
            
        except Exception as e:
            self._logger.error(
                "Failed to get message attachments",
                error=str(e),
                error_type=type(e).__name__,
                message_id=message_id
            )
            raise EmailPollingError(f"Getting attachments failed: {str(e)}") from e
    
    def _build_odata_filter(self, criteria: FilterCriteria) -> str:
        """Build OData filter query for message filtering.
        
        Args:
            criteria: Filter criteria
            
        Returns:
            OData filter string
        """
        filters = []
        
        # Add sender filters
        if criteria.sender_patterns:
            sender_filters = []
            for pattern in criteria.sender_patterns:
                sender_filters.append(f"contains(from/emailAddress/address, '{pattern}')")
            if sender_filters:
                filters.append(f"({' or '.join(sender_filters)})")
        
        # Add subject filters
        if criteria.subject_patterns:
            subject_filters = []
            for pattern in criteria.subject_patterns:
                subject_filters.append(f"contains(subject, '{pattern}')")
            if subject_filters:
                filters.append(f"({' or '.join(subject_filters)})")
        
        # Add age filter
        if criteria.max_age_days:
            cutoff_date = datetime.utcnow() - timedelta(days=criteria.max_age_days)
            iso_date = cutoff_date.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            filters.append(f"receivedDateTime ge {iso_date}")
        
        # Only include messages with attachments
        filters.append("hasAttachments eq true")
        
        return " and ".join(filters) if filters else ""
    
    async def _query_messages(self, access_token: str, odata_filter: str) -> List[EmailMessage]:
        """Query messages from MS Graph API.
        
        Args:
            access_token: Valid access token
            odata_filter: OData filter string
            
        Returns:
            List of email messages
        """
        url = self._messages_endpoint
        params = {
            "$top": str(self._max_messages),
            "$select": "id,from,subject,receivedDateTime,hasAttachments,bodyPreview",
            "$orderby": "receivedDateTime desc"
        }
        
        if odata_filter:
            params["$filter"] = odata_filter
        
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            async with session.get(url, headers=headers, params=params) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise EmailPollingError(
                        f"Failed to query messages: {response.status} - {error_text}"
                    )
                
                data = await response.json()
                messages_data = data.get("value", [])
        
        # Parse message data
        messages = []
        for msg_data in messages_data:
            message = self._parse_message_data(msg_data)
            messages.append(message)
        
        return messages
    
    def _parse_message_data(self, msg_data: Dict[str, Any]) -> EmailMessage:
        """Parse message data from MS Graph API response.
        
        Args:
            msg_data: Message data from API
            
        Returns:
            EmailMessage instance
        """
        sender_email = ""
        from_data = msg_data.get("from", {})
        if from_data and "emailAddress" in from_data:
            sender_email = from_data["emailAddress"].get("address", "")
        
        return EmailMessage(
            id=msg_data["id"],
            sender=sender_email,
            subject=msg_data.get("subject", ""),
            received_datetime=msg_data.get("receivedDateTime", ""),
            has_attachments=msg_data.get("hasAttachments", False),
            body_preview=msg_data.get("bodyPreview", "")
        )
    
    def _is_csv_attachment(self, attachment_data: Dict[str, Any]) -> bool:
        """Check if an attachment is a CSV file.
        
        Args:
            attachment_data: Attachment data from API
            
        Returns:
            True if attachment is a CSV file
        """
        name = attachment_data.get("name", "").lower()
        content_type = attachment_data.get("contentType", "").lower()
        
        # Check file extension
        csv_extensions = [".csv"]
        has_csv_extension = any(name.endswith(ext) for ext in csv_extensions)
        
        # Check content type
        csv_content_types = ["text/csv", "application/csv", "text/plain"]
        has_csv_content_type = any(csv_type in content_type for csv_type in csv_content_types)
        
        return has_csv_extension or has_csv_content_type
    
    def _parse_attachment_data(self, attachment_data: Dict[str, Any]) -> CsvAttachment:
        """Parse attachment data from MS Graph API response.
        
        Args:
            attachment_data: Attachment data from API
            
        Returns:
            CsvAttachment instance
        """
        return CsvAttachment(
            id=attachment_data["id"],
            name=attachment_data.get("name", ""),
            size=attachment_data.get("size", 0),
            content_type=attachment_data.get("contentType", ""),
            download_url=None  # Will be set when downloading
        )
    
    def clear_processed_messages_cache(self) -> None:
        """Clear the cache of processed messages."""
        self._processed_messages.clear()
        self._logger.info("Cleared processed messages cache")
    
    def get_processed_messages_count(self) -> int:
        """Get the count of processed messages in cache."""
        return len(self._processed_messages)