from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from typing import Dict, List, Tuple

from filters.blacklist import load_title_blacklist, is_title_blacklisted

# Scraper imports
from scrapers.astrid import AstridScraper
from scrapers.bizztalent import BizzTalentScraper
from scrapers.cheops import CheopsScraper
from scrapers.cobral import CobralScraper
from scrapers.decathlon import DecathlonScraper
from scrapers.district09 import District09Scraper
from scrapers.equalminds import EqualMindsScraper
from scrapers.harveynash import HarveyNashScraper
from scrapers.hr_planet import HRPlanetScraper
from scrapers.it_planet import ITPlanetScraper
from scrapers.itsgroup import ITSGroupScraper
from scrapers.logitechnic import LogiTechnicScraper
from scrapers.projinit import ProjinitScraper
from scrapers.resolvus import ResolvusScraper
from scrapers.simac import SimacScraper
from scrapers.splendit import SplendITScraper
from scrapers.talencia import TalenciaScraper
from scrapers.televic import TelevicScraper
from scrapers.uilenspel import UilenspelScraper
from scrapers.upgrade_estate import UpgradeEstateScraper
from scrapers.verdon import VerdonScraper
from scrapers.xcare import XCareScraper
from scrapers.xelor import XelorScraper
from scrapers.oost_vlaanderen import OostVlaanderenScraper
from scrapers.infrabel import InfrabelScraper
from scrapers.hieronymus import HieronymusScraper
from scrapers.durabrik import DurabrikScraper
from scrapers.colruytgroup import ColruytGroupScraper
from scrapers.itprovider import ITProviderScraper
from scrapers.ardis import ArdisScraper
from scrapers.dataclean import DataCleanScraper
from scrapers.evara import EvaraScraper
from scrapers.solidaris import SolidarisScraper
from scrapers.battmobility import BattMobilityScraper
from scrapers.hogent import HOGentScraper
from scrapers.signpost import SignpostScraper
from scrapers.vdkbank import VDKScraper
from scrapers.fluxys import FluxysScraper
from scrapers.volvocars import VolvoCarsScraper
from scrapers.taborgroep import TaborGroepScraper
from scrapers.meatandmore import MeatAndMoreScraper
from scrapers.crelan import CrelanScraper
from scrapers.hays import HaysScraper
from scrapers.synamedia import SynamediaScraper

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
FILTERS_DIR = BASE_DIR / "filters"

DATA_DIR.mkdir(exist_ok=True)
FILTERS_DIR.mkdir(exist_ok=True)

CSV_FILE = DATA_DIR / "jobs.csv"
TITLE_BLACKLIST_FILE = FILTERS_DIR / "title_blacklist.txt"
DISABLE_BLACKLIST = True

FIELDNAMES = [
    "source",
    "title",
    "url",
    "location",
    "location_is_guess",
    "first_seen_date",
    "last_seen_date",
    "is_active",
]


def load_existing_jobs(csv_file: Path) -> Dict[Tuple[str, str], Dict[str, str]]:
    """
    Load existing jobs from CSV into a dict keyed by (source, url).
    """
    jobs: Dict[Tuple[str, str], Dict[str, str]] = {}

    if not csv_file.exists():
        return jobs

    with csv_file.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row["source"], row["url"])

            if "location" not in row:
                row["location"] = ""
            if "location_is_guess" not in row:
                row["location_is_guess"] = "False"

            jobs[key] = row

    return jobs


def save_jobs(csv_file: Path, jobs: Dict[Tuple[str, str], Dict[str, str]]) -> None:
    """
    Save all jobs back to CSV.
    """
    rows = sorted(
        jobs.values(),
        key=lambda row: (row["source"], row["title"], row["url"]),
    )

    with csv_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def remove_blacklisted_existing_jobs(
    existing_jobs: Dict[Tuple[str, str], Dict[str, str]],
    title_blacklist,
) -> Dict[Tuple[str, str], Dict[str, str]]:
    """
    Remove already-stored jobs whose titles are blacklisted.
    """
    cleaned_jobs: Dict[Tuple[str, str], Dict[str, str]] = {}

    for key, row in existing_jobs.items():
        title = row.get("title", "")
        source = row.get("source", "")

        if is_title_blacklisted(title, title_blacklist, source=source):
            continue

        cleaned_jobs[key] = row

    return cleaned_jobs


