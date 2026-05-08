# crawler/models/result.py

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class CrawlStatus(Enum):
    """
    How the crawl ended.
    Knowing WHY it stopped is as important as knowing that it stopped.
    """
    SUCCESS        = "success"          # completed normally
    MAX_PAGES_HIT  = "max_pages_hit"    # stopped because MAX_PAGES was reached
    MAX_DEPTH_HIT  = "max_depth_hit"    # stopped because MAX_DEPTH was reached
    CANCELLED      = "cancelled"        # manually stopped
    FAILED         = "failed"           # crashed with an unrecoverable error


@dataclass
class PageRecord:
    """
    A record of a single page visited during the crawl.
    The crawler stores one of these per URL it successfully fetches.
    """
    url:          str
    depth:        int
    status_code:  int
    links_found:  int                   # how many valid links were extracted
    crawled_at:   datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error:        str      = None


@dataclass
class CrawlResult:
    """
    Output contract for the crawler.
    Represents the complete result of one crawl run.
    """

    # ── Identity ──────────────────────────────────────────────────────────────
    seed_url:      str

    # ── Outcome ───────────────────────────────────────────────────────────────
    status:        CrawlStatus         = CrawlStatus.FAILED
    error:         str                 = None

    # ── Discovered URLs ───────────────────────────────────────────────────────
    pages:         list[PageRecord]    = field(default_factory=list)
    urls_visited:  set[str]            = field(default_factory=set)
    urls_failed:   list[str]           = field(default_factory=list)

    # ── Stats ─────────────────────────────────────────────────────────────────
    total_pages:   int                 = 0
    max_depth_reached: int             = 0

    # ── Timing ────────────────────────────────────────────────────────────────
    started_at:    datetime            = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at:   datetime            = None

    def finish(self, status: CrawlStatus) -> None:
        """Call this when the crawl ends to record final state."""
        self.status      = status
        self.finished_at = datetime.now(timezone.utc)
        self.total_pages = len(self.urls_visited)

    @property
    def duration_seconds(self) -> float | None:
        """How long the crawl took in seconds."""
        if self.finished_at is None:
            return None
        return (self.finished_at - self.started_at).total_seconds()

    def summary(self) -> str:
        """Single-line human-readable summary for logging."""
        duration = f"{self.duration_seconds:.1f}s" if self.duration_seconds else "ongoing"
        return (
            f"seed={self.seed_url} "
            f"status={self.status.value} "
            f"pages={self.total_pages} "
            f"failed={len(self.urls_failed)} "
            f"max_depth_reached={self.max_depth_reached} "
            f"duration={duration}"
        )

    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict for storage."""
        return {
            "seed_url":          self.seed_url,
            "status":            self.status.value,
            "error":             self.error,
            "total_pages":       self.total_pages,
            "max_depth_reached": self.max_depth_reached,
            "urls_visited":      sorted(self.urls_visited),
            "urls_failed":       self.urls_failed,
            "pages": [
                {
                    "url":         p.url,
                    "depth":       p.depth,
                    "status_code": p.status_code,
                    "links_found": p.links_found,
                    "crawled_at":  p.crawled_at.isoformat(),
                    "error":       p.error,
                }
                for p in self.pages
            ],
            "started_at":  self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_seconds": self.duration_seconds,
        }