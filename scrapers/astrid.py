from __future__ import annotations

import re

from bs4 import BeautifulSoup

from scrapers.base import ListingDetailScraper


class AstridScraper(ListingDetailScraper):
    source = "astrid"
    base_url = "https://jobs.astrid.be"
    listing_url = "https://jobs.astrid.be/search/?createNewAlert=false&q=&locale=nl_NL"

    job_path_prefixes = ("/job/",)
    title_suffixes_to_strip = (" Functiedetails | ASTRID",)

    listing_anchor_text_blacklist = (
        "meer informatie",
        "cookie",
    )

    def extract_title_from_listing_anchor(
        self,
        a: BeautifulSoup,
        url: str,
    ) -> str:
        return self.clean_text(a.get_text(" ", strip=True))

    def extract_title_from_detail_soup(
        self,
        soup: BeautifulSoup,
        url: str,
    ) -> str:
        title = super().extract_title_from_detail_soup(soup, url)

        title = re.sub(
            r"\s+Functiedetails\s*\|\s*ASTRID$",
            "",
            title,
            flags=re.IGNORECASE,
        )

        return self.clean_text(title)