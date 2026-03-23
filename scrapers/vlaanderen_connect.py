from __future__ import annotations

import re
from typing import Dict, List

from .base import ApiScraper


class VlaanderenConnectScraper(ApiScraper):
    source = "vlaanderen_connect"
    base_url = "https://www.vlaanderen.be"
    api_url = "https://www.vlaanderen.be/api/overview-search"

    page_size = 12
    start_page = 0

    def __init__(self) -> None:
        super().__init__()
        self.session.headers.update(
            {
                "accept": "application/json, text/plain, */*",
                "authorization": "Basic d2VicGxhdGZvcm1kZXY6d2VicGxhdGZvcm1kZXY=",
                "content-type": "application/json",
                "origin": "https://www.vlaanderen.be",
                "referer": (
                    "https://www.vlaanderen.be/werken-voor-vlaanderen/vacatures"
                    "?contentSubtypeData__internal=false"
                    "&contentSubtypeData__hiringOrganization.IN=Vlaanderen%20connect."
                    "&order_publicationdate=desc"
                ),
            }
        )

    def next_page_value(self, page: int) -> int:
        return page + 1

    def get_api_page(self, page: int) -> Dict:
        payload = {
            "page": {
                # Important:
                # this API uses page index in "offset", not row offset
                "offset": page,
                "limit": self.page_size,
            },
            "filter": {
                "contentType": {
                    "IN": ["Job"]
                },
                "contentTypeSubtypeRelatedFiltersOperator": "OR",
                "visibility": {
                    "hub": "cc0f4502-9afd-42cf-b71f-31e43937d855"
                },
                "collectionFilters": {
                    "contentSubtypeData__sources": {
                        "IN": ["VO"]
                    },
                    "contentSubtypeData__hiringOrganization": {
                        "IN": ["Vlaanderen connect."]
                    },
                    "contentSubtypeData__internal": {
                        "EQ": False
                    },
                },
            },
            "orderBy": {
                "publicationDate": "DESC"
            },
            "resolverContext": {
                "language": "nl",
                "revision": "default",
            },
            "facetFilterKeys": [
                "q",
                "contentSubtypeData.internal",
                "contentSubtypeData.reservedForDisability",
                "contentSubtypeData.domain",
                "contentSubtypeData.degreeLevel.name",
                "locations.address.city",
                "contentSubtypeData.employmentType",
                "contentSubtypeData.hiringOrganization",
            ],
        }

        response = self.post(self.api_url, json=payload)
        return response.json()

    def extract_results(self, response_json: Dict) -> List[Dict]:
        items = response_json.get("items", [])
        if isinstance(items, list):
            return items
        return []

    def extract_total_count(self, response_json: Dict) -> int | None:
        total_items = response_json.get("totalItems")
        if isinstance(total_items, int):
            return total_items
        return None

    def should_continue(
        self,
        page: int,
        results: List[Dict],
        jobs_by_url: Dict[str, Dict[str, str]],
        total_count: int | None,
    ) -> bool:
        if not results:
            return False

        if total_count is not None and len(jobs_by_url) >= total_count:
            return False

        is_last_page = self._last_response_json.get("isLastPage")
        if isinstance(is_last_page, bool):
            return not is_last_page

        return len(results) == self.page_size

    def _clean_title(self, title: str) -> str:
        title = self.clean_text(title)

        # Remove trailing "via Vlaanderen connect" variants
        title = re.sub(
            r"\s+via\s+vlaanderen\s+connect\.?\s*$",
            "",
            title,
            flags=re.IGNORECASE,
        )

        return self.clean_text(title)

    def _extract_title(self, raw_job: Dict) -> str:
        display_title = raw_job.get("displayTitle")
        if isinstance(display_title, str):
            display_title = self._clean_title(display_title)
            if display_title:
                return display_title

        title_obj = raw_job.get("title", {})
        if isinstance(title_obj, dict):
            html_encoded = title_obj.get("htmlEncoded")
            if isinstance(html_encoded, str):
                html_encoded = self._clean_title(html_encoded)
                if html_encoded:
                    return html_encoded

        return ""

    def _extract_url(self, raw_job: Dict) -> str:
        link = raw_job.get("link")
        if isinstance(link, str) and link.strip():
            return self.normalize_url(self.base_url, link)

        identifier = raw_job.get("identifier")
        if isinstance(identifier, str) and identifier.strip():
            return self.normalize_url(self.base_url, f"/Job/{identifier.strip()}")

        return ""

    def _extract_location(self, raw_job: Dict) -> tuple[str, bool]:
        locations = raw_job.get("locations", [])

        if isinstance(locations, list):
            city_names: List[str] = []

            for location in locations:
                if not isinstance(location, dict):
                    continue

                address = location.get("address", {})
                if not isinstance(address, dict):
                    continue

                city = address.get("city")
                if isinstance(city, str):
                    city = self.clean_text(city)
                    if city:
                        city_names.append(city)

            unique_cities = sorted(set(city_names))
            if len(unique_cities) == 1:
                return unique_cities[0], False

        description = raw_job.get("description", {})
        if isinstance(description, dict):
            raw_text = description.get("raw")
            if isinstance(raw_text, str) and raw_text.strip():
                guessed = self.guess_location_from_text(raw_text)
                if guessed:
                    return guessed, True

        return "", False

    def parse_job(self, raw_job: Dict) -> Dict[str, str] | None:
        if not isinstance(raw_job, dict):
            return None

        hiring_organization = raw_job.get("hiringOrganization")
        if hiring_organization != "Vlaanderen connect.":
            return None

        title = self._extract_title(raw_job)
        if not title:
            return None

        url = self._extract_url(raw_job)
        if not url:
            return None

        location, location_is_guess = self._extract_location(raw_job)

        return self.build_job_dict(
            title=title,
            url=url,
            location=location,
            location_is_guess=location_is_guess,
        )

    def scrape_jobs(self) -> List[Dict[str, str]]:
        self.before_scrape()

        jobs_by_url: Dict[str, Dict[str, str]] = {}
        page = self.start_page
        total_count: int | None = None
        self._last_response_json: Dict = {}

        while True:
            self.log_fetching(f"API page {page}")

            response_json = self.get_api_page(page)
            self._last_response_json = response_json

            results = self.extract_results(response_json)

            for raw_job in results:
                parsed_job = self.parse_job(raw_job)
                if not parsed_job:
                    continue

                title = self.clean_text(parsed_job.get("title", ""))
                url = parsed_job.get("url", "").strip()
                location = self.clean_text(parsed_job.get("location", ""))
                location_is_guess = str(
                    parsed_job.get("location_is_guess", "False")
                ).strip() or "False"

                if not title or not url:
                    continue

                parsed_job["title"] = title
                parsed_job["location"] = location
                parsed_job["location_is_guess"] = location_is_guess
                jobs_by_url[url] = parsed_job

            if total_count is None:
                total_count = self.extract_total_count(response_json)

            if not self.should_continue(
                page=page,
                results=results,
                jobs_by_url=jobs_by_url,
                total_count=total_count,
            ):
                break

            page = self.next_page_value(page)

        jobs = self.sort_jobs(list(jobs_by_url.values()))

        self.log_found(len(jobs))

        for job in jobs:
            self.log_scraping(job["url"])

        return jobs