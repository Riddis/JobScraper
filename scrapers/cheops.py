from __future__ import annotations

from scrapers.base import ListingDetailScraper


class CheopsScraper(ListingDetailScraper):
    source = "cheops"
    base_url = "https://www.cheops.com"
    listing_url = "https://www.cheops.com/jobs/"

    job_path_prefixes = ("/jobs/",)