import asyncio
from datetime import datetime, timezone

import aiohttp

from crawler.config.settings import (
    CONCURRENT_REQUESTS,
    POLITENESS_DELAY,
    REQUEST_TIMEOUT,
)
from crawler.core.fetcher import Fetcher
from crawler.core.parser import Parser
from crawler.core.robots import RobotsCache
from crawler.models.request import CrawlRequest
from crawler.models.result import CrawlResult, CrawlStatus, PageRecord
from crawler.utils.logger import get_logger
from crawler.utils.url import (
    normalize_url,
    extract_domain,
    get_seed_path,
)

logger = get_logger(__name__)


# ── Politeness Manager ────────────────────────────────────────────────────────

class PolitenessManager:
    """
    Enforces per-domain request delays.
    Tracks the last request time for each domain and sleeps
    as needed before the next request to that domain.
    """

    def __init__(self, default_delay: float = POLITENESS_DELAY):
        self._default_delay = default_delay
        self._last_request:  dict[str, float] = {}
        self._domain_delays: dict[str, float] = {}

    def set_domain_delay(self, domain: str, delay: float) -> None:
        """
        Override the delay for a specific domain.
        Used when robots.txt specifies a Crawl-delay.
        The higher of robots.txt delay and default delay is used.
        """
        self._domain_delays[domain] = max(delay, self._default_delay)

    async def wait(self, url: str) -> None:
        """
        Waits the required delay before allowing a request to this domain.
        Updates last request time after waiting.
        """
        domain = extract_domain(url)
        delay  = self._domain_delays.get(domain, self._default_delay)

        if domain in self._last_request:
            elapsed = asyncio.get_event_loop().time() - self._last_request[domain]
            remaining = delay - elapsed
            if remaining > 0:
                logger.debug(f"Politeness delay {remaining:.2f}s for {domain}")
                await asyncio.sleep(remaining)

        self._last_request[domain] = asyncio.get_event_loop().time()


# ── Crawler ───────────────────────────────────────────────────────────────────

