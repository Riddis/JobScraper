from __future__ import annotations

import json
import time
from typing import Dict, List

from bs4 import BeautifulSoup

from scrapers.base import BaseScraper


class VDKScraper(BaseScraper):
    source = "vdk"
    base_url = "https://www.vdk.be"
    listing_url = "https://www.vdk.be/nl/overzicht-vacatures"
    ajax_url = "https://www.vdk.be/nl/views/ajax"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        )
    }

    def __init__(self) -> None:
        super().__init__()
        self.session.headers.update(self.headers)

    def get_soup(self, url: str) -> BeautifulSoup:
        response = self.session.get(url, timeout=20)
        response.raise_for_status()
        return BeautifulSoup(response.text, "lxml")

    def get_html(self, url: str) -> str:
        response = self.session.get(url, timeout=20)
        response.raise_for_status()
        return response.text

    def clean_text(self, text: str) -> str:
        return " ".join(text.split())

    def is_job_detail_url(self, url: str) -> bool:
        path = self.url_path(url)

        if not path.startswith("/nl/overzicht-vacatures/"):
            return False

        if path == "/nl/overzicht-vacatures":
            return False

        return True

    def normalize_location(self, text: str) -> str:
        location = self.clean_text(text)

        if not location:
            return ""

        if location.lower().startswith("hoofdzetel "):
            location = location[len("hoofdzetel "):]

        if location.lower() in {"brussel / bruxelles", "bruxelles / brussel"}:
            return "Brussel"

        return self.clean_text(location)

    def extract_jobs_from_html(self, html: str) -> Dict[str, Dict[str, str]]:
        soup = BeautifulSoup(html, "lxml")
        jobs_by_url: Dict[str, Dict[str, str]] = {}

        for node in soup.select(".node--type-vacancy"):
            link = node.select_one("h3 a[href], a.spread-link[href]")
            if not link:
                continue

            absolute_url = self.normalize_url(self.base_url, link.get("href"))
            if not absolute_url:
                continue

            if not self.is_job_detail_url(absolute_url):
                continue

            title = self.clean_text(link.get_text(" ", strip=True))

            location = ""
            location_el = node.select_one(".field--name-field-location")
            if location_el:
                location = self.normalize_location(
                    location_el.get_text(" ", strip=True)
                )

            jobs_by_url[absolute_url] = {
                "title": title,
                "location": location,
            }

        if jobs_by_url:
            return jobs_by_url

        for a in soup.find_all("a", href=True):
            absolute_url = self.normalize_url(self.base_url, a["href"])

            if not absolute_url:
                continue

            if not self.is_job_detail_url(absolute_url):
                continue

            jobs_by_url.setdefault(
                absolute_url,
                {
                    "title": self.clean_text(a.get_text(" ", strip=True)),
                    "location": "",
                },
            )

        return jobs_by_url

    def get_view_dom_id(self, html: str) -> str:
        soup = BeautifulSoup(html, "lxml")

        view = soup.find(attrs={"data-view-dom-id": True})
        if view:
            return self.clean_text(view.get("data-view-dom-id", ""))

        for element in soup.find_all(class_=True):
            classes = element.get("class", [])
            for class_name in classes:
                if class_name.startswith("js-view-dom-id-"):
                    return class_name.replace("js-view-dom-id-", "")

        return ""

    def fetch_ajax_page(self, view_dom_id: str, page_number: int) -> str:
        params = {
            "_wrapper_format": "drupal_ajax",
            "view_name": "jobs_mpleo",
            "view_display_id": "block_1",
            "view_args": "",
            "view_path": "/node/1989",
            "view_base_path": "",
            "view_dom_id": view_dom_id,
            "pager_element": "0",
            "exposed_form_display": "1",
            "page": str(page_number),
            "_drupal_ajax": "1",
            "ajax_page_state[theme]": "calibr8_easytheme",
            "ajax_page_state[theme_token]": "",
            "ajax_page_state[libraries]": "",
        }

        ajax_headers = {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Referer": self.listing_url,
            "X-Requested-With": "XMLHttpRequest",
        }

        response = self.session.get(
            self.ajax_url,
            params=params,
            headers=ajax_headers,
            timeout=20,
        )
        response.raise_for_status()

        try:
            payload = response.json()
        except json.JSONDecodeError:
            return ""

        if not isinstance(payload, list):
            return ""

        html_parts = []

        for item in payload:
            if not isinstance(item, dict):
                continue

            data = item.get("data")

            if isinstance(data, str) and "/nl/overzicht-vacatures/" in data:
                html_parts.append(data)
                continue

            if isinstance(data, dict):
                for value in data.values():
                    if isinstance(value, str) and "/nl/overzicht-vacatures/" in value:
                        html_parts.append(value)

        return "\n".join(html_parts)

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
                title = self.clean_text(title_tag.get_text(" ", strip=True))

        if not title and soup.title and soup.title.string:
            title = self.clean_text(soup.title.string)
            title = title.replace(" | vdk bank", "")
            title = title.replace(" - vdk bank", "")
            title = self.clean_text(title)

        if not title:
            return None

        return self.build_job_dict(
            title=title,
            url=job_url,
            location=self.normalize_location(listing_location),
            location_is_guess=False,
        )

    def scrape_jobs(self) -> List[Dict[str, str]]:
        jobs_by_url: Dict[str, Dict[str, str]] = {}

        print(f"Fetching listing page: {self.listing_url}")

        try:
            first_page_html = self.get_html(self.listing_url)
        except Exception as exc:
            print(f"Failed to fetch listing page {self.listing_url}: {exc}")
            return []

        jobs_by_url.update(self.extract_jobs_from_html(first_page_html))

        view_dom_id = self.get_view_dom_id(first_page_html)

        if view_dom_id:
            ajax_page_number = 1

            while True:
                ajax_page_label = f"{self.ajax_url}?page={ajax_page_number}"
                print(f"Fetching listing page: {ajax_page_label}")

                try:
                    page_html = self.fetch_ajax_page(view_dom_id, ajax_page_number)
                except Exception as exc:
                    print(f"Failed to fetch listing page {ajax_page_label}: {exc}")
                    break

                if not page_html:
                    break

                page_jobs = self.extract_jobs_from_html(page_html)

                if not page_jobs:
                    break

                previous_count = len(jobs_by_url)
                jobs_by_url.update(page_jobs)

                if len(jobs_by_url) == previous_count:
                    break

                ajax_page_number += 1
                time.sleep(1)

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