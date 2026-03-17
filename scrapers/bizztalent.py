from __future__ import annotations

from scrapers.base import ListingDetailScraper


class BizzTalentScraper(ListingDetailScraper):
    source = "bizztalent"
    base_url = "https://www.bizztalent.be"
    listing_url = "https://www.bizztalent.be/vacatures"
    job_path_prefixes = ("/vacatures/",)
    job_path_excludes = (
        "/vacatures/send-us-your-cv",
        "/vacatures/solliciteer-spontaan",
        "/vacatures/apply-spontaneously",
    )

    listing_anchor_text_blacklist = (
        "send us your cv",
        "solliciteer spontaan",
        "apply spontaneously",
    )