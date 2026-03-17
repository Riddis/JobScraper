from __future__ import annotations

from typing import Dict, List

import requests
from bs4 import BeautifulSoup

from scrapers.base import BaseScraper


class VerdonScraper(BaseScraper):
    source = "verdon"
    base_url = "https://www.groupe-verdon.com"
    listing_url = "https://www.groupe-verdon.com/en/recruitment"

    def clean_text(self, text: str) -> str:
        return " ".join(text.split())

    def is_job_url(self, url: str) -> bool:
        path = self.url_path(url)
        return path.startswith("/en/offer-") or path.startswith("/fr/offre-")

    def scrape_jobs(self) -> List[Dict[str, str]]:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        }

        links = set()
        link_titles = {}

        print(f"Fetching listing page: {self.listing_url}")

        response = requests.get(self.listing_url, headers=headers, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")

        for a in soup.select("a[href]"):
            href = a.get("href")
            url = self.normalize_url(self.listing_url, href)
            if not url:
                continue

            if not self.is_job_url(url):
                continue

            title = ""
            title_el = a.select_one(".offers_title")
            if title_el:
                title = self.clean_text(title_el.get_text(" ", strip=True))

            links.add(url)
            if title:
                link_titles[url] = title

        print(f"Found {len(links)} job links")

        jobs: List[Dict[str, str]] = []

        for url in sorted(links):
            print(f"Scraping: {url}")

            title = link_titles.get(url, "")

            if not title:
                response = requests.get(url, headers=headers, timeout=30)
                response.raise_for_status()

                soup = BeautifulSoup(response.text, "lxml")

                h1 = soup.find("h1")
                if h1:
                    title = self.clean_text(h1.get_text(" ", strip=True))

                if not title:
                    h2 = soup.find("h2")
                    if h2:
                        title = self.clean_text(h2.get_text(" ", strip=True))

            if not title:
                continue

            jobs.append(
                {
                    "source": self.source,
                    "title": title,
                    "url": url,
                }
            )

        return sorted(jobs, key=lambda job: (job["title"], job["url"]))