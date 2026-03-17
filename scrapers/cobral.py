from __future__ import annotations

import json
import re
from typing import Dict

from bs4 import BeautifulSoup

from scrapers.base import ListingDetailScraper


class CobralScraper(ListingDetailScraper):
    source = "cobral"
    base_url = "https://www.cobral.be"
    listing_url = "https://www.cobral.be/jobs/"

    job_path_prefixes = ("/jobs/",)

    def normalize_first_seen_date(self, value: str) -> str:
        value = self.clean_text(value)

        match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", value)
        if match:
            return match.group(1)

        return ""

    def extract_first_seen_date_from_detail_soup(
        self,
        soup: BeautifulSoup,
    ) -> str:
        for script in soup.select("script[type='application/ld+json']"):
            raw = script.string or script.get_text(" ", strip=True)
            if not raw:
                continue

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            graph = data.get("@graph")
            if not isinstance(graph, list):
                continue

            for item in graph:
                if not isinstance(item, dict):
                    continue

                if item.get("@type") != "WebPage":
                    continue

                date_published = item.get("datePublished")
                if isinstance(date_published, str):
                    normalized = self.normalize_first_seen_date(date_published)
                    if normalized:
                        return normalized

        return ""

    def parse_job_detail(
        self,
        url: str,
        listing_title: str = "",
        listing_location: str = "",
    ) -> Dict[str, str] | None:
        soup = self.get_soup(url)

        title = self.clean_text(listing_title)
        if not title:
            title = self.extract_title_from_detail_soup(soup, url)

        if not title:
            return None

        location = self.clean_text(listing_location)
        location_is_guess = False

        if not location:
            location = self.extract_location_from_detail_soup(soup, url)

        if not location:
            candidate_text = self.extract_location_candidate_text(soup)
            location = self.guess_location_from_text(candidate_text)
            if location:
                location_is_guess = True

        first_seen_date = self.extract_first_seen_date_from_detail_soup(soup)

        return self.build_job_dict(
            title=title,
            url=url,
            first_seen_date=first_seen_date,
            location=location,
            location_is_guess=location_is_guess,
        )