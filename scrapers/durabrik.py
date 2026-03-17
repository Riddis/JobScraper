from __future__ import annotations

from bs4 import BeautifulSoup

from scrapers.base import ListingDetailScraper


class DurabrikScraper(ListingDetailScraper):
    source = "durabrik"
    base_url = "https://www.durabrik.be"
    listing_url = "https://www.durabrik.be/nl/jobs/vacatures"

    job_path_prefixes = ("/nl/jobs/vacatures/",)
    listing_anchor_text_blacklist = (
        "geen vacature op jouw maat teruggevonden?",
    )

    def extract_title_from_listing_anchor(
        self,
        a: BeautifulSoup,
        url: str,
    ) -> str:
        return self.clean_text(a.get_text(" ", strip=True))