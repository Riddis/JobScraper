from __future__ import annotations

from bs4 import BeautifulSoup

from scrapers.base import ListingDetailScraper


class District09Scraper(ListingDetailScraper):
    source = "district09"
    base_url = "https://district09.gent"
    listing_url = "https://district09.gent/nl/vacatures"

    job_path_prefixes = ("/nl/vacatures/",)
    listing_anchor_text_required = ("lees meer over",)

    def extract_location_from_listing_anchor(
        self,
        a: BeautifulSoup,
        url: str,
    ) -> str:
        return "Gent"

    def extract_location_from_detail_soup(
        self,
        soup: BeautifulSoup,
        url: str,
    ) -> str:
        return "Gent"