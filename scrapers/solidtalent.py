from __future__ import annotations

from scrapers.planet_group import PlanetGroupAjaxScraper


class SolidTalentScraper(PlanetGroupAjaxScraper):
    source = "planetgroup_solidtalent"
    base_url = "https://jobs.solid-talent.be/"
    listing_url = "https://jobs.solid-talent.be/"
    ajax_url = "https://jobs.solid-talent.be/wp-admin/admin-ajax.php"