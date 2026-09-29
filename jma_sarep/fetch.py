"""
Fetch the latest JMA SAREP (Dvorak fix) BUFR files from JMA's WIS2 node.

Directory layout (confirmed against the live listing):

    SAREP/<YYYYMMDD>/<HHMMSS>/<BUFR files>

Date folders sit directly under BASE_URL; inside each is one folder per
3-hourly cycle (000000, 030000, 060000, ...). Only the four main synoptic
hours (00/06/12/18Z) carry full Dvorak analyses, so the interim
03/09/15/21Z folders are skipped.
"""

import re
from urllib.parse import urljoin

import aiohttp

BASE_URL = "https://www.wis-jma.go.jp/d/o/RJTD/BUFR/Satellite(Himawari)/SAREP/"

SYNOPTIC_HOURS_UTC = ("00", "06", "12", "18")


class DvorakFetchError(Exception):
    """Raised when the SAREP listing or a BUFR file can't be retrieved."""


def parse_dir_listing(html: str, base_url: str) -> list[str]:
    """
    Parse an Apache-style autoindex page into absolute entry URLs.
    Skips the column-sort header links (?C=...) and the "Parent Directory"
    row, which a naive href scrape would otherwise treat as content.
    """
    rows = re.findall(r'<a href="([^"]+)"[^>]*>([^<]*)</a>', html)
    entries = []
    for href, text in rows:
        if href.startswith("?"):
            continue
        if text.strip() == "Parent Directory":
            continue
        entries.append(urljoin(base_url, href))
    return entries


def is_synoptic_hour_dir(href: str) -> bool:
    """True if the final path segment is exactly 000000/, 060000/, 120000/ or 180000/."""
    basename = href.rstrip("/").rsplit("/", 1)[-1]
    return len(basename) == 6 and basename[:2] in SYNOPTIC_HOURS_UTC and basename[2:] == "0000"


async def _list_dir_entries(session: aiohttp.ClientSession, url: str) -> list[str]:
    async with session.get(url) as resp:
        if resp.status != 200:
            raise DvorakFetchError(f"{url} returned HTTP {resp.status}")
        html = await resp.text()
    return parse_dir_listing(html, url)


async def find_latest_files(session: aiohttp.ClientSession, base_url: str = BASE_URL) -> list[str]:
    """
    Return the URLs of every file in the most recent 00/06/12/18Z folder.
    Walks date folders newest-first; within a date, tries only the synoptic
    folders, newest-first. Falls back to older folders if the newest one
    doesn't exist yet or is empty (e.g. just after 00Z).
    """
    date_entries = await _list_dir_entries(session, base_url)
    date_dirs = sorted({e for e in date_entries if e.endswith("/")}, reverse=True)
    if not date_dirs:
        raise DvorakFetchError(f"No date folders found at {base_url}")

    tried_any = False
    for date_url in date_dirs:
        try:
            time_entries = await _list_dir_entries(session, date_url)
        except DvorakFetchError:
            continue

        synoptic_dirs = sorted(
            {e for e in time_entries if e.endswith("/") and is_synoptic_hour_dir(e)},
            reverse=True,
        )
        for time_url in synoptic_dirs:
            tried_any = True
            entries = await _list_dir_entries(session, time_url)
            files = sorted({e for e in entries if not e.endswith("/")})
            if files:
                return files

    if not tried_any:
        raise DvorakFetchError("No 00/06/12/18Z folders found in any recent date folder")
    raise DvorakFetchError("Found 00/06/12/18Z folders, but all were empty")


async def download_bufr(session: aiohttp.ClientSession, url: str) -> bytes:
    async with session.get(url) as resp:
        if resp.status != 200:
            raise DvorakFetchError(f"Download of {url} returned HTTP {resp.status}")
        return await resp.read()


async def fetch_latest_fixes(session: aiohttp.ClientSession, base_url: str = BASE_URL) -> list[tuple[str, bytes]]:
    """Download every file in the latest synoptic folder. Returns [(url, raw_bytes), ...]."""
    files = await find_latest_files(session, base_url)
    return [(url, await download_bufr(session, url)) for url in files]
