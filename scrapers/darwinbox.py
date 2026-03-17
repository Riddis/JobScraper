from __future__ import annotations

from typing import Dict, List

from scrapers.base import ApiScraper


class DarwinboxScraper(ApiScraper):
    source: str = ""
    base_url: str = ""
    company_id: str = ""
    listing_url: str = ""
    api_url: str = ""

    page_size = 10
    page_delay_seconds = 1.0

    def before_scrape(self) -> None:
        self.warm_up_session()

    def warm_up_session(self) -> None:
        response = self.session.get(
            self.listing_url,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "sec-ch-ua": '"Not:A-Brand";v="99", "Microsoft Edge";v="145", "Chromium";v="145"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
            },
            timeout=20,
        )
        response.raise_for_status()

    def api_headers(self) -> Dict[str, str]:
        return {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Content-Type": "application/json;charset=UTF-8",
            "Origin": self.base_url,
            "Referer": self.listing_url,
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Priority": "u=1, i",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "X-Requested-With": "XMLHttpRequest",
            "sec-ch-ua": '"Not:A-Brand";v="99", "Microsoft Edge";v="145", "Chromium";v="145"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        }

    def get_api_page(self, page: int) -> Dict:
        payload = {
            "companyId": self.company_id,
            "page": page,
            "sort_option": "new",
            "limit": self.page_size,
        }

        response = self.session.post(
            self.api_url,
            headers=self.api_headers(),
            json=payload,
            timeout=20,
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

        slug = job.get("job_slug") or job.get("slug")
        job_id = job.get("job_id") or job.get("id") or job.get("jobId")

        if slug:
            return f"{self.base_url}/ms/candidatev2/main/careers/job/{slug}"

        if job_id:
            return f"{self.base_url}/ms/candidatev2/main/careers/job/{job_id}"

        return ""

    def extract_title(self, job: Dict) -> str:
        for key in ("job_title", "title", "jobTitle", "name"):
            value = job.get(key)
            if value:
                return str(value).strip()
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

    def extract_location(self, job: Dict) -> tuple[str, bool]:
        explicit_location = self.clean_text(str(job.get("officelocation_show_arr", "")))
        if explicit_location:
            explicit_location = explicit_location.split("(")[0].strip().rstrip(",")
            explicit_location = self.clean_text(explicit_location)
            if explicit_location:
                return explicit_location, False

        return self.extract_location_from_api_data(
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

    def parse_job(self, job: Dict) -> Dict[str, str] | None:
        title = self.extract_title(job)
        url = self.build_job_url(job)

        if not title or not url:
            return None

        location, location_is_guess = self.extract_location(job)

        return self.build_job_dict(
            title=title,
            url=url,
            first_seen_date=self.extract_first_seen_date(job),
            location=location,
            location_is_guess=location_is_guess,
        )