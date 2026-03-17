from __future__ import annotations

from bs4 import BeautifulSoup

from scrapers.base import PaginatedListingDetailScraper


class EvaraScraper(PaginatedListingDetailScraper):
    source = "evara"
    base_url = "https://evara.be"
    listing_url = "https://evara.be/jobs"

    job_path_prefixes = ("/jobs/",)

    page_param = "page"
    start_page = 1

    def extract_location_from_listing_anchor(
        self,
        a: BeautifulSoup,
        url: str,
    ) -> str:
        cell = a.find_parent("td")
        if not cell:
            return ""

        time_tag = cell.find("time")
        if not time_tag:
            return ""

        text = self.clean_text(cell.get_text(" ", strip=True))
        time_text = self.clean_text(time_tag.get_text(" ", strip=True))

        if not text or not time_text:
            return ""

        if time_text in text:
            text = text.split(time_text, 1)[1].strip()

        parts = [self.clean_text(part) for part in text.split(" - ") if self.clean_text(part)]

        if len(parts) >= 2:
            city = parts[0]
            guessed = self.guess_location_from_text(city)
            if guessed:
                return guessed
            return self.normalize_location_value(city)

        return ""