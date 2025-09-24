"""Microsoft Graph authentication provider using MSAL for app-only authentication."""

import asyncio
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import msal

from ..core.interfaces import AuthenticationProvider, Logger
from ..core.exceptions import AuthenticationError


class MSGraphAuthenticationProvider(AuthenticationProvider):
    """Authentication provider for MS Graph API using app-only OAuth flow."""
    
    def __init__(self, config: Dict[str, Any], logger: Logger) -> None:
        """Initialize the authentication provider.
        
        Args:
            config: Authentication configuration containing:
                - client_id: Azure AD Application Client ID
                - client_secret: Azure AD Application Client Secret  
                - tenant_id: Azure AD Tenant ID
                - authority: Azure AD Authority URL (optional)
                - scopes: OAuth scopes (optional)
            logger: Logger instance for structured logging
        """
        self._config = config
        self._logger = logger
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        
        # Initialize MSAL confidential client app
        authority = config.get("authority", "https://login.microsoftonline.com")
        tenant_id = config["tenant_id"]
        self._authority_url = f"{authority}/{tenant_id}"
        
        try:
            self._app = msal.ConfidentialClientApplication(
                client_id=config["client_id"],
                client_credential=config["client_secret"],
                authority=self._authority_url
            )
            self._scopes = config.get("scopes", ["https://graph.microsoft.com/.default"])
            self._logger.info(
                "Initialized MS Graph authentication provider",
                client_id=config["client_id"],
                tenant_id=tenant_id,
                authority=self._authority_url
            )
        except Exception as e:
            self._logger.error(
                "Failed to initialize authentication provider",
                error=str(e),
                client_id=config.get("client_id", ""),
                tenant_id=config.get("tenant_id", "")
            )
            raise AuthenticationError(f"Failed to initialize authentication: {str(e)}") from e
    
    async def get_access_token(self) -> str:
        """Get a valid access token for MS Graph API.
        
        Returns:
            Valid access token string
            
        Raises:
            AuthenticationError: If token acquisition fails
        """
        try:
            # Check if current token is still valid
            if self._is_token_valid():
                return self._access_token
            
            # Acquire new token using client credentials flow
            await self._acquire_new_token()
            
            if not self._access_token:
                raise AuthenticationError("Failed to acquire access token")
            
            return self._access_token
            
        except Exception as e:
            self._logger.error(
                "Failed to get access token",
                error=str(e)
            )
            raise AuthenticationError(f"Token acquisition failed: {str(e)}") from e
    
    async def refresh_token_if_needed(self) -> None:
        """Refresh the access token if it's close to expiry.
        
        Refreshes the token if it expires within the next 5 minutes.
        """
        if not self._is_token_valid(buffer_minutes=5):
            self._logger.info("Refreshing access token proactively")
            await self._acquire_new_token()
    
    def _is_token_valid(self, buffer_minutes: int = 1) -> bool:
        """Check if the current token is valid.
        
        Args:
            buffer_minutes: Minutes before expiry to consider token invalid
            
        Returns:
            True if token is valid, False otherwise
        """
        if not self._access_token or not self._token_expires_at:
            return False
        
        buffer_time = timedelta(minutes=buffer_minutes)
        return datetime.utcnow() + buffer_time < self._token_expires_at
    
    async def _acquire_new_token(self) -> None:
        """Acquire a new access token using client credentials flow."""
        try:
            self._logger.debug("Acquiring new access token")
            
            # Run token acquisition in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._app.acquire_token_for_client,
                self._scopes
            )
            
            if "access_token" in result:
                self._access_token = result["access_token"]
                # Calculate expiry time (tokens typically last 3600 seconds)
                expires_in = result.get("expires_in", 3600)
                self._token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
                
                self._logger.info(
                    "Successfully acquired new access token",
                    expires_at=self._token_expires_at.isoformat(),
                    expires_in_seconds=expires_in
                )
            else:
                error_msg = result.get("error_description", "Unknown error")
                error_code = result.get("error", "unknown_error")
                
                self._logger.error(
                    "Failed to acquire access token",
                    error_code=error_code,
                    error_description=error_msg
                )
                raise AuthenticationError(f"Token acquisition failed: {error_msg}")
                
        except Exception as e:
            self._logger.error(
                "Exception during token acquisition",
                error=str(e),
                error_type=type(e).__name__
            )
            raise AuthenticationError(f"Token acquisition failed: {str(e)}") from e
    
    def get_token_info(self) -> Dict[str, Any]:
        """Get information about the current token for debugging.
        
        Returns:
            Dictionary with token information (without exposing the actual token)
        """
        return {
            "has_token": self._access_token is not None,
            "token_expires_at": self._token_expires_at.isoformat() if self._token_expires_at else None,
            "is_valid": self._is_token_valid(),
            "authority": self._authority_url,
            "scopes": self._scopes,
            "client_id": self._config["client_id"]
        }