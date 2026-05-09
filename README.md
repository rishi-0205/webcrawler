# webcrawler

A production-grade, pure Python web crawler built from scratch with no third-party crawling frameworks. Accepts a seed URL, discovers all pages within that URL's path scope using async concurrent fetching, respects robots.txt, enforces politeness delays, and saves the full crawl result as a JSON file.

---

## Features

- **Path-scoped crawling** — stays within the seed URL's path, never drifts to unrelated sections of the same domain
- **Async concurrency** — fetches multiple pages simultaneously using `aiohttp` and `asyncio` for fast crawling
- **robots.txt enforcement** — fetches, parses, and respects each domain's robots.txt with per-domain caching
- **Politeness manager** — enforces configurable per-domain delays; respects `Crawl-delay` from robots.txt
- **Exponential backoff** — retries failed requests with increasing wait times (2s → 4s → 8s)
- **Smart retry logic** — retries server errors (5xx) but never client errors (4xx) that won't resolve
- **Depth and page limits** — configurable `MAX_DEPTH` and `MAX_PAGES` to control crawl scope
- **Proxy support** — architecture is proxy-aware from day one via optional proxy field
- **Structured logging** — logs to both console and file with timestamps, log levels, and module tracking
- **Abstract storage** — swappable storage backends via abstract base class (JSON now, PostgreSQL later)
- **Clean data models** — strict typed `dataclasses` for input and output contracts
- **75 passing tests** — full test suite with zero real HTTP requests (all mocked)
- **CLI interface** — run from terminal with seed URL and configurable flags

---

## Table of Contents

