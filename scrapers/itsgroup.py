from __future__ import annotations

import re
from typing import Dict, List

from bs4 import BeautifulSoup

from scrapers.base import BaseScraper


class ITSGroupScraper(BaseScraper):
    source = "itsgroup"
    base_url = "https://carriere.itsgroup.fr"
    listing_url = "https://carriere.itsgroup.fr/"

    title_suffixes_to_strip: tuple[str, ...] = ()

    location_selectors: tuple[str, ...] = ()

    location_patterns: tuple[str, ...] = (
        r"\b(?:locatie|location|standplaats|plaats van tewerkstelling|lieu de travail|arbeitsort)\s*[:\-]\s*([A-ZÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ'’\-/ ]+)",
        r"\b(?:gebaseerd in|based in|basé à|based at)\s+([A-ZÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ'’\-/ ]+)",
        r"\b(?:hoofdzetel te|gevestigd te)\s+([A-ZÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ'’\-/ ]+)",
    )

    def get_total_pages(self, soup: BeautifulSoup) -> int:
        max_page = 1

        for a in soup.find_all("a", class_="pagination"):
            text = self.clean_text(a.get_text(" ", strip=True))
            if text.isdigit():
                max_page = max(max_page, int(text))

        return max_page

    def get_listing_page(self, page: int) -> BeautifulSoup:
        data = {
            "mots_clef": "",
            "region": "",
            "profil": "",
            "type_contrat": "",
            "entite": "",
            "date_publication": "",
            "val_selected": "9",
            "page": str(page),
            "o_mots": "",
            "o_region": "",
            "o_type_contrat": "",
            "o_profil": "",
            "o_entite": "",
            "o_date_publi": "",
        }

        response = self.session.post(
            self.listing_url,
            headers={
                "Origin": self.base_url,
                "Referer": self.listing_url,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data=data,
            timeout=20,
        )
        response.raise_for_status()
        return BeautifulSoup(response.text, "lxml")

    def extract_first_seen_date_from_card(self, card: BeautifulSoup) -> str:
        text = self.clean_text(card.get_text(" ", strip=True))
        match = re.search(r"Publié le\s+(\d{4}-\d{2}-\d{2})", text)
        if match:
            return match.group(1)
        return ""

    def extract_title_from_card(self, card: BeautifulSoup) -> str:
        title_tag = card.select_one("h1.titre_offre")
        if title_tag:
            text = self.clean_text(title_tag.get_text(" ", strip=True))
            if text:
                return text

        for tag_name in ("h1", "h2", "h3", "h4"):
            tag = card.find(tag_name)
            if tag:
                text = self.clean_text(tag.get_text(" ", strip=True))
                if text:
                    return text

        for tag in card.find_all(["strong", "a"]):
            text = self.clean_text(tag.get_text(" ", strip=True))
            if text and not text.lower().startswith("publié le"):
                return text

        return ""

    def extract_location_from_card(self, card: BeautifulSoup) -> str:
        location_tag = card.select_one("p.localisation")
        if not location_tag:
            return ""

        text = self.clean_text(location_tag.get_text(" ", strip=True))
        if not text:
            return ""

        guessed = self.guess_location_from_text(text)
        if guessed:
            return guessed

        return text

    def extract_offer_id_from_card(self, card: BeautifulSoup) -> str:
        html = str(card)

        patterns = [
            r'id_offre["\']?\s*[:=]\s*["\']?(\d+)',
            r'name=["\']id_offre["\']\s+value=["\'](\d+)["\']',
            r'value=["\'](\d+)["\']\s+name=["\']id_offre["\']',
            r'/(\d+)/detail_annonce\.php',
            r'detail_annonce\.php[^"\']*id_offre=(\d+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                return match.group(1)

        return ""

    def build_job_url(self, offer_id: str) -> str:
        return f"{self.base_url}/{offer_id}/detail_annonce.php"

    def extract_jobs_from_page(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        jobs: List[Dict[str, str]] = []
        cards = soup.find_all(class_="resultat")

        for card in cards:
            title = self.extract_title_from_card(card)
            location = self.extract_location_from_card(card)
            offer_id = self.extract_offer_id_from_card(card)
            first_seen_date = self.extract_first_seen_date_from_card(card)

            if not title or not offer_id:
                continue

            jobs.append(
                {
                    "source": self.source,
                    "title": title,
                    "url": self.build_job_url(offer_id),
                    "first_seen_date": first_seen_date,
                    "location": location,
                    "location_is_guess": "False",
                }
            )

        return jobs

    def extract_title_from_detail_soup(
        self,
        soup: BeautifulSoup,
        fallback_title: str = "",
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

        if not title:
            title = self.clean_text(fallback_title)

        for suffix in self.title_suffixes_to_strip:
            title = title.replace(suffix, "")

        return self.clean_text(title)

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

    def scrape_jobs(self) -> List[Dict[str, str]]:
        self.log_fetching(f"{self.listing_url} (page 1)")
        first_page_soup = self.get_listing_page(page=1)
        total_pages = self.get_total_pages(first_page_soup)

        jobs_by_url: Dict[str, Dict[str, str]] = {}

        first_page_jobs = self.extract_jobs_from_page(first_page_soup)
        for job in first_page_jobs:
            jobs_by_url[job["url"]] = job

        for page in range(2, total_pages + 1):
            self.log_fetching(f"{self.listing_url} (page {page})")
            soup = self.get_listing_page(page=page)
            page_jobs = self.extract_jobs_from_page(soup)

            for job in page_jobs:
                jobs_by_url[job["url"]] = job

        self.log_found(len(jobs_by_url))

        jobs: List[Dict[str, str]] = []

        for url in sorted(jobs_by_url):
            self.log_scraping(url)

            listing_title = jobs_by_url[url].get("title", "")
            listing_location = jobs_by_url[url].get("location", "")
            first_seen_date = jobs_by_url[url].get("first_seen_date", "")

            soup = self.get_soup(url)

            title = self.clean_text(listing_title) or self.extract_title_from_detail_soup(
                soup,
                fallback_title=listing_title,
            )
            if not title:
                continue

            location = self.clean_text(listing_location)
            location_is_guess = False

            if not location:
                location, location_is_guess = self.extract_location_from_detail_soup(soup)

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