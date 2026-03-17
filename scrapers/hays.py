from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
from datetime import datetime
from typing import Dict, List
from urllib import response
from zoneinfo import ZoneInfo

from scrapers.base import ApiScraper


class HaysScraper(ApiScraper):
    source = "hays"
    base_url = "https://m.hays.be"
    listing_url = "https://m.hays.be/careers/search?lang=nl"
    api_url = "https://mapi.hays.com/jobportalapi/int/ns/bel/bn/careers/job/browse/v1/list"

    start_page = 0
    page_size = 10
    page_delay_seconds = 1.0

    hmac_key = "aDX5UzaKVndUKKfP"

    def __init__(self) -> None:
        super().__init__()
        self.current_token = ""
        self.current_session_id = ""

    def before_scrape(self) -> None:
        self.warm_up_session()

    def warm_up_session(self) -> None:
        response = self.session.get(self.listing_url, timeout=20)
        response.raise_for_status()

        html = response.text

        token_patterns = [
            r'localStorage\.setItem\("AhaysToken","([^"]+)"\)',
            r"localStorage\.setItem\('AhaysToken','([^']+)'\)",
            r'"AhaysToken"\s*:\s*"([^"]+)"',
        ]

        for pattern in token_patterns:
            match = re.search(pattern, html)
            if match:
                self.current_token = match.group(1).strip()
                break

        if not self.current_token:
            self.current_token = self.get_cookie_value("AhaysToken")

        self.current_session_id = self.get_cookie_value("Asessionid")

        if not self.current_token:
            raise RuntimeError("Hays warm-up failed: token not found.")

        if not self.current_session_id:
            raise RuntimeError("Hays warm-up failed: Asessionid cookie not found.")
        
        self.current_token = "eyJhbGciOiJIUzUxMiJ9.eyJndWlkIjoiNWNiZGNlZWYtZGMyZC00N2E3LTg2ZjctMmI3ZTk5NzNjOTU4IiwiZG9tYWluTmFtZSI6InBsIiwic3ViIjoiNWNiZGNlZWYtZGMyZC00N2E3LTg2ZjctMmI3ZTk5NzNjOTU4IiwiaWF0IjoxNzczNjUyNjUxLCJuYmYiOjE3NzM2NTI2NTEsImF1ZCI6Imh0dHBzOi8vbS5oYXlzLnBsL2NhcmVlcnMvIiwiaXNzIjoiaHR0cHM6Ly9tLmhheXMuY29tIiwiZXhwIjoxNzgxNDI4NjUxfQ.HxZgEcRgvOUIiPm3wmDcV29PaPsKTtIPZusG2WawgXzQzVz57YyOVM-sbQwJwIbF35DI7nmc6RiMate_HhgfDw"
        self.current_session_id = "2181cada-60b3-4df4-b3e9-226ce2706f57"

    def get_cookie_value(self, name: str) -> str:
        value = self.session.cookies.get(name)
        if value:
            return str(value)

        for cookie in self.session.cookies:
            if cookie.name == name and cookie.value:
                return str(cookie.value)

        return ""

    def build_payload(self, page: int) -> Dict:
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
            "pageToken": str(page),
            "jobId": "",
            "jobRefrence": "",
            "crossCountryUrl": "",
            "payType": "",
            "type": "search",
            "cookieDomain": ".hays.be",
        }

    def build_activityurl(self) -> str:
        return (
            "/search?q=&location=&specialismId=&subSpecialismId=&locationf=&industryf="
            "&sortType=0&jobType=-1&flexiWorkType=-1&payTypefacet=-1&minPay=-1&maxPay=-1"
            "&jobSource=HaysGCJ&searchPageTitle=Zoek%20een%20job%20-%20Hays%20Rekrutering%20-%20Belgi%C3%AB"
            "&searchPageDesc=Bekijk%20onze%20vacatures%20en%20vind%20een%20job%20bij%20de%20beste%20werkgevers."
            "%20Vind%20je%20droomjob%20via%20Hays%20Belgium"
        )

    def get_request_time(self) -> str:
        return datetime.now(ZoneInfo("Europe/Brussels")).strftime("%Y-%m-%dT%H:%M:%S%z")

    def build_string_to_sign(
        self,
        method: str,
        content_type: str,
        request_time: str,
        body: Dict,
    ) -> str:
        body_str = json.dumps(body, separators=(",", ":"), ensure_ascii=False)

        return (
            f"{method}\n"
            f"{content_type}\n"
            f"{request_time}\n"
            f"/jobportalapi/int/ns/bel/bn/careers/job/browse/v1/list\n"
            f"{body_str}"
        )

    def generate_x_auth(
        self,
        token: str,
        request_time: str,
        body: Dict,
    ) -> str:
        string_to_sign = self.build_string_to_sign(
            method="POST",
            content_type="application/json",
            request_time=request_time,
            body=body,
        )

        digest = hmac.new(
            token.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).digest()

        signature = base64.b64encode(digest).decode("utf-8")
        return f"{self.hmac_key}:{signature}"

    def get_api_page(self, page: int) -> Dict:
        if not self.current_token:
            raise RuntimeError("Hays request failed: missing auth token.")

        if not self.current_session_id:
            raise RuntimeError("Hays request failed: missing session id.")

        payload = self.build_payload(page)
        request_time = self.get_request_time()
        x_auth = self.generate_x_auth(
            token=self.current_token,
            request_time=request_time,
            body=payload,
        )

        response = self.session.post(
            self.api_url,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Origin": "https://m.hays.be",
                "Referer": "https://m.hays.be/",
                "Authorization": f"Bearer {self.current_token}",
                "x-auth": x_auth,
                "x-date": request_time,
                "x-session": self.current_session_id,
                "activityurl": self.build_activityurl(),
                "Cache-Control": "no-cache",
            },
            json=payload,
            timeout=20,
        )
        print("HAYS DEBUG STATUS:", response.status_code)
        print("HAYS DEBUG RESPONSE TEXT:", response.text[:1000])
        response.raise_for_status()

        next_token = response.headers.get("x-token") or response.headers.get("X-Token")
        if next_token:
            self.current_token = next_token.strip()

        latest_session_id = self.get_cookie_value("Asessionid")
        if latest_session_id:
            self.current_session_id = latest_session_id

        return response.json()

    def extract_results(self, response_json: Dict) -> List[Dict]:
        data = response_json.get("data", {})
        if not isinstance(data, dict):
            return []

        results = data.get("data", [])
        if isinstance(results, list):
            return [item for item in results if isinstance(item, dict)]

        return []

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

        if len(results) < self.page_size:
            return False

        return True

    def build_job_url(self, job: Dict) -> str:
        job_id = job.get("jobId")
        if job_id:
            return f"{self.base_url}/careers/Job/Detail/{job_id}?lang=nl"
        return ""

    def extract_location(self, job: Dict) -> tuple[str, bool]:
        return self.extract_location_from_api_data(
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

    def parse_job(self, job: Dict) -> Dict[str, str] | None:
        title = str(job.get("jobTitle", "")).strip()
        url = self.build_job_url(job)
        first_seen_date = str(job.get("createDate", "")).strip()
        location, location_is_guess = self.extract_location(job)

        if not title or not url:
            return None

        return self.build_job_dict(
            title=title,
            url=url,
            first_seen_date=first_seen_date,
            location=location,
            location_is_guess=location_is_guess,
        )