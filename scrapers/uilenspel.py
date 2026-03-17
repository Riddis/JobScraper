from __future__ import annotations

import time
from typing import Dict, List

import requests

from scrapers.base import BaseScraper


class UilenspelScraper(BaseScraper):
    source = "uilenspel"
    listing_url = "https://www.uilenspel.be/nl/vrijwilligersvacatures"
    api_url = "https://www.giveaday.eu/api/widget/vacancies"
    org_id = 637

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "*/*",
        "Origin": "https://www.uilenspel.be",
        "Referer": "https://www.uilenspel.be/",
    }

    def get_jobs_page(self, offset: int = 0, limit: int = 12) -> Dict:
        response = requests.get(
            self.api_url,
            headers=self.headers,
            params={
                "orgid": self.org_id,
                "limit": limit,
                "offset": offset,
                "lang": "nl",
            },
            timeout=20,
        )
        response.raise_for_status()
        return response.json()

    def parse_job(self, job: Dict) -> Dict[str, str] | None:
        title = str(job.get("name", "")).strip()
        url = str(job.get("vacancy_url", "")).strip()

        if not title or not url:
            return None

        location = self.clean_text(str(job.get("address_city", "")))

        return self.build_job_dict(
            title=title,
            url=url,
            location=location,
            location_is_guess=False,
        )

    def scrape_jobs(self) -> List[Dict[str, str]]:
        jobs_by_url = {}
        offset = 0
        limit = 12
        total = None

        while True:
            print(f"Fetching listing page: API offset {offset}")

            response_json = self.get_jobs_page(offset=offset, limit=limit)
            results = response_json.get("data", [])

            if not results:
                break

            for job in results:
                parsed_job = self.parse_job(job)

                if not parsed_job:
                    continue

                jobs_by_url[parsed_job["url"]] = parsed_job

            if total is None:
                total = response_json.get("meta", {}).get("total")

            offset += limit

            if total is not None and offset >= total:
                break

            if len(results) < limit:
                break

            time.sleep(1)

        jobs = self.sort_jobs(list(jobs_by_url.values()))

        print(f"Found {len(jobs)} jobs\n")

        for job in jobs:
            print(f"Scraping: {job['url']}")

        return jobs