from dataclasses import dataclass, field
from crawler.config.settings import (
    REQUEST_TIMEOUT,
    MAX_DEPTH,
    MAX_PAGES,
    CONCURRENT_REQUESTS,
    POLITENESS_DELAY,
)


@dataclass
class CrawlRequest:
    """
    Input contract for the crawler.
    Defines everything needed to start and control a crawl.
    """

    # ── Required ──────────────────────────────────────────────────────────────
    seed_url: str                               # where the crawl starts

    # ── Crawl Limits ──────────────────────────────────────────────────────────
    max_depth:           int   = MAX_DEPTH
    max_pages:           int   = MAX_PAGES

    # ── Concurrency & Politeness ──────────────────────────────────────────────
    concurrent_requests: int   = CONCURRENT_REQUESTS
    politeness_delay:    float = POLITENESS_DELAY

    # ── HTTP ──────────────────────────────────────────────────────────────────
    timeout:             int   = REQUEST_TIMEOUT
    headers:             dict  = field(default_factory=dict)
    proxy:               str   = None

    # ── Behaviour ─────────────────────────────────────────────────────────────
    respect_robots_txt:  bool  = True

    def __post_init__(self):
        self._validate()
        self._normalize()

    def _validate(self):
        if not self.seed_url:
            raise ValueError("seed_url cannot be empty")
        if not self.seed_url.startswith(("http://", "https://")):
            raise ValueError(f"seed_url must start with http:// or https://: {self.seed_url}")
        if self.max_depth < 0:
            raise ValueError("max_depth cannot be negative")
        if self.max_pages < 1:
            raise ValueError("max_pages must be at least 1")
        if self.concurrent_requests < 1:
            raise ValueError("concurrent_requests must be at least 1")
        if self.politeness_delay < 0:
            raise ValueError("politeness_delay cannot be negative")
        if self.timeout < 1:
            raise ValueError("timeout must be at least 1 second")

    def _normalize(self):
        self.seed_url = self.seed_url.strip()

        # Remove fragment — #section has no meaning for crawling
        if "#" in self.seed_url:
            self.seed_url = self.seed_url.split("#")[0]