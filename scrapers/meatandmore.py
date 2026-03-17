from __future__ import annotations

from bs4 import BeautifulSoup

from scrapers.base import ListingDetailScraper


class MeatAndMoreScraper(ListingDetailScraper):
    source = "meatandmore"
    base_url = "https://www.meatandmore.be"
    listing_url = "https://www.meatandmore.be/nl/vacatures?page=0"

    page_param = "page"
    start_page = 0
    max_pages = 100

    job_path_prefixes = ("/nl/vacatures/",)
    job_path_excludes = ("/nl/vacatures",)

    def is_job_url(self, url: str) -> bool:
        path = self.url_path(url)

        if not path.startswith("/nl/vacatures/"):
            return False

        if path == "/nl/vacatures":
            return False

        return True

    def should_keep_listing_anchor(
        self,
        a: BeautifulSoup,
        url: str,
    ) -> bool:
        article = a.find_parent("article", class_="node--job--teaser")
        if not article:
            return False

        title = self.extract_title_from_listing_anchor(a, url)
        if not title:
            return False

        if title.lower() == "spontane sollicitatie":
            return False

        return True

    def extract_links_from_listing_soup(
        self,
        soup: BeautifulSoup,
        page_url: str,
    ):
        jobs_by_url = {}

        for article in soup.select("article.node--job--teaser"):
            title_tag = article.select_one("h3.teaser-title")
            title = self.clean_text(title_tag.get_text(" ", strip=True)) if title_tag else ""

            if not title or title.lower() == "spontane sollicitatie":
                continue

            location = ""
            subtitle = article.select_one(".field--subtitle")
            if subtitle:
                text = self.clean_text(subtitle.get_text(" ", strip=True))
                if text:
                    guessed = self.guess_location_from_text(text)
                    location = guessed or text

            if not location:
                address = article.select_one(".field--address")
                if address:
                    text = self.clean_text(address.get_text(" ", strip=True))
                    guessed = self.guess_location_from_text(text)
                    if guessed:
                        location = guessed

            onclick = article.get("onclick", "")
            url = ""

            if onclick:
                import re

                match = re.search(r"location\.href=['\"]([^'\"]+)['\"]", onclick)
                if match:
                    url = self.normalize_url(self.base_url, match.group(1))

            if not url:
                for a in article.select("a[href]"):
                    candidate = self.normalize_url(self.base_url, a.get("href"))
                    if candidate and self.is_job_url(candidate):
                        url = candidate
                        break

            if not url or not self.is_job_url(url):
                continue

            self.merge_job_stub(
                jobs_by_url=jobs_by_url,
                url=url,
                title=title,
                location=location,
            )

        return jobs_by_url