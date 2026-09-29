"""
Command-line entry point.

    python -m jma_sarep                 # fetch + print the latest fixes
    python -m jma_sarep --raw           # also dump every decoded field
    python -m jma_sarep --file x.bufr   # decode a local file (no network)
"""

import argparse
import asyncio
import sys

import aiohttp

from .decode import decode_bufr, group_storms, storm_identity
from .fetch import DvorakFetchError, fetch_latest_fixes
from .format import format_raw, format_storm_fix


def print_fixes(files: list[tuple[str, bytes]], raw: bool) -> int:
    seen = set()
    count = 0
    for source, data in files:
        try:
            subsets = decode_bufr(data)
        except Exception as e:  # malformed/unsupported file -- skip, keep going
            print(f"[skip] could not decode {source}: {e}", file=sys.stderr)
            continue
        for records in subsets:
            if raw:
                print(f"--- raw: {source} ---\n{format_raw(records)}\n")
            _header, storms = group_storms(records)
            for storm in storms:
                key = storm_identity(storm)
                if key in seen:
                    continue  # same storm repeated across files (e.g. amended bulletin)
                seen.add(key)
                title, body = format_storm_fix(storm)
                print(f"{title}\n{body}\n")
                count += 1
    if count == 0:
        print("No active storms in the latest SAREP bulletin.")
    return count


async def _fetch() -> list[tuple[str, bytes]]:
    async with aiohttp.ClientSession() as session:
        return await fetch_latest_fixes(session)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch/decode JMA SAREP Dvorak fixes (BUFR).")
    parser.add_argument("--file", help="decode a local BUFR file instead of fetching")
    parser.add_argument("--raw", action="store_true", help="dump every decoded field")
    args = parser.parse_args()

    if args.file:
        with open(args.file, "rb") as f:
            files = [(args.file, f.read())]
    else:
        try:
            files = asyncio.run(_fetch())
        except DvorakFetchError as e:
            sys.exit(f"Fetch failed: {e}")

    print_fixes(files, args.raw)


if __name__ == "__main__":
    main()