class Crawler:
    """
    Async web crawler.

    Manages a pool of worker coroutines that pull URLs from a shared
    frontier queue, fetch pages, extract links, and record results.

    Usage:
        async with Crawler() as crawler:
            result = await crawler.crawl(request)
    """

    def __init__(
        self,
        fetcher:    Fetcher      = None,
        parser:     Parser       = None,
        robots:     RobotsCache  = None,
    ):
        self._fetcher    = fetcher
        self._parser     = parser or Parser()
        self._robots     = robots or RobotsCache()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self) -> None:
        if self._fetcher is None:
            self._fetcher = Fetcher()
            await self._fetcher.start()

    async def close(self) -> None:
        if self._fetcher:
            await self._fetcher.close()

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    # ── Public Interface ──────────────────────────────────────────────────────

    async def crawl(self, request: CrawlRequest) -> CrawlResult:
        """
        Runs the full crawl and returns a CrawlResult.
        This is the only public method external code needs to call.
        """
        logger.info(f"Starting crawl: {request.seed_url}")
        logger.info(
            f"Limits: max_depth={request.max_depth} "
            f"max_pages={request.max_pages} "
            f"concurrent={request.concurrent_requests}"
        )

        # ── Shared State ──────────────────────────────────────────────────────
        frontier   = asyncio.Queue()
        visited    = set()
        result     = CrawlResult(seed_url=request.seed_url)
        politeness = PolitenessManager(request.politeness_delay)

        # Seed the frontier — crawl starts here
        seed_url = normalize_url(request.seed_url)
        await frontier.put((seed_url, 0))
        visited.add(seed_url)

        # ── Spawn Workers ─────────────────────────────────────────────────────
        workers = [
            asyncio.create_task(
                self._worker(
                    worker_id  = i,
                    frontier   = frontier,
                    visited    = visited,
                    result     = result,
                    request    = request,
                    politeness = politeness,
                )
            )
            for i in range(request.concurrent_requests)
        ]

        # Wait until frontier is empty AND all workers are idle
        try:
            await frontier.join()
        except Exception as e:
            logger.error(f"Crawl error: {e}")
            result.error = str(e)
            result.finish(CrawlStatus.FAILED)
        finally:
            # Cancel all workers — they're waiting on frontier.get()
            for worker in workers:
                worker.cancel()

            # Wait for all workers to finish cancelling
            await asyncio.gather(*workers, return_exceptions=True)

        # Set final status if not already set to FAILED
        if result.status == CrawlStatus.FAILED and not result.error:
            result.finish(CrawlStatus.SUCCESS)
        elif result.status != CrawlStatus.FAILED:
            result.finish(result.status)

        logger.info(f"Crawl complete: {result.summary()}")
        return result

    # ── Worker ────────────────────────────────────────────────────────────────

    async def _worker(
        self,
        worker_id:  int,
        frontier:   asyncio.Queue,
        visited:    set,
        result:     CrawlResult,
        request:    CrawlRequest,
        politeness: PolitenessManager,
    ) -> None:
        """
        A single worker coroutine.
        Runs in a loop pulling URLs from the frontier until cancelled.
        """
        logger.debug(f"Worker {worker_id} started")

        while True:
            try:
                url, depth = await frontier.get()
            except asyncio.CancelledError:
                logger.debug(f"Worker {worker_id} cancelled")
                break

            try:
                await self._process_page(
                    url        = url,
                    depth      = depth,
                    frontier   = frontier,
                    visited    = visited,
                    result     = result,
                    request    = request,
                    politeness = politeness,
                )
            except asyncio.CancelledError:
                frontier.task_done()
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} error processing {url}: {e}")
                result.urls_failed.append(url)
            finally:
                frontier.task_done()

    # ── Page Processing ───────────────────────────────────────────────────────

    async def _process_page(
        self,
        url:        str,
        depth:      int,
        frontier:   asyncio.Queue,
        visited:    set,
        result:     CrawlResult,
        request:    CrawlRequest,
        politeness: PolitenessManager,
    ) -> None:
        """
        Processes a single URL:
        - Checks robots.txt
        - Applies politeness delay
        - Fetches the page
        - Extracts and queues new links
        - Records the result
        """

        # ── Hard Limits ───────────────────────────────────────────────────────
        if len(result.urls_visited) >= request.max_pages:
            result.finish(CrawlStatus.MAX_PAGES_HIT)
            logger.info(f"MAX_PAGES ({request.max_pages}) reached")
            return

        # ── robots.txt Check ──────────────────────────────────────────────────
        allowed = await self._robots.is_allowed(url, self._fetcher._session)
        if not allowed:
            logger.debug(f"Blocked by robots.txt: {url}")
            return

        # ── Apply robots.txt Crawl-delay if present ───────────────────────────
        crawl_delay = await self._robots.get_crawl_delay(
            url, self._fetcher._session
        )
        if crawl_delay:
            politeness.set_domain_delay(extract_domain(url), crawl_delay)

        # ── Politeness Delay ──────────────────────────────────────────────────
        await politeness.wait(url)

        # ── Fetch ─────────────────────────────────────────────────────────────
        status_code, html = await self._fetcher.fetch(
            url,
            headers=request.headers
        )

        if status_code == -1 or not html:
            result.urls_failed.append(url)
            return

        # ── Record Visit ──────────────────────────────────────────────────────
        result.urls_visited.add(url)

        # Update max depth reached
        if depth > result.max_depth_reached:
            result.max_depth_reached = depth

        # ── Extract Links ─────────────────────────────────────────────────────
        new_links = []

        if depth < request.max_depth:
            new_links = self._parser.extract_links(
                html     = html,
                page_url = url,
                seed_url = request.seed_url,
                visited  = visited,
            )

            # Add new links to frontier and visited set atomically
            for link in new_links:
                if link not in visited:
                    visited.add(link)
                    await frontier.put((link, depth + 1))
        else:
            logger.debug(f"MAX_DEPTH ({request.max_depth}) reached at {url}")
            result.status = CrawlStatus.MAX_DEPTH_HIT

        # ── Record Page ───────────────────────────────────────────────────────
        result.pages.append(PageRecord(
            url         = url,
            depth       = depth,
            status_code = status_code,
            links_found = len(new_links),
        ))

        logger.info(
            f"[depth={depth}] {url} "
            f"→ {status_code} "
            f"links={len(new_links)}"
        )

    # ── Async Entry Point ─────────────────────────────────────────────────────

    @staticmethod
    def run(request: CrawlRequest) -> CrawlResult:
        """
        Synchronous entry point for running the crawler.
        Handles creating and closing the event loop.
        Used by main.py so the CLI doesn't need to know about asyncio.
        """
        async def _run():
            async with Crawler() as crawler:
                return await crawler.crawl(request)

        return asyncio.run(_run())