"""
White Box Tests for ControlDService.

Tests the Control D API integration layer with mocked HTTP responses.
CRITICAL: No real API calls to api.controld.com - all calls are intercepted
by mock class and mocked.
"""

import pytest
import re
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from aioresponses import aioresponses

from app.services.controld import ControlDService
from app.config import Settings


# ============================================================================
# MODULE LEVEL ISOLATION FIXTURES (Prevents Live API Leakage)
# ============================================================================

@pytest.fixture(autouse=True)
def mock_all_settings_leakage(mock_settings: Settings):
    """
    Forcefully intercepts both the dynamic settings generator function
    and the already-imported module-level variable inside 'app.services.controld'.
    This guarantees that the real .env file token is never queried.
    """
    with patch("app.config.get_settings", return_value=mock_settings), \
         patch("app.services.controld.settings", mock_settings):
        yield


# ============================================================================
# TEST SUITE: ControlDService.create_dns_device()
# ============================================================================


@pytest.mark.asyncio
async def test_create_dns_device_success(mock_settings: Settings, test_device_data: dict):
    """
    White Box Test: Verify successful device creation on Control D.
    """
    service = ControlDService(mock_settings)
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "success",
        "body": {
            "device": {
                "pk": test_device_data["device_id"]
            },
            "resolver": {
                "dns_over_https": test_device_data["doh"],
                "dns_over_tls": test_device_data["dot"],
            },
        },
    }
    
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        result = await service.create_dns_device(
            tg_user_id=123456789,
            profile_id="mock_profile_12345",
            device_type="mobile",
        )
        
        assert result is not None, "create_dns_device should return device data"
        assert result["device_id"] == test_device_data["device_id"]
        assert result["doh"] == test_device_data["doh"]
        assert result["dot"] == test_device_data["dot"]


@pytest.mark.asyncio
async def test_create_dns_device_robust_parsing(mock_settings: Settings):
    """
    White Box Test: Verify robust parsing of different Control D response formats.
    """
    service = ControlDService(mock_settings)
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "success",
        "body": {
            "PK": "device_pk_alternative_format",
            "resolver": {
                "doh": "https://dns.example.com/doh",
                "dns_over_tls": "dns.example.com",
            },
        },
    }
    
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        result = await service.create_dns_device(
            tg_user_id=123456789,
            profile_id="mock_profile_12345",
        )
        
        assert result is not None
        assert result["device_id"] == "device_pk_alternative_format"


@pytest.mark.asyncio
async def test_create_dns_device_api_error_500(mock_settings: Settings):
    """
    White Box Test: Verify graceful handling of 500 Internal Server Error.
    """
    service = ControlDService(mock_settings)
    
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = '{"error": "Internal Server Error"}'
    
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        result = await service.create_dns_device(
            tg_user_id=123456789,
            profile_id="mock_profile_12345",
        )
        
        assert result is None, "Should return None on API error"


@pytest.mark.asyncio
async def test_create_dns_device_api_error_400(mock_settings: Settings):
    """
    White Box Test: Verify handling of 400 Bad Request (invalid profile).
    """
    service = ControlDService(mock_settings)
    
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = '{"error": "Invalid profile_id"}'
    
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        result = await service.create_dns_device(
            tg_user_id=123456789,
            profile_id="invalid_profile_id",
        )
        
        assert result is None


@pytest.mark.asyncio
async def test_create_dns_device_incomplete_response(mock_settings: Settings):
    """
    White Box Test: Verify handling of incomplete API response.
    """
    service = ControlDService(mock_settings)
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "success",
        "body": {
            "device_id": "test_device_123",
            # Missing: resolvers/doh field
        },
    }
    
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        result = await service.create_dns_device(
            tg_user_id=123456789,
            profile_id="mock_profile_12345",
        )
        
        assert result is None, "Should return None when response is incomplete"


# ============================================================================
# TEST SUITE: ControlDService.delete_dns_device()
# ============================================================================


@pytest.mark.asyncio
async def test_delete_dns_device_success(mock_settings: Settings):
    """
    White Box Test: Verify successful device deletion from Control D.
    """
    service = ControlDService(mock_settings)
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.delete.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        result = await service.delete_dns_device("device_pk_mock_12345")
        
        assert result is True


