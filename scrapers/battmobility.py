from __future__ import annotations

from typing import Dict, List

from bs4 import BeautifulSoup

from scrapers.base import SinglePageSectionScraper


class BattMobilityScraper(SinglePageSectionScraper):
    source = "battmobility"
    base_url = "https://battmobility.be"
    listing_url = "https://battmobility.be/careers"

    def extract_jobs_from_listing_soup(
        self,
        soup: BeautifulSoup,
        page_url: str,
    ) -> List[Dict[str, str]]:
        jobs_by_url: Dict[str, Dict[str, str]] = {}

        for h3 in soup.find_all("h3"):
            title = self.clean_text(h3.get_text(" ", strip=True))
            if not title:
                continue

            if "solliciteer voor deze functie" in title.lower():
                continue

            parent = h3.parent
            parent_text = self.clean_text(
                parent.get_text(" ", strip=True) if parent else ""
            )
            parent_text_lower = parent_text.lower()

            if "gent" not in parent_text_lower and "voltijds" not in parent_text_lower:
                continue

            url = self.build_hash_url(page_url, self.slugify_text(title))

            location = ""
            if "gent" in parent_text_lower:
                location = "Gent"

            jobs_by_url[url] = self.build_job_dict(
                title=title,
                url=url,
                location=location,
                location_is_guess=False,
            )

        return list(jobs_by_url.values())