from __future__ import annotations

import json
import time
from typing import Dict, List

from bs4 import BeautifulSoup

from scrapers.base import BaseScraper


class TaborGroepScraper(BaseScraper):
    source = "taborgroep"
    base_url = "https://www.taborgroep.be"
    listing_url = "https://www.taborgroep.be/nl/vacatures"
    ajax_url = "https://www.taborgroep.be/nl/views/ajax"

    def get_html(self, url: str) -> str:
        response = self.get(url)
        return response.text

    def is_job_detail_url(self, url: str) -> bool:
        return self.url_path(url).startswith("/nl/vacature/")

    def extract_job_links_from_html(self, html: str) -> List[str]:
        soup = BeautifulSoup(html, "lxml")
        links = set()

        for a in soup.select("a[href]"):
            url = self.normalize_url(self.base_url, a["href"])
            if url and self.is_job_detail_url(url):
                links.add(url)

        return sorted(links)

    def get_view_dom_id(self, html: str) -> str:
        soup = BeautifulSoup(html, "lxml")

        view = soup.find(attrs={"data-view-dom-id": True})
        if view:
            return view.get("data-view-dom-id", "").strip()

        for element in soup.find_all(class_=True):
            for cls in element.get("class", []):
                if cls.startswith("js-view-dom-id-"):
                    return cls.replace("js-view-dom-id-", "")

        return ""

    def fetch_ajax_page(self, view_dom_id: str, page_number: int) -> str:
        params = {
            "_wrapper_format": "drupal_ajax",
            "view_name": "inhoudsoverzichten",
            "view_display_id": "block_3",
            "view_args": "",
            "view_path": "/node/12",
            "view_base_path": "waardegericht-ondernemend",
            "view_dom_id": view_dom_id,
            "pager_element": "0",
            "page": str(page_number),
            "_drupal_ajax": "1",
        }

        headers = {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Referer": self.listing_url,
            "X-Requested-With": "XMLHttpRequest",
        }

        response = self.session.get(
            self.ajax_url,
            params=params,
            headers=headers,
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
            if isinstance(item, dict):
                data = item.get("data")
                if isinstance(data, str):
                    html_parts.append(data)
                elif isinstance(data, dict):
                    html_parts.extend(v for v in data.values() if isinstance(v, str))

        return "\n".join(html_parts)

    def parse_job_detail(self, job_url: str) -> Dict[str, str] | None:
        soup = self.get_soup(job_url)

        title = ""
        h1 = soup.find("h1")
        if h1:
            title = self.clean_text(h1.get_text(" ", strip=True))
        elif soup.title:
            title = (
                self.clean_text(soup.title.get_text())
                .replace(" | Tabor", "")
                .replace(" - Tabor", "")
            )

        if not title:
            return None

        return self.build_job_dict(
            title=title,
            url=job_url,
        )

    def scrape_jobs(self) -> List[Dict[str, str]]:
        all_job_links = set()

        print(f"Fetching listing page: {self.listing_url}")

        try:
            first_page_html = self.get_html(self.listing_url)
        except Exception as exc:
            print(f"Failed to fetch listing page {self.listing_url}: {exc}")
            return []

        all_job_links.update(self.extract_job_links_from_html(first_page_html))

        view_dom_id = self.get_view_dom_id(first_page_html)

        if view_dom_id:
            page_number = 1

            while True:
                page_label = f"{self.ajax_url}?page={page_number}"
                print(f"Fetching listing page: {page_label}")

                try:
                    page_html = self.fetch_ajax_page(view_dom_id, page_number)
                except Exception as exc:
                    print(f"Failed to fetch listing page {page_label}: {exc}")
                    break

                if not page_html:
                    break

                page_links = self.extract_job_links_from_html(page_html)

                if not page_links:
                    break

                prev_count = len(all_job_links)
                all_job_links.update(page_links)

                if len(all_job_links) == prev_count:
                    break

                page_number += 1
                time.sleep(1)

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