import pytest
from crawler.core.parser import Parser


# ── Helpers ───────────────────────────────────────────────────────────────────

SEED_URL = "https://docs.python.org/3/"
PAGE_URL = "https://docs.python.org/3/tutorial/"


def make_html(*links: str) -> str:
    """Builds a minimal HTML page with the given hrefs as anchor tags."""
    anchors = "".join(f'<a href="{link}">link</a>' for link in links)
    return f"<html><body>{anchors}</body></html>"


# ── Basic Extraction ──────────────────────────────────────────────────────────

class TestBasicExtraction:

    def test_extracts_absolute_link_within_scope(self):
        parser = Parser()
        html   = make_html("https://docs.python.org/3/library/")

        links = parser.extract_links(html, PAGE_URL, SEED_URL, set())

        assert "https://docs.python.org/3/library/" in links

    def test_extracts_relative_link_within_scope(self):
        parser = Parser()
        html   = make_html("../library/os.html")

        links = parser.extract_links(html, PAGE_URL, SEED_URL, set())

        assert any("library/os.html" in link for link in links)

    def test_extracts_absolute_path_within_scope(self):
        parser = Parser()
        html   = make_html("/3/library/os.html")

        links = parser.extract_links(html, PAGE_URL, SEED_URL, set())

        assert any("library/os.html" in link for link in links)

    def test_returns_list(self):
        parser = Parser()
        html   = make_html("/3/tutorial/intro.html")

        links = parser.extract_links(html, PAGE_URL, SEED_URL, set())

        assert isinstance(links, list)

    def test_empty_html_returns_empty_list(self):
        parser = Parser()

        links = parser.extract_links("", PAGE_URL, SEED_URL, set())

        assert links == []

    def test_html_with_no_links_returns_empty_list(self):
        parser = Parser()
        html   = "<html><body><p>no links here</p></body></html>"

        links = parser.extract_links(html, PAGE_URL, SEED_URL, set())

        assert links == []


# ── Filtering ─────────────────────────────────────────────────────────────────

class TestFiltering:

    def test_mailto_excluded(self):
        parser = Parser()
        html   = make_html("mailto:someone@example.com")

        links = parser.extract_links(html, PAGE_URL, SEED_URL, set())

        assert not any("mailto" in link for link in links)

    def test_tel_excluded(self):
        parser = Parser()
        html   = make_html("tel:+1234567890")

        links = parser.extract_links(html, PAGE_URL, SEED_URL, set())

        assert links == []

    def test_javascript_excluded(self):
        parser = Parser()
        html   = make_html("javascript:void(0)")

        links = parser.extract_links(html, PAGE_URL, SEED_URL, set())

        assert links == []

    def test_fragment_only_excluded(self):
        parser = Parser()
        html   = make_html("#section")

        links = parser.extract_links(html, PAGE_URL, SEED_URL, set())

        assert links == []

    def test_external_domain_excluded(self):
        parser = Parser()
        html   = make_html("https://github.com/python/cpython")

        links = parser.extract_links(html, PAGE_URL, SEED_URL, set())

        assert links == []

    def test_out_of_scope_path_excluded(self):
        # /2/ is outside the seed scope of /3/
        parser = Parser()
        html   = make_html("https://docs.python.org/2/tutorial/")

        links = parser.extract_links(html, PAGE_URL, SEED_URL, set())

        assert links == []

    def test_already_visited_excluded(self):
        parser  = Parser()
        html    = make_html("https://docs.python.org/3/library/")
        visited = {"https://docs.python.org/3/library/"}

        links = parser.extract_links(html, PAGE_URL, SEED_URL, visited)

        assert links == []


# ── Deduplication ─────────────────────────────────────────────────────────────

class TestDeduplication:

    def test_duplicate_links_on_same_page_deduplicated(self):
        parser = Parser()
        # Same link appears three times on the page
        html   = make_html(
            "/3/library/os.html",
            "/3/library/os.html",
            "/3/library/os.html",
        )

        links = parser.extract_links(html, PAGE_URL, SEED_URL, set())

        assert len(links) == 1

    def test_equivalent_urls_deduplicated(self):
        # These normalize to the same URL
        parser = Parser()
        html   = make_html(
            "https://docs.python.org/3/library/",
            "https://DOCS.PYTHON.ORG/3/library/",
        )

        links = parser.extract_links(html, PAGE_URL, SEED_URL, set())

        assert len(links) == 1

    def test_multiple_distinct_links_all_returned(self):
        parser = Parser()
        html   = make_html(
            "/3/tutorial/intro.html",
            "/3/tutorial/datastructures.html",
            "/3/library/os.html",
        )

        links = parser.extract_links(html, PAGE_URL, SEED_URL, set())

        assert len(links) == 3


# ── Base Tag ──────────────────────────────────────────────────────────────────

class TestBaseTag:

    def test_relative_links_resolved_against_base_tag(self):
        parser = Parser()
        html   = """
            <html>
                <head><base href="https://docs.python.org/3/library/"></head>
                <body><a href="os.html">os</a></body>
            </html>
        """

        links = parser.extract_links(html, PAGE_URL, SEED_URL, set())

        assert any("library/os.html" in link for link in links)

    def test_page_url_used_when_no_base_tag(self):
        parser = Parser()
        html   = "<html><body><a href='intro.html'>intro</a></body></html>"

        links = parser.extract_links(html, PAGE_URL, SEED_URL, set())

        # Should resolve against PAGE_URL = /3/tutorial/
        assert any("tutorial/intro.html" in link for link in links)


# ── Edge Cases ────────────────────────────────────────────────────────────────

class TestEdgeCases:

    def test_malformed_html_does_not_raise(self):
        parser = Parser()
        html   = "<html><body><a href='/3/tutorial/'>unclosed"

        # Should not raise — BeautifulSoup handles malformed HTML gracefully
        links = parser.extract_links(html, PAGE_URL, SEED_URL, set())

        assert isinstance(links, list)

    def test_empty_href_excluded(self):
        parser = Parser()
        html   = '<html><body><a href="">empty</a></body></html>'

        links = parser.extract_links(html, PAGE_URL, SEED_URL, set())

        assert links == []

    def test_anchor_tag_without_href_excluded(self):
        parser = Parser()
        html   = '<html><body><a name="anchor">no href</a></body></html>'

        links = parser.extract_links(html, PAGE_URL, SEED_URL, set())

        assert links == []

    def test_visited_set_not_mutated(self):
        # Parser should read visited but never modify it
        parser  = Parser()
        html    = make_html("/3/library/os.html")
        visited = set()

        parser.extract_links(html, PAGE_URL, SEED_URL, visited)

        assert len(visited) == 0