@pytest.mark.asyncio
async def test_delete_dns_device_not_found(mock_settings: Settings):
    """
    White Box Test: Verify handling of device not found (404).
    """
    service = ControlDService(mock_settings)
    
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = '{"error": "Device not found"}'
    
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.delete.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        result = await service.delete_dns_device("nonexistent_device")
        
        assert result is False


@pytest.mark.asyncio
async def test_delete_dns_device_api_error(mock_settings: Settings):
    """
    White Box Test: Verify handling of API errors during deletion.
    """
    service = ControlDService(mock_settings)
    
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = '{"error": "Internal Server Error"}'
    
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.delete.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        result = await service.delete_dns_device("device_pk_mock_12345")
        
        assert result is False


# ============================================================================
# TEST SUITE: ControlDService.fetch_controld_profiles()
# ============================================================================


@pytest.mark.asyncio
async def test_fetch_controld_profiles_success(mock_settings: Settings):
    """
    White Box Test: Verify successful fetching of available profiles.
    """
    service = ControlDService(mock_settings)
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "success",
        "body": {
            "profiles": [
                {
                    "id": "profile_adult_filter",
                    "name": "Adult Filter",
                    "description": "Blocks adult content",
                },
                {
                    "id": "profile_malware_protection",
                    "name": "Malware Protection",
                    "description": "Blocks malware domains",
                },
            ]
        },
    }
    
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        profiles = await service.fetch_controld_profiles()
        
        assert profiles is not None
        assert len(profiles) == 2
        assert profiles[0]["id"] == "profile_adult_filter"
        assert profiles[0]["name"] == "Adult Filter"


@pytest.mark.asyncio
async def test_fetch_controld_profiles_empty(mock_settings: Settings):
    """
    White Box Test: Verify handling of empty profile list.
    """
    service = ControlDService(mock_settings)
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "success",
        "body": {
            "profiles": []
        }
    }
    
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        profiles = await service.fetch_controld_profiles()
        
        assert profiles is not None
        assert len(profiles) == 0


@pytest.mark.asyncio
async def test_fetch_controld_profiles_api_error(mock_settings: Settings):
    """
    White Box Test: Verify handling of API error when fetching profiles.
    """
    service = ControlDService(mock_settings)
    
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = '{"error": "Internal Server Error"}'
    
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        profiles = await service.fetch_controld_profiles()
        
        assert profiles is None


# ============================================================================
# TEST SUITE: Timeout and Network Error Handling
# ============================================================================


@pytest.mark.asyncio
async def test_create_dns_device_timeout(mock_settings: Settings):
    """
    White Box Test: Verify timeout handling during device creation.
    """
    service = ControlDService(mock_settings)
    
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.post.side_effect = asyncio.TimeoutError("Request timed out")
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        result = await service.create_dns_device(
            tg_user_id=123456789,
            profile_id="mock_profile_12345",
        )
        
        assert result is None


@pytest.mark.asyncio
async def test_create_dns_device_connection_error(mock_settings: Settings):
    """
    White Box Test: Verify connection error handling.
    """
    service = ControlDService(mock_settings)
    
    with patch("httpx.AsyncClient") as mock_client_class:
        import httpx
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.ConnectError("Connection refused")
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        result = await service.create_dns_device(
            tg_user_id=123456789,
            profile_id="mock_profile_12345",
        )
        
        assert result is None


# ============================================================================
# TEST SUITE: Authentication and API Token Validation
# ============================================================================


@pytest.mark.asyncio
async def test_create_dns_device_invalid_token(mock_settings: Settings):
    """
    White Box Test: Verify rejection of invalid API tokens.
    """
    service = ControlDService(mock_settings)
    
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = '{"error": "Unauthorized"}'
    
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        result = await service.create_dns_device(
            tg_user_id=123456789,
            profile_id="mock_profile_12345",
        )
        
        assert result is None


# ============================================================================
# TEST SUITE: Settings Injection and Dependency
# ============================================================================


@pytest.mark.asyncio
async def test_service_uses_settings_api_token(mock_settings: Settings):
    """
    White Box Test: Verify service correctly injects API token from settings.
    """
    service = ControlDService(mock_settings)
    
    assert service.settings.controld_api_token == "mock_controld_token_12345"
    assert service.settings.controld_profile_id == "mock_profile_12345"


@pytest.mark.asyncio
async def test_service_default_settings(mock_settings: Settings):
    """
    White Box Test: Verify service falls back to default settings if not provided.
    """
    with patch("app.services.controld.settings", mock_settings):
        service = ControlDService(None)
        
        assert service.settings is not None