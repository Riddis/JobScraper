from __future__ import annotations

import re
import time
from typing import Dict, List
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from scrapers.base import BaseScraper


class PlanetGroupAjaxScraper(BaseScraper):
    source: str = ""
    base_url: str = ""
    listing_url: str = ""
    ajax_url: str = ""
    ajax_action: str = "myfilter"

    location_selectors: tuple[str, ...] = ()
    title_suffixes_to_strip: tuple[str, ...] = ()

    location_patterns: tuple[str, ...] = (
        r"\b(?:locatie|location|standplaats|plaats van tewerkstelling|lieu de travail|arbeitsort)\s*[:\-]\s*([A-ZÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ'’\-/ ]+)",
        r"\b(?:gebaseerd in|based in|basé à|based at)\s+([A-ZÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ'’\-/ ]+)",
        r"\b(?:hoofdzetel te|gevestigd te)\s+([A-ZÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ'’\-/ ]+)",
    )

    def get_ajax_page(self, page: int) -> BeautifulSoup:
        response = self.session.post(
            self.ajax_url,
            headers={
                "Accept": "*/*",
                "Origin": self.base_url,
                "Referer": self.listing_url,
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            },
            data={
                "page": str(page),
                "action": self.ajax_action,
            },
            timeout=20,
        )
        response.raise_for_status()
        return BeautifulSoup(response.text, "lxml")

    def extract_total_pages(self, soup: BeautifulSoup) -> int:
        max_page = 1

        for li in soup.select("ul.pagination-wrapper li.pagination"):
            value = li.get("value", "").strip()
            text = self.clean_text(li.get_text(" ", strip=True))

            if value.isdigit():
                max_page = max(max_page, int(value))

            if text.isdigit():
                max_page = max(max_page, int(text))

        return max_page

    def extract_first_seen_date(self, meta_text: str) -> str:
        """
        Convert '9/3/2026 - Oost-Vlaanderen' -> '2026-03-09'
        """
        match = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", meta_text)
        if not match:
            return ""

        day, month, year = match.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"

    def normalize_location_value(self, text: str) -> str:
        text = self.clean_text(text)
        text = re.split(r"\s{2,}|\s+\|\s+|\s+/\s+", text)[0]
        text = re.sub(
            r"^(locatie|location|standplaats|plaats van tewerkstelling|lieu de travail|arbeitsort)\s*[:\-]\s*",
            "",
            text,
            flags=re.IGNORECASE,
        )
        return self.clean_text(text)

    def extract_location_from_candidate(self, text: str) -> str:
        candidate = self.normalize_location_value(text)
        if not candidate:
            return ""

        guessed = self.guess_location_from_text(candidate)
        if guessed:
            return guessed

        if len(candidate) <= 120:
            return candidate

        return ""

    def split_title_and_location(self, title: str) -> tuple[str, str]:
        title = self.clean_text(title)

        for suffix in self.title_suffixes_to_strip:
            title = title.replace(suffix, "")

        title = self.clean_text(title)
        if not title:
            return "", ""

        match = re.match(
            r"^(?P<title>.+?)\s*[-–—]\s*(?P<location>[^-–—]+?)\s*$",
            title,
        )
        if not match:
            return title, ""

        clean_title = self.clean_text(match.group("title"))
        location = self.extract_location_from_candidate(match.group("location"))

        if clean_title and location:
            return clean_title, location

        return title, ""

    def extract_location_from_url(self, url: str) -> str:
        parsed = urlparse(url)
        slug = parsed.path.rstrip("/").split("/")[-1].strip().lower()
        if not slug:
            return ""

        parts = [part for part in slug.split("-") if part]
        if not parts:
            return ""

        for size in range(min(3, len(parts)), 0, -1):
            candidate = " ".join(parts[-size:])
            location = self.extract_location_from_candidate(candidate)
            if location:
                return location

        return ""

    def extract_location_from_meta_text(self, meta_text: str) -> tuple[str, bool]:
        candidate = re.sub(
            r"^\s*\d{1,2}/\d{1,2}/\d{4}\s*[-–—]\s*",
            "",
            meta_text,
            flags=re.IGNORECASE,
        )
        candidate = self.normalize_location_value(candidate)

        if not candidate:
            return "", False

        guessed = self.guess_location_from_text(candidate)
        if guessed:
            return guessed, False

        return candidate, False

    def extract_title_from_detail_soup(
        self,
        soup: BeautifulSoup,
        url: str,
    ) -> str:
        title = ""

        h1 = soup.find("h1")
        if h1:
            title = self.clean_text(h1.get_text(" ", strip=True))

        if not title:
            og_title = soup.find("meta", attrs={"property": "og:title"})
            if og_title and og_title.get("content"):
                title = self.clean_text(og_title["content"])

        if not title:
            title_tag = soup.find("title")
            if title_tag:
                title = self.clean_text(title_tag.get_text(" ", strip=True))

        for suffix in self.title_suffixes_to_strip:
            title = title.replace(suffix, "")

        title, _ = self.split_title_and_location(title)
        return self.clean_text(title)

    def extract_location_from_selectors(self, soup: BeautifulSoup) -> str:
        for selector in self.location_selectors:
            for el in soup.select(selector):
                text = self.normalize_location_value(el.get_text(" ", strip=True))
                if not text:
                    continue

                guessed = self.guess_location_from_text(text)
                if guessed:
                    return guessed

                if len(text) <= 120:
                    return text

        return ""

    def extract_location_from_patterns(self, soup: BeautifulSoup) -> str:
        text = self.extract_location_candidate_text(soup)

        for pattern in self.location_patterns:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                candidate = self.normalize_location_value(match.group(1))
                if not candidate:
                    continue

                guessed = self.guess_location_from_text(candidate)
                if guessed:
                    return guessed

                if len(candidate) <= 120:
                    return candidate

        return ""

    def extract_location_from_detail_soup(
        self,
        soup: BeautifulSoup,
        url: str,
    ) -> tuple[str, bool]:
        location = self.extract_location_from_selectors(soup)
        if location:
            return location, False

        location = self.extract_location_from_patterns(soup)
        if location:
            return location, False

        candidate_text = self.extract_location_candidate_text(soup)
        location = self.guess_location_from_text(candidate_text)
        if location:
            return location, True

        return "", False

    def extract_jobs_from_soup(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        jobs: List[Dict[str, str]] = []

        for card in soup.select("div.vacature-search-result"):
            link = card.find("a", href=True)
            if not link:
                continue

            title_tag = link.find("h3")
            meta_tag = link.find("p")

            raw_title = (
                self.clean_text(title_tag.get_text(" ", strip=True))
                if title_tag
                else ""
            )
            title, title_location = self.split_title_and_location(raw_title)

            url = link["href"].strip()
            meta_text = (
                self.clean_text(meta_tag.get_text(" ", strip=True))
                if meta_tag
                else ""
            )
            first_seen_date = self.extract_first_seen_date(meta_text)

            meta_location, meta_location_is_guess = self.extract_location_from_meta_text(
                meta_text
            )

            listing_location = ""
            listing_location_is_guess = False

            if title_location:
                listing_location = title_location
                listing_location_is_guess = False
            elif meta_location:
                listing_location = meta_location
                listing_location_is_guess = meta_location_is_guess
            else:
                url_location = self.extract_location_from_url(url)
                if url_location:
                    listing_location = url_location
                    listing_location_is_guess = False

            if not title or not url:
                continue

            jobs.append(
                {
                    "source": self.source,
                    "title": title,
                    "url": url,
                    "first_seen_date": first_seen_date,
                    "location": listing_location,
                    "location_is_guess": (
                        "True" if listing_location_is_guess else "False"
                    ),
                }
            )

        return jobs

    def scrape_jobs(self) -> List[Dict[str, str]]:
        self.log_fetching("API page 1")
        first_page_soup = self.get_ajax_page(1)
        total_pages = self.extract_total_pages(first_page_soup)

        jobs_by_url: Dict[str, Dict[str, str]] = {}

        first_page_jobs = self.extract_jobs_from_soup(first_page_soup)
        for job in first_page_jobs:
            jobs_by_url[job["url"]] = job

        for page in range(2, total_pages + 1):
            self.log_fetching(f"API page {page}")
            soup = self.get_ajax_page(page)
            page_jobs = self.extract_jobs_from_soup(soup)

            for job in page_jobs:
                jobs_by_url[job["url"]] = job

            time.sleep(1)

        jobs: List[Dict[str, str]] = []

        for url in sorted(jobs_by_url):
            self.log_scraping(url)

            listing_title = self.clean_text(jobs_by_url[url].get("title", ""))
            first_seen_date = jobs_by_url[url].get("first_seen_date", "")
            fallback_location = self.clean_text(jobs_by_url[url].get("location", ""))
            fallback_location_is_guess = (
                str(jobs_by_url[url].get("location_is_guess", "False")).strip()
                == "True"
            )

            soup = self.get_soup(url)

            title = self.extract_title_from_detail_soup(soup, url) or listing_title
            if not title:
                continue

            location, location_is_guess = self.extract_location_from_detail_soup(
                soup,
                url,
            )

            if not location:
                location = fallback_location
                location_is_guess = fallback_location_is_guess

            jobs.append(
                self.build_job_dict(
                    title=title,
                    url=url,
                    first_seen_date=first_seen_date,
                    location=location,
                    location_is_guess=location_is_guess,
                )
            )

        return self.sort_jobs(jobs)