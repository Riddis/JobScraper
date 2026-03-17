from __future__ import annotations

from bs4 import BeautifulSoup

from scrapers.base import PaginatedListingDetailScraper


class SignpostScraper(PaginatedListingDetailScraper):
    source = "signpost"
    base_url = "https://signpost.be"
    listing_url = "https://signpost.be/nl-be/jobs?page_num=1"

    page_param = "page_num"
    start_page = 1

    job_path_prefixes = ("/nl-be/jobs/",)
    job_path_excludes = ("/nl-be/jobs?page_num=",)
    title_suffixes_to_strip = ("| Signpost", "- Signpost")

    def extract_title_from_detail_soup(
        self,
        soup: BeautifulSoup,
        url: str,
    ) -> str:
        title = ""

        h1 = soup.find("h1")
        if h1:
            title = self.clean_text(h1.get_text(" ", strip=True))

        if not title and soup.title and soup.title.string:
            title = self.clean_text(soup.title.string)
            title = title.replace(" | Signpost", "")
            title = title.replace(" - Signpost", "")

        return self.clean_text(title)