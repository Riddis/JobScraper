from __future__ import annotations

from bs4 import BeautifulSoup

from scrapers.base import ListingDetailScraper


class ITProviderScraper(ListingDetailScraper):
    source = "itprovider"
    base_url = "https://axi.recruitee.com"
    listing_url = "https://axi.recruitee.com/kmo"

    job_path_prefixes = ("/o/",)
    title_suffixes_to_strip = (" - AXI Holding Services",)

    def extract_location_from_listing_anchor(
        self,
        a: BeautifulSoup,
        url: str,
    ) -> str:
        el = a.select_one("span.custom-css-style-job-location-city")
        if not el:
            return ""

        text = self.clean_text(el.get_text(" ", strip=True))
        guessed = self.guess_location_from_text(text)

        if guessed:
            return guessed

        return text