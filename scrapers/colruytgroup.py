from __future__ import annotations

from typing import Dict, List
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from bs4 import BeautifulSoup

from scrapers.base import ListingDetailScraper


class ColruytGroupScraper(ListingDetailScraper):
    source = "colruytgroup"
    base_url = "https://jobs.colruytgroup.com"
    listing_url = (
        "https://jobs.colruytgroup.com/nl/vacatures/"
        "vakgebieden/it-digital?filter-radius=500&page=1"
    )

    use_curl = True
    fetch_detail_pages = False

    job_path_prefixes = ("/nl/vacatures/",)
    job_path_excludes = ("/nl/vacatures/vakgebieden",)

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

    def is_it_subcategory_url(self, url: str) -> bool:
        parsed = urlparse(url)
        path = parsed.path.rstrip("/").lower()

        if not url.startswith(self.base_url):
            return False

        if not path.startswith("/nl/vacatures/vakgebieden/it-digital/"):
            return False

        if path == "/nl/vacatures/vakgebieden/it-digital":
            return False

        return True

    def extract_title_from_listing_anchor(
        self,
        a: BeautifulSoup,
        url: str,
    ) -> str:
        title_tag = a.find("p", class_=lambda value: value and "font-bold" in " ".join(value))
        if title_tag:
            title = self.clean_text(title_tag.get_text(" ", strip=True))
            if title:
                return title

        return self.clean_text(a.get_text(" ", strip=True))

    def extract_location_from_listing_anchor(
        self,
        a: BeautifulSoup,
        url: str,
    ) -> str:
        location = a.get("data-tms-content-location", "")
        location = self.clean_text(str(location))

        if location:
            guessed = self.guess_location_from_text(location)
            if guessed:
                return guessed
            return self.normalize_location_value(location)

        for p in a.find_all("p"):
            text = self.clean_text(p.get_text(" ", strip=True))
            if not text:
                continue

            icon = p.find(
                "span",
                class_=lambda value: value and "icon-location" in value,
            )
            if icon:
                guessed = self.guess_location_from_text(text)
                if guessed:
                    return guessed
                return self.normalize_location_value(text)

        return ""

    def extract_first_seen_date_from_listing_anchor(
        self,
        a: BeautifulSoup,
    ) -> str:
        raw = self.clean_text(str(a.get("data-tms-content-creation-date", "")))
        if raw:
            return raw
        return ""

    def extract_links_from_listing_soup(
        self,
        soup: BeautifulSoup,
        page_url: str,
    ) -> Dict[str, Dict[str, str]]:
        jobs_by_url: Dict[str, Dict[str, str]] = {}
        base_for_links = self.listing_link_base_url or page_url

        for a in soup.select("a[href]"):
            href = a.get("href")
            url = self.normalize_url(base_for_links, href)
            if not url:
                continue

            if not self.is_job_url(url):
                continue

            if not self.should_keep_listing_anchor(a, url):
                continue

            title = self.extract_title_from_listing_anchor(a, url)
            location = self.extract_location_from_listing_anchor(a, url)
            first_seen_date = self.extract_first_seen_date_from_listing_anchor(a)

            existing = jobs_by_url.get(url, {})

            if title and not existing.get("title"):
                existing["title"] = title
            elif "title" not in existing:
                existing["title"] = ""

            if location and not existing.get("location"):
                existing["location"] = location
            elif "location" not in existing:
                existing["location"] = ""

            if first_seen_date and not existing.get("first_seen_date"):
                existing["first_seen_date"] = first_seen_date
            elif "first_seen_date" not in existing:
                existing["first_seen_date"] = ""

            jobs_by_url[url] = existing

        return jobs_by_url

    def parse_job_detail(
        self,
        url: str,
        listing_title: str = "",
        listing_location: str = "",
    ) -> Dict[str, str] | None:
        title = self.clean_text(listing_title)
        location = self.clean_text(listing_location)

        if not title:
            return None

        return self.build_job_dict(
            title=title,
            url=url,
            location=location,
            location_is_guess=False,
        )

    def scrape_jobs(self) -> List[Dict[str, str]]:
        jobs_by_url = self.scrape_listing_pages()

        self.log_found(len(jobs_by_url))

        jobs = []

        for url in sorted(jobs_by_url):
            self.log_scraping(url)

            listing_title = jobs_by_url[url].get("title", "")
            listing_location = jobs_by_url[url].get("location", "")
            first_seen_date = jobs_by_url[url].get("first_seen_date", "")

            title = self.clean_text(listing_title)
            location = self.clean_text(listing_location)

            if not title:
                continue

            jobs.append(
                self.build_job_dict(
                    title=title,
                    url=url,
                    first_seen_date=first_seen_date,
                    location=location,
                    location_is_guess=False,
                )
            )

        return self.sort_jobs(jobs)

    def extract_subcategory_links(self, listing_url: str) -> List[str]:
        soup = self.get_soup(listing_url)
        links = set()

        for a in soup.select("a[href]"):
            href = a.get("href")
            url = self.normalize_url(self.base_url, href)
            if not url:
                continue

            if self.is_it_subcategory_url(url):
                links.add(url)

        return sorted(links)

    def scrape_listing_pages(self) -> Dict[str, Dict[str, str]]:
        jobs_by_url: Dict[str, Dict[str, str]] = {}
        scraped_listing_urls = set()

        page_number = 1
        while True:
            page_url = self.build_listing_url(page_number)
            previous_count = len(jobs_by_url)

            page_jobs = self.scrape_listing_page_into_jobs_by_url(
                jobs_by_url,
                page_url,
            )
            if not page_jobs:
                break

            scraped_listing_urls.add(page_url)

            if len(jobs_by_url) == previous_count:
                break

            page_number += 1

        root_url = "https://jobs.colruytgroup.com/nl/vacatures/vakgebieden/it-digital"

        if root_url not in scraped_listing_urls:
            self.scrape_listing_page_into_jobs_by_url(jobs_by_url, root_url)
            scraped_listing_urls.add(root_url)

        subcategory_links = self.extract_subcategory_links(root_url)

        for subcategory_url in subcategory_links:
            if subcategory_url in scraped_listing_urls:
                continue

            self.scrape_listing_page_into_jobs_by_url(jobs_by_url, subcategory_url)
            scraped_listing_urls.add(subcategory_url)

        return jobs_by_url