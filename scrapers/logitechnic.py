from __future__ import annotations

from bs4 import BeautifulSoup

from scrapers.base import ListingDetailScraper


class LogiTechnicScraper(ListingDetailScraper):
    source = "logitechnic"
    base_url = "https://www.logi-technic.be"
    listing_url = "https://www.logi-technic.be/jobs/"

    job_path_prefixes = ("/job/",)

    def extract_title_from_detail_soup(
        self,
        soup: BeautifulSoup,
        url: str,
    ) -> str:
        h1 = soup.find("h1")
        if h1:
            title = self.clean_text(h1.get_text(" ", strip=True))
            if title:
                return title

        for tag in soup.find_all(["h1", "h2", "h3"]):
            text = self.clean_text(tag.get_text(" ", strip=True))
            if text:
                return text

        title_tag = soup.find("title")
        if title_tag:
            return self.clean_text(title_tag.get_text(" ", strip=True))

        return ""