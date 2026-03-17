from __future__ import annotations

from typing import Dict, List

from bs4 import BeautifulSoup

from scrapers.base import BaseScraper


class VerdonScraper(BaseScraper):
    source = "verdon"
    base_url = "https://www.groupe-verdon.com"
    listing_url = "https://www.groupe-verdon.com/en/recruitment"

    def is_job_url(self, url: str) -> bool:
        path = self.url_path(url)
        return path.startswith("/en/offer-") or path.startswith("/fr/offre-")

    def scrape_jobs(self) -> List[Dict[str, str]]:
        links = set()
        link_titles: Dict[str, str] = {}
        link_locations: Dict[str, str] = {}

        print(f"Fetching listing page: {self.listing_url}")

        soup = self.get_soup(self.listing_url)

        for a in soup.select("a[href]"):
            href = a.get("href")
            url = self.normalize_url(self.listing_url, href)
            if not url:
                continue

            if not self.is_job_url(url):
                continue

            title = ""
            title_el = a.select_one(".offers_title")
            if title_el:
                title = self.clean_text(title_el.get_text(" ", strip=True))

            location = ""
            location_els = a.select(".offers_text")
            if len(location_els) >= 2:
                location = self.clean_text(location_els[-1].get_text(" ", strip=True))

            links.add(url)

            if title:
                link_titles[url] = title

            if location:
                link_locations[url] = location

        print(f"Found {len(links)} job links")

        jobs: List[Dict[str, str]] = []

        for url in sorted(links):
            print(f"Scraping: {url}")

            title = link_titles.get(url, "")
            location = link_locations.get(url, "")

            if not title:
                soup = self.get_soup(url)

                h1 = soup.find("h1")
                if h1:
                    title = self.clean_text(h1.get_text(" ", strip=True))

                if not title:
                    h2 = soup.find("h2")
                    if h2:
                        title = self.clean_text(h2.get_text(" ", strip=True))

            if not title:
                continue

            jobs.append(
                self.build_job_dict(
                    title=title,
                    url=url,
                    location=location,
                    location_is_guess=False,
                )
            )

        return self.sort_jobs(jobs)