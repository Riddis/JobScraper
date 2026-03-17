from __future__ import annotations

from typing import Dict, List

import requests
from bs4 import BeautifulSoup

from scrapers.base import BaseScraper


class TelevicScraper(BaseScraper):
    source = "televic"
    base_url = "https://careers.televic.com"
    listing_url = "https://careers.televic.com/jobs/"

    def clean_text(self, text: str) -> str:
        return " ".join(text.split())

    def is_job_url(self, url: str) -> bool:
        path = self.url_path(url)
        parts = [part for part in path.split("/") if part]

        if len(parts) != 3:
            return False

        if parts[0] != "jobs":
            return False

        return True

    def is_belgium_text(self, text: str) -> bool:
        return "belgium" in text.lower()

    def extract_title_from_card(self, card) -> str:
        for selector in ("h2", "h3", ".job-title", ".entry-title"):
            el = card.select_one(selector)
            if el:
                title = self.clean_text(el.get_text(" ", strip=True))
                if title:
                    return title

        return ""

    def extract_title_from_detail(self, soup: BeautifulSoup) -> str:
        h1 = soup.find("h1")
        if h1:
            title = self.clean_text(h1.get_text(" ", strip=True))
            if title:
                return title

        og_title = soup.find("meta", attrs={"property": "og:title"})
        if og_title and og_title.get("content"):
            return self.clean_text(og_title["content"])

        title_tag = soup.find("title")
        if title_tag:
            return self.clean_text(title_tag.get_text(" ", strip=True))

        return ""

    def detail_is_belgium(self, soup: BeautifulSoup) -> bool:
        text = self.clean_text(soup.get_text(" ", strip=True))
        return self.is_belgium_text(text)

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

            card = a
            for parent in a.parents:
                parent_text = self.clean_text(parent.get_text(" ", strip=True))
                if not parent_text:
                    continue

                if "read more" in parent_text.lower():
                    card = parent
                    break

            card_text = self.clean_text(card.get_text(" ", strip=True))
            if not self.is_belgium_text(card_text):
                continue

            title = self.extract_title_from_card(card)
            if not title:
                title = self.clean_text(a.get_text(" ", strip=True))

            if not title:
                continue

            if "spontaneous" in title.lower():
                continue

            links.add(url)
            link_titles[url] = title

        print(f"Found {len(links)} job links")

        jobs: List[Dict[str, str]] = []

        for url in sorted(links):
            print(f"Scraping: {url}")

            title = link_titles.get(url, "")

            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "lxml")

            if not self.detail_is_belgium(soup):
                continue

            if not title:
                title = self.extract_title_from_detail(soup)

            if not title:
                continue

            if "spontaneous" in title.lower():
                continue

            jobs.append(
                {
                    "source": self.source,
                    "title": title,
                    "url": url,
                }
            )

        return sorted(jobs, key=lambda job: (job["title"], job["url"]))