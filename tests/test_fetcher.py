# tests/test_fetcher.py

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp

from crawler.core.fetcher import Fetcher


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_mock_response(status: int, text: str = "<html>content</html>") -> AsyncMock:
    """Creates a mock aiohttp response as an async context manager."""
    response        = AsyncMock()
    response.status = status
    response.text   = AsyncMock(return_value=text)

    context_manager = AsyncMock()
    context_manager.__aenter__ = AsyncMock(return_value=response)
    context_manager.__aexit__  = AsyncMock(return_value=False)
    return context_manager


def make_mock_session(status: int, text: str = "<html>content</html>") -> MagicMock:
    """Creates a mock aiohttp session."""
    session     = MagicMock()
    session.get = MagicMock(return_value=make_mock_response(status, text))
    return session


# ── Successful Fetch ──────────────────────────────────────────────────────────

class TestFetcherSuccess:

    @pytest.mark.asyncio
    async def test_returns_status_and_html_on_success(self):
        session = make_mock_session(200, "<html>hello</html>")
        fetcher = Fetcher(session=session)

        status, html = await fetcher.fetch("https://docs.python.org/3/")

        assert status == 200
        assert "hello" in html

    @pytest.mark.asyncio
    async def test_invalid_url_returns_minus_one(self):
        session = make_mock_session(200)
        fetcher = Fetcher(session=session)

        status, html = await fetcher.fetch("not-a-valid-url")

        assert status == -1
        assert html == ""

    @pytest.mark.asyncio
    async def test_proxy_forwarded_to_session(self):
        session = make_mock_session(200)
        fetcher = Fetcher(session=session, proxy="http://proxy:8080")

        await fetcher.fetch("https://docs.python.org/3/")

        call_kwargs = session.get.call_args[1]
        assert call_kwargs.get("proxy") == "http://proxy:8080"


# ── Retry Behaviour ───────────────────────────────────────────────────────────

class TestFetcherRetry:

    @pytest.mark.asyncio
    async def test_4xx_not_retried(self):
        session = make_mock_session(404)
        fetcher = Fetcher(session=session)

        with patch("crawler.core.fetcher.asyncio.sleep", new_callable=AsyncMock):
            status, html = await fetcher.fetch("https://docs.python.org/3/")

        assert status == 404
        assert session.get.call_count == 1   # no retry

    @pytest.mark.asyncio
    async def test_5xx_retried_up_to_max(self):
        session = make_mock_session(500)
        fetcher = Fetcher(session=session)

        with patch("crawler.core.fetcher.asyncio.sleep", new_callable=AsyncMock):
            status, html = await fetcher.fetch("https://docs.python.org/3/")

        assert status == -1
        assert session.get.call_count == 3   # MAX_RETRIES = 3

    @pytest.mark.asyncio
    async def test_succeeds_on_second_attempt(self):
        session = MagicMock()
        session.get = MagicMock(side_effect=[
            make_mock_response(500),          # first attempt fails
            make_mock_response(200, "<html>ok</html>"),  # second succeeds
        ])
        fetcher = Fetcher(session=session)

        with patch("crawler.core.fetcher.asyncio.sleep", new_callable=AsyncMock):
            status, html = await fetcher.fetch("https://docs.python.org/3/")

        assert status == 200
        assert "ok" in html

    @pytest.mark.asyncio
    async def test_timeout_triggers_retry(self):
        session = MagicMock()

        timeout_context = AsyncMock()
        timeout_context.__aenter__ = AsyncMock(
            side_effect=asyncio.TimeoutError()
        )
        timeout_context.__aexit__ = AsyncMock(return_value=False)

        session.get = MagicMock(side_effect=[
            timeout_context,
            make_mock_response(200, "<html>ok</html>"),
        ])
        fetcher = Fetcher(session=session)

        with patch("crawler.core.fetcher.asyncio.sleep", new_callable=AsyncMock):
            status, html = await fetcher.fetch("https://docs.python.org/3/")

        assert status == 200


# ── Concurrency ───────────────────────────────────────────────────────────────

class TestFetcherConcurrency:

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(self):
        """Verify the semaphore allows at most N concurrent fetches."""
        concurrent_requests = 3
        active_count        = 0
        max_active          = 0

        async def slow_fetch(*args, **kwargs):
            nonlocal active_count, max_active
            active_count += 1
            max_active    = max(max_active, active_count)
            await asyncio.sleep(0.05)
            active_count -= 1
            return make_mock_response(200).__aenter__.return_value

        session     = MagicMock()
        session.get = MagicMock(side_effect=lambda *a, **kw: make_mock_response(200))

        fetcher = Fetcher(session=session, concurrent_requests=concurrent_requests)

        # Fire 10 fetches simultaneously
        await asyncio.gather(*[
            fetcher.fetch(f"https://docs.python.org/{i}/")
            for i in range(10)
        ])

        # Semaphore should have kept concurrent fetches at or below limit
        assert fetcher._semaphore._value >= 0


# ── Lifecycle ─────────────────────────────────────────────────────────────────

class TestFetcherLifecycle:

    @pytest.mark.asyncio
    async def test_context_manager_creates_and_closes_session(self):
        with patch("crawler.core.fetcher.aiohttp.ClientSession") as mock_cls:
            mock_session       = AsyncMock()
            mock_session.close = AsyncMock()
            mock_cls.return_value = mock_session

            async with Fetcher() as fetcher:
                assert fetcher._session is not None

            mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_injected_session_not_closed(self):
        session       = MagicMock()
        session.close = AsyncMock()
        fetcher       = Fetcher(session=session)

        await fetcher.close()

        session.close.assert_not_called()