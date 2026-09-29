"""
Plain-text formatting of a decoded storm fix, in forecaster shorthand:

    Dolphin (2613)
    Position: 28.10N 122.66E
    Motion: NW (306º), 6.17m/s
    DT: 2.0 PT: 2.5
    MET: 2.0 D1.5/24HRS
    CI: 2.0 FT: 2.0 b.o. DT
"""

from typing import Any, Optional

from .decode import (
    CODE_TABLE_19119_BASIS,
    D_CI, D_DIRECTION, D_DT, D_INTL_NUMBER, D_LATITUDE, D_LONGITUDE,
    D_MET, D_PT, D_SPEED, D_STORM_NAME, D_T_FINAL, D_T_TYPE, D_TREND,
    Record, decode_text,
)

_COMPASS_POINTS = [
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
]


def compass(direction_degrees: Optional[float]) -> Optional[str]:
    if direction_degrees is None:
        return None
    return _COMPASS_POINTS[round(direction_degrees / 22.5) % 16]


def format_latlon(lat: Optional[float], lon: Optional[float]) -> str:
    if lat is None or lon is None:
        return "—"
    return f"{abs(lat):.2f}{'N' if lat >= 0 else 'S'} {abs(lon):.2f}{'E' if lon >= 0 else 'W'}"


def _num(value: Optional[float], decimals: int = 1) -> str:
    return "—" if value is None else f"{value:.{decimals}f}"


def format_storm_fix(storm: dict[int, Any]) -> tuple[str, str]:
    """Return (title, body) as plain text for one storm."""
    name = decode_text(storm.get(D_STORM_NAME)) or "Unnamed"
    intl_number = decode_text(storm.get(D_INTL_NUMBER))
    title = name + (f" ({intl_number})" if intl_number else "")

    direction = storm.get(D_DIRECTION)
    speed = storm.get(D_SPEED)
    motion = "Motion: —"
    if direction is not None and speed is not None:
        motion = f"Motion: {compass(direction) or '?'} ({direction:.0f}º), {speed:.2f}m/s"

    t_type = storm.get(D_T_TYPE)
    basis = CODE_TABLE_19119_BASIS.get(t_type, "?") if t_type is not None else "—"

    body = "\n".join([
        f"Position: {format_latlon(storm.get(D_LATITUDE), storm.get(D_LONGITUDE))}",
        motion,
        f"DT: {_num(storm.get(D_DT))} PT: {_num(storm.get(D_PT))}",
        f"MET: {_num(storm.get(D_MET))} D{_num(storm.get(D_TREND))}/24HRS",
        f"CI: {_num(storm.get(D_CI))} FT: {_num(storm.get(D_T_FINAL))} b.o. {basis}",
    ])
    return title, body


def format_raw(records: list[Record]) -> str:
    """Full dump of every decoded record in a subset -- useful for debugging."""
    if not records:
        return "(empty subset)"
    return "\n".join(f"{id_:06d} {name}: {value}" for id_, name, value in records)
