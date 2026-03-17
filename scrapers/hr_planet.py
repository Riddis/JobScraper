from __future__ import annotations

from bs4 import BeautifulSoup

from scrapers.planet_group import PlanetGroupAjaxScraper


class HRPlanetScraper(PlanetGroupAjaxScraper):
    source = "planetgroup_hrplanet"
    base_url = "https://hr-planet.be"
    listing_url = "https://hr-planet.be/vacatures/"
    ajax_url = "https://hr-planet.be/wp-admin/admin-ajax.php"
