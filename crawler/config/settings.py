# crawler/config/settings.py

from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent.parent

OUTPUT_DIR = BASE_DIR / "output"
LOG_DIR    = BASE_DIR / "logs"

OUTPUT_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

# ── HTTP ─────────────────────────────────────────────────────────────────────

REQUEST_TIMEOUT      = 30       # seconds — per request timeout
MAX_RETRIES          = 3        # retry attempts on failure
RETRY_DELAY          = 2        # seconds — base for exponential backoff

# ── Concurrency ──────────────────────────────────────────────────────────────

CONCURRENT_REQUESTS  = 10       # max simultaneous requests in flight

# ── Crawl Limits ─────────────────────────────────────────────────────────────

MAX_DEPTH            = 4        # max link-hops from seed URL
MAX_PAGES            = 1000     # hard cap on total pages crawled

# ── Politeness ───────────────────────────────────────────────────────────────

POLITENESS_DELAY     = 1.0      # seconds between requests to same domain
ROBOTS_TXT_ENABLED   = True     # whether to respect robots.txt
ROBOTS_TXT_CACHE_TTL = 3600     # seconds to cache robots.txt (1 hour)

# ── Logging ───────────────────────────────────────────────────────────────────

LOG_LEVEL            = "DEBUG"
LOG_FILE             = LOG_DIR / "crawler.log"

# ── Storage ───────────────────────────────────────────────────────────────────

DEFAULT_OUTPUT_DIR   = OUTPUT_DIR

# ── CLI Defaults ──────────────────────────────────────────────────────────────

DEFAULT_URL          = "https://docs.python.org/3/"