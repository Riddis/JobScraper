from __future__ import annotations

import re
import subprocess
import unicodedata
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup


class BaseScraper(ABC):
    source: str
    base_url: str = ""
    listing_url: str = ""

    use_curl: bool = False
    curl_headers: tuple[str, ...] = ()
    default_curl_headers: tuple[str, ...] = (
        "accept: text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8,"
        "application/signed-exchange;v=b3;q=0.7",
        "accept-language: nl,en;q=0.9,en-GB;q=0.8,en-US;q=0.7",
        "cache-control: max-age=0",
        "priority: u=0, i",
        'sec-ch-ua: "Not:A-Brand";v="99", "Microsoft Edge";v="145", "Chromium";v="145"',
        "sec-ch-ua-mobile: ?0",
        'sec-ch-ua-platform: "Windows"',
        "sec-fetch-dest: document",
        "sec-fetch-mode: navigate",
        "sec-fetch-site: same-origin",
        "sec-fetch-user: ?1",
        "upgrade-insecure-requests: 1",
        (
            "user-agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0"
        ),
    )

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                )
            }
        )
        self._city_names_cache: List[str] | None = None

    def clean_text(self, text: str) -> str:
        return " ".join(text.split())

    def slugify_text(self, text: str) -> str:
        slug = self.clean_text(text).lower()
        slug = slug.replace("&", "en")
        slug = re.sub(r"[^a-z0-9]+", "-", slug)
        slug = re.sub(r"-+", "-", slug).strip("-")
        return slug

    def build_hash_url(self, base_url: str, fragment: str) -> str:
        fragment = fragment.strip().lstrip("#")
        if not fragment:
            return base_url
        return f"{base_url}#{fragment}"

    def get(self, url: str, **kwargs) -> requests.Response:
        response = self.session.get(url, timeout=30, **kwargs)
        response.raise_for_status()
        return response

    def post(self, url: str, **kwargs) -> requests.Response:
        response = self.session.post(url, timeout=30, **kwargs)
        response.raise_for_status()
        return response

    def get_soup_via_curl(self, url: str) -> BeautifulSoup:
        command = [
            "curl",
            "--silent",
            "--show-error",
            "--location",
            "--compressed",
            url,
        ]

        headers = self.curl_headers or self.default_curl_headers
        for header in headers:
            command.extend(["-H", header])

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
        )

        return BeautifulSoup(result.stdout, "lxml")

    def get_soup(self, url: str, **kwargs) -> BeautifulSoup:
        if self.use_curl:
            return self.get_soup_via_curl(url)

        response = self.get(url, **kwargs)
        return BeautifulSoup(response.text, "lxml")

    def normalize_url(self, base_url: str, href: str | None) -> str:
        if not href:
            return ""

        href = href.strip()

        if href.startswith("#"):
            return ""

        if href.startswith("mailto:"):
            return ""

        if href.startswith("javascript:"):
            return ""

        return urljoin(base_url, href)

    def url_path(self, url: str) -> str:
        return urlparse(url).path.rstrip("/").lower()

    def get_listing_urls(self) -> List[str]:
        return [self.listing_url]

    def build_job_dict(
        self,
        title: str,
        url: str,
        first_seen_date: str = "",
        location: str = "",
        location_is_guess: bool = False,
    ) -> Dict[str, str]:
        job = {
            "source": self.source,
            "title": self.clean_text(title),
            "url": url,
            "location": self.clean_text(location),
            "location_is_guess": "True" if location_is_guess else "False",
        }

        if first_seen_date:
            job["first_seen_date"] = str(first_seen_date).strip()

        return job

    def sort_jobs(self, jobs: List[Dict[str, str]]) -> List[Dict[str, str]]:
        return sorted(jobs, key=lambda job: (job["title"], job["url"]))

    def merge_job_stub(
        self,
        jobs_by_url: Dict[str, Dict[str, str]],
        url: str,
        title: str = "",
        location: str = "",
    ) -> None:
        existing = jobs_by_url.get(url, {})

        title = self.clean_text(title)
        location = self.clean_text(location)

        if title and not existing.get("title"):
            existing["title"] = title
        elif "title" not in existing:
            existing["title"] = ""

        if location and not existing.get("location"):
            existing["location"] = location
        elif "location" not in existing:
            existing["location"] = ""

        jobs_by_url[url] = existing

    def log_fetching(self, url: str) -> None:
        print(f"Fetching listing page: {url}")

    def log_found(self, count: int) -> None:
        print(f"Found {count} job links")

    def log_scraping(self, url: str) -> None:
        print(f"Scraping: {url}")

    def project_root(self) -> Path:
        return Path(__file__).resolve().parent.parent

    def cities_file(self) -> Path:
        return self.project_root() / "data" / "cities.txt"

    def load_city_names(self) -> List[str]:
        if self._city_names_cache is not None:
            return self._city_names_cache

        cities_path = self.cities_file()

        if not cities_path.exists():
            self._city_names_cache = []
            return self._city_names_cache

        text = ""
        for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                text = cities_path.read_text(encoding=encoding)
                break
            except UnicodeDecodeError:
                continue

        if not text:
            self._city_names_cache = []
            return self._city_names_cache

        cities: List[str] = []

        for line in text.splitlines():
            city = self.clean_text(line.strip())
            if not city:
                continue
            cities.append(city)

        cities = sorted(set(cities), key=lambda city: (-len(city), city.lower()))
        self._city_names_cache = cities
        return self._city_names_cache

    def normalize_for_matching(self, text: str) -> str:
        text = unicodedata.normalize("NFKD", text)
        text = "".join(char for char in text if not unicodedata.combining(char))
        text = text.lower()
        text = self.clean_text(text)
        return text

    def extract_location_candidate_text(self, soup: BeautifulSoup) -> str:
        soup = BeautifulSoup(str(soup), "lxml")

        for tag in soup.select(
            "script, style, noscript, svg, header, footer, nav, aside, form"
        ):
            tag.decompose()

        for tag in soup.select(
            "[aria-label*='cookie' i], "
            "[class*='cookie' i], [id*='cookie' i], "
            "[class*='newsletter' i], [id*='newsletter' i], "
            "[class*='footer' i], [id*='footer' i], "
            "[class*='header' i], [id*='header' i], "
            "[class*='nav' i], [id*='nav' i], "
            "[class*='menu' i], [id*='menu' i], "
            "[class*='breadcrumb' i], [id*='breadcrumb' i], "
            "[class*='legal' i], [id*='legal' i], "
            "[class*='contact' i], [id*='contact' i]"
        ):
            tag.decompose()

        preferred_selectors = [
            "main",
            "article",
            "[role='main']",
            ".job",
            ".jobs",
            ".job-detail",
            ".job-details",
            ".job-content",
            ".vacancy",
            ".vacancies",
            ".vacancy-detail",
            ".vacancy-details",
            ".content",
            ".entry-content",
            ".post-content",
            ".page-content",
        ]

        chunks: List[str] = []

        for selector in preferred_selectors:
            for el in soup.select(selector):
                text = self.clean_text(el.get_text(" ", strip=True))
                if text and len(text) >= 80:
                    chunks.append(text)

        if chunks:
            return self.clean_text(" ".join(chunks))

        body = soup.body or soup
        return self.clean_text(body.get_text(" ", strip=True))

    def guess_location_from_text(self, text: str) -> str:
        text_normalized = self.normalize_for_matching(text)
        if not text_normalized:
            return ""

        matches: List[str] = []

        for city in self.load_city_names():
            city_normalized = self.normalize_for_matching(city)
            pattern = r"(?<!\w)" + re.escape(city_normalized) + r"(?!\w)"

            if re.search(pattern, text_normalized):
                matches.append(city)

        if len(matches) == 1:
            return matches[0]

        return ""

    @abstractmethod
    def scrape_jobs(self) -> List[Dict[str, str]]:
        raise NotImplementedError


