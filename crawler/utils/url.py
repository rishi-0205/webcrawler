# crawler/utils/url.py

from urllib.parse import urlparse, urljoin, urlencode, parse_qsl, urlunparse


# Schemes the crawler can actually fetch
ALLOWED_SCHEMES = {"http", "https"}


def is_allowed_scheme(url: str) -> bool:
    """
    Returns True only for http and https URLs.
    Filters out mailto, tel, ftp, javascript, fragments, and anything else
    that cannot be fetched with an HTTP client.
    """
    try:
        scheme = urlparse(url).scheme.lower()
        return scheme in ALLOWED_SCHEMES
    except Exception:
        return False


def is_valid_url(url: str) -> bool:
    """
    Returns True if the URL has a valid http/https scheme and a non-empty netloc.
    Does not make any network requests.
    """
    try:
        parsed = urlparse(url)
        return (
            parsed.scheme in ALLOWED_SCHEMES
            and bool(parsed.netloc)
        )
    except Exception:
        return False


def normalize_url(url: str) -> str:
    """
    Normalizes a URL to a canonical form so that equivalent URLs
    are treated as identical by the visited set.

    - Lowercases scheme and host
    - Removes fragments (#section)
    - Sorts query parameters
    - Ensures non-empty paths have at least a trailing slash
    - Strips empty query strings
    """
    parsed = urlparse(url.strip())

    scheme   = parsed.scheme.lower()
    netloc   = parsed.netloc.lower()
    path     = parsed.path or "/"
    query    = urlencode(sorted(parse_qsl(parsed.query)))
    fragment = ""                          # always strip fragments

    return urlunparse((scheme, netloc, path, "", query, fragment))


def extract_domain(url: str) -> str:
    """
    Returns the netloc (domain + port if present) of a URL.
    Example: https://docs.python.org/3/ → docs.python.org
    """
    return urlparse(url).netloc.lower()


def resolve_relative_url(base_url: str, relative_url: str) -> str:
    """
    Resolves a relative href against the page's base URL.
    Then normalizes the result.

    Example:
        base_url    = "https://docs.python.org/3/tutorial/"
        relative    = "../library/os.html"
        result      = "https://docs.python.org/3/library/os.html"
    """
    resolved = urljoin(base_url, relative_url.strip())
    return normalize_url(resolved)


def get_seed_path(seed_url: str) -> str:
    """
    Extracts the path from the seed URL and ensures it ends with a slash.
    This is the boundary for path scoping.

    Example:
        https://developer.mozilla.org/en-US/docs/Web/JavaScript
        → /en-US/docs/Web/JavaScript/
    """
    path = urlparse(seed_url).path

    if not path.endswith("/"):
        path = path + "/"

    return path


def is_within_path(url: str, seed_url: str) -> bool:
    """
    Returns True if the URL falls within the seed URL's path scope.

    Uses the seed path with a trailing slash to avoid prefix collisions.

    Example:
        seed_url = https://developer.mozilla.org/en-US/docs/Web/JavaScript
        seed_path = /en-US/docs/Web/JavaScript/

        ✅ /en-US/docs/Web/JavaScript/Guide       → True
        ✅ /en-US/docs/Web/JavaScript/Reference   → True
        ❌ /en-US/docs/Web/JavaScriptSomething    → False
        ❌ /en-US/docs/Web/CSS                    → False

    Also checks domain matches — a URL on a different domain is never
    within the seed path even if the path matches.
    """
    if extract_domain(url) != extract_domain(seed_url):
        return False

    seed_path = get_seed_path(seed_url)
    url_path  = urlparse(url).path

    # The seed URL itself is always within scope
    if url_path == seed_path.rstrip("/") or url_path == seed_path:
        return True

    return url_path.startswith(seed_path)