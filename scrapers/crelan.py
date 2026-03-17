from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup

from scrapers.base import ListingDetailScraper


class CrelanScraper(ListingDetailScraper):
    source = "crelan"
    base_url = "https://www.crelan.be"
    listing_url = "https://www.crelan.be/nl/jobs/hoofdzetel"

    job_path_prefixes = (
        "/nl/jobs/functie/",
        "/fr/jobs/fonction/",
        "/nl/particulieren/functie/",
        "/fr/particuliers/fonction/",
    )

    def extract_title_from_listing_anchor(
        self,
        a: BeautifulSoup,
        url: str,
    ) -> str:
        text = self.clean_text(a.get_text(" ", strip=True))
        match = re.search(r"^Bekijk de (.+?) vacature$", text, re.IGNORECASE)
        if match:
            return self.clean_text(match.group(1))
        return ""

    def extract_title_from_detail_soup(
        self,
        soup: BeautifulSoup,
        url: str,
    ) -> str:
        h1 = soup.find("h1")
        if h1:
            title = self.clean_text(h1.get_text(" ", strip=True))
            title = re.sub(
                r"^Werken bij Crelan als\s+",
                "",
                title,
                flags=re.IGNORECASE,
            )
            if title:
                return title

        ignored_headings = {
            "werken bij crelan",
            "wat verwacht crelan van jou?",
            "jouw functie",
            "jouw profiel",
            "geïnteresseerd in deze job?",
            "wij bieden jou...",
            "ons aanbod",
        }

        for heading in soup.find_all(["h1", "h2", "h3"]):
            text = self.clean_text(heading.get_text(" ", strip=True))
            if not text:
                continue

            text = re.sub(
                r"^Werken bij Crelan als\s+",
                "",
                text,
                flags=re.IGNORECASE,
            )
            text = self.clean_text(text)

            if text and text.lower() not in ignored_headings:
                return text

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

                if item.get("@type") != "JobPosting":
                    continue

                date_posted = item.get("datePosted")
                if isinstance(date_posted, str):
                    match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", date_posted)
                    if match:
                        return match.group(1)

        return ""

    def parse_job_detail(
        self,
        url: str,
        listing_title: str = "",
        listing_location: str = "",
    ) -> dict[str, str] | None:
        need_detail = True

        soup = self.get_soup(url) if need_detail else None
        if soup is None:
            return None

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