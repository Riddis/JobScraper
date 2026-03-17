from __future__ import annotations

from typing import Dict, List

from bs4 import BeautifulSoup

from scrapers.base import BaseScraper


class TelevicScraper(BaseScraper):
    source = "televic"
    base_url = "https://careers.televic.com"
    listing_url = "https://careers.televic.com/jobs/"

    def is_job_url(self, url: str) -> bool:
        path = self.url_path(url)
        parts = [part for part in path.split("/") if part]

        if len(parts) != 3:
            return False

        if parts[0] != "jobs":
            return False

        return True

    def is_belgium_text(self, text: str) -> bool:
        return "belgium" in text.lower()

    def normalize_location(self, text: str) -> str:
        location = self.clean_text(text)
        if not location:
            return ""

        if location.lower().endswith(", belgium"):
            location = location[:-9]

        return self.clean_text(location.rstrip(",").strip())

    def extract_title_from_card(self, card: BeautifulSoup) -> str:
        for selector in ("h2", "h3", ".job-title", ".entry-title"):
            el = card.select_one(selector)
            if el:
                title = self.clean_text(el.get_text(" ", strip=True))
                if title:
                    return title

        return ""

    def extract_location_from_card(self, card: BeautifulSoup) -> str:
        location_label = None

        for heading in card.select(".elementor-heading-title"):
            text = self.clean_text(heading.get_text(" ", strip=True)).lower()
            if text == "location":
                location_label = heading
                break

        if location_label:
            container = location_label.find_parent(
                class_=lambda value: value and "e-con" in " ".join(value)
            )
            if container:
                sibling_container = container.find_next_sibling(
                    class_=lambda value: value and "e-con" in " ".join(value)
                )
                if sibling_container:
                    widget_container = sibling_container.select_one(
                        ".elementor-widget-container"
                    )
                    if widget_container:
                        location_text = self.clean_text(
                            widget_container.get_text(" ", strip=True)
                        )
                        if location_text:
                            return self.normalize_location(location_text)

        for el in card.select(".elementor-widget-container"):
            text = self.clean_text(el.get_text(" ", strip=True))
            if text and self.is_belgium_text(text):
                return self.normalize_location(text)

        return ""

    def extract_title_from_detail(self, soup: BeautifulSoup) -> str:
        h1 = soup.find("h1")
        if h1:
            title = self.clean_text(h1.get_text(" ", strip=True))
            if title:
                return title

        og_title = soup.find("meta", attrs={"property": "og:title"})
        if og_title and og_title.get("content"):
            return self.clean_text(og_title["content"])

        title_tag = soup.find("title")
        if title_tag:
            return self.clean_text(title_tag.get_text(" ", strip=True))

        return ""

    def detail_is_belgium(self, soup: BeautifulSoup) -> bool:
        text = self.clean_text(soup.get_text(" ", strip=True))
        return self.is_belgium_text(text)

    def scrape_jobs(self) -> List[Dict[str, str]]:
        links = set()
        link_titles: Dict[str, str] = {}
        link_locations: Dict[str, str] = {}

        print(f"Fetching listing page: {self.listing_url}")

        soup = self.get_soup(self.listing_url)

        for a in soup.select("a[href]"):
            href = a.get("href")
            url = self.normalize_url(self.listing_url, href)
            if not url:
                continue

            if not self.is_job_url(url):
                continue

            card = None

            overlay_wrap = a.find_parent(class_="jet-engine-listing-overlay-wrap")
            if overlay_wrap:
                card = overlay_wrap

            if card is None:
                for parent in a.parents:
                    parent_text = self.clean_text(parent.get_text(" ", strip=True))
                    if not parent_text:
                        continue

                    if "read more" in parent_text.lower():
                        card = parent
                        break

            if card is None:
                card = a

            card_text = self.clean_text(card.get_text(" ", strip=True))
            if not self.is_belgium_text(card_text):
                continue

            title = self.extract_title_from_card(card)
            if not title:
                title = self.clean_text(a.get_text(" ", strip=True))

            if not title:
                continue

            if "spontaneous" in title.lower():
                continue

            location = self.extract_location_from_card(card)

            links.add(url)
            link_titles[url] = title
            if location:
                link_locations[url] = location

        print(f"Found {len(links)} job links")

        jobs: List[Dict[str, str]] = []

        for url in sorted(links):
            print(f"Scraping: {url}")

            title = link_titles.get(url, "")
            location = link_locations.get(url, "")

            soup = self.get_soup(url)

            if not self.detail_is_belgium(soup):
                continue

            if not title:
                title = self.extract_title_from_detail(soup)

            if not title:
                continue

            if "spontaneous" in title.lower():
                continue

            jobs.append(
                self.build_job_dict(
                    title=title,
                    url=url,
                    location=location,
                    location_is_guess=False,
                )
            )

        return self.sort_jobs(jobs)