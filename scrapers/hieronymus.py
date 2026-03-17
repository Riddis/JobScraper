from __future__ import annotations

from bs4 import BeautifulSoup
from urllib.parse import urlparse

from scrapers.base import ListingDetailScraper


class HieronymusScraper(ListingDetailScraper):
    source = "hieronymus"
    base_url = "https://www.hieronymus.be"
    listing_url = "https://www.hieronymus.be/vacatures/"

    def is_job_url(self, url: str) -> bool:
        parsed = urlparse(url)
        path = parsed.path.rstrip("/").lower()
        netloc = parsed.netloc.lower()

        if netloc != "hieronymus.hr-technologies.com":
            return False

        return path.startswith("/front/nl/vacancies/")

    def extract_title_from_listing_anchor(
        self,
        a: BeautifulSoup,
        url: str,
    ) -> str:
        return self.clean_text(a.get_text(" ", strip=True))