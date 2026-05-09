# crawler/core/robots.py

import asyncio
from datetime import datetime, timezone
from urllib.robotparser import RobotFileParser
from urllib.parse import urlparse

import aiohttp

from crawler.config.settings import (
    ROBOTS_TXT_ENABLED,
    ROBOTS_TXT_CACHE_TTL,
    REQUEST_TIMEOUT,
)
from crawler.utils.logger import get_logger
from crawler.utils.url import extract_domain

logger = get_logger(__name__)


class RobotsCache:
    """
    Fetches, parses, and caches robots.txt files per domain.

    - One robots.txt fetch per domain per TTL period
    - Gracefully handles missing robots.txt (404 → allow all)
    - Extracts Crawl-delay for the politeness manager
    - Thread-safe via asyncio.Lock per domain
    """

    def __init__(self):
        # { domain: {"parser": RobotFileParser, "fetched_at": datetime} }
        self._cache: dict = {}

        # Per-domain locks — prevent multiple coroutines fetching
        # the same robots.txt simultaneously
        self._locks: dict[str, asyncio.Lock] = {}

    # ── Public Interface ──────────────────────────────────────────────────────

    async def is_allowed(
        self,
        url: str,
        session: aiohttp.ClientSession,
        user_agent: str = "*"
    ) -> bool:
        """
        Returns True if the crawler is allowed to fetch this URL.
        Always returns True if ROBOTS_TXT_ENABLED is False.
        """
        if not ROBOTS_TXT_ENABLED:
            return True

        parser = await self._get_parser(url, session)

        if parser is None:
            # Could not fetch or parse robots.txt — allow by default
            return True

        allowed = parser.can_fetch(user_agent, url)
        if not allowed:
            logger.debug(f"robots.txt disallows: {url}")

        return allowed

    async def get_crawl_delay(
        self,
        url: str,
        session: aiohttp.ClientSession,
        user_agent: str = "*"
    ) -> float | None:
        """
        Returns the Crawl-delay specified in robots.txt for this domain.
        Returns None if no Crawl-delay is set.
        The politeness manager uses this to override the default delay.
        """
        if not ROBOTS_TXT_ENABLED:
            return None

        parser = await self._get_parser(url, session)

        if parser is None:
            return None

        return parser.crawl_delay(user_agent)

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _get_parser(
        self,
        url: str,
        session: aiohttp.ClientSession
    ) -> RobotFileParser | None:
        """
        Returns a cached parser for the domain, fetching if needed.
        Uses a per-domain lock to prevent duplicate fetches.
        """
        domain = extract_domain(url)

        # Ensure a lock exists for this domain
        if domain not in self._locks:
            self._locks[domain] = asyncio.Lock()

        async with self._locks[domain]:
            # Check cache inside the lock
            if self._is_cache_fresh(domain):
                return self._cache[domain]["parser"]

            # Cache miss or expired — fetch fresh
            parser = await self._fetch_robots(domain, session)
            self._cache[domain] = {
                "parser":     parser,
                "fetched_at": datetime.now(timezone.utc),
            }
            return parser

    def _is_cache_fresh(self, domain: str) -> bool:
        """Returns True if the cached robots.txt is still within TTL."""
        if domain not in self._cache:
            return False

        fetched_at = self._cache[domain]["fetched_at"]
        age = (datetime.now(timezone.utc) - fetched_at).total_seconds()
        return age < ROBOTS_TXT_CACHE_TTL

    async def _fetch_robots(
        self,
        domain: str,
        session: aiohttp.ClientSession
    ) -> RobotFileParser | None:
        """
        Fetches and parses robots.txt for a domain.
        Returns None on any failure — caller treats None as allow-all.
        """
        # Try https first, fall back to http
        for scheme in ("https", "http"):
            robots_url = f"{scheme}://{domain}/robots.txt"
            try:
                async with session.get(
                    robots_url,
                    timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
                ) as response:

                    if response.status == 404:
                        logger.debug(f"No robots.txt found for {domain} — allowing all")
                        return self._allow_all_parser(robots_url)

                    if response.status != 200:
                        logger.warning(
                            f"Unexpected status {response.status} "
                            f"fetching robots.txt for {domain}"
                        )
                        return None

                    content = await response.text()
                    parser  = RobotFileParser()
                    parser.set_url(robots_url)
                    parser.parse(content.splitlines())

                    logger.debug(f"Fetched robots.txt for {domain}")
                    return parser

            except asyncio.TimeoutError:
                logger.warning(f"Timeout fetching robots.txt for {domain}")
                return None
            except Exception as e:
                logger.warning(f"Error fetching robots.txt for {domain}: {e}")
                return None

        return None

    def _allow_all_parser(self, robots_url: str) -> RobotFileParser:
        """
        Returns a parser that allows everything.
        Used when robots.txt is missing (404).
        """
        parser = RobotFileParser()
        parser.set_url(robots_url)
        parser.parse([])            # empty rules = allow all
        return parser