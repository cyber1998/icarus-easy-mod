"""Browse the ProjectDaedalus community mod database (https://www.projectdaedalus.app)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.projectdaedalus.app"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0 Safari/537.36"
)
REQUEST_TIMEOUT = 25


class CatalogError(Exception):
    """Raised when the mod database cannot be reached or parsed."""


@dataclass(frozen=True)
class ModEntry:
    name: str
    author: str
    version: str
    updated: str
    week: str
    description: str
    download_type: str
    download_url: Optional[str]
    filename: Optional[str]
    detail_url: str


@dataclass
class CatalogResult:
    mods: list[ModEntry]
    total_mods: int
    page: int
    total_pages: int
    authors: list[tuple[str, str]]


def fetch_catalog(
    query: str = "",
    download_type: str = "pak",
    author: str = "",
    page: int = 1,
) -> CatalogResult:
    """Fetch the mod list from ProjectDaedalus.

    With a query or a type filter the site returns all matches unpaginated.
    Author pages list everything by that author; extra filters are applied locally.
    """
    try:
        if author:
            response = requests.get(
                f"{BASE_URL}/mods/{author}",
                headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
                timeout=REQUEST_TIMEOUT,
            )
        else:
            params: dict[str, object] = {}
            if query:
                params["query"] = query
            if download_type and download_type != "all":
                params["type"] = download_type
            if page and page > 1:
                params["page"] = page
            response = requests.get(
                BASE_URL + "/",
                params=params,
                headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
                timeout=REQUEST_TIMEOUT,
            )
    except requests.RequestException as exc:
        raise CatalogError(f"Could not reach ProjectDaedalus: {exc}") from exc

    if response.status_code == 403:
        raise CatalogError(
            "ProjectDaedalus temporarily blocked this request. Wait a moment and try again."
        )
    if response.status_code != 200:
        raise CatalogError(f"ProjectDaedalus returned HTTP {response.status_code}.")

    result = parse_catalog(response.text)
    if author:
        result.mods = _apply_local_filters(result.mods, query, download_type)
        result.total_mods = len(result.mods)
        result.total_pages = 1
        result.page = 1
    return result


def _apply_local_filters(mods: list[ModEntry], query: str, download_type: str) -> list[ModEntry]:
    filtered = mods
    if download_type and download_type != "all":
        filtered = [m for m in filtered if m.download_type.lower().startswith(download_type.lower())]
    if query:
        needle = query.lower()
        filtered = [
            m
            for m in filtered
            if needle in m.name.lower() or needle in m.description.lower() or needle in m.author.lower()
        ]
    return filtered


def parse_catalog(html: str) -> CatalogResult:
    soup = BeautifulSoup(html, "html.parser")
    frame = soup.find("turbo-frame", id="mods") or soup

    mods: list[ModEntry] = []
    for row in frame.select('tr[id^="mod_"]'):
        cells = row.find_all("td", recursive=False)

        def cell(index: int) -> str:
            return cells[index].get_text(" ", strip=True) if len(cells) > index else ""

        button = row.find("button", attrs={"data-mods-url-param": True})
        detail_path = row.get("data-mods-path-param") or ""
        mods.append(
            ModEntry(
                name=cell(0),
                author=cell(2),
                version=cell(3),
                updated=cell(4),
                week=cell(5),
                description=cell(6),
                download_type=(button.get_text(strip=True) if button else ""),
                download_url=(button.get("data-mods-url-param") if button else None),
                filename=(button.get("data-mods-file-name-param") if button else None),
                detail_url=f"{BASE_URL}{detail_path}" if detail_path else "",
            )
        )

    text = frame.get_text(" ", strip=True)
    match = re.search(r"(\d+)\s+mods\s*\(page\s*(\d+)\s*of\s*(\d+)\)", text)
    if match:
        total_mods, page_no, total_pages = int(match.group(1)), int(match.group(2)), int(match.group(3))
    else:
        total_mods, page_no, total_pages = len(mods), 1, 1

    return CatalogResult(
        mods=mods,
        total_mods=total_mods,
        page=page_no,
        total_pages=total_pages,
        authors=parse_authors(soup),
    )


def parse_authors(soup: BeautifulSoup) -> list[tuple[str, str]]:
    for select in soup.find_all("select"):
        if select.find("option", string=re.compile("Filter By Author")):
            authors: list[tuple[str, str]] = []
            for option in select.find_all("option"):
                value = (option.get("value") or "").strip()
                label = option.get_text(strip=True)
                if value and label:
                    authors.append((value, label))
            return authors
    return []


def fetch_size(url: str, timeout: float = 15) -> Optional[int]:
    """Content length of a mod download, or None when it cannot be determined."""
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.head(url, headers=headers, timeout=timeout, allow_redirects=True)
        length = response.headers.get("Content-Length")
        if response.status_code == 200 and length:
            return int(length)
        with requests.get(url, headers=headers, stream=True, timeout=timeout, allow_redirects=True) as response:
            length = response.headers.get("Content-Length")
            if response.status_code == 200 and length:
                return int(length)
    except (requests.RequestException, ValueError):
        return None
    return None
