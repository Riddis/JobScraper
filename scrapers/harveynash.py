from __future__ import annotations

from datetime import datetime
from typing import Dict, List
from zoneinfo import ZoneInfo

from scrapers.base import ApiScraper


class HarveyNashScraper(ApiScraper):
    source = "harveynash"
    base_url = "https://www.harveynash.be"
    api_url = "https://www.harveynash.be/_sf/api/v1/jobs/search.json"

    start_page = 0
    page_size = 21
    page_delay_seconds = 1.0

    def get_api_page(self, page: int) -> Dict:
        payload = {
            "job_search": {
                "query": "",
                "location": {
                    "address": "",
                    "radius": 5,
                    "region": "BE",
                    "radius_units": "miles",
                },
                "filters": {},
                "commute_filter": {},
                "offset": page,
                "jobs_per_page": self.page_size,
            }
        }

        response = self.session.post(
            self.api_url,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=20,
        )
        response.raise_for_status()
        return response.json()

    def extract_results(self, response_json: Dict) -> List[Dict]:
        results = response_json.get("results", [])
        if isinstance(results, list):
            return [item for item in results if isinstance(item, dict)]
        return []

    def extract_total_count(self, response_json: Dict) -> int | None:
        total_size = response_json.get("total_size")
        if isinstance(total_size, int):
            return total_size
        return None

    def next_page_value(self, page: int) -> int:
        return page + self.page_size

    def should_continue(
        self,
        page: int,
        results: List[Dict],
        jobs_by_url: Dict[str, Dict[str, str]],
        total_count: int | None,
    ) -> bool:
        if not results:
            return False

        next_offset = page + self.page_size

        if total_count is not None and next_offset >= total_count:
            return False

        if len(results) < self.page_size:
            return False

        return True

    def build_job_url(self, url_slug: str) -> str:
        return f"{self.base_url}/jobs/{url_slug}"

    def extract_location(self, job: Dict) -> tuple[str, bool]:
        location = self.extract_location_from_category_values(
            job.get("categories"),
            category_names=("location",),
        )
        if location:
            guessed = self.guess_location_from_text(location)
            if guessed:
                return guessed, False
            return location, False

        derived_info = job.get("derived_info", {})
        if isinstance(derived_info, dict):
            location = self.extract_location_from_postal_addresses(
                derived_info.get("locations")
            )
            if location:
                return location, False

        location = self.extract_single_string_from_list(job.get("addresses"))
        if location:
            guessed = self.guess_location_from_text(location)
            if guessed:
                return guessed, False
            return location, False

        description = job.get("description", "")
        if isinstance(description, str):
            guessed = self.guess_location_from_text(description)
            if guessed:
                return guessed, True

        return "", False

    def parse_job(self, item: Dict) -> Dict[str, str] | None:
        job = item.get("job", {})
        if not isinstance(job, dict):
            return None

        title = str(job.get("title", "")).strip()
        url_slug = str(job.get("url_slug", "")).strip()

        if not title or not url_slug:
            return None

        url = self.build_job_url(url_slug)
        if url.rstrip("/").endswith("/jobs"):
            return None

        published_at = job.get("published_at")
        first_seen_date = ""

        if published_at:
            dt = datetime.fromtimestamp(
                published_at,
                tz=ZoneInfo("Europe/Brussels"),
            )
            first_seen_date = dt.strftime("%Y-%m-%d")

        location, location_is_guess = self.extract_location(job)

        return self.build_job_dict(
            title=title,
            url=url,
            first_seen_date=first_seen_date,
            location=location,
            location_is_guess=location_is_guess,
        )