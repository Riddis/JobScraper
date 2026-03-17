from __future__ import annotations

import time
from typing import Dict, List
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from scrapers.base import BaseScraper


class VolvoCarsScraper(BaseScraper):
    source = "volvocars"
    base_url = "https://jobs.volvocars.com"
    listing_url = (
        "https://jobs.volvocars.com/search/"
        "?createNewAlert=false&q=&locationsearch=ghent"
        "&optionsFacetsDD_department=&optionsFacetsDD_country="
    )

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

    def build_listing_url(self, page_number: int) -> str:
        parsed = urlparse(self.listing_url)
        query = parse_qs(parsed.query)

        query["page"] = [str(page_number)]

        return urlunparse(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                urlencode(query, doseq=True),
                parsed.fragment,
            )
        )

    def is_job_detail_url(self, url: str) -> bool:
        path = self.url_path(url)

        if not path.startswith("/job/"):
            return False

        return True

    def extract_job_links_from_page(self, listing_url: str) -> List[str]:
        soup = self.get_soup(listing_url)
        links = set()

        for a in soup.find_all("a", href=True):
            absolute_url = self.normalize_url(self.base_url, a["href"])

            if not absolute_url:
                continue

            if not self.is_job_detail_url(absolute_url):
                continue

            links.add(absolute_url)

        return sorted(links)

    def parse_job_detail(self, job_url: str) -> Dict[str, str]:
        soup = self.get_soup(job_url)

        title = ""
        title_tag = soup.find("h1")
        if title_tag:
            title = self.clean_text(title_tag.get_text(" ", strip=True))

        if not title and soup.title and soup.title.string:
            title = self.clean_text(soup.title.string)
            title = title.replace(" Job Details | Volvo Car Corporation", "")
            title = self.clean_text(title)

        return {
            "source": self.source,
            "title": title,
            "url": job_url,
        }

    def scrape_jobs(self) -> List[Dict[str, str]]:
        all_job_links = set()
        page_number = 1

        while True:
            listing_url = self.build_listing_url(page_number)
            print(f"Fetching listing page: {listing_url}")

            try:
                page_links = self.extract_job_links_from_page(listing_url)
            except Exception as exc:
                print(f"Failed to fetch listing page {listing_url}: {exc}")
                break

            if not page_links:
                break

            previous_count = len(all_job_links)
            all_job_links.update(page_links)

            if len(all_job_links) == previous_count:
                break

            page_number += 1
            time.sleep(1)

        job_links = sorted(all_job_links)

        print(f"Found {len(job_links)} job links\n")

        jobs = []

        for url in job_links:
            print(f"Scraping: {url}")
            try:
                jobs.append(self.parse_job_detail(url))
                time.sleep(1)
            except Exception as exc:
                print(f"Failed to scrape {url}: {exc}")

        return jobs