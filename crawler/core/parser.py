# crawler/core/parser.py

from bs4 import BeautifulSoup

from crawler.utils.logger import get_logger
from crawler.utils.url import (
    is_allowed_scheme,
    is_valid_url,
    resolve_relative_url,
    is_within_path,
)

logger = get_logger(__name__)


class Parser:
    """
    Extracts valid in-scope links from raw HTML.

    Single responsibility — link extraction only.
    No content extraction, no text cleaning, no title parsing.
    That is the scraper's job.
    """

    def extract_links(
        self,
        html:        str,
        page_url:    str,
        seed_url:    str,
        visited:     set[str],
    ) -> list[str]:
        """
        Parses raw HTML and returns a list of valid, in-scope,
        not-yet-visited absolute URLs.

        Args:
            html:     Raw HTML of the page
            page_url: URL of the page being parsed
                      (used as base for relative link resolution)
            seed_url: The crawl's seed URL
                      (used for path scope checking)
            visited:  Set of already-crawled URLs
                      (used to skip duplicates)

        Returns:
            List of unique, valid, in-scope URLs not in visited set
        """
        if not html:
            logger.debug(f"Empty HTML for {page_url} — no links extracted")
            return []

        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception as e:
            logger.error(f"Failed to parse HTML for {page_url}: {e}")
            return []

        base_url  = self._get_base_url(soup, page_url)
        links     = self._extract_raw_hrefs(soup)
        filtered  = self._filter_links(links, base_url, seed_url, visited)

        logger.debug(
            f"Extracted {len(filtered)} valid links from {page_url} "
            f"({len(links)} raw hrefs found)"
        )

        return filtered

    # ── Internal ──────────────────────────────────────────────────────────────

    def _get_base_url(self, soup: BeautifulSoup, page_url: str) -> str:
        """
        Returns the base URL for resolving relative links.
        Uses <base href> tag if present, otherwise uses the page URL.
        """
        base_tag = soup.find("base", href=True)
        if base_tag:
            logger.debug(f"Found <base href={base_tag['href']}> on {page_url}")
            return base_tag["href"]
        return page_url

    def _extract_raw_hrefs(self, soup: BeautifulSoup) -> list[str]:
        """
        Extracts all href values from <a> tags.
        Returns raw strings — no filtering or normalization yet.
        """
        hrefs = []
        for tag in soup.find_all("a", href=True):
            href = tag["href"].strip()
            if href:
                hrefs.append(href)
        return hrefs

    def _filter_links(
        self,
        hrefs:    list[str],
        base_url: str,
        seed_url: str,
        visited:  set[str],
    ) -> list[str]:
        """
        Runs every href through the full filtering pipeline.
        Returns only links that pass all checks.
        """
        seen    = set()     # deduplicates within this page's links
        results = []

        for href in hrefs:

            # Step 1 — filter non-http schemes before doing anything else
            if not is_allowed_scheme(href) and not href.startswith("/") \
                    and not href.startswith("."):
                continue

            # Step 2 — resolve relative URLs to absolute
            try:
                url = resolve_relative_url(base_url, href)
            except Exception:
                continue

            # Step 3 — validate the resolved URL
            if not is_valid_url(url):
                continue

            # Step 4 — check path scope
            if not is_within_path(url, seed_url):
                continue

            # Step 5 — skip already visited
            if url in visited:
                continue

            # Step 6 — deduplicate within this page's results
            if url in seen:
                continue

            seen.add(url)
            results.append(url)

        return results