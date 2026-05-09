# main.py

import argparse
import sys

from crawler.config.settings import (
    DEFAULT_URL,
    MAX_DEPTH,
    MAX_PAGES,
    CONCURRENT_REQUESTS,
    POLITENESS_DELAY,
    REQUEST_TIMEOUT,
)
from crawler.core.crawler import Crawler
from crawler.models.request import CrawlRequest
from crawler.models.result import CrawlStatus
from crawler.storage.json_storage import JsonStorage
from crawler.utils.logger import get_logger

logger = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pure Python web crawler — discovers and records URLs within a path scope.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "url",
        nargs="?",
        default=DEFAULT_URL,
        help="Seed URL to start crawling from",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=MAX_DEPTH,
        help="Maximum link-hops from the seed URL",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=MAX_PAGES,
        help="Maximum total pages to crawl",
    )
    parser.add_argument(
        "--concurrent",
        type=int,
        default=CONCURRENT_REQUESTS,
        help="Number of concurrent requests",
    )
    parser.add_argument(
        "--politeness",
        type=float,
        default=POLITENESS_DELAY,
        help="Minimum delay in seconds between requests to the same domain",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=REQUEST_TIMEOUT,
        help="Request timeout in seconds",
    )
    parser.add_argument(
        "--proxy",
        type=str,
        default=None,
        help="Proxy URL (e.g. http://user:pass@host:port)",
    )
    parser.add_argument(
        "--no-robots",
        action="store_true",
        default=False,
        help="Ignore robots.txt (use responsibly)",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        default=False,
        help="Print results to console without saving to disk",
    )

    return parser.parse_args()


def run(args: argparse.Namespace) -> int:
    """
    Core logic — separated from __main__ so it can be called in tests.
    Returns exit code: 0 for success, 1 for failure.
    """

    # ── Build Request ─────────────────────────────────────────────────────────
    try:
        request = CrawlRequest(
            seed_url            = args.url,
            max_depth           = args.max_depth,
            max_pages           = args.max_pages,
            concurrent_requests = args.concurrent,
            politeness_delay    = args.politeness,
            timeout             = args.timeout,
            proxy               = args.proxy,
            respect_robots_txt  = not args.no_robots,
        )
    except ValueError as e:
        print(f"\n❌ Invalid arguments: {e}")
        return 1

    # ── Print Crawl Config ────────────────────────────────────────────────────
    print(f"""
╔══════════════════════════════════════════════════╗
║              Pure Python Web Crawler             ║
╚══════════════════════════════════════════════════╝
  Seed URL    : {request.seed_url}
  Max depth   : {request.max_depth}
  Max pages   : {request.max_pages}
  Concurrent  : {request.concurrent_requests}
  Politeness  : {request.politeness_delay}s
  Robots.txt  : {"respected" if request.respect_robots_txt else "ignored"}
  Proxy       : {request.proxy or "none"}
""")

    # ── Run Crawl ─────────────────────────────────────────────────────────────
    try:
        result = Crawler.run(request)
    except Exception as e:
        print(f"\n❌ Crawl failed with unexpected error: {e}")
        logger.exception("Unexpected error during crawl")
        return 1

    # ── Print Summary ─────────────────────────────────────────────────────────
    status_icon = "✅" if result.status == CrawlStatus.SUCCESS else "⚠️"

    print(f"""
══════════════════════════════════════════════════
  {status_icon}  Crawl Complete
══════════════════════════════════════════════════
  Status        : {result.status.value}
  Total pages   : {result.total_pages}
  Failed URLs   : {len(result.urls_failed)}
  Max depth hit : {result.max_depth_reached}
  Duration      : {f"{result.duration_seconds:.1f}s" if result.duration_seconds else "N/A"}
""")

    # ── Print Visited URLs ────────────────────────────────────────────────────
    if result.urls_visited:
        print("  Pages crawled (first 10):")
        for url in sorted(result.urls_visited)[:10]:
            print(f"    {url}")
        if len(result.urls_visited) > 10:
            print(f"    ... and {len(result.urls_visited) - 10} more")

    # ── Print Failed URLs ─────────────────────────────────────────────────────
    if result.urls_failed:
        print(f"\n  Failed URLs (first 5):")
        for url in result.urls_failed[:5]:
            print(f"    ✗ {url}")

    # ── Save Result ───────────────────────────────────────────────────────────
    if not args.no_save:
        storage = JsonStorage()
        saved   = storage.save(result)

        if saved:
            print(f"\n  💾 Result saved to output/")
        else:
            print(f"\n  ⚠️  Failed to save result to disk")
    else:
        print("\n  ℹ️  --no-save flag set — result not saved")

    print()

    # ── Exit Code ─────────────────────────────────────────────────────────────
    return 0 if result.status in (
        CrawlStatus.SUCCESS,
        CrawlStatus.MAX_PAGES_HIT,
        CrawlStatus.MAX_DEPTH_HIT,
    ) else 1


if __name__ == "__main__":
    args = parse_args()
    sys.exit(run(args))