from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ClassificationResult:
    category: str
    subcategory: str


class JobClassifier:
    def __init__(
        self,
        category_rules_file: Path,
        title_overrides_file: Path,
    ) -> None:
        self.category_rules_file = category_rules_file
        self.title_overrides_file = title_overrides_file

        self.title_overrides = self._load_title_overrides(title_overrides_file)
        self.category_rules = self._load_category_rules(category_rules_file)

    @staticmethod
    def strip_accents(text: str) -> str:
        return "".join(
            ch for ch in unicodedata.normalize("NFKD", text)
            if not unicodedata.combining(ch)
        )

    @classmethod
    def normalize_title(cls, title: str) -> str:
        text = cls.strip_accents(title.lower())

        for old in ["&", "/", "\\", "-", "_", ".", ",", ":", ";", "(", ")", "[", "]", "|"]:
            text = text.replace(old, " ")

        replacements = {
            "front end": "frontend",
            "back end": "backend",
            "full stack": "fullstack",
            "dev ops": "devops",
            "site reliability engineer": "sre",
            "site reliability": "sre",
            "service desk": "helpdesk",
            "servicedesk": "helpdesk",
            "sys admin": "system administrator",
            "system admin": "system administrator",
            "1st line": "first line",
            "2nd line": "second line",
            "3rd line": "third line",
            "l1": "first line",
            "l2": "second line",
            "l3": "third line",
        }

        for old, new in replacements.items():
            text = text.replace(old, new)

        text = re.sub(r"\s+", " ", text).strip()
        return text

    def classify_job_title(self, title: str) -> ClassificationResult:
        normalized = self.normalize_title(title)

        if not normalized:
            return ClassificationResult(category="unrelated", subcategory="empty_title")

        if normalized in self.title_overrides:
            category, subcategory = self.title_overrides[normalized]
            return ClassificationResult(category=category, subcategory=subcategory)

        for category, subcategory, keyword in self.category_rules:
            if keyword in normalized:
                return ClassificationResult(category=category, subcategory=subcategory)

        return ClassificationResult(category="unrelated", subcategory="unmatched")

    def _load_title_overrides(self, file_path: Path) -> dict[str, tuple[str, str]]:
        overrides: dict[str, tuple[str, str]] = {}

        if not file_path.exists():
            return overrides

        with file_path.open("r", encoding="utf-8") as f:
            for line_number, raw_line in enumerate(f, start=1):
                line = raw_line.strip()

                if not line or line.startswith("#"):
                    continue

                parts = [part.strip() for part in line.split("|")]
                if len(parts) != 3:
                    raise ValueError(
                        f"Invalid line in {file_path.name} at line {line_number}: {raw_line.rstrip()}"
                    )

                raw_title, category, subcategory = parts
                normalized_title = self.normalize_title(raw_title)
                overrides[normalized_title] = (category, subcategory)

        return overrides

    def _load_category_rules(self, file_path: Path) -> list[tuple[str, str, str]]:
        rules: list[tuple[str, str, str]] = []

        if not file_path.exists():
            return rules

        with file_path.open("r", encoding="utf-8") as f:
            for line_number, raw_line in enumerate(f, start=1):
                line = raw_line.strip()

                if not line or line.startswith("#"):
                    continue

                parts = [part.strip() for part in line.split("|")]
                if len(parts) != 3:
                    raise ValueError(
                        f"Invalid line in {file_path.name} at line {line_number}: {raw_line.rstrip()}"
                    )

                category, subcategory, keyword = parts
                normalized_keyword = self.normalize_title(keyword)
                rules.append((category, subcategory, normalized_keyword))

        return rules