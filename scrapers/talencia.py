from __future__ import annotations

from typing import Dict, List

from bs4 import BeautifulSoup

from scrapers.base import BaseScraper


class TalenciaScraper(BaseScraper):
    source = "talencia"
    base_url = "https://www.talencia.be"
    listing_url = "https://www.talencia.be/all-jobs/"

    def is_job_url(self, url: str) -> bool:
        path = self.url_path(url)
        return path.startswith("/jobs/")

    def build_listing_url(self, page: int) -> str:
        if page == 1:
            return self.listing_url
        return f"{self.listing_url}?paged={page}"

    def extract_job_links_from_page(self, page_url: str) -> List[str]:
        soup = self.get_soup(page_url)
        links = set()

        for a in soup.select("a[href]"):
            url = self.normalize_url(page_url, a.get("href"))
            if not url:
                continue

            if not self.is_job_url(url):
                continue

            links.add(url)

        return sorted(links)

    def extract_location_from_detail_soup(self, soup: BeautifulSoup) -> str:
        for el in soup.select(".job-location"):
            text = self.clean_text(el.get_text(" ", strip=True))
            if not text:
                continue

            text = text.replace("fa-map-marker", "").strip()
            if text:
                return text

        return ""

    def parse_job_detail(self, url: str) -> Dict[str, str] | None:
        soup = self.get_soup(url)

        title = ""

        for tag in ["h1", "h2"]:
            heading = soup.find(tag)
            if heading:
                text = self.clean_text(heading.get_text(" ", strip=True))
                if text:
                    title = text
                    break

        if not title:
            og_title = soup.find("meta", attrs={"property": "og:title"})
            if og_title and og_title.get("content"):
                title = self.clean_text(og_title["content"])

        if not title:
            title_tag = soup.find("title")
            if title_tag:
                title = self.clean_text(title_tag.get_text(" ", strip=True))

        if not title:
            return None

        location = self.extract_location_from_detail_soup(soup)

        return self.build_job_dict(
            title=title,
            url=url,
            location=location,
            location_is_guess=False,
        )

    def scrape_jobs(self) -> List[Dict[str, str]]:
        links = set()
        page = 1

        while True:
            page_url = self.build_listing_url(page)
            print(f"Fetching listing page: {page_url}")

            page_links = self.extract_job_links_from_page(page_url)
            if not page_links:
                break

            previous_count = len(links)
            links.update(page_links)

            if len(links) == previous_count:
                break

            page += 1

        print(f"Found {len(links)} job links")

        jobs: List[Dict[str, str]] = []

        for url in sorted(links):
            print(f"Scraping: {url}")

            job = self.parse_job_detail(url)
            if not job:
                continue

            jobs.append(job)

        return self.sort_jobs(jobs)