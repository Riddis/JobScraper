from __future__ import annotations

from typing import Dict, List

from bs4 import BeautifulSoup

from scrapers.planet_group import PlanetGroupAjaxScraper


class ITPlanetScraper(PlanetGroupAjaxScraper):
    source = "planetgroup_itplanet"
    base_url = "https://it-planet.be"
    listing_url = "https://it-planet.be/vacatures/"
    ajax_url = "https://it-planet.be/wp-admin/admin-ajax.php"

    def extract_title_from_detail_soup(
        self,
        soup: BeautifulSoup,
        url: str,
    ) -> str:
        title = super().extract_title_from_detail_soup(soup, url)
        clean_title, _ = self.split_title_and_location(title)
        return self.clean_text(clean_title)

    def extract_jobs_from_soup(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        jobs: List[Dict[str, str]] = []

        for card in soup.select("div.vacature-search-result"):
            link = card.find("a", href=True)
            if not link:
                continue

            title_tag = link.find("h3")
            meta_tag = link.find("p")

            raw_title = (
                self.clean_text(title_tag.get_text(" ", strip=True))
                if title_tag
                else ""
            )
            title, _ = self.split_title_and_location(raw_title)

            url = link["href"].strip()
            meta_text = (
                self.clean_text(meta_tag.get_text(" ", strip=True))
                if meta_tag
                else ""
            )
            first_seen_date = self.extract_first_seen_date(meta_text)
            location, location_is_guess = self.extract_location_from_meta_text(meta_text)

            if not title or not url:
                continue

            jobs.append(
                {
                    "source": self.source,
                    "title": title,
                    "url": url,
                    "first_seen_date": first_seen_date,
                    "location": location,
                    "location_is_guess": (
                        "True" if location_is_guess else "False"
                    ),
                }
            )

        return jobs