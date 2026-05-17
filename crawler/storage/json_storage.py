import json
import re
from datetime import datetime, timezone
from pathlib import Path

from crawler.config.settings import DEFAULT_OUTPUT_DIR
from crawler.models.result import CrawlResult, CrawlStatus, PageRecord
from crawler.storage.base import BaseStorage
from crawler.utils.logger import get_logger

logger = get_logger(__name__)


class JsonStorage(BaseStorage):
    """
    Saves each CrawlResult as an individual JSON file.

    File naming: {sanitized_seed_url}_{timestamp}.json
    Example: docs.python.org_3__20260509_143022.json

    Each file represents one complete crawl run.
    Multiple crawls of the same seed URL produce multiple files.
    """

    def __init__(self, output_dir: Path = DEFAULT_OUTPUT_DIR):
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    # ── Public Interface ──────────────────────────────────────────────────────

    def save(self, result: CrawlResult) -> bool:
        """
        Saves a CrawlResult to a JSON file.
        Returns True on success, False on failure.
        """
        try:
            filename = self._make_filename(result)
            filepath = self._output_dir / filename

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)

            logger.info(f"Saved crawl result to {filepath}")
            return True

        except Exception as e:
            logger.error(f"Failed to save crawl result for {result.seed_url}: {e}")
            return False

    def load(self, seed_url: str) -> CrawlResult | None:
        """
        Loads the most recent CrawlResult for a given seed URL.
        Returns None if no result is found.
        """
        files = self._find_files_for_seed(seed_url)

        if not files:
            logger.debug(f"No stored results found for {seed_url}")
            return None

        # Most recent file — sorted by filename which includes timestamp
        latest = sorted(files)[-1]

        try:
            with open(latest, "r", encoding="utf-8") as f:
                data = json.load(f)
            return self._dict_to_result(data)

        except Exception as e:
            logger.error(f"Failed to load crawl result from {latest}: {e}")
            return None

    def exists(self, seed_url: str) -> bool:
        """Returns True if at least one crawl result exists for this seed URL."""
        return len(self._find_files_for_seed(seed_url)) > 0

    def delete(self, seed_url: str) -> bool:
        """
        Deletes the most recent crawl result for a given seed URL.
        Returns True if a file was deleted, False if nothing was found.
        """
        files = self._find_files_for_seed(seed_url)

        if not files:
            logger.debug(f"No stored results found to delete for {seed_url}")
            return False

        latest = sorted(files)[-1]

        try:
            latest.unlink()
            logger.info(f"Deleted crawl result: {latest}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete {latest}: {e}")
            return False

    def list_crawls(self) -> list[dict]:
        """
        Returns a lightweight summary list of all stored crawl runs.
        Reads only the fields needed for the summary — avoids loading
        full page records into memory.
        """
        summaries = []

        for filepath in sorted(self._output_dir.glob("*.json")):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)

                summaries.append({
                    "seed_url":    data.get("seed_url", ""),
                    "status":      data.get("status", ""),
                    "total_pages": data.get("total_pages", 0),
                    "started_at":  data.get("started_at", ""),
                    "filename":    filepath.name,
                })

            except Exception as e:
                logger.warning(f"Could not read summary from {filepath}: {e}")

        return summaries

    # ── Internal ──────────────────────────────────────────────────────────────

    def _make_filename(self, result: CrawlResult) -> str:
        """
        Generates a filename from the seed URL and crawl start time.

        Example:
            seed_url   = "https://docs.python.org/3/"
            started_at = 2026-05-09 14:30:22 UTC
            filename   = "docs.python.org_3__20260509_143022.json"
        """
        # Strip scheme
        sanitized = re.sub(r"^https?://", "", result.seed_url)

        # Replace filesystem-unsafe characters with underscores
        sanitized = re.sub(r"[^\w\-.]", "_", sanitized)

        # Collapse consecutive underscores
        sanitized = re.sub(r"_+", "_", sanitized)

        # Cap length to avoid OS filename limits
        sanitized = sanitized[:180]

        # Append timestamp for uniqueness across multiple crawl runs
        timestamp = result.started_at.strftime("%Y%m%d_%H%M%S")

        return f"{sanitized}_{timestamp}.json"

    def _find_files_for_seed(self, seed_url: str) -> list[Path]:
        """
        Finds all JSON files in the output directory that belong
        to a given seed URL, by matching the sanitized URL prefix.
        """
        # Build the same sanitized prefix the filename would start with
        sanitized = re.sub(r"^https?://", "", seed_url)
        sanitized = re.sub(r"[^\w\-.]", "_", sanitized)
        sanitized = re.sub(r"_+", "_", sanitized)
        sanitized = sanitized[:180]

        return list(self._output_dir.glob(f"{sanitized}_*.json"))

    def _dict_to_result(self, data: dict) -> CrawlResult:
        """
        Reconstructs a CrawlResult from a JSON-loaded dict.
        Handles datetime parsing and enum reconstruction.
        """
        pages = [
            PageRecord(
                url         = p["url"],
                depth       = p["depth"],
                status_code = p["status_code"],
                links_found = p["links_found"],
                crawled_at  = datetime.fromisoformat(p["crawled_at"]),
                error       = p.get("error"),
            )
            for p in data.get("pages", [])
        ]

        result = CrawlResult(
            seed_url          = data["seed_url"],
            status            = CrawlStatus(data["status"]),
            error             = data.get("error"),
            pages             = pages,
            urls_visited      = set(data.get("urls_visited", [])),
            urls_failed       = data.get("urls_failed", []),
            total_pages       = data.get("total_pages", 0),
            max_depth_reached = data.get("max_depth_reached", 0),
            started_at        = datetime.fromisoformat(data["started_at"]),
            finished_at       = datetime.fromisoformat(data["finished_at"])
                                if data.get("finished_at") else None,
        )

        return result