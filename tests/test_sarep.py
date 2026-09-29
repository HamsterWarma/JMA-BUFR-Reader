"""Offline tests -- no network access to JMA required."""

import asyncio

import aiohttp
from aiohttp import web

from jma_sarep import fetch
from jma_sarep.decode import (
    D_CI, D_DIRECTION, D_DT, D_INTL_NUMBER, D_LATITUDE, D_LONGITUDE, D_MET,
    D_PT, D_SATELLITE_ID, D_SPEED, D_STORM_NAME, D_T_FINAL, D_TREND,
    group_storms, storm_identity,
)
from jma_sarep.format import compass, format_storm_fix


def _listing(*names):
    rows = "".join(f'<a href="{n}">{n}</a>' for n in names)
    return f'<a href="?C=N;O=D">Name</a><a href="/d/o/">Parent Directory</a>{rows}'


def test_parse_dir_listing_skips_sort_and_parent_links():
    html = _listing("20260809/", "20260810/")
    entries = fetch.parse_dir_listing(html, "https://x/SAREP/")
    assert entries == ["https://x/SAREP/20260809/", "https://x/SAREP/20260810/"]


def test_synoptic_filter():
    assert fetch.is_synoptic_hour_dir("https://x/20260809/060000/")
    assert not fetch.is_synoptic_hour_dir("https://x/20260809/030000/")
    assert not fetch.is_synoptic_hour_dir("https://x/20260809/061500/")


def test_group_storms_keeps_every_storm_in_one_subset():
    records = [
        (D_SATELLITE_ID, "SATELLITE", 173),
        (D_STORM_NAME, "NAME", b"Dolphin   "), (D_INTL_NUMBER, "NUM", b"2613"), (D_CI, "CI", 2.0),
        (D_STORM_NAME, "NAME", b"Chan-hom  "), (D_INTL_NUMBER, "NUM", b"2615"), (D_CI, "CI", 3.5),
    ]
    header, storms = group_storms(records)
    assert header == {D_SATELLITE_ID: 173}
    assert len(storms) == 2
    assert storm_identity(storms[0]) == ("Dolphin", "2613")
    assert storm_identity(storms[1]) == ("Chan-hom", "2615")
    assert storms[0][D_CI] == 2.0 and storms[1][D_CI] == 3.5  # no overwriting


def test_format_matches_forecaster_shorthand():
    storm = {
        D_STORM_NAME: b"Dolphin   ", D_INTL_NUMBER: b"2613",
        D_LATITUDE: 28.10, D_LONGITUDE: 122.66, D_DIRECTION: 306, D_SPEED: 6.17,
        D_DT: 2.0, D_PT: 2.5, D_MET: 2.0, D_TREND: 1.5, D_CI: 2.0, D_T_FINAL: 2.0,
    }
    title, body = format_storm_fix(storm)
    assert title == "Dolphin (2613)"
    assert body.splitlines() == [
        "Position: 28.10N 122.66E",
        "Motion: NW (306º), 6.17m/s",
        "DT: 2.0 PT: 2.5",
        "MET: 2.0 D1.5/24HRS",
        "CI: 2.0 FT: 2.0 b.o. —",
    ]
    assert compass(275) == "W"


def test_find_latest_files_walks_tree_and_skips_interim_hours():
    """Newest date has only an interim 03Z folder -> must fall back to 18Z of the day before."""
    tree = {
        "/SAREP/": _listing("20260809/", "20260810/"),
        "/SAREP/20260810/": _listing("030000/"),
        "/SAREP/20260809/": _listing("120000/", "180000/", "210000/"),
        "/SAREP/20260809/180000/": _listing("A_IUCC10RJTD.bin", "B_IUCC10RJTD.bin"),
    }

    async def handler(request):
        if request.path in tree:
            return web.Response(text=tree[request.path], content_type="text/html")
        return web.Response(status=404)

    async def run():
        app = web.Application()
        app.router.add_route("GET", "/{tail:.*}", handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 8791)
        await site.start()
        try:
            async with aiohttp.ClientSession() as session:
                return await fetch.find_latest_files(session, "http://127.0.0.1:8791/SAREP/")
        finally:
            await runner.cleanup()

    files = asyncio.run(run())
    assert [f.rsplit("/", 2)[-2] for f in files] == ["180000", "180000"]
    assert files[0].endswith("A_IUCC10RJTD.bin")
