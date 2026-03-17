from __future__ import annotations

from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from scrapers.base import ListingDetailScraper


class HOGentScraper(ListingDetailScraper):
    source = "hogent"
    base_url = "https://hogent.cvw.io"
    listing_url = "https://hogent.cvw.io/?lang=nl-BE"

    title_suffixes_to_strip = (" - HOGENT Jobs",)

    def normalize_job_detail_url(self, url: str) -> str:
        parsed = urlparse(url)

        if parsed.netloc.lower() not in {"hogent.cvw.io", "www.hogent.cvw.io"}:
            return ""

        path = parsed.path.rstrip("/")

        if path.lower().startswith("/applicationform/appform"):
            return ""

        query = parse_qs(parsed.query)
        job_ids = query.get("job", [])

        if not job_ids:
            return ""

        normalized_query = {
            "lang": ["nl-BE"],
            "job": [job_ids[0]],
        }

        if query.get("q"):
            normalized_query["q"] = [query["q"][0]]

        return urlunparse(
            (
                parsed.scheme or "https",
                parsed.netloc,
                "",
                "",
                urlencode(normalized_query, doseq=True),
                "",
            )
        )

    def is_job_url(self, url: str) -> bool:
        return bool(self.normalize_job_detail_url(url))

    def extract_links_from_listing_soup(
        self,
        soup,
        page_url: str,
    ):
        jobs_by_url = {}

        for a in soup.select("a[href]"):
            href = a.get("href")
            url = self.normalize_url(self.base_url, href)
            if not url:
                continue

            normalized_url = self.normalize_job_detail_url(url)
            if not normalized_url:
                continue

            self.merge_job_stub(
                jobs_by_url=jobs_by_url,
                url=normalized_url,
                title="",
                location="Gent",
            )

        return jobs_by_url