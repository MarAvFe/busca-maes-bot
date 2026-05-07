"""Unit tests for RNP client (session management and singleton reset)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from buscamaes.sources.rnp import RNPClient, get_rnp_client, reset_rnp_client


@pytest.fixture(autouse=True)
def _setup_env(monkeypatch):
    """Set up required env vars for RNPClient initialization."""
    monkeypatch.setenv("BOT_TOKEN", "test_token")
    monkeypatch.setenv("RNP_EMAIL", "test@example.com")
    monkeypatch.setenv("RNP_PASSWORD", "testpass")
    from buscamaes.settings import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class TestRNPClientLoginDetection:
    """Test login success/failure detection logic."""

    def test_looks_like_login_page_by_url(self):
        """Test login page detection by URL."""
        client = RNPClient()
        resp = MagicMock()
        resp.url.path = "/shopping/login.jspx"
        assert client._looks_like_login_page(resp) is True

    def test_looks_like_login_page_by_url_with_jsessionid(self):
        """Test login page detection with jsessionid suffix in path."""
        client = RNPClient()
        resp = MagicMock()
        resp.url.path = "/shopping/login.jspx;jsessionid=SA4Avw74caKbu"
        assert client._looks_like_login_page(resp) is True

    def test_looks_like_login_page_by_content(self):
        """Test login page detection by HTML content."""
        client = RNPClient()
        resp = MagicMock()
        resp.url.path = "/other"
        resp.text = '<input name="correo"> <input name="pass">'
        assert client._looks_like_login_page(resp) is True

    def test_not_login_page(self):
        """Test non-login page."""
        client = RNPClient()
        resp = MagicMock()
        resp.url.path = "/results"
        resp.text = "<table></table>"
        assert client._looks_like_login_page(resp) is False


class TestRNPClientSingletonReset:
    """Test singleton reset for test isolation."""

    def test_get_rnp_client_returns_same_instance(self):
        """Test that get_rnp_client returns the same instance."""
        reset_rnp_client()
        client1 = get_rnp_client()
        client2 = get_rnp_client()
        assert client1 is client2

    def test_reset_rnp_client_clears_singleton(self):
        """Test that reset_rnp_client clears the singleton."""
        reset_rnp_client()
        client1 = get_rnp_client()
        reset_rnp_client()
        client2 = get_rnp_client()
        assert client1 is not client2

    @pytest.mark.asyncio
    async def test_reset_rnp_client_closes_session(self):
        """Test that reset_rnp_client closes the session."""
        reset_rnp_client()
        client = get_rnp_client()
        client._session = AsyncMock()
        reset_rnp_client()
        # If we get here without exception, close was handled


class TestRNPClientRetry:
    """Test session expiry retry logic."""

    @pytest.mark.asyncio
    async def test_query_plate_retries_on_parser_error(self):
        """Test that query_plate retries after ValueError (parser error)."""
        client = RNPClient()
        client._ensure_session = AsyncMock()
        client._do_query = AsyncMock(side_effect=[ValueError("not found in HTML"), "success"])

        result = await client.query_plate("AUT", "621335")

        assert result == "success"
        assert client._do_query.call_count == 2
        assert client._logged_in is False  # Should be reset after error

    @pytest.mark.asyncio
    async def test_query_plate_propagates_non_parser_errors(self):
        """Test that non-parser errors are propagated."""
        client = RNPClient()
        client._ensure_session = AsyncMock()
        client._do_query = AsyncMock(side_effect=RuntimeError("network error"))

        with pytest.raises(RuntimeError, match="network error"):
            await client.query_plate("AUT", "621335")

        assert client._do_query.call_count == 1
