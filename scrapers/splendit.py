from __future__ import annotations

import time
from typing import Dict, List
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from scrapers.base import BaseScraper


class SplendITScraper(BaseScraper):
    source = "splendit"
    base_url = "http://splenditnet.webhosting.be"
    listing_url = "http://splenditnet.webhosting.be/nl/onze-vacatures"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        )
    }

    def get_soup(self, url: str) -> BeautifulSoup:
        response = requests.get(url, headers=self.headers, timeout=30)
        response.raise_for_status()
        return BeautifulSoup(response.text, "lxml")

    def clean_text(self, text: str) -> str:
        return " ".join(text.split())

    def is_job_detail_url(self, url: str) -> bool:
        parsed = urlparse(url)
        path = parsed.path.rstrip("/").lower()

        if not path.startswith("/nl/onze-vacatures/"):
            return False

        if path == "/nl/onze-vacatures":
            return False

        return True

    def extract_job_links_from_page(self, listing_url: str) -> List[str]:
        soup = self.get_soup(listing_url)
        jobs_by_url = self.extract_listing_jobs(soup)
        return sorted(jobs_by_url)

    def find_job_url_for_article(self, article: BeautifulSoup) -> str:
        for a in article.find_all("a", href=True):
            absolute_url = urljoin(self.base_url, a["href"])
            if self.is_job_detail_url(absolute_url):
                return absolute_url

        parent = article.parent
        while parent is not None:
            if getattr(parent, "name", None) == "a" and parent.get("href"):
                absolute_url = urljoin(self.base_url, parent["href"])
                if self.is_job_detail_url(absolute_url):
                    return absolute_url

            for a in parent.find_all("a", href=True):
                absolute_url = urljoin(self.base_url, a["href"])
                if self.is_job_detail_url(absolute_url):
                    return absolute_url

            parent = parent.parent

        return ""

    def extract_listing_jobs(self, soup: BeautifulSoup) -> Dict[str, Dict[str, str]]:
        jobs_by_url: Dict[str, Dict[str, str]] = {}

        for article in soup.select("article[itemtype='http://schema.org/JobPosting']"):
            job_url = self.find_job_url_for_article(article)
            if not job_url:
                continue

            cta_text = self.clean_text(article.get_text(" ", strip=True)).lower()
            if "bekijk deze vacature" not in cta_text and "lees meer" not in cta_text:
                continue

            title = ""
            title_el = article.select_one("[itemprop='title'], h1, h2, h3, h4")
            if title_el:
                title = self.clean_text(title_el.get_text(" ", strip=True))

            location = ""
            location_el = article.select_one(
                ".vacature-item-practical-region[itemprop='jobLocation']"
            )
            if not location_el:
                location_el = article.select_one("[itemprop='jobLocation']")

            if location_el:
                location = self.clean_text(location_el.get_text(" ", strip=True))

            jobs_by_url[job_url] = {
                "title": title,
                "location": location,
            }

        return jobs_by_url

    def parse_job_detail(
        self,
        job_url: str,
        listing_title: str = "",
        listing_location: str = "",
    ) -> Dict[str, str] | None:
        soup = self.get_soup(job_url)

        title = self.clean_text(listing_title)

        if not title:
            title_tag = soup.find("h1")
            if title_tag:
                title = self.clean_text(title_tag.get_text())

        if not title:
            for tag in soup.find_all(["h1", "h2", "h3"]):
                text = self.clean_text(tag.get_text(" ", strip=True))
                if text and text.lower() not in {"onze vacatures", "solliciteer"}:
                    title = text
                    break

        if not title and soup.title and soup.title.string:
            title = self.clean_text(soup.title.string)

        if not title:
            return None

        return self.build_job_dict(
            title=title,
            url=job_url,
            location=self.clean_text(listing_location),
            location_is_guess=False,
        )

    def scrape_jobs(self) -> List[Dict[str, str]]:
        jobs_by_url: Dict[str, Dict[str, str]] = {}

        for listing_url in self.get_listing_urls():
            print(f"Fetching listing page: {listing_url}")
            soup = self.get_soup(listing_url)
            page_jobs = self.extract_listing_jobs(soup)
            jobs_by_url.update(page_jobs)

        job_links = sorted(jobs_by_url)

        print(f"Found {len(job_links)} job links\n")

        jobs = []

        for url in job_links:
            print(f"Scraping: {url}")
            try:
                job = self.parse_job_detail(
                    job_url=url,
                    listing_title=jobs_by_url[url].get("title", ""),
                    listing_location=jobs_by_url[url].get("location", ""),
                )
                if job:
                    jobs.append(job)
                time.sleep(1)
            except Exception as exc:
                print(f"Failed to scrape {url}: {exc}")

        return self.sort_jobs(jobs)