class ListingDetailScraper(BaseScraper):
    listing_link_base_url: str | None = None
    job_path_prefixes: tuple[str, ...] = ()
    job_path_contains: tuple[str, ...] = ()
    job_path_excludes: tuple[str, ...] = ()
    title_suffixes_to_strip: tuple[str, ...] = ()
    location_selectors: tuple[str, ...] = ()

    listing_anchor_text_blacklist: tuple[str, ...] = ()
    listing_anchor_text_required: tuple[str, ...] = ()

    fetch_detail_pages: bool = True

    location_patterns: tuple[str, ...] = (
        r"\b(?:locatie|location|standplaats|plaats van tewerkstelling|lieu de travail|arbeitsort)\s*[:\-]\s*([A-ZÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ'’\-/ ]+)",
        r"\b(?:gebaseerd in|based in|basé à|based at)\s+([A-ZÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ'’\-/ ]+)",
        r"\b(?:hoofdzetel te|gevestigd te)\s+([A-ZÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ'’\-/ ]+)",
    )

    def is_job_url(self, url: str) -> bool:
        path = self.url_path(url)

        for excluded in self.job_path_excludes:
            if excluded.lower() in path:
                return False

        for prefix in self.job_path_prefixes:
            if path.startswith(prefix.lower()):
                return True

        for chunk in self.job_path_contains:
            if chunk.lower() in path:
                return True

        return False

    def should_keep_listing_anchor(
        self,
        a: BeautifulSoup,
        url: str,
    ) -> bool:
        text = self.clean_text(a.get_text(" ", strip=True)).lower()

        if not text:
            return False

        if self.listing_anchor_text_required:
            if not any(
                required.lower() in text
                for required in self.listing_anchor_text_required
            ):
                return False

        for bad in self.listing_anchor_text_blacklist:
            if bad.lower() in text:
                return False

        return True

    def extract_title_from_listing_anchor(
        self,
        a: BeautifulSoup,
        url: str,
    ) -> str:
        return ""

    def extract_location_from_listing_anchor(
        self,
        a: BeautifulSoup,
        url: str,
    ) -> str:
        return ""

    def normalize_location_value(self, text: str) -> str:
        text = self.clean_text(text)
        text = re.split(r"\s{2,}|\s+\|\s+|\s+/\s+", text)[0]
        text = re.sub(
            r"^(locatie|location|standplaats|plaats van tewerkstelling|lieu de travail|arbeitsort)\s*[:\-]\s*",
            "",
            text,
            flags=re.IGNORECASE,
        )
        return self.clean_text(text)

    def extract_links_from_listing_soup(
        self,
        soup: BeautifulSoup,
        page_url: str,
    ) -> Dict[str, Dict[str, str]]:
        jobs_by_url: Dict[str, Dict[str, str]] = {}
        base_for_links = self.listing_link_base_url or page_url

        for a in soup.select("a[href]"):
            href = a.get("href")
            url = self.normalize_url(base_for_links, href)
            if not url:
                continue

            if not self.is_job_url(url):
                continue

            if not self.should_keep_listing_anchor(a, url):
                continue

            title = self.extract_title_from_listing_anchor(a, url)
            location = self.extract_location_from_listing_anchor(a, url)

            self.merge_job_stub(
                jobs_by_url=jobs_by_url,
                url=url,
                title=title,
                location=location,
            )

        return jobs_by_url

    def scrape_listing_page_into_jobs_by_url(
        self,
        jobs_by_url: Dict[str, Dict[str, str]],
        page_url: str,
    ) -> Dict[str, Dict[str, str]]:
        self.log_fetching(page_url)
        soup = self.get_soup(page_url)
        page_jobs = self.extract_links_from_listing_soup(soup, page_url)

        for url, data in page_jobs.items():
            self.merge_job_stub(
                jobs_by_url=jobs_by_url,
                url=url,
                title=data.get("title", ""),
                location=data.get("location", ""),
            )

        return page_jobs

    def extract_title_from_detail_soup(
        self,
        soup: BeautifulSoup,
        url: str,
    ) -> str:
        title = ""

        h1 = soup.find("h1")
        if h1:
            title = self.clean_text(h1.get_text(" ", strip=True))

        if not title:
            og_title = soup.find("meta", attrs={"property": "og:title"})
            if og_title and og_title.get("content"):
                title = self.clean_text(og_title["content"])

        if not title:
            title_tag = soup.find("title")
            if title_tag:
                title = self.clean_text(title_tag.get_text(" ", strip=True))

        for suffix in self.title_suffixes_to_strip:
            title = title.replace(suffix, "")

        return self.clean_text(title)

    def extract_location_from_selectors(
        self,
        soup: BeautifulSoup,
    ) -> str:
        for selector in self.location_selectors:
            for el in soup.select(selector):
                text = self.normalize_location_value(el.get_text(" ", strip=True))
                if not text:
                    continue

                guessed = self.guess_location_from_text(text)
                if guessed:
                    return guessed

                if len(text) <= 120:
                    return text

        return ""

    def extract_location_from_patterns(
        self,
        soup: BeautifulSoup,
    ) -> str:
        text = self.extract_location_candidate_text(soup)

        for pattern in self.location_patterns:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                candidate = self.normalize_location_value(match.group(1))
                if not candidate:
                    continue

                guessed = self.guess_location_from_text(candidate)
                if guessed:
                    return guessed

                if len(candidate) <= 120:
                    return candidate

        return ""

    def extract_location_from_detail_soup(
        self,
        soup: BeautifulSoup,
        url: str,
    ) -> str:
        location = self.extract_location_from_selectors(soup)
        if location:
            return location

        location = self.extract_location_from_patterns(soup)
        if location:
            return location

        return ""

    def parse_job_detail(
        self,
        url: str,
        listing_title: str = "",
        listing_location: str = "",
    ) -> Dict[str, str] | None:
        title = self.clean_text(listing_title)
        location = self.clean_text(listing_location)
        location_is_guess = False

        if not self.fetch_detail_pages:
            if not title:
                return None

            return self.build_job_dict(
                title=title,
                url=url,
                location=location,
                location_is_guess=location_is_guess,
            )

        need_detail = not listing_title or not listing_location

        soup: BeautifulSoup | None = None
        if need_detail:
            soup = self.get_soup(url)

        if not title and soup is not None:
            title = self.extract_title_from_detail_soup(soup, url)

        if not title:
            return None

        if not location and soup is not None:
            location = self.extract_location_from_detail_soup(soup, url)

        if not location and soup is not None:
            candidate_text = self.extract_location_candidate_text(soup)
            location = self.guess_location_from_text(candidate_text)
            if location:
                location_is_guess = True

        return self.build_job_dict(
            title=title,
            url=url,
            location=location,
            location_is_guess=location_is_guess,
        )

    def scrape_listing_pages(self) -> Dict[str, Dict[str, str]]:
        jobs_by_url: Dict[str, Dict[str, str]] = {}

        for page_url in self.get_listing_urls():
            self.scrape_listing_page_into_jobs_by_url(jobs_by_url, page_url)

        return jobs_by_url

    def scrape_jobs(self) -> List[Dict[str, str]]:
        jobs_by_url = self.scrape_listing_pages()

        self.log_found(len(jobs_by_url))

        jobs: List[Dict[str, str]] = []

        for url in sorted(jobs_by_url):
            self.log_scraping(url)

            listing_title = jobs_by_url[url].get("title", "")
            listing_location = jobs_by_url[url].get("location", "")

            job = self.parse_job_detail(
                url=url,
                listing_title=listing_title,
                listing_location=listing_location,
            )
            if not job:
                continue

            jobs.append(job)

        return self.sort_jobs(jobs)


