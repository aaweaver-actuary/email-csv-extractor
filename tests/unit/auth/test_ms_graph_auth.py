"""Tests for MS Graph authentication provider."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from email_csv_extractor.auth.ms_graph_auth import MSGraphAuthenticationProvider
from email_csv_extractor.core.exceptions import AuthenticationError


class TestMSGraphAuthenticationProvider:
    """Test cases for MS Graph authentication provider."""
    
    def test_init_valid_config(self, mock_logger, mock_msal_app):
        """Test initialization with valid configuration."""
        config = {
            "client_id": "test-client-id",
            "client_secret": "test-client-secret", 
            "tenant_id": "test-tenant-id"
        }
        
        with patch('email_csv_extractor.auth.ms_graph_auth.msal.ConfidentialClientApplication', return_value=mock_msal_app):
            provider = MSGraphAuthenticationProvider(config, mock_logger)
            
            assert provider._config == config
            assert provider._logger == mock_logger
            assert provider._access_token is None
            assert provider._token_expires_at is None
    
    def test_init_invalid_config(self, mock_logger):
        """Test initialization with invalid configuration."""
        config = {
            "client_id": "test-client-id",
            # Missing required fields
        }
        
        with pytest.raises(AuthenticationError):
            MSGraphAuthenticationProvider(config, mock_logger)
    
    @pytest.mark.asyncio
    async def test_get_access_token_success(self, mock_logger, mock_msal_app):
        """Test successful token acquisition."""
        config = {
            "client_id": "test-client-id",
            "client_secret": "test-client-secret",
            "tenant_id": "test-tenant-id"
        }
        
        # Mock successful token response
        mock_msal_app.acquire_token_for_client.return_value = {
            "access_token": "mock-access-token",
            "expires_in": 3600
        }
        
        with patch('email_csv_extractor.auth.ms_graph_auth.msal.ConfidentialClientApplication', return_value=mock_msal_app):
            provider = MSGraphAuthenticationProvider(config, mock_logger)
            
            token = await provider.get_access_token()
            
            assert token == "mock-access-token"
            assert provider._access_token == "mock-access-token"
            assert provider._token_expires_at is not None
    
    @pytest.mark.asyncio 
    async def test_get_access_token_failure(self, mock_logger, mock_msal_app):
        """Test token acquisition failure."""
        config = {
            "client_id": "test-client-id",
            "client_secret": "test-client-secret",
            "tenant_id": "test-tenant-id"
        }
        
        # Mock failed token response
        mock_msal_app.acquire_token_for_client.return_value = {
            "error": "invalid_client",
            "error_description": "Invalid client credentials"
        }
        
        with patch('email_csv_extractor.auth.ms_graph_auth.msal.ConfidentialClientApplication', return_value=mock_msal_app):
            provider = MSGraphAuthenticationProvider(config, mock_logger)
            
            with pytest.raises(AuthenticationError, match="Token acquisition failed"):
                await provider.get_access_token()
    
    @pytest.mark.asyncio
    async def test_get_access_token_cached(self, mock_logger, mock_msal_app):
        """Test using cached token when still valid."""
        config = {
            "client_id": "test-client-id",
            "client_secret": "test-client-secret",
            "tenant_id": "test-tenant-id"
        }
        
        with patch('email_csv_extractor.auth.ms_graph_auth.msal.ConfidentialClientApplication', return_value=mock_msal_app):
            provider = MSGraphAuthenticationProvider(config, mock_logger)
            
            # Set a valid cached token
            provider._access_token = "cached-token"
            provider._token_expires_at = datetime.utcnow() + timedelta(hours=1)
            
            token = await provider.get_access_token()
            
            assert token == "cached-token"
            # Should not call acquire_token_for_client for cached token
            mock_msal_app.acquire_token_for_client.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_refresh_token_if_needed(self, mock_logger, mock_msal_app):
        """Test proactive token refresh."""
        config = {
            "client_id": "test-client-id",
            "client_secret": "test-client-secret",
            "tenant_id": "test-tenant-id"
        }
        
        mock_msal_app.acquire_token_for_client.return_value = {
            "access_token": "new-token",
            "expires_in": 3600
        }
        
        with patch('email_csv_extractor.auth.ms_graph_auth.msal.ConfidentialClientApplication', return_value=mock_msal_app):
            provider = MSGraphAuthenticationProvider(config, mock_logger)
            
            # Set token that expires soon
            provider._access_token = "old-token"
            provider._token_expires_at = datetime.utcnow() + timedelta(minutes=3)
            
            await provider.refresh_token_if_needed()
            
            assert provider._access_token == "new-token"
    
    def test_is_token_valid(self, mock_logger, mock_msal_app):
        """Test token validity checking."""
        config = {
            "client_id": "test-client-id",
            "client_secret": "test-client-secret",
            "tenant_id": "test-tenant-id"
        }
        
        with patch('email_csv_extractor.auth.ms_graph_auth.msal.ConfidentialClientApplication', return_value=mock_msal_app):
            provider = MSGraphAuthenticationProvider(config, mock_logger)
            
            # No token
            assert not provider._is_token_valid()
            
            # Valid token
            provider._access_token = "valid-token"
            provider._token_expires_at = datetime.utcnow() + timedelta(hours=1)
            assert provider._is_token_valid()
            
            # Expired token
            provider._token_expires_at = datetime.utcnow() - timedelta(hours=1)
            assert not provider._is_token_valid()
    
    def test_get_token_info(self, mock_logger, mock_msal_app):
        """Test getting token information."""
        config = {
            "client_id": "test-client-id",
            "client_secret": "test-client-secret",
            "tenant_id": "test-tenant-id"
        }
        
        with patch('email_csv_extractor.auth.ms_graph_auth.msal.ConfidentialClientApplication', return_value=mock_msal_app):
            provider = MSGraphAuthenticationProvider(config, mock_logger)
            
            # Set token
            provider._access_token = "test-token"
            provider._token_expires_at = datetime.utcnow() + timedelta(hours=1)
            
            token_info = provider.get_token_info()
            
            assert token_info["has_token"] is True
            assert token_info["is_valid"] is True
            assert token_info["client_id"] == "test-client-id"
            assert "authority" in token_info
            assert "scopes" in token_info
            # Should not expose actual token
            assert "access_token" not in token_info