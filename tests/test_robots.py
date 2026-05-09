# tests/test_robots.py

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta

from crawler.core.robots import RobotsCache


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_mock_response(status: int, text: str = "") -> AsyncMock:
    """Creates a mock aiohttp response as an async context manager."""
    response = AsyncMock()
    response.status = status
    response.text   = AsyncMock(return_value=text)

    context_manager = AsyncMock()
    context_manager.__aenter__ = AsyncMock(return_value=response)
    context_manager.__aexit__  = AsyncMock(return_value=False)
    return context_manager


def make_mock_session(status: int, text: str = "") -> MagicMock:
    """Creates a mock aiohttp session that returns the given response."""
    session      = MagicMock()
    session.get  = MagicMock(return_value=make_mock_response(status, text))
    return session


ROBOTS_TXT_DISALLOW_ADMIN = """
User-agent: *
Disallow: /admin/
Allow: /public/
Crawl-delay: 2
"""

ROBOTS_TXT_ALLOW_ALL = """
User-agent: *
Disallow:
"""


# ── is_allowed ────────────────────────────────────────────────────────────────

class TestIsAllowed:

    @pytest.mark.asyncio
    async def test_allowed_url_returns_true(self):
        cache   = RobotsCache()
        session = make_mock_session(200, ROBOTS_TXT_DISALLOW_ADMIN)

        result = await cache.is_allowed(
            "https://docs.python.org/3/tutorial/",
            session
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_disallowed_url_returns_false(self):
        cache   = RobotsCache()
        session = make_mock_session(200, ROBOTS_TXT_DISALLOW_ADMIN)

        result = await cache.is_allowed(
            "https://docs.python.org/admin/settings",
            session
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_missing_robots_txt_allows_all(self):
        cache   = RobotsCache()
        session = make_mock_session(404)

        result = await cache.is_allowed(
            "https://docs.python.org/3/tutorial/",
            session
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_robots_disabled_always_allows(self):
        cache   = RobotsCache()
        session = make_mock_session(200, ROBOTS_TXT_DISALLOW_ADMIN)

        with patch("crawler.core.robots.ROBOTS_TXT_ENABLED", False):
            result = await cache.is_allowed(
                "https://docs.python.org/admin/",
                session
            )
        assert result is True

    @pytest.mark.asyncio
    async def test_server_error_allows_by_default(self):
        cache   = RobotsCache()
        session = make_mock_session(500)

        result = await cache.is_allowed(
            "https://docs.python.org/3/tutorial/",
            session
        )
        assert result is True


# ── get_crawl_delay ───────────────────────────────────────────────────────────

class TestGetCrawlDelay:

    @pytest.mark.asyncio
    async def test_returns_crawl_delay_from_robots(self):
        cache   = RobotsCache()
        session = make_mock_session(200, ROBOTS_TXT_DISALLOW_ADMIN)

        delay = await cache.get_crawl_delay(
            "https://docs.python.org/3/",
            session
        )
        assert delay == 2.0

    @pytest.mark.asyncio
    async def test_returns_none_when_no_crawl_delay(self):
        cache   = RobotsCache()
        session = make_mock_session(200, ROBOTS_TXT_ALLOW_ALL)

        delay = await cache.get_crawl_delay(
            "https://docs.python.org/3/",
            session
        )
        assert delay is None

    @pytest.mark.asyncio
    async def test_returns_none_when_robots_disabled(self):
        cache   = RobotsCache()
        session = make_mock_session(200, ROBOTS_TXT_DISALLOW_ADMIN)

        with patch("crawler.core.robots.ROBOTS_TXT_ENABLED", False):
            delay = await cache.get_crawl_delay(
                "https://docs.python.org/3/",
                session
            )
        assert delay is None


# ── Caching ───────────────────────────────────────────────────────────────────

class TestCaching:

    @pytest.mark.asyncio
    async def test_robots_fetched_only_once_per_domain(self):
        cache   = RobotsCache()
        session = make_mock_session(200, ROBOTS_TXT_ALLOW_ALL)

        # Call is_allowed three times for the same domain
        await cache.is_allowed("https://docs.python.org/3/", session)
        await cache.is_allowed("https://docs.python.org/3/tutorial/", session)
        await cache.is_allowed("https://docs.python.org/3/library/", session)

        # Session.get should only have been called once
        assert session.get.call_count == 1

    @pytest.mark.asyncio
    async def test_different_domains_fetch_separately(self):
        cache   = RobotsCache()
        session = make_mock_session(200, ROBOTS_TXT_ALLOW_ALL)

        await cache.is_allowed("https://docs.python.org/3/", session)
        await cache.is_allowed("https://developer.mozilla.org/en-US/", session)

        assert session.get.call_count == 2

    @pytest.mark.asyncio
    async def test_expired_cache_refetches(self):
        cache   = RobotsCache()
        session = make_mock_session(200, ROBOTS_TXT_ALLOW_ALL)

        # First fetch
        await cache.is_allowed("https://docs.python.org/3/", session)
        assert session.get.call_count == 1

        # Manually expire the cache entry
        cache._cache["docs.python.org"]["fetched_at"] = (
            datetime.now(timezone.utc) - timedelta(seconds=9999)
        )

        # Second fetch — cache expired, should re-fetch
        await cache.is_allowed("https://docs.python.org/3/", session)
        assert session.get.call_count == 2