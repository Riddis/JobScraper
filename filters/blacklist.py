from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Pattern


@dataclass
class BlacklistRule:
    source: str | None
    pattern: Pattern[str]


def load_title_blacklist(file_path: Path) -> List[BlacklistRule]:
    """
    Load blacklist rules from a plain text file.

    Supported formats:
    - intern          -> global exact word match
    - intern*         -> global prefix match
    - *intern         -> global suffix match
    - *intern*        -> global contains match
    - resolvus: foo   -> source-specific rule
    - xelor: *java*   -> source-specific contains rule

    Notes:
    - Empty lines are ignored
    - Lines starting with # are comments
    - Matching is case-insensitive
    """
    rules: List[BlacklistRule] = []

    if not file_path.exists():
        return rules

    with file_path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()

            if not line:
                continue

            if line.startswith("#"):
                continue

            source, entry = parse_blacklist_line(line)
            regex = convert_entry_to_regex(entry)

            rules.append(
                BlacklistRule(
                    source=source.lower() if source else None,
                    pattern=re.compile(regex, re.IGNORECASE),
                )
            )

    return rules


def parse_blacklist_line(line: str) -> tuple[str | None, str]:
    """
    Parse either:
    - 'keyword'
    - 'source: keyword'
    """
    if ":" in line:
        source, entry = line.split(":", 1)
        return source.strip(), entry.strip()

    return None, line.strip()


def convert_entry_to_regex(entry: str) -> str:
    """
    Convert user-friendly wildcard syntax into regex.

    intern      -> exact word match
    intern*     -> starts with
    *intern     -> ends with
    *intern*    -> contains anywhere
    """
    starts_with_star = entry.startswith("*")
    ends_with_star = entry.endswith("*")

    word = entry.strip("*")
    word = re.escape(word)

    if starts_with_star and ends_with_star:
        return word

    if starts_with_star:
        return f"{word}\\b"

    if ends_with_star:
        return f"\\b{word}"

    return f"\\b{word}\\b"


def is_title_blacklisted(
    title: str,
    rules: Iterable[BlacklistRule],
    source: str | None = None,
) -> bool:
    """
    Check whether a title matches any global or source-specific blacklist rule.
    """
    normalized_source = source.lower() if source else None

    for rule in rules:
        if rule.source is not None and rule.source != normalized_source:
            continue

        if rule.pattern.search(title):
            return True

    return False