def filter_scraped_jobs(
    scraped_jobs: List[Dict[str, str]],
    title_blacklist,
) -> List[Dict[str, str]]:
    """
    Remove blacklisted jobs from newly scraped results.
    """
    filtered_jobs: List[Dict[str, str]] = []

    for job in scraped_jobs:
        title = job.get("title", "")
        source = job.get("source", "")

        if not DISABLE_BLACKLIST:
            if is_title_blacklisted(title, title_blacklist, source=source):
                continue

        filtered_jobs.append(job)

    return filtered_jobs


def merge_scrape_results(
    existing_jobs: Dict[Tuple[str, str], Dict[str, str]],
    scraped_jobs: List[Dict[str, str]],
    scraped_date: str,
) -> Dict[Tuple[str, str], Dict[str, str]]:
    """
    Merge current scrape results into the historical dataset.

    Important behavior:
    - New jobs are added
    - Existing jobs are updated
    - Jobs from scraped sources that are no longer present are marked inactive
    - Jobs from sources not scraped in this run are left untouched
    """
    current_keys = set()
    scraped_sources = {job["source"] for job in scraped_jobs}

    for job in scraped_jobs:
        key = (job["source"], job["url"])
        current_keys.add(key)

        location = job.get("location", "").strip()
        location_is_guess = str(job.get("location_is_guess", "False")).strip() or "False"

        if key in existing_jobs:
            existing_jobs[key]["title"] = job["title"]
            existing_jobs[key]["location"] = location
            existing_jobs[key]["location_is_guess"] = location_is_guess
            existing_jobs[key]["last_seen_date"] = scraped_date
            existing_jobs[key]["is_active"] = "True"
        else:
            existing_jobs[key] = {
                "source": job["source"],
                "title": job["title"],
                "url": job["url"],
                "location": location,
                "location_is_guess": location_is_guess,
                "first_seen_date": job.get("first_seen_date") or scraped_date,
                "last_seen_date": scraped_date,
                "is_active": "True",
            }

    for key, row in existing_jobs.items():
        if key not in current_keys and row["source"] in scraped_sources:
            row["is_active"] = "False"

    return existing_jobs


def main() -> None:
    scraped_date = date.today().isoformat()
    title_blacklist = load_title_blacklist(TITLE_BLACKLIST_FILE)

    scrapers = [
        #ArdisScraper(),
        #AstridScraper(),
        #BattMobilityScraper(),
        #BizzTalentScraper(),
        #CheopsScraper(),
        #CobralScraper(),
        #ColruytGroupScraper(),
        #CrelanScraper(),
        #DataCleanScraper(),
        #DecathlonScraper(),
        #District09Scraper(),
        #DurabrikScraper(),
        #EqualMindsScraper(),
        #EvaraScraper(),
        #FluxysScraper(),
        #HarveyNashScraper(),
        ##HaysScraper(),
        #HieronymusScraper(),
        #HOGentScraper(),
        #HRPlanetScraper(),
        #InfrabelScraper(),
        #ITPlanetScraper(),
        #ITProviderScraper(),
        #ITSGroupScraper(),
        #LogiTechnicScraper(),
        #MeatAndMoreScraper(),
        #OostVlaanderenScraper(),
        #ProjinitScraper(),
        #ResolvusScraper(),
        #SignpostScraper(),
        #SimacScraper(),
        #SolidarisScraper(),
        #SplendITScraper(),
        ##SynamediaScraper(),
        #TaborGroepScraper(),
        #TalenciaScraper(),
        TelevicScraper(),
        #UilenspelScraper(),
        UpgradeEstateScraper(),
        #VDKScraper(),
        #VerdonScraper(),
        #VolvoCarsScraper(),
        #XCareScraper(),
        #XelorScraper(),
    ]

    if DISABLE_BLACKLIST:
        print("⚠️ Blacklist disabled (testing mode)")

    existing_jobs = load_existing_jobs(CSV_FILE)
    existing_jobs = remove_blacklisted_existing_jobs(existing_jobs, title_blacklist)

    for scraper in scrapers:
        print(f"\n--- Running scraper: {scraper.source} ---\n")
        scraped_jobs = scraper.scrape_jobs()
        scraped_jobs = filter_scraped_jobs(scraped_jobs, title_blacklist)
        existing_jobs = merge_scrape_results(existing_jobs, scraped_jobs, scraped_date)

    save_jobs(CSV_FILE, existing_jobs)

    print(f"\nSaved results to {CSV_FILE.resolve()}")


if __name__ == "__main__":
    main()