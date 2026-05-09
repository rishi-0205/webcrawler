# tests/test_crawler.py

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from crawler.core.crawler import Crawler, PolitenessManager
from crawler.core.fetcher import Fetcher
from crawler.core.parser import Parser
from crawler.core.robots import RobotsCache
from crawler.models.request import CrawlRequest
from crawler.models.result import CrawlResult, CrawlStatus


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_request(**kwargs) -> CrawlRequest:
    """Creates a CrawlRequest with safe test defaults."""
    defaults = {
        "seed_url":            "https://docs.python.org/3/",
        "max_depth":           2,
        "max_pages":           10,
        "concurrent_requests": 2,
        "politeness_delay":    0,    # no delay in tests
        "respect_robots_txt":  False,
    }
    defaults.update(kwargs)
    return CrawlRequest(**defaults)


def make_fetcher(status: int = 200, html: str = None) -> MagicMock:
    """Creates a mock Fetcher that returns the given status and html."""
    if html is None:
        html = (
            "<html><body>"
            "<a href='/3/tutorial/'>tutorial</a>"
            "<a href='/3/library/'>library</a>"
            "</body></html>"
        )
    fetcher        = MagicMock(spec=Fetcher)
    fetcher.fetch  = AsyncMock(return_value=(status, html))
    fetcher.close  = AsyncMock()
    fetcher._session = MagicMock()
    return fetcher


def make_robots(allowed: bool = True) -> MagicMock:
    """Creates a mock RobotsCache."""
    robots                  = MagicMock(spec=RobotsCache)
    robots.is_allowed       = AsyncMock(return_value=allowed)
    robots.get_crawl_delay  = AsyncMock(return_value=None)
    return robots


# ── Crawl Pipeline ────────────────────────────────────────────────────────────

class TestCrawlPipeline:

    @pytest.mark.asyncio
    async def test_successful_crawl_returns_success_status(self):
        fetcher = make_fetcher(200, "<html><body>no links here</body></html>")
        crawler = Crawler(fetcher=fetcher, robots=make_robots())

        result = await crawler.crawl(make_request(max_depth=0))

        assert result.status in (CrawlStatus.SUCCESS, CrawlStatus.MAX_DEPTH_HIT)
        assert result.seed_url == "https://docs.python.org/3/"

    @pytest.mark.asyncio
    async def test_seed_url_is_always_visited(self):
        fetcher = make_fetcher(200, "<html><body>no links</body></html>")
        crawler = Crawler(fetcher=fetcher, robots=make_robots())

        result = await crawler.crawl(make_request(max_depth=0))

        assert len(result.urls_visited) >= 1

    @pytest.mark.asyncio
    async def test_failed_fetch_recorded_in_urls_failed(self):
        fetcher = make_fetcher(-1, "")
        crawler = Crawler(fetcher=fetcher, robots=make_robots())

        result = await crawler.crawl(make_request(max_depth=0))

        assert len(result.urls_failed) >= 1

    @pytest.mark.asyncio
    async def test_result_has_timing_info(self):
        fetcher = make_fetcher(200, "<html><body>no links</body></html>")
        crawler = Crawler(fetcher=fetcher, robots=make_robots())

        result = await crawler.crawl(make_request(max_depth=0))

        assert result.started_at  is not None
        assert result.finished_at is not None
        assert result.duration_seconds >= 0


# ── Depth Control ─────────────────────────────────────────────────────────────

class TestDepthControl:

    @pytest.mark.asyncio
    async def test_max_depth_zero_crawls_only_seed(self):
        fetcher = make_fetcher(200)
        crawler = Crawler(fetcher=fetcher, robots=make_robots())

        result = await crawler.crawl(make_request(max_depth=0))

        # With max_depth=0, links are extracted but not followed
        # Only the seed URL should be fetched
        assert fetcher.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_links_not_extracted_at_max_depth(self):
        # Page has links but we're at max depth — they should not be queued
        html    = "<html><body><a href='/3/other/'>link</a></body></html>"
        fetcher = make_fetcher(200, html)
        crawler = Crawler(fetcher=fetcher, robots=make_robots())

        result = await crawler.crawl(make_request(max_depth=0))

        # Only seed URL fetched — link not followed
        assert fetcher.fetch.call_count == 1


# ── Page Limits ───────────────────────────────────────────────────────────────

class TestPageLimits:

    @pytest.mark.asyncio
    async def test_max_pages_stops_crawl(self):
        # Give it links to follow but limit to 1 page
        fetcher = make_fetcher(200)
        crawler = Crawler(fetcher=fetcher, robots=make_robots())

        result = await crawler.crawl(make_request(max_pages=1, max_depth=3))

        assert result.total_pages <= 1


# ── robots.txt Enforcement ────────────────────────────────────────────────────

class TestRobotsEnforcement:

    @pytest.mark.asyncio
    async def test_disallowed_url_not_fetched(self):
        fetcher = make_fetcher(200, "<html><body>no links</body></html>")
        robots  = make_robots(allowed=False)
        crawler = Crawler(fetcher=fetcher, robots=robots)

        result = await crawler.crawl(make_request())

        # robots.txt blocked everything — fetcher never called
        assert fetcher.fetch.call_count == 0

    @pytest.mark.asyncio
    async def test_crawl_delay_applied_from_robots(self):
        fetcher              = make_fetcher(200, "<html><body>no links</body></html>")
        robots               = make_robots(allowed=True)
        robots.get_crawl_delay = AsyncMock(return_value=0.0)
        crawler              = Crawler(fetcher=fetcher, robots=robots)

        result = await crawler.crawl(make_request(max_depth=0))

        # Crawl delay was checked
        robots.get_crawl_delay.assert_called()


# ── Politeness Manager ────────────────────────────────────────────────────────

class TestPolitenessManager:

    @pytest.mark.asyncio
    async def test_no_delay_on_first_request(self):
        pm = PolitenessManager(default_delay=1.0)

        with patch("crawler.core.crawler.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await pm.wait("https://docs.python.org/3/")
            mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_delay_applied_on_second_request_to_same_domain(self):
        pm = PolitenessManager(default_delay=1.0)

        # Simulate first request happened just now
        import asyncio as _asyncio
        pm._last_request["docs.python.org"] = _asyncio.get_event_loop().time()

        with patch("crawler.core.crawler.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await pm.wait("https://docs.python.org/3/tutorial/")
            mock_sleep.assert_called_once()

    def test_robots_delay_overrides_default_when_higher(self):
        pm = PolitenessManager(default_delay=1.0)
        pm.set_domain_delay("docs.python.org", 3.0)
        assert pm._domain_delays["docs.python.org"] == 3.0

    def test_default_used_when_robots_delay_is_lower(self):
        pm = PolitenessManager(default_delay=2.0)
        pm.set_domain_delay("docs.python.org", 0.5)
        # Default (2.0) wins because it's higher
        assert pm._domain_delays["docs.python.org"] == 2.0


# ── Context Manager ───────────────────────────────────────────────────────────

class TestCrawlerContextManager:

    @pytest.mark.asyncio
    async def test_close_called_on_normal_exit(self):
        fetcher = make_fetcher(200, "<html><body>no links</body></html>")
        crawler = Crawler(fetcher=fetcher, robots=make_robots())

        async with crawler:
            await crawler.crawl(make_request(max_depth=0))

        fetcher.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_called_on_exception(self):
        fetcher = make_fetcher(200)
        crawler = Crawler(fetcher=fetcher, robots=make_robots())

        with pytest.raises(ValueError):
            async with crawler:
                raise ValueError("something went wrong")

        fetcher.close.assert_called_once()