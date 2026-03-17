from __future__ import annotations

import re
import time
from typing import Dict, List
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from scrapers.base import BaseScraper


class ResolvusScraper(BaseScraper):
    source = "resolvus"
    base_url = "https://resolvus.be"
    listing_url = "https://resolvus.be/vacatures/"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        )
    }

    def get_soup(self, url: str) -> BeautifulSoup:
        response = requests.get(url, headers=self.headers, timeout=20)
        response.raise_for_status()
        return BeautifulSoup(response.text, "lxml")

    def clean_text(self, text: str) -> str:
        return " ".join(text.split())

    def is_job_detail_url(self, url: str) -> bool:
        parsed = urlparse(url)
        path = parsed.path.rstrip("/").lower()

        if parsed.netloc and parsed.netloc != urlparse(self.base_url).netloc:
            return False

        if path in {"", "/", "/vacatures"}:
            return False

        if path.startswith("/vacature-"):
            return True

        if path.startswith("/vacature/"):
            return True

        return False

    def extract_job_links_from_page(self, listing_url: str) -> List[str]:
        soup = self.get_soup(listing_url)
        links = set()

        for a in soup.find_all("a", href=True):
            absolute_url = urljoin(self.base_url, a["href"])

            if not self.is_job_detail_url(absolute_url):
                continue

            text = self.clean_text(a.get_text(" ", strip=True)).lower()
            if "spontane sollicitatie" in text:
                continue
            if "solliciteer spontaan" in text:
                continue

            links.add(absolute_url)

        return sorted(links)

    def extract_location(self, soup: BeautifulSoup) -> tuple[str, bool]:
        for el in soup.select(".iwt-text"):
            text = self.clean_text(el.get_text(" ", strip=True))
            if not text:
                continue

            address_match = re.search(
                r"\b\d{4}\s+([A-Za-zÀ-ÖØ-öø-ÿ'’\-/ ]+)$",
                text,
            )
            if address_match:
                city = self.clean_text(address_match.group(1))
                if city:
                    return city, False

            guessed_location = self.guess_location_from_text(text)
            if guessed_location:
                return guessed_location, True

        return "", False

    def parse_job_detail(self, job_url: str) -> Dict[str, str] | None:
        soup = self.get_soup(job_url)

        title = ""
        title_tag = soup.find("h1")
        if title_tag:
            title = self.clean_text(title_tag.get_text())

        if not title:
            for tag in soup.find_all(["h1", "h2", "h3"]):
                text = self.clean_text(tag.get_text(" ", strip=True))
                if text and text.lower() not in {"vacatures", "spontane sollicitatie"}:
                    title = text
                    break

        if not title and soup.title and soup.title.string:
            title = self.clean_text(soup.title.string)

        if not title:
            return None

        location, location_is_guess = self.extract_location(soup)

        return self.build_job_dict(
            title=title,
            url=job_url,
            location=location,
            location_is_guess=location_is_guess,
        )

    def scrape_jobs(self) -> List[Dict[str, str]]:
        all_job_links = set()

        for listing_url in self.get_listing_urls():
            print(f"Fetching listing page: {listing_url}")
            page_links = self.extract_job_links_from_page(listing_url)
            all_job_links.update(page_links)

        job_links = sorted(all_job_links)

        print(f"Found {len(job_links)} job links\n")

        jobs = []

        for url in job_links:
            print(f"Scraping: {url}")
            try:
                job = self.parse_job_detail(url)
                if job:
                    jobs.append(job)
                time.sleep(1)
            except Exception as exc:
                print(f"Failed to scrape {url}: {exc}")

        return self.sort_jobs(jobs)