class PaginatedListingDetailScraper(ListingDetailScraper):
    page_param: str = "page"
    start_page: int = 1
    max_pages: int | None = None

    def build_listing_page_url(self, page: int) -> str:
        if page == self.start_page:
            return self.listing_url

        parsed = urlparse(self.listing_url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query[self.page_param] = str(page)

        return urlunparse(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                urlencode(query),
                parsed.fragment,
            )
        )

    def scrape_listing_pages(self) -> Dict[str, Dict[str, str]]:
        jobs_by_url: Dict[str, Dict[str, str]] = {}
        page = self.start_page

        while True:
            if self.max_pages is not None and page > self.max_pages:
                break

            page_url = self.build_listing_page_url(page)
            page_jobs = self.scrape_listing_page_into_jobs_by_url(jobs_by_url, page_url)

            if not page_jobs:
                break

            page += 1

        return jobs_by_url


class SinglePageSectionScraper(BaseScraper):
    @abstractmethod
    def extract_jobs_from_listing_soup(
        self,
        soup: BeautifulSoup,
        page_url: str,
    ) -> List[Dict[str, str]]:
        raise NotImplementedError

    def scrape_jobs(self) -> List[Dict[str, str]]:
        self.log_fetching(self.listing_url)
        soup = self.get_soup(self.listing_url)

        jobs = self.extract_jobs_from_listing_soup(soup, self.listing_url)
        jobs = self.sort_jobs(jobs)

        self.log_found(len(jobs))

        for job in jobs:
            self.log_scraping(job["url"])

        return jobs


