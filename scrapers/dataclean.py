from __future__ import annotations

from scrapers.base import ListingDetailScraper


class DataCleanScraper(ListingDetailScraper):
    source = "dataclean"
    base_url = "https://www.dataclean.be"
    listing_url = "https://www.dataclean.be/nl/jobs"

    def is_job_url(self, url: str) -> bool:
        path = self.url_path(url)

        if not path.startswith("/nl/jobs/"):
            return False

        parts = path.split("/")
        return len(parts) >= 4 and parts[3].isdigit()