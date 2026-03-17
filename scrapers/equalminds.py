from __future__ import annotations

from scrapers.base import ListingDetailScraper


class EqualMindsScraper(ListingDetailScraper):
    source = "equalminds"
    base_url = "https://equalminds.eu"
    listing_url = "https://equalminds.eu/about-us/careers/"

    job_path_prefixes = ("/career/",)