from __future__ import annotations

from scrapers.planet_group import PlanetGroupAjaxScraper


class XCareScraper(PlanetGroupAjaxScraper):
    source = "planetgroup_xcare"
    base_url = "https://x-care.be/"
    listing_url = "https://x-care.be/vacatures/"
    ajax_url = "https://x-care.be/wp-admin/admin-ajax.php"