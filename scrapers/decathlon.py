from __future__ import annotations

import re
from typing import List

from bs4 import BeautifulSoup

from scrapers.base import ListingDetailScraper


class DecathlonScraper(ListingDetailScraper):
    source = "decathlon"
    base_url = "https://jobs.decathlon.be"
    listing_url = "https://jobs.decathlon.be/nl/vacatures?o=0#vacancy-overview"

    fetch_detail_pages = False

    job_path_prefixes = ("/nl/vacatures/",)
    job_path_excludes = (
        "/nl/vacatures/favorieten",
    )

    def clean_job_title(self, title: str) -> str:
        title = title.replace("Bekijk vacature", "").strip()

        if " - " in title:
            title = title.split(" - ")[0]

        if " | " in title:
            title = title.split(" | ")[0]

        return title.strip()

    def extract_total_jobs(self, soup: BeautifulSoup) -> int | None:
        page_text = soup.get_text(" ", strip=True)
        match = re.search(
            r"\b\d+\s+t/m\s+\d+\s+van\s+(\d+)\b",
            page_text,
            re.IGNORECASE,
        )

        if match:
            return int(match.group(1))

        return None

    def build_listing_url(self, offset: int) -> str:
        return f"{self.base_url}/nl/vacatures?o={offset}#vacancy-overview"

    def extract_title_from_listing_anchor(
        self,
        a: BeautifulSoup,
        url: str,
    ) -> str:
        title_tag = a.find("h3")
        if title_tag:
            title = self.clean_text(title_tag.get_text(" ", strip=True))
        else:
            title = self.clean_text(a.get_text(" ", strip=True))

        if not title:
            return ""

        if title.lower() == "bekijk vacature":
            return ""

        return self.clean_job_title(title)

    def extract_location_from_listing_anchor(
        self,
        a: BeautifulSoup,
        url: str,
    ) -> str:
        location_li = a.select_one("li.location")
        if location_li:
            location_text = location_li.select_one(".metadata-text")
            if location_text:
                text = self.clean_text(location_text.get_text(" ", strip=True))
                if text:
                    guessed = self.guess_location_from_text(text)
                    if guessed:
                        return guessed
                    return self.normalize_location_value(text)

        for li in a.select("li"):
            classes = " ".join(li.get("class", []))
            if "location" not in classes.lower():
                continue

            location_text = li.select_one(".metadata-text")
            if not location_text:
                continue

            text = self.clean_text(location_text.get_text(" ", strip=True))
            if not text:
                continue

            guessed = self.guess_location_from_text(text)
            if guessed:
                return guessed
            return self.normalize_location_value(text)

        return ""

    def get_listing_urls(self) -> List[str]:
        first_page_url = self.build_listing_url(0)
        soup = self.get_soup(first_page_url)

        total_jobs = self.extract_total_jobs(soup)
        if total_jobs is None:
            return [first_page_url]

        page_size = 10
        offsets = range(0, total_jobs, page_size)

        return [self.build_listing_url(offset) for offset in offsets]