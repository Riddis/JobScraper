from __future__ import annotations

from scrapers.base import ListingDetailScraper


class BX1Scraper(ListingDetailScraper):
    source = "bx1"
    base_url = "https://bx1.be"
    listing_url = "https://bx1.be/annonce/"

    job_path_prefixes = ("/annonce/",)