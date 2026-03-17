from __future__ import annotations

from typing import Dict, List

from scrapers.base import ApiScraper


class FluxysScraper(ApiScraper):
    source = "fluxys"
    base_url = "https://careers.fluxys.com"
    listing_url = (
        "https://careers.fluxys.com/api/jobs"
        "?lang=nl-NL&page=1&stretch=500&stretchUnit=MILES"
        "&limit=100&sortBy=relevance&descending=false&internal=false"
    )

    def get_api_page(self, page: int) -> Dict | List[Dict]:
        response = self.session.get(
            self.listing_url,
            headers={
                "Accept": "application/json, text/plain, */*",
                "Referer": (
                    "https://careers.fluxys.com/jobs"
                    "?lang=nl-NL&page=1&stretch=500&stretchUnit=MILES&limit=100"
                ),
            },
            timeout=20,
        )
        response.raise_for_status()
        return response.json()

    def extract_results(self, response_json: Dict | List[Dict]) -> List[Dict]:
        if isinstance(response_json, list):
            return [item for item in response_json if isinstance(item, dict)]

        if isinstance(response_json, dict):
            for key in ("jobs", "data", "results", "items"):
                value = response_json.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]

        return []

    def should_continue(
        self,
        page: int,
        results: List[Dict],
        jobs_by_url: Dict[str, Dict[str, str]],
        total_count: int | None,
    ) -> bool:
        return False

    def build_job_url(self, job_data: Dict) -> str:
        meta_data = job_data.get("meta_data", {})
        if isinstance(meta_data, dict):
            canonical_url = meta_data.get("canonical_url", "")
            if isinstance(canonical_url, str):
                canonical_url = canonical_url.strip()
                if canonical_url:
                    return canonical_url

        slug = str(job_data.get("slug", "")).strip()
        if slug:
            return f"{self.base_url}/jobs/{slug}?lang=nl-NL"

        return ""

    def get_title(self, job_data: Dict) -> str:
        for key in ("title", "name", "jobTitle", "job_title"):
            value = job_data.get(key)
            if isinstance(value, str):
                value = self.clean_text(value)
                if value:
                    return value
        return ""

    def parse_job(self, item: Dict) -> Dict[str, str] | None:
        job_data = item.get("data", {})
        if not isinstance(job_data, dict):
            return None

        title = self.get_title(job_data)
        url = self.build_job_url(job_data)

        if not title or not url:
            return None

        location, location_is_guess = self.extract_location_from_api_data(
            job_data,
            text_keys=(
                "city",
                "full_location",
                "short_location",
                "location_name",
            ),
            list_keys=(),
            category_keys=(),
            description_keys=("description",),
        )

        return self.build_job_dict(
            title=title,
            url=url,
            location=location,
            location_is_guess=location_is_guess,
        )