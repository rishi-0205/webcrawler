# crawler/storage/base.py

from abc import ABC, abstractmethod

from crawler.models.result import CrawlResult


class BaseStorage(ABC):
    """
    Abstract storage interface for crawl results.

    Any storage backend (JSON, PostgreSQL, SQLite, etc.) must implement
    all abstract methods. The rest of the codebase depends only on this
    interface — never on a concrete implementation.
    """

    @abstractmethod
    def save(self, result: CrawlResult) -> bool:
        """
        Saves a CrawlResult to storage.
        Returns True on success, False on failure.
        """
        ...

    @abstractmethod
    def load(self, seed_url: str) -> CrawlResult | None:
        """
        Loads the most recent CrawlResult for a given seed URL.
        Returns None if no result exists for that URL.
        """
        ...

    @abstractmethod
    def exists(self, seed_url: str) -> bool:
        """
        Returns True if at least one crawl result exists for this seed URL.
        Does not load the full result — just checks existence.
        """
        ...

    @abstractmethod
    def delete(self, seed_url: str) -> bool:
        """
        Deletes the most recent crawl result for a given seed URL.
        Returns True on success, False if nothing was found to delete.
        """
        ...

    @abstractmethod
    def list_crawls(self) -> list[dict]:
        """
        Returns a lightweight list of all stored crawl runs.
        Each entry is a dict with summary info only — not the full result.
        Avoids loading all results into memory.

        Each dict contains:
            {
                "seed_url":    str,
                "status":      str,
                "total_pages": int,
                "started_at":  str,   # ISO 8601
                "filename":    str,
            }
        """
        ...

    def save_many(self, results: list[CrawlResult]) -> dict:
        """
        Saves multiple CrawlResults.
        Concrete method — all backends get this for free.
        Returns {"saved": N, "failed": N, "total": N}.
        """
        saved  = 0
        failed = 0

        for result in results:
            if self.save(result):
                saved += 1
            else:
                failed += 1

        return {
            "saved":  saved,
            "failed": failed,
            "total":  len(results),
        }