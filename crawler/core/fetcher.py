# crawler/core/fetcher.py

import asyncio
import aiohttp

from crawler.config.settings import (
    REQUEST_TIMEOUT,
    MAX_RETRIES,
    RETRY_DELAY,
    CONCURRENT_REQUESTS,
)
from crawler.utils.logger import get_logger
from crawler.utils.url import is_valid_url

logger = get_logger(__name__)


class Fetcher:
    """
    Async HTTP fetcher for the crawler.

    - Uses aiohttp for non-blocking requests
    - Enforces concurrency limit via asyncio.Semaphore
    - Retries on transient failures with exponential backoff
    - Returns (status_code, html) tuple — never raises
    """

    def __init__(
        self,
        session:              aiohttp.ClientSession = None,
        concurrent_requests:  int                   = CONCURRENT_REQUESTS,
        timeout:              int                   = REQUEST_TIMEOUT,
        proxy:                str                   = None,
    ):
        self._session              = session
        self._semaphore            = asyncio.Semaphore(concurrent_requests)
        self._timeout              = aiohttp.ClientTimeout(total=timeout)
        self._proxy                = proxy
        self._owns_session         = session is None   # tracks if we created it

    # ── Session Lifecycle ─────────────────────────────────────────────────────

    async def start(self) -> None:
        """Creates the aiohttp session if one wasn't injected."""
        if self._session is None:
            self._session = aiohttp.ClientSession(timeout=self._timeout)

    async def close(self) -> None:
        """Closes the session — only if this fetcher created it."""
        if self._session and self._owns_session:
            await self._session.close()
            self._session = None

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    # ── Public Interface ──────────────────────────────────────────────────────

    async def fetch(self, url: str, headers: dict = None) -> tuple[int, str]:
        """
        Fetches a URL and returns (status_code, html).

        Returns (-1, "") on complete failure after all retries.
        Never raises — all exceptions are caught and logged.
        """
        if not is_valid_url(url):
            logger.warning(f"Invalid URL skipped: {url}")
            return -1, ""

        async with self._semaphore:
            return await self._fetch_with_retry(url, headers or {})

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _fetch_with_retry(
        self,
        url:     str,
        headers: dict,
    ) -> tuple[int, str]:
        """
        Attempts to fetch a URL up to MAX_RETRIES times.
        Uses exponential backoff between attempts.
        """
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                status, html = await self._fetch_once(url, headers)

                # 4xx — client error, retrying won't help
                if 400 <= status < 500:
                    logger.warning(f"Client error {status} for {url} — not retrying")
                    return status, ""

                # 2xx — success
                if status < 400:
                    return status, html

                # 5xx — server error, retry
                logger.warning(f"Server error {status} for {url} — attempt {attempt}/{MAX_RETRIES}")

            except asyncio.TimeoutError:
                logger.warning(f"Timeout fetching {url} — attempt {attempt}/{MAX_RETRIES}")

            except aiohttp.ClientConnectionError:
                logger.warning(f"Connection error fetching {url} — attempt {attempt}/{MAX_RETRIES}")

            except Exception as e:
                logger.error(f"Unexpected error fetching {url}: {e}")
                return -1, ""

            # Exponential backoff before next attempt
            if attempt < MAX_RETRIES:
                wait = RETRY_DELAY * (2 ** (attempt - 1))
                logger.debug(f"Retrying {url} in {wait}s")
                await asyncio.sleep(wait)

        logger.error(f"All {MAX_RETRIES} attempts failed for {url}")
        return -1, ""

    async def _fetch_once(
        self,
        url:     str,
        headers: dict,
    ) -> tuple[int, str]:
        """
        Makes a single HTTP GET request.
        Returns (status_code, html).
        """
        kwargs = {
            "headers": headers,
            "allow_redirects": True,
            "ssl": False,           # don't verify SSL — avoids failures on
                                    # sites with self-signed certs
        }

        if self._proxy:
            kwargs["proxy"] = self._proxy

        async with self._session.get(url, **kwargs) as response:
            html = await response.text(errors="replace")
            logger.debug(f"Fetched {url} → {response.status}")
            return response.status, html