- [Installation](#installation)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Architecture](#architecture)
- [File Breakdown](#file-breakdown)
- [Configuration](#configuration)
- [Testing](#testing)
- [Design Decisions](#design-decisions)

---

## Installation

**1. Clone the repository**
```bash
git clone https://github.com/yourusername/webcrawler.git
cd webcrawler
```

**2. Create and activate a virtual environment**
```bash
# Create
python -m venv venv

# Activate — Windows
venv\Scripts\activate

# Activate — Mac/Linux
source venv/bin/activate
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
```

---

## Usage

**Crawl the default URL** *(set `DEFAULT_URL` in `settings.py`)*
```bash
python main.py
```

**Crawl a specific URL**
```bash
python main.py https://docs.python.org/3/
```

**Custom depth and page limits**
```bash
python main.py https://docs.python.org/3/ --max-depth 2 --max-pages 50
```

**Adjust concurrency and politeness**
```bash
python main.py https://docs.python.org/3/ --concurrent 20 --politeness 0.5
```

**Print result without saving to file**
```bash
python main.py https://docs.python.org/3/ --no-save
```

**Ignore robots.txt**
```bash
python main.py https://docs.python.org/3/ --no-robots
```

**Use a proxy**
```bash
python main.py https://docs.python.org/3/ --proxy http://user:pass@host:port
```

### Example Output

```
╔══════════════════════════════════════════════════╗
║              Pure Python Web Crawler             ║
╚══════════════════════════════════════════════════╝
  Seed URL    : https://docs.python.org/3/
  Max depth   : 4
  Max pages   : 1000
  Concurrent  : 10
  Politeness  : 1.0s
  Robots.txt  : respected
  Proxy       : none

══════════════════════════════════════════════════
  ✅  Crawl Complete
══════════════════════════════════════════════════
  Status        : success
  Total pages   : 342
  Failed URLs   : 2
  Max depth hit : 4
  Duration      : 87.4s

  Pages crawled (first 10):
    https://docs.python.org/3/
    https://docs.python.org/3/tutorial/
    https://docs.python.org/3/tutorial/interpreter.html
    https://docs.python.org/3/library/
    https://docs.python.org/3/library/os.html
    https://docs.python.org/3/reference/
    https://docs.python.org/3/reference/datamodel.html
    https://docs.python.org/3/howto/
    https://docs.python.org/3/whatsnew/3.13.html
    https://docs.python.org/3/glossary.html
    ... and 332 more

  💾 Result saved to output/
```

### Use as a Library

```python
from crawler.core.crawler import Crawler
from crawler.models.request import CrawlRequest
from crawler.storage.json_storage import JsonStorage

async with Crawler() as crawler:
    request = CrawlRequest(
        seed_url  = "https://docs.python.org/3/",
        max_depth = 3,
        max_pages = 500,
    )
    result = await crawler.crawl(request)

if result.status.value == "success":
    print(f"Crawled {result.total_pages} pages")
    print(f"Duration: {result.duration_seconds:.1f}s")
    print(result.urls_visited)

    storage = JsonStorage()
    storage.save(result)
```

Or use the synchronous entry point:

```python
result = Crawler.run(request)
```

---

## Project Structure

```
webcrawler/
│
├── crawler/                        # Main package
│   ├── __init__.py
│   │
│   ├── core/                       # Heart of the crawler
│   │   ├── __init__.py
│   │   ├── fetcher.py              # Async HTTP fetching with aiohttp
│   │   ├── parser.py               # Link extraction from raw HTML
│   │   ├── crawler.py              # Orchestrator — manages the full crawl loop
│   │   └── robots.py               # robots.txt fetching, parsing, and caching
│   │
│   ├── models/                     # Data shapes and contracts
│   │   ├── __init__.py
│   │   ├── request.py              # CrawlRequest — defines what goes IN
│   │   └── result.py               # CrawlResult, PageRecord — defines what comes OUT
│   │
│   ├── storage/                    # Where results are saved
│   │   ├── __init__.py
│   │   ├── base.py                 # Abstract storage interface (BaseStorage)
│   │   └── json_storage.py         # JSON file implementation of BaseStorage
│   │
│   ├── utils/                      # Shared helper tools
│   │   ├── __init__.py
│   │   ├── logger.py               # Centralized structured logging
│   │   └── url.py                  # URL validation, normalization, path scoping
│   │
│   └── config/                     # All settings in one place
│       ├── __init__.py
│       └── settings.py             # Single source of truth for all config values
│
├── tests/                          # Full test suite
│   ├── __init__.py
│   ├── test_url.py                 # 20 tests
│   ├── test_robots.py              # 9 tests
│   ├── test_fetcher.py             # 9 tests
│   ├── test_parser.py              # 24 tests
│   └── test_crawler.py             # 13 tests
│
├── output/                         # Crawl JSON results saved here
├── logs/                           # crawler.log written here
├── main.py                         # CLI entry point
├── pytest.ini                      # asyncio_mode = auto
├── requirements.txt
└── .gitignore
```

---

## Architecture

The crawler is built around strict separation of concerns. Each layer has one responsibility and knows nothing about the others. External code only ever talks to `Crawler` — never directly to `Fetcher`, `Parser`, `RobotsCache`, or storage.

```
┌─────────────────────────────────────────────────┐
│               main.py / caller                  │
│      CrawlRequest(seed_url="https://...")       │
└───────────────────────┬─────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────┐
│            Crawler (orchestrator)               │
│  - Spawns N concurrent worker coroutines        │
│  - Manages frontier queue and visited set       │
│  - Enforces depth and page limits               │
│  - Coordinates politeness and robots checks     │
└──────┬──────────┬──────────┬────────────────────┘
       │          │          │
       ▼          ▼          ▼
┌──────────┐ ┌────────┐ ┌──────────────┐
│  Fetcher │ │ Parser │ │ RobotsCache  │
│          │ │        │ │              │
│ aiohttp  │ │Extract │ │Fetch once    │
│ Semaphore│ │ links  │ │per domain    │
│ Retry +  │ │Filter  │ │Cache with    │
│ backoff  │ │ scope  │ │TTL           │
└──────────┘ └────────┘ └──────────────┘
       │          │
       ▼          ▼
┌─────────────────────────────────────────────────┐
│         CrawlResult + PageRecord models         │
│  seed_url, status, urls_visited, urls_failed,   │
│  pages, total_pages, max_depth_reached, timing  │
└───────────────────────┬─────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────┐
│              Storage (abstract)                 │
│  BaseStorage → JsonStorage (default)            │
│              → PostgresStorage (future)         │
└─────────────────────────────────────────────────┘
```

### Crawl Pipeline

```
CrawlRequest received
        │
        ├── Seed URL added to frontier at depth 0
        ├── N worker coroutines spawned (CONCURRENT_REQUESTS)
        │
        └── Each worker loops:
                │
                ├── Pull (url, depth) from frontier queue
                ├── Check robots.txt → blocked? skip
                ├── Apply politeness delay for domain
                ├── Fetch page with aiohttp
                │     ├── 2xx → proceed
                │     ├── 4xx → record failure, no retry
                │     └── 5xx/timeout → retry with exponential backoff
                ├── Record url in urls_visited
                ├── depth < MAX_DEPTH?
                │     ├── YES → extract links → filter → add to frontier
                │     └── NO  → skip link extraction
                └── Append PageRecord to result
```

### Path Scoping

```
Seed URL: https://developer.mozilla.org/en-US/docs/Web/JavaScript
Seed path (normalized): /en-US/docs/Web/JavaScript/

✅ /en-US/docs/Web/JavaScript/Guide        → within scope
✅ /en-US/docs/Web/JavaScript/Reference    → within scope
❌ /en-US/docs/Web/CSS                     → different section
❌ /en-US/docs/Web/JavaScriptSomethingElse → trailing slash prevents collision
❌ github.com/anything                     → different domain
```

### Link Filtering Pipeline

```
Raw <a href> found
        │
        ├── Step 1: Explicit non-HTTP scheme? (mailto, tel, ftp, javascript) → reject
        ├── Step 2: Fragment only? (#section) → reject
        ├── Step 3: resolve_relative_url() → absolute URL
        ├── Step 4: is_valid_url() → invalid? reject
        ├── Step 5: is_within_path() → out of scope? reject
        ├── Step 6: already in visited set? → skip
        └── Step 7: duplicate on this page? → skip
                    │
                    └── PASS → add to frontier
```

---

## File Breakdown

### `crawler/config/settings.py`
Single source of truth for every configuration value. No magic numbers anywhere else in the codebase. Uses `pathlib.Path` for cross-platform paths. Automatically creates `output/` and `logs/` directories on import.

| Constant | Value | Purpose |
|---|---|---|
| `REQUEST_TIMEOUT` | `30` | Seconds before a request gives up |
| `MAX_RETRIES` | `3` | Max retry attempts per request |
| `RETRY_DELAY` | `2` | Base seconds for exponential backoff |
| `CONCURRENT_REQUESTS` | `10` | Max simultaneous requests in flight |
| `MAX_DEPTH` | `4` | Max link-hops from seed URL |
| `MAX_PAGES` | `1000` | Hard cap on total pages crawled |
| `POLITENESS_DELAY` | `1.0` | Seconds between requests to same domain |
| `ROBOTS_TXT_ENABLED` | `True` | Whether to respect robots.txt |
| `ROBOTS_TXT_CACHE_TTL` | `3600` | Seconds to cache a fetched robots.txt |
| `LOG_LEVEL` | `"DEBUG"` | Logging verbosity |

---

### `crawler/utils/logger.py`
Centralized logger — all modules call `get_logger(__name__)` instead of `print()`. Sets up one root logger with two handlers:

- **Console handler** (`INFO`) — clean, human-readable format for real-time monitoring
- **File handler** (`DEBUG`) — detailed format with filename and line number for debugging

A guard prevents duplicate log lines when multiple modules import the logger.

```python
from crawler.utils.logger import get_logger
logger = get_logger(__name__)

logger.debug("Detailed info for development")
logger.info("General progress")
logger.warning("Unexpected but not fatal")
logger.error("Something failed")
```

---

### `crawler/models/request.py` — `CrawlRequest`

Input contract. Validated and normalized in `__post_init__` before anything else runs.

```python
@dataclass
class CrawlRequest:
    seed_url:            str          # Required — must be http:// or https://
    max_depth:           int  = 4     # Max link-hops from seed
    max_pages:           int  = 1000  # Hard cap on total pages
    concurrent_requests: int  = 10    # Simultaneous requests
    politeness_delay:    float = 1.0  # Seconds between requests to same domain
    timeout:             int  = 30    # Seconds before giving up
    headers:             dict = {}    # Custom headers
    proxy:               str  = None  # Optional: "http://user:pass@host:port"
    respect_robots_txt:  bool = True  # Whether to check robots.txt
```

---

### `crawler/models/result.py` — `CrawlResult` + `PageRecord` + `CrawlStatus`

Output contract. Always returned — even on failure. Check `result.status` to determine outcome.

```python
class CrawlStatus(Enum):
    SUCCESS       = "success"        # Completed normally
    MAX_PAGES_HIT = "max_pages_hit"  # Stopped at page limit
    MAX_DEPTH_HIT = "max_depth_hit"  # Stopped at depth limit
    CANCELLED     = "cancelled"      # Manually stopped
    FAILED        = "failed"         # Unrecoverable error

@dataclass
class CrawlResult:
    seed_url:          str               # The starting URL
    status:            CrawlStatus       # How the crawl ended
    pages:             list[PageRecord]  # One record per crawled page
    urls_visited:      set[str]          # All successfully crawled URLs
    urls_failed:       list[str]         # URLs that could not be fetched
    total_pages:       int               # len(urls_visited)
    max_depth_reached: int               # Deepest depth reached
    started_at:        datetime          # UTC, auto-set
    finished_at:       datetime          # Set by finish()
    error:             str               # Set on FAILED status
```

`finish(status)` sets `status`, `finished_at`, and `total_pages` atomically.
`summary()` returns a one-line human-readable log string.
`to_dict()` serializes for storage with ISO 8601 datetimes.

---

### `crawler/utils/url.py`

All URL handling lives here. Uses Python's built-in `urllib.parse` — no extra dependencies.

| Function | Purpose |
|---|---|
| `is_allowed_scheme(url)` | Returns True only for http/https — filters mailto, tel, ftp, javascript |
| `is_valid_url(url)` | Returns True if URL has valid http/https scheme and netloc |
| `normalize_url(url)` | Lowercases scheme/host, removes fragments, sorts query params |
| `extract_domain(url)` | Returns netloc (e.g. `docs.python.org`) |
| `resolve_relative_url(base, relative)` | Resolves relative hrefs to absolute URLs |
| `get_seed_path(seed_url)` | Extracts path from seed URL, ensures trailing slash |
| `is_within_path(url, seed_url)` | Returns True if URL is within seed URL's path scope |

> The trailing slash in `get_seed_path` is critical — without it, `/JavaScript/` and `/JavaScriptSomethingElse` would both match a `/JavaScript` prefix check.

---

### `crawler/core/robots.py` — `RobotsCache`

Fetches, parses, and caches robots.txt per domain. Uses Python's built-in `urllib.robotparser` — no third-party dependency.

Key behaviors:
- **Fetched once per domain per TTL** — never fetches the same robots.txt twice within `ROBOTS_TXT_CACHE_TTL` seconds
- **Per-domain asyncio locks** — prevents multiple coroutines fetching the same robots.txt simultaneously
- **404 → allow all** — a missing robots.txt means no restrictions
- **`get_crawl_delay()`** — extracts the `Crawl-delay` directive so the politeness manager can respect it

---

### `crawler/core/fetcher.py` — `Fetcher`

The only file that makes network requests. Uses `aiohttp` for non-blocking async HTTP.

- **`asyncio.Semaphore`** enforces `CONCURRENT_REQUESTS` — at most N requests in flight simultaneously
- **Persistent `aiohttp.ClientSession`** for connection pooling and keep-alive
- **Exponential backoff** uses `await asyncio.sleep()` — never blocks the event loop
- **Dependency injection** — session can be injected for testing; fetcher only closes sessions it created
- **Async context manager** (`async with Fetcher() as fetcher`) — guarantees session cleanup

---

### `crawler/core/parser.py` — `Parser`

Extracts valid in-scope links from raw HTML. Single responsibility — no content extraction, no title parsing. That is the scraper's job.

Full filtering pipeline per href:
1. Reject non-HTTP schemes and fragment-only hrefs
2. Resolve relative URLs to absolute
3. Validate resolved URL
4. Check path scope against seed URL
5. Skip already-visited URLs
6. Deduplicate within the current page

Handles `<base href>` tags — if a page declares a base URL, relative links are resolved against it instead of the page URL.

---

### `crawler/core/crawler.py` — `Crawler` + `PolitenessManager`

The orchestrator. The only file that knows `Fetcher`, `Parser`, and `RobotsCache` all exist.

**Worker model:** N coroutines run concurrently, all pulling from the same `asyncio.Queue` frontier. Each worker independently handles robots checks, politeness delays, fetching, and link extraction.

**Termination:** `frontier.join()` waits until the queue is empty AND all workers have called `task_done()` — correctly handles the case where the frontier is temporarily empty while workers are still processing pages.

**`PolitenessManager`:** tracks `{domain: last_request_time}` and sleeps only the remaining delay before each request. The higher of `politeness_delay` and robots.txt `Crawl-delay` is always used.

**`Crawler.run(request)`:** static synchronous entry point that wraps `asyncio.run()` — `main.py` never needs to know about async.

---

### `crawler/storage/base.py` — `BaseStorage`

Abstract base class using Python's `abc.ABC`. Any subclass that fails to implement an abstract method raises `TypeError` at instantiation.

```python
class BaseStorage(ABC):
    @abstractmethod
    def save(self, result: CrawlResult) -> bool: ...

    @abstractmethod
    def load(self, seed_url: str) -> CrawlResult | None: ...

    @abstractmethod
    def exists(self, seed_url: str) -> bool: ...

    @abstractmethod
    def delete(self, seed_url: str) -> bool: ...

    @abstractmethod
    def list_crawls(self) -> list[dict]: ...

    def save_many(self, results) -> dict: ...  # Concrete — free for all subclasses
```

---

### `crawler/storage/json_storage.py` — `JsonStorage`

Concrete `BaseStorage` implementation. Saves each `CrawlResult` as an individual `.json` file.

**File naming:**
```
https://docs.python.org/3/ crawled at 2026-05-09 14:30:22
→ docs.python.org_3__20260509_143022.json
```
Scheme stripped → unsafe characters replaced with `_` → consecutive `_` collapsed → timestamp appended for uniqueness across multiple runs of the same seed URL.

**`list_crawls()`** reads only summary fields — avoids loading full page records into memory when listing past runs.

---

## Configuration

All configuration lives in `crawler/config/settings.py`. Edit values there — never hardcode in other files.

```python
MAX_DEPTH            = 4      # Increase for deeper sites (Mozilla needs 4)
MAX_PAGES            = 1000   # Decrease for faster test runs
CONCURRENT_REQUESTS  = 10     # Increase for faster crawling (watch politeness)
POLITENESS_DELAY     = 1.0    # Increase to be more conservative
ROBOTS_TXT_ENABLED   = True   # Set False only for sites you own
ROBOTS_TXT_CACHE_TTL = 3600   # Seconds before re-fetching robots.txt
LOG_LEVEL            = "DEBUG" # Change to "INFO" to reduce console verbosity
```

---

## Testing

**Run all tests**
```bash
python -m pytest tests/ -v
```

**Run a specific file**
```bash
python -m pytest tests/test_crawler.py -v
```

**Run a specific test class**
```bash
python -m pytest tests/test_crawler.py::TestDepthControl -v
```

**Run a single test**
```bash
python -m pytest tests/test_crawler.py::TestDepthControl::test_max_depth_zero_crawls_only_seed -v
```

**Stop at first failure**
```bash
python -m pytest tests/ -v -x
```

### Test Coverage

| File | Classes | Tests | What's covered |
|---|---|---|---|
| `test_url.py` | 6 | 20 | Scheme filtering, URL validation, normalization, domain extraction, relative URL resolution, seed path extraction, path scope checking including trailing slash collision case |
| `test_robots.py` | 3 | 9 | Allowed/disallowed URLs, missing robots.txt (404), robots disabled flag, server error fallback, crawl delay extraction, cache hit (single fetch per domain), multiple domains fetched separately, expired cache re-fetch |
| `test_fetcher.py` | 4 | 9 | Successful fetch, invalid URL, proxy forwarding, 4xx no-retry, 5xx retry exhaustion, success on second attempt, timeout retry, semaphore concurrency, session lifecycle |
| `test_parser.py` | 5 | 24 | Absolute/relative/absolute-path links, empty HTML, no links, mailto/tel/javascript/fragment/external/out-of-scope/visited filtering, deduplication within page, equivalent URL deduplication, base tag resolution, page URL fallback, malformed HTML, empty href, anchor without href, visited set not mutated |
| `test_crawler.py` | 5 | 13 | Successful pipeline, seed URL always visited, failed fetch recorded, timing info present, max_depth=0 crawls only seed, links not extracted at max depth, max pages stops crawl, disallowed URL not fetched, crawl delay applied, politeness no delay on first request, delay on second request, robots delay overrides default, context manager cleanup |

**Testing patterns used:**
- `AsyncMock` — mocks async functions like `session.get()` and `robots.is_allowed()`
- `MagicMock` with `side_effect` lists — simulates retry sequences (fail, succeed)
- `@patch("crawler.core.fetcher.asyncio.sleep")` — makes retry tests instant
- `make_fetcher()` / `make_robots()` / `make_request()` — shared helpers avoid repetition
- `pytest-asyncio` with `asyncio_mode = auto` — runs async test functions natively

---

## Design Decisions

**Path scoping over domain scoping**
Domain scoping would crawl everything on `developer.mozilla.org` when given a JavaScript docs URL — CSS docs, HTML docs, blog posts, everything. Path scoping stays within the seed URL's subtree, which is always what a focused crawl intends. Domain scoping can be added later as an opt-in flag.

**Trailing slash in `get_seed_path()`**
Without a trailing slash, `/en-US/docs/Web/JavaScript` would incorrectly match `/en-US/docs/Web/JavaScriptSomethingElse` via `startswith`. The trailing slash makes path boundaries exact.

**`asyncio.Queue` over `collections.deque`**
`asyncio.Queue` is the async-native frontier. Its `await queue.get()` suspends a coroutine cleanly while waiting, and `task_done()` + `join()` give a reliable termination signal that accounts for in-flight work, not just queue emptiness.

**Termination via `frontier.join()` not queue emptiness**
The queue can be temporarily empty while workers are still processing pages that will produce new URLs. `frontier.join()` waits until the queue is empty AND all `task_done()` calls have been made — the correct signal that all work is truly complete.

**Per-domain asyncio locks in `RobotsCache`**
Without locks, 10 concurrent workers hitting a new domain simultaneously would all find an empty cache and fire 10 identical robots.txt requests. The lock ensures only the first coroutine fetches — the rest wait and find the cache populated.

**`PolitenessManager` uses the higher of two delays**
When robots.txt specifies a `Crawl-delay`, the politeness manager uses `max(robots_delay, default_delay)`. A site asking for a 2s delay should never be overridden by a lower configured default — the site's preference always wins upward.

**`task_done()` in `finally` blocks**
No matter what happens during page processing — success, failure, or unexpected exception — `task_done()` must be called. Without it, `frontier.join()` waits forever. `finally` guarantees it always runs.

**Plain `set` for visited URLs**
A Python `set` gives O(1) lookup and is correct for all practical crawl sizes. A Bloom filter would use significantly less memory at millions of URLs but introduces a small false-positive rate. The `set` is the right starting point — swapping in a Bloom filter during an optimization phase is a one-class change since nothing else in the codebase touches the visited set directly.

**Abstract storage from day one**
Starting with `BaseStorage` → `JsonStorage` instead of writing JSON logic directly means switching to PostgreSQL later requires writing one new class and changing one import in `main.py`. Nothing else in the codebase changes.

**`Crawler.run()` static method**
`main.py` should not need to know about `asyncio.run()`. The static method wraps the entire async execution so the CLI stays synchronous and clean. The async internals remain an implementation detail.

---

## Dependencies

```
aiohttp>=3.9.0
aiofiles>=23.2.0
beautifulsoup4>=4.12.0
lxml>=5.1.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
```

```bash
pip install aiohttp aiofiles beautifulsoup4 lxml pytest pytest-asyncio
```

---

## License

MIT
