from __future__ import annotations

import time
from typing import Dict, List
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from scrapers.base import BaseScraper


class SimacScraper(BaseScraper):
    source = "simac"
    base_url = "https://jobssimac.be"
    listing_url = "https://jobssimac.be/vacatures/"

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

        if not url.startswith(self.base_url):
            return False

        if path in {
            "",
            "/",
            "/vacatures",
            "/contacteer-ons",
            "/disclaimer",
            "/privacy-en-cookiebeleid",
            "/fr/vacatures",
            "/en/vacancies",
        }:
            return False

        return True

    def extract_job_links_from_page(self, listing_url: str) -> List[str]:
        soup = self.get_soup(listing_url)
        links = set()

        for a in soup.find_all("a", href=True):
            absolute_url = urljoin(self.base_url, a["href"])
            if not self.is_job_detail_url(absolute_url):
                continue

            text = self.clean_text(a.get_text(" ", strip=True)).lower()
            if "bekijk vacature" not in text:
                continue

            links.add(absolute_url)

        return sorted(links)

    def extract_listing_locations(self, soup: BeautifulSoup) -> Dict[str, str]:
        locations_by_url: Dict[str, str] = {}

        for card in soup.select(".jet-listing-grid__item"):
            link = card.select_one("h4 a[href]")
            if not link:
                continue

            job_url = urljoin(self.base_url, link.get("href"))
            if not self.is_job_detail_url(job_url):
                continue

            for span in card.select(".elementor-icon-box-title span"):
                text = self.clean_text(span.get_text(" ", strip=True))
                if not text:
                    continue

                guessed_location = self.guess_location_from_text(text)
                if guessed_location:
                    locations_by_url[job_url] = guessed_location
                    break

        return locations_by_url

    def parse_job_detail(
        self,
        job_url: str,
        listing_location: str = "",
    ) -> Dict[str, str] | None:
        soup = self.get_soup(job_url)

        title = ""
        title_tag = soup.find("h1")
        if title_tag:
            title = self.clean_text(title_tag.get_text())

        if not title and soup.title and soup.title.string:
            title = self.clean_text(soup.title.string)

        if not title:
            return None

        return self.build_job_dict(
            title=title,
            url=job_url,
            location=listing_location,
            location_is_guess=False,
        )

    def scrape_jobs(self) -> List[Dict[str, str]]:
        all_job_links = set()
        locations_by_url: Dict[str, str] = {}

        for listing_url in self.get_listing_urls():
            print(f"Fetching listing page: {listing_url}")
            soup = self.get_soup(listing_url)
            page_links = self.extract_job_links_from_page(listing_url)
            all_job_links.update(page_links)
            locations_by_url.update(self.extract_listing_locations(soup))

        job_links = sorted(all_job_links)

        print(f"Found {len(job_links)} job links\n")

        jobs = []

        for url in job_links:
            print(f"Scraping: {url}")
            try:
                job = self.parse_job_detail(
                    job_url=url,
                    listing_location=locations_by_url.get(url, ""),
                )
                if job:
                    jobs.append(job)
                time.sleep(1)
            except Exception as exc:
                print(f"Failed to scrape {url}: {exc}")

        return self.sort_jobs(jobs)