import pytest
from crawler.utils.url import (
    is_allowed_scheme,
    is_valid_url,
    normalize_url,
    extract_domain,
    resolve_relative_url,
    get_seed_path,
    is_within_path,
)


# ── is_allowed_scheme ─────────────────────────────────────────────────────────

class TestIsAllowedScheme:

    def test_http_allowed(self):
        assert is_allowed_scheme("http://example.com") is True

    def test_https_allowed(self):
        assert is_allowed_scheme("https://example.com") is True

    def test_mailto_rejected(self):
        assert is_allowed_scheme("mailto:someone@example.com") is False

    def test_tel_rejected(self):
        assert is_allowed_scheme("tel:+1234567890") is False

    def test_ftp_rejected(self):
        assert is_allowed_scheme("ftp://files.example.com") is False

    def test_javascript_rejected(self):
        assert is_allowed_scheme("javascript:void(0)") is False

    def test_fragment_rejected(self):
        assert is_allowed_scheme("#section") is False

    def test_empty_string_rejected(self):
        assert is_allowed_scheme("") is False


# ── is_valid_url ──────────────────────────────────────────────────────────────

class TestIsValidUrl:

    def test_valid_https_url(self):
        assert is_valid_url("https://docs.python.org/3/") is True

    def test_valid_http_url(self):
        assert is_valid_url("http://example.com") is True

    def test_missing_scheme_rejected(self):
        assert is_valid_url("docs.python.org/3/") is False

    def test_missing_netloc_rejected(self):
        assert is_valid_url("https://") is False

    def test_empty_string_rejected(self):
        assert is_valid_url("") is False

    def test_ftp_rejected(self):
        assert is_valid_url("ftp://files.example.com") is False


# ── normalize_url ─────────────────────────────────────────────────────────────

class TestNormalizeUrl:

    def test_lowercases_scheme(self):
        assert normalize_url("HTTPS://example.com/").startswith("https://")

    def test_lowercases_host(self):
        assert "EXAMPLE.COM" not in normalize_url("https://EXAMPLE.COM/")

    def test_strips_fragment(self):
        result = normalize_url("https://example.com/page#section")
        assert "#" not in result

    def test_sorts_query_params(self):
        url1 = normalize_url("https://example.com/?b=2&a=1")
        url2 = normalize_url("https://example.com/?a=1&b=2")
        assert url1 == url2

    def test_empty_query_stripped(self):
        result = normalize_url("https://example.com/?")
        assert "?" not in result

    def test_preserves_path(self):
        result = normalize_url("https://example.com/3/tutorial/")
        assert "/3/tutorial/" in result


# ── extract_domain ────────────────────────────────────────────────────────────

class TestExtractDomain:

    def test_extracts_domain(self):
        assert extract_domain("https://docs.python.org/3/") == "docs.python.org"

    def test_lowercases_domain(self):
        assert extract_domain("https://DOCS.PYTHON.ORG/3/") == "docs.python.org"

    def test_includes_port(self):
        assert extract_domain("https://localhost:8080/") == "localhost:8080"


# ── resolve_relative_url ──────────────────────────────────────────────────────

class TestResolveRelativeUrl:

    def test_resolves_relative_path(self):
        result = resolve_relative_url(
            "https://docs.python.org/3/tutorial/",
            "interpreter.html"
        )
        assert result == "https://docs.python.org/3/tutorial/interpreter.html"

    def test_resolves_absolute_path(self):
        result = resolve_relative_url(
            "https://docs.python.org/3/tutorial/",
            "/3/library/os.html"
        )
        assert result == "https://docs.python.org/3/library/os.html"

    def test_resolves_parent_path(self):
        result = resolve_relative_url(
            "https://docs.python.org/3/tutorial/",
            "../library/os.html"
        )
        assert result == "https://docs.python.org/3/library/os.html"

    def test_strips_fragment(self):
        result = resolve_relative_url(
            "https://docs.python.org/3/tutorial/",
            "interpreter.html#section"
        )
        assert "#" not in result

    def test_absolute_url_unchanged(self):
        result = resolve_relative_url(
            "https://docs.python.org/3/tutorial/",
            "https://other.com/page"
        )
        assert "other.com" in result


# ── get_seed_path ─────────────────────────────────────────────────────────────

class TestGetSeedPath:

    def test_adds_trailing_slash(self):
        result = get_seed_path("https://developer.mozilla.org/en-US/docs/Web/JavaScript")
        assert result == "/en-US/docs/Web/JavaScript/"

    def test_preserves_existing_trailing_slash(self):
        result = get_seed_path("https://docs.python.org/3/")
        assert result == "/3/"

    def test_root_path(self):
        result = get_seed_path("https://docs.python.org/")
        assert result == "/"


# ── is_within_path ────────────────────────────────────────────────────────────

class TestIsWithinPath:

    def test_direct_child_within_scope(self):
        assert is_within_path(
            "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide",
            "https://developer.mozilla.org/en-US/docs/Web/JavaScript"
        ) is True

    def test_deeply_nested_within_scope(self):
        assert is_within_path(
            "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Intro",
            "https://developer.mozilla.org/en-US/docs/Web/JavaScript"
        ) is True

    def test_seed_url_itself_within_scope(self):
        assert is_within_path(
            "https://developer.mozilla.org/en-US/docs/Web/JavaScript",
            "https://developer.mozilla.org/en-US/docs/Web/JavaScript"
        ) is True

    def test_different_section_out_of_scope(self):
        assert is_within_path(
            "https://developer.mozilla.org/en-US/docs/Web/CSS",
            "https://developer.mozilla.org/en-US/docs/Web/JavaScript"
        ) is False

    def test_trailing_slash_prevents_prefix_collision(self):
        # JavaScriptSomethingElse should NOT match /JavaScript/ scope
        assert is_within_path(
            "https://developer.mozilla.org/en-US/docs/Web/JavaScriptSomethingElse",
            "https://developer.mozilla.org/en-US/docs/Web/JavaScript"
        ) is False

    def test_different_domain_out_of_scope(self):
        assert is_within_path(
            "https://github.com/en-US/docs/Web/JavaScript/Guide",
            "https://developer.mozilla.org/en-US/docs/Web/JavaScript"
        ) is False

    def test_parent_path_out_of_scope(self):
        assert is_within_path(
            "https://developer.mozilla.org/en-US/docs/Web",
            "https://developer.mozilla.org/en-US/docs/Web/JavaScript"
        ) is False