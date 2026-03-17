from __future__ import annotations

from scrapers.darwinbox import DarwinboxScraper


class SynamediaScraper(DarwinboxScraper):
    source = "darwinbox_synamedia"
    base_url = "https://synamedia.darwinbox.com"
    company_id = "main"
    listing_url = "https://synamedia.darwinbox.com/ms/candidatev2/main/careers/allJobs"
    api_url = "https://synamedia.darwinbox.com/ms/candidateapi/job/alljobs?companyId=main"