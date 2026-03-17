from __future__ import annotations

import html
import re
from typing import Dict, List

from scrapers.base import ApiScraper


class InfrabelScraper(ApiScraper):
    source = "infrabel"
    base_url = "https://jobs.infrabel.be"
    listing_url = "https://jobs.infrabel.be/search/?searchResultView=LIST"
    api_url = "https://jobs.infrabel.be/services/recruiting/v1/jobs"

    start_page = 0
    page_size = 10
    page_delay_seconds = 1.0

    def __init__(self) -> None:
        super().__init__()
        self.csrf_token = ""

    def before_scrape(self) -> None:
        self.warm_up_session()
        if not self.csrf_token:
            self.fetch_csrf_token()

    def warm_up_session(self) -> str:
        response = self.session.get(self.listing_url, timeout=20)
        response.raise_for_status()

        html_text = response.text

        patterns = [
            r'"csrfToken"\s*:\s*"([^"]+)"',
            r'"CSRFToken"\s*:\s*"([^"]+)"',
            r"csrfToken\s*=\s*'([^']+)'",
            r'csrfToken\s*=\s*"([^"]+)"',
            r'"csrf"\s*:\s*"([^"]+)"',
        ]

        for pattern in patterns:
            match = re.search(pattern, html_text, re.IGNORECASE)
            if match:
                self.csrf_token = match.group(1)
                return self.csrf_token

        return ""

    def fetch_csrf_token(self) -> str:
        response = self.session.get(
            self.api_url,
            headers={
                "Accept": "application/json",
                "X-CSRF-Token": "Fetch",
                "Referer": self.listing_url,
                "Origin": self.base_url,
            },
            timeout=20,
        )

        token = response.headers.get("X-CSRF-Token", "")
        if token:
            self.csrf_token = token

        return self.csrf_token

    def get_api_page(self, page: int) -> Dict:
        payload = {
            "locale": "nl_NL",
            "pageNumber": page,
            "sortBy": "",
            "keywords": "",
            "location": "",
            "facetFilters": {},
            "brand": "",
            "skills": [],
            "categoryId": 0,
            "alertId": "",
            "rcmCandidateId": "",
        }

        response = self.session.post(
            self.api_url,
            headers={
                "Accept": "*/*",
                "Content-Type": "application/json",
                "Origin": self.base_url,
                "Referer": self.listing_url,
                "X-CSRF-Token": self.csrf_token,
            },
            json=payload,
            timeout=20,
        )
        response.raise_for_status()
        return response.json()

    def extract_results(self, response_json: Dict) -> List[Dict]:
        results = response_json.get("jobSearchResult", [])
        if isinstance(results, list):
            return [item for item in results if isinstance(item, dict)]
        return []

    def extract_total_count(self, response_json: Dict) -> int | None:
        total_jobs = response_json.get("totalJobs")
        if isinstance(total_jobs, int):
            return total_jobs
        return None

    def build_job_url(self, job_response: Dict) -> str:
        url_title = html.unescape(str(job_response.get("unifiedUrlTitle", "")).strip())
        job_id = str(job_response.get("id", "")).strip()

        if not url_title or not job_id:
            return ""

        return f"{self.base_url}/job/{url_title}/{job_id}-nl_NL/"

    def parse_first_seen_date(self, raw_date: str) -> str:
        raw_date = raw_date.strip()
        if not raw_date:
            return ""

        parts = raw_date.split("-")
        if len(parts) == 3:
            day, month, year = parts
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"

        return ""

    def normalize_location_entry(self, value: str) -> str:
        value = self.clean_text(value)
        value = re.sub(r"\s*,\s*BEL\s*$", "", value, flags=re.IGNORECASE)
        return self.clean_text(value)

    def extract_location_from_job_location_short(
        self,
        job_response: Dict,
    ) -> tuple[str, bool]:
        values = job_response.get("jobLocationShort")
        if not isinstance(values, list):
            return "", False

        locations: List[str] = []

        for value in values:
            if not isinstance(value, str):
                continue

            normalized = self.normalize_location_entry(value)
            if not normalized:
                continue

            guessed = self.guess_location_from_text(normalized)
            if guessed:
                locations.append(guessed)
            else:
                locations.append(normalized)

        unique_locations = sorted(set(locations))
        if len(unique_locations) == 1:
            return unique_locations[0], False

        return "", False

    def parse_job(self, item: Dict) -> Dict[str, str] | None:
        job_response = item.get("response", {})
        if not isinstance(job_response, dict):
            return None

        title = str(job_response.get("unifiedStandardTitle", "")).strip()
        url = self.build_job_url(job_response)

        if not title or not url:
            return None

        raw_date = str(job_response.get("unifiedStandardStart", "")).strip()
        first_seen_date = self.parse_first_seen_date(raw_date)

        location, location_is_guess = self.extract_location_from_job_location_short(
            job_response
        )

        if not location:
            location, location_is_guess = self.extract_location_from_api_data(
                job_response,
                text_keys=(
                    "location",
                    "city",
                    "jobLocation",
                    "job_location",
                    "full_location",
                    "short_location",
                    "region",
                    "office",
                    "unifiedStandardLocation",
                    "unifiedStandardLocationName",
                ),
                list_keys=("addresses", "locations"),
                category_keys=("location",),
                description_keys=("description", "jobDescription"),
            )

        return self.build_job_dict(
            title=title,
            url=url,
            first_seen_date=first_seen_date,
            location=location,
            location_is_guess=location_is_guess,
        )