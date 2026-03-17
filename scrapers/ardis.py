from __future__ import annotations

from scrapers.base import ListingDetailScraper


class ArdisScraper(ListingDetailScraper):
    source = "ardis"
    base_url = "https://www.ardis.eu"
    listing_url = "https://www.ardis.eu/nl-BE/over-ons/jobs"
    listing_link_base_url = "https://www.ardis.eu/nl-BE/over-ons/"
    job_path_contains = ("/vacancies/",)
    title_suffixes_to_strip = (
        " - ARDIS | Cutting edge manufacturing software.",
    )