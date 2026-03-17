from __future__ import annotations

import time
from typing import Dict, List

from scrapers.base import BaseScraper


class SynamediaScraper(BaseScraper):
    source = "darwinbox_synamedia"
    base_url = "https://synamedia.darwinbox.com"
    listing_url = "https://synamedia.darwinbox.com/ms/candidatev2/main/careers/allJobs"
    api_url = "https://synamedia.darwinbox.com/ms/candidateapi/job/alljobs?companyId=main"
    company_id = "main"
    page_size = 10
    page_delay_seconds = 1.0

    def before_scrape(self) -> None:
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0"
                )
            }
        )
        response = self.session.get(
            self.listing_url,
            headers={
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,"
                    "image/avif,image/webp,image/apng,*/*;q=0.8"
                ),
                "Accept-Language": "en",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Microsoft Edge";v="146"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
            },
            timeout=30,
        )
        response.raise_for_status()

    def get_api_page(self, page: int) -> Dict:
        payload = {
            "companyId": self.company_id,
            "page": page,
            "sort_option": "new",
            "limit": self.page_size,
        }

        response = self.session.post(
            self.api_url,
            headers={
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en",
                "Content-Type": "application/json",
                "Origin": self.base_url,
                "Priority": "u=1, i",
                "Referer": self.listing_url,
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
                "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Microsoft Edge";v="146"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
            },
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def extract_results(self, response_json: Dict) -> List[Dict]:
        for key in ("data", "result", "results", "jobs"):
            value = response_json.get(key)
            if isinstance(value, list):
                return value

        data = response_json.get("data")
        if isinstance(data, dict):
            for key in ("data", "result", "results", "jobs", "jobList"):
                value = data.get(key)
                if isinstance(value, list):
                    return value

        return []

    def extract_total_count(self, response_json: Dict) -> int | None:
        for key in ("total", "totalCount", "count", "totalRecords"):
            value = response_json.get(key)
            if isinstance(value, int):
                return value

        data = response_json.get("data")
        if isinstance(data, dict):
            for key in ("total", "totalCount", "count", "totalRecords"):
                value = data.get(key)
                if isinstance(value, int):
                    return value

        return None

    def build_job_url(self, job: Dict) -> str:
        for key in ("jobUrl", "url", "job_url"):
            value = job.get(key)
            if value:
                return str(value).strip()

        job_id = job.get("job_id") or job.get("id") or job.get("jobId")
        slug = job.get("job_slug") or job.get("slug")

        if job_id:
            return f"{self.base_url}/ms/candidatev2/main/careers/jobDetails/{job_id}"

        if slug:
            return f"{self.base_url}/ms/candidatev2/main/careers/jobDetails/{slug}"

        return ""

    def extract_title(self, job: Dict) -> str:
        for key in ("job_title", "title", "jobTitle", "name"):
            value = job.get(key)
            if value:
                return self.clean_text(str(value))
        return ""

    def extract_first_seen_date(self, job: Dict) -> str:
        for key in (
            "created_at",
            "posted_on",
            "createdOn",
            "date_posted",
            "published_at",
        ):
            value = job.get(key)
            if value:
                return str(value).strip()
        return ""

    def extract_location(self, job: Dict) -> str:
        raw_location = self.clean_text(str(job.get("officelocation_show_arr", "")))
        if raw_location:
            return self.clean_text(raw_location.split("(")[0].strip().rstrip(","))

        location, _ = self.extract_location_from_api_data(
            job,
            text_keys=(
                "location",
                "city",
                "job_location",
                "jobLocation",
                "office",
            ),
            list_keys=("locations",),
            category_keys=("location",),
            description_keys=("description", "job_description"),
        )
        return location

    def parse_job(self, raw_job: Dict) -> Dict[str, str] | None:
        title = self.extract_title(raw_job)
        url = self.build_job_url(raw_job)

        if not title or not url:
            return None

        return self.build_job_dict(
            title=title,
            url=url,
            location=self.extract_location(raw_job),
            location_is_guess=False,
            first_seen_date=self.extract_first_seen_date(raw_job),
        )

    def scrape_jobs(self) -> List[Dict[str, str]]:
        self.before_scrape()

        jobs_by_url: Dict[str, Dict[str, str]] = {}
        page = 1
        total_count: int | None = None

        while True:
            self.log_fetching(f"API page {page}")

            response_json = self.get_api_page(page)
            results = self.extract_results(response_json)

            for raw_job in results:
                job = self.parse_job(raw_job)
                if not job:
                    continue
                jobs_by_url[job["url"]] = job

            if total_count is None:
                total_count = self.extract_total_count(response_json)

            if not results:
                break

            if total_count is not None and len(jobs_by_url) >= total_count:
                break

            if len(results) < self.page_size:
                break

            page += 1

            if self.page_delay_seconds > 0:
                import time as _time
                _time.sleep(self.page_delay_seconds)

        jobs = self.sort_jobs(list(jobs_by_url.values()))

        self.log_found(len(jobs))

        for job in jobs:
            self.log_scraping(job["url"])

        return jobs