class ApiScraper(BaseScraper):
    start_page: int = 1
    page_size: int = 10
    page_delay_seconds: float = 0.0

    def before_scrape(self) -> None:
        pass

    @abstractmethod
    def get_api_page(self, page: int) -> Dict:
        raise NotImplementedError

    def extract_results(self, response_json: Dict) -> List[Dict]:
        return []

    def extract_total_count(self, response_json: Dict) -> int | None:
        return None

    def next_page_value(self, page: int) -> int:
        return page + 1

    def extract_location_from_category_values(
        self,
        categories: object,
        category_names: tuple[str, ...] = ("location",),
    ) -> str:
        if not isinstance(categories, list):
            return ""

        wanted = {name.lower() for name in category_names}

        for category in categories:
            if not isinstance(category, dict):
                continue

            category_name = self.clean_text(str(category.get("name", ""))).lower()
            if category_name not in wanted:
                continue

            values = category.get("values", [])
            if not isinstance(values, list):
                continue

            names: List[str] = []

            for value in values:
                if not isinstance(value, dict):
                    continue

                name = value.get("name")
                if isinstance(name, str):
                    name = self.clean_text(name)
                    if name:
                        names.append(name)

            unique_names = sorted(set(names))
            if len(unique_names) == 1:
                return unique_names[0]

        return ""

    def extract_single_string_from_list(self, value: object) -> str:
        if not isinstance(value, list):
            return ""

        items = [
            self.clean_text(item)
            for item in value
            if isinstance(item, str) and self.clean_text(item)
        ]

        unique_items = sorted(set(items))
        if len(unique_items) == 1:
            return unique_items[0]

        return ""

    def extract_location_from_postal_addresses(
        self,
        locations: object,
    ) -> str:
        if not isinstance(locations, list):
            return ""

        localities: List[str] = []
        admin_areas: List[str] = []
        address_lines: List[str] = []

        for location in locations:
            if not isinstance(location, dict):
                continue

            postal_address = location.get("postal_address", {})
            if not isinstance(postal_address, dict):
                continue

            locality = postal_address.get("locality")
            if isinstance(locality, str):
                locality = self.clean_text(locality)
                if locality:
                    localities.append(locality)

            administrative_area = postal_address.get("administrative_area")
            if isinstance(administrative_area, str):
                administrative_area = self.clean_text(administrative_area)
                if administrative_area:
                    admin_areas.append(administrative_area)

            lines = postal_address.get("address_lines", [])
            if isinstance(lines, list):
                for line in lines:
                    if isinstance(line, str):
                        line = self.clean_text(line)
                        if line:
                            address_lines.append(line)

        unique_localities = sorted(set(localities))
        if len(unique_localities) == 1:
            return unique_localities[0]

        unique_admin_areas = sorted(set(admin_areas))
        if len(unique_admin_areas) == 1:
            guessed = self.guess_location_from_text(unique_admin_areas[0])
            if guessed:
                return guessed
            return unique_admin_areas[0]

        unique_address_lines = sorted(set(address_lines))
        if len(unique_address_lines) == 1:
            guessed = self.guess_location_from_text(unique_address_lines[0])
            if guessed:
                return guessed
            return unique_address_lines[0]

        return ""

    def extract_location_from_text_fields(
        self,
        data: Dict,
        keys: tuple[str, ...],
    ) -> str:
        for key in keys:
            value = data.get(key)
            if isinstance(value, str):
                value = self.clean_text(value)
                if not value:
                    continue

                guessed = self.guess_location_from_text(value)
                if guessed:
                    return guessed
                return value

        return ""

    def extract_location_from_api_data(
        self,
        data: Dict,
        *,
        text_keys: tuple[str, ...] = (
            "city",
            "location",
            "jobLocation",
            "job_location",
            "full_location",
            "short_location",
            "location_name",
            "region",
            "office",
        ),
        list_keys: tuple[str, ...] = (
            "addresses",
            "locations",
            "jobLocations",
            "job_locations",
        ),
        category_keys: tuple[str, ...] = ("location",),
        derived_info_key: str = "derived_info",
        description_keys: tuple[str, ...] = ("description",),
    ) -> tuple[str, bool]:
        location = self.extract_location_from_text_fields(data, text_keys)
        if location:
            return location, False

        for key in list_keys:
            value = data.get(key)
            location = self.extract_single_string_from_list(value)
            if location:
                guessed = self.guess_location_from_text(location)
                if guessed:
                    return guessed, False
                return location, False

        location = self.extract_location_from_category_values(
            data.get("categories"),
            category_names=category_keys,
        )
        if location:
            guessed = self.guess_location_from_text(location)
            if guessed:
                return guessed, False
            return location, False

        derived_info = data.get(derived_info_key, {})
        if isinstance(derived_info, dict):
            location = self.extract_location_from_postal_addresses(
                derived_info.get("locations")
            )
            if location:
                return location, False

        candidate_chunks: List[str] = []

        for key in description_keys:
            value = data.get(key)
            if isinstance(value, str):
                text = self.clean_text(value)
                if text:
                    candidate_chunks.append(text)

        if candidate_chunks:
            guessed = self.guess_location_from_text(" ".join(candidate_chunks))
            if guessed:
                return guessed, True

        return "", False

    @abstractmethod
    def parse_job(self, raw_job: Dict) -> Dict[str, str] | None:
        raise NotImplementedError

    def should_continue(
        self,
        page: int,
        results: List[Dict],
        jobs_by_url: Dict[str, Dict[str, str]],
        total_count: int | None,
    ) -> bool:
        if not results:
            return False

        if total_count is not None and len(jobs_by_url) >= total_count:
            return False

        if len(results) < self.page_size:
            return False

        return True

    def scrape_jobs(self) -> List[Dict[str, str]]:
        self.before_scrape()

        jobs_by_url: Dict[str, Dict[str, str]] = {}
        page = self.start_page
        total_count: int | None = None

        while True:
            self.log_fetching(f"API page {page}")

            response_json = self.get_api_page(page)
            results = self.extract_results(response_json)

            for raw_job in results:
                parsed_job = self.parse_job(raw_job)
                if not parsed_job:
                    continue

                title = self.clean_text(parsed_job.get("title", ""))
                url = parsed_job.get("url", "").strip()
                location = self.clean_text(parsed_job.get("location", ""))
                location_is_guess = str(
                    parsed_job.get("location_is_guess", "False")
                ).strip() or "False"

                if not title:
                    continue

                if not url:
                    continue

                parsed_job["title"] = title
                parsed_job["location"] = location
                parsed_job["location_is_guess"] = location_is_guess
                jobs_by_url[url] = parsed_job

            if total_count is None:
                total_count = self.extract_total_count(response_json)

            if not self.should_continue(
                page=page,
                results=results,
                jobs_by_url=jobs_by_url,
                total_count=total_count,
            ):
                break

            if self.page_delay_seconds > 0:
                import time
                time.sleep(self.page_delay_seconds)

            page = self.next_page_value(page)

        jobs = self.sort_jobs(list(jobs_by_url.values()))

        self.log_found(len(jobs))

        for job in jobs:
            self.log_scraping(job["url"])

        return jobs