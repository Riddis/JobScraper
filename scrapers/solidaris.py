from __future__ import annotations

from bs4 import BeautifulSoup

from scrapers.base import ListingDetailScraper


class SolidarisScraper(ListingDetailScraper):
    source = "solidaris"
    base_url = "https://jobs.solidaris-vlaanderen.be"
    listing_url = "https://jobs.solidaris-vlaanderen.be/"

    job_path_prefixes = ("/vacatures/",)
    title_suffixes_to_strip = (" - Jobs - Solidaris",)

    def extract_title_from_listing_anchor(
        self,
        a: BeautifulSoup,
        url: str,
    ) -> str:
        card = a.find_parent(class_=lambda value: value and "job card" in value)
        if card:
            title_el = card.select_one("h4 a span")
            if title_el:
                return self.clean_text(title_el.get_text(" ", strip=True))

        return self.clean_text(a.get_text(" ", strip=True))

    def extract_location_from_listing_anchor(
        self,
        a: BeautifulSoup,
        url: str,
    ) -> str:
        card = a.find_parent(class_=lambda value: value and "job card" in value)
        if not card:
            return ""

        meta_group = card.select_one(".meta_group.job__meta")
        if not meta_group:
            return ""

        for p in meta_group.select("p"):
            icon = p.select_one("i.bi-pin")
            if not icon:
                continue

            location_el = p.select_one("span.font-semibold")
            if not location_el:
                continue

            location = self.clean_text(location_el.get_text(" ", strip=True))
            if location:
                return location

        return ""