# jma-sarep-dvorak

Fetch and decode **JMA RSMC Tokyo SAREP** bulletins — the Dvorak satellite
intensity fixes JMA issues for active West Pacific tropical cyclones — straight
from JMA's WIS2 node, in BUFR format.

Pure Python (no compiled BUFR libraries), so it runs on Windows, macOS and Linux.

```
Dolphin (2613)
Position: 28.10N 122.66E
Motion: NW (306º), 6.17m/s
DT: 2.0 PT: 2.5
MET: 2.0 D1.5/24HRS
CI: 2.0 FT: 2.0 b.o. DT
```

## Install

```bash
pip install -r requirements.txt
```

## Usage

```bash
python -m jma_sarep                  # fetch + print the latest fixes
python -m jma_sarep --raw            # also dump every decoded BUFR field
python -m jma_sarep --file fix.bufr  # decode a local file (no network)
```

As a library:

```python
import asyncio, aiohttp
from jma_sarep import fetch_latest_fixes, decode_storms, format_storm_fix

async def main():
    async with aiohttp.ClientSession() as session:
        for url, raw in await fetch_latest_fixes(session):
            for header, storm in decode_storms(raw):
                title, body = format_storm_fix(storm)
                print(title, body, sep="\n")

asyncio.run(main())
```

## How it works

| Module | Role |
|---|---|
| `fetch.py` | Walks `SAREP/<YYYYMMDD>/<HHMMSS>/` on the WIS2 node and downloads the newest 00/06/12/18Z files (interim 03/09/15/21Z folders are skipped — they aren't full Dvorak cycles). |
| `decode.py` | Decodes BUFR with `pybufrkit` and splits each subset into one record per storm. |
| `format.py` | Renders a storm as plain-text forecaster shorthand. |

**Multi-storm subsets.** JMA packs every active storm into a *single* BUFR
subset via delayed replication, repeating the same descriptors once per storm.
Decoding into a `{name: value}` dict silently overwrites storm 1 with storm 2,
so records are kept as an ordered list and split on descriptor `001027`
(WMO long storm name).

Descriptor sequence (BUFR edition 4, category 12), confirmed with the DWD BUFR
Viewer against real files:

```
301005 301011 301012 001007 025150 122000 031001
[per storm] 001027 019150 019106 008005 005002 006002 008005
            019107 019005 019006 019108 019109 019110 019111
            019112 019113 019114 019115 019116 019117 019118 019119
```

## Known limitation

The numeric mapping for WMO Code Table **0-19-119** (which of DT/PT/MET the
final T-number is based on — the "b.o." field) is unverified: every real sample
so far reported it as missing. If you capture a file with a real value, run
`--raw` and open an issue.

## Tests

Offline — no connection to JMA needed:

```bash
pip install pytest
pytest
```

## Data source

Bulletins are published by the Japan Meteorological Agency (RSMC Tokyo –
Typhoon Center). This project is not affiliated with JMA. Dvorak fixes are
for information only — use official warnings for any safety decisions.
