from __future__ import annotations

import time
from typing import Dict, List
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from scrapers.base import BaseScraper


class UpgradeEstateScraper(BaseScraper):
    source = "upgrade_estate"
    base_url = "https://upgrade-estate.be"
    jobs_base_url = "https://jobs.upgrade-estate.be"
    listing_url = "https://upgrade-estate.be/nl/jobs"

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
        netloc = parsed.netloc.lower()

        if netloc != "jobs.upgrade-estate.be":
            return False

        if not path.startswith("/nl/"):
            return False

        excluded_paths = {
            "/nl",
            "/nl/jobs",
            "/nl/spontane-sollicitatie",
            "/nl/stage",
        }

        if path in excluded_paths:
            return False

        return True

    def extract_job_links_from_page(self, listing_url: str) -> List[str]:
        soup = self.get_soup(listing_url)
        links = set()

        for a in soup.find_all("a", href=True):
            href = a["href"]
            absolute_url = urljoin(self.base_url, href)

            if not self.is_job_detail_url(absolute_url):
                continue

            text = self.clean_text(a.get_text(" ", strip=True)).lower()
            if not text:
                continue

            if "spontane sollicitatie" in text:
                continue
            if "spontaneous application" in text:
                continue

            links.add(absolute_url)

        return sorted(links)

    def extract_location(self, soup: BeautifulSoup) -> str:
        header = soup.select_one("#job_header_text")
        if not header:
            return ""

        h2 = header.select_one("h2")
        if not h2:
            return ""

        spans = h2.select("span")
        for span in spans:
            text = self.clean_text(span.get_text(" ", strip=True))
            if not text:
                continue

            if text.lower().startswith("in "):
                return self.clean_text(text[3:])

        h2_text = self.clean_text(h2.get_text(" ", strip=True))
        if h2_text.lower().startswith("in "):
            return self.clean_text(h2_text[3:])

        return ""

    def parse_job_detail(self, job_url: str) -> Dict[str, str] | None:
        soup = self.get_soup(job_url)

        title = ""
        title_tag = soup.find("h1")
        if title_tag:
            title = self.clean_text(title_tag.get_text())

        if not title:
            for tag in soup.find_all(["h1", "h2", "h3"]):
                text = self.clean_text(tag.get_text(" ", strip=True))
                if text and text.lower() not in {"jobs", "spontane sollicitatie"}:
                    title = text
                    break

        if not title and soup.title and soup.title.string:
            title = self.clean_text(soup.title.string)

        if not title:
            return None

        location = self.extract_location(soup)

        return self.build_job_dict(
            title=title,
            url=job_url,
            location=location,
            location_is_guess=False,
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