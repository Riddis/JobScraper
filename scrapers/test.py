from __future__ import annotations

import time
from typing import Dict, List

import requests

from scrapers.base import BaseScraper


class HaysScraper(BaseScraper):
    source = "hays"
    base_url = "https://m.hays.be"
    listing_url = "https://m.hays.be/careers/search?lang=nl"
    api_url = "https://mapi.hays.com/jobportalapi/int/ns/bel/bn/careers/job/browse/v1/list"

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                )
            }
        )

    def warm_up_session(self) -> None:
        response = self.session.get(self.listing_url, timeout=20)
        response.raise_for_status()

        print("HAYS DEBUG warmup status:", response.status_code)
        print("HAYS DEBUG warmup final URL:", response.url)
        print("HAYS DEBUG warmup cookies:", self.session.cookies.get_dict())
        print("HAYS DEBUG warmup response headers:", dict(response.headers))
        print("HAYS DEBUG session headers after warmup:", dict(self.session.headers))

    def build_payload(self, page_token: int = 0) -> Dict:
        return {
            "facetLocation": "",
            "flexibleWorking": "false",
            "fullTime": "false",
            "industry": "",
            "isSponsored": False,
            "jobType": "",
            "partTime": "false",
            "query": "",
            "locations": "",
            "salMax": "",
            "salMin": "",
            "sortType": "RELEVANCE_DESC",
            "specialismId": "",
            "subSpecialismId": "",
            "typeOnlyFilter": "",
            "userAgent": "-Desktop",
            "radius": 100,
            "isCrossCountry": False,
            "isResponseCountry": False,
            "responseSiteLocale": "",
            "pageToken": str(page_token),
            "jobId": "",
            "jobRefrence": "",
            "crossCountryUrl": "",
            "payType": "",
            "type": "search",
            "cookieDomain": ".hays.be",
        }

    def get_jobs_page(self, page_token: int = 0) -> Dict:
        payload = self.build_payload(page_token=page_token)

        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": "https://m.hays.be",
            "Referer": self.listing_url,
        }

        print("HAYS DEBUG listing_url:", self.listing_url)
        print("HAYS DEBUG api_url:", self.api_url)
        print("HAYS DEBUG page_token:", page_token)
        print("HAYS DEBUG cookies before POST:", self.session.cookies.get_dict())
        print("HAYS DEBUG session headers before POST:", dict(self.session.headers))
        print("HAYS DEBUG request headers:", headers)
        print("HAYS DEBUG payload:", payload)

        response = self.session.post(
            self.api_url,
            headers=headers,
            json=payload,
            timeout=20,
        )

        print("HAYS DEBUG status:", response.status_code)
        print("HAYS DEBUG response headers:", dict(response.headers))
        print("HAYS DEBUG response text:", response.text[:2000])

        response.raise_for_status()
        return response.json()

    def build_job_url(self, job: Dict) -> str:
        job_id = job.get("jobId")
        if job_id:
            return f"{self.base_url}/careers/Job/Detail/{job_id}?lang=nl"
        return ""

    def extract_location(self, job: Dict) -> tuple[str, bool]:
        location, location_is_guess = self.extract_location_from_api_data(
            job,
            text_keys=(
                "location",
                "city",
                "facetLocation",
                "locations",
                "region",
                "office",
            ),
            list_keys=("addresses",),
            category_keys=("location",),
            description_keys=("jobDescription", "description"),
        )
        return location, location_is_guess

    def parse_job(self, job: Dict) -> Dict[str, str]:
        title = str(job.get("jobTitle", "")).strip()
        url = self.build_job_url(job)
        first_seen_date = str(job.get("createDate", "")).strip()
        location, location_is_guess = self.extract_location(job)

        return {
            "source": self.source,
            "title": title,
            "url": url,
            "first_seen_date": first_seen_date,
            "location": location,
            "location_is_guess": "True" if location_is_guess else "False",
        }

    def scrape_jobs(self) -> List[Dict[str, str]]:
        self.warm_up_session()

        jobs_by_url = {}
        page_token = 0
        page_size = 10

        while True:
            print(f"Fetching listing page: API offset {page_token}")

            response_json = self.get_jobs_page(page_token=page_token)
            data = response_json.get("data", {})
            results = data.get("data", []) if isinstance(data, dict) else []

            print("HAYS DEBUG results count:", len(results) if isinstance(results, list) else "not-a-list")
            print("HAYS DEBUG top-level keys:", list(response_json.keys()) if isinstance(response_json, dict) else type(response_json))

            if not results:
                break

            for job in results:
                parsed_job = self.parse_job(job)

                if not parsed_job["title"]:
                    continue
                if not parsed_job["url"]:
                    continue

                jobs_by_url[parsed_job["url"]] = parsed_job

            if len(results) < page_size:
                break

            page_token += page_size
            time.sleep(1)

        jobs = sorted(jobs_by_url.values(), key=lambda job: job["title"])

        print(f"Found {len(jobs)} jobs\n")

        for job in jobs:
            print(f"Scraping: {job['url']}")

        return jobs