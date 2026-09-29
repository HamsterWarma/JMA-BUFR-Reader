"""
Decode JMA RSMC Tokyo SAREP BUFR messages with pybufrkit (pure Python,
no compiled dependencies).

Real descriptor sequence for RJTD SAREP (BUFR edition 4, category 12),
confirmed with the DWD BUFR Viewer against real files:

    301005 301011 301012 001007 025150 122000 031001
    [repeated once per storm via delayed replication]:
      001027 019150 019106 008005 005002 006002 008005
      019107 019005 019006 019108 019109 019110 019111
      019112 019113 019114 019115 019116 019117 019118 019119

Important: a single BUFR *subset* can carry MULTIPLE storms. Collapsing
a subset into a {name: value} dict would silently overwrite storm 1's
fields with storm 2's, so decode_bufr() keeps an ordered record list and
group_storms() splits it on descriptor 001027 (WMO long storm name).
"""

from typing import Any, Optional

from pybufrkit.decoder import Decoder

# Descriptor IDs
D_SATELLITE_ID = 1007
D_ANALYSIS_METHOD = 25150
D_STORM_NAME = 1027          # marks the start of each storm's block
D_INTL_NUMBER = 19150
D_CYCLONE_ID = 19106
D_LATITUDE = 5002
D_LONGITUDE = 6002
D_DIRECTION = 19005
D_SPEED = 19006
D_POSITION_ACCURACY = 19108
D_CLOUD_DIAMETER = 19109
D_24H_CHANGE = 19110
D_CI = 19111                 # Current Intensity number
D_DT = 19112                 # Data T-number
D_DT_PATTERN = 19113
D_MET = 19114                # Model Expected T-number
D_TREND = 19115              # 24h trend
D_PT = 19116                 # Pattern T-number
D_PT_PATTERN = 19117
D_T_FINAL = 19118            # Final T-number (FT)
D_T_TYPE = 19119             # what the final T-number is based on

# WMO Common Code Table 0-19-119 (basis of the final T-number).
# NOTE: unverified -- every real sample so far reported this field as
# missing, so this mapping is a best-effort guess. PRs with a real
# non-missing value are welcome.
CODE_TABLE_19119_BASIS = {0: "DT", 1: "DT", 2: "PT", 3: "MET", 4: "avg"}

Record = tuple[int, str, Any]

_decoder = Decoder()


def decode_bufr(raw: bytes) -> list[list[Record]]:
    """
    Decode a raw BUFR message into a list of subsets, each an ORDERED list
    of (descriptor_id, descriptor_name, value) records. Deliberately not a
    dict -- see module docstring.
    """
    message = _decoder.process(raw)
    template_data = message.template_data.value

    subsets: list[list[Record]] = []
    for i in range(template_data.n_subsets):
        descriptors = template_data.decoded_descriptors_all_subsets[i]
        values = template_data.decoded_values_all_subsets[i]
        subsets.append([
            (d.id, getattr(d, "name", None) or str(d), v)
            for d, v in zip(descriptors, values)
        ])
    return subsets


def group_storms(records: list[Record]) -> tuple[dict[int, Any], list[dict[int, Any]]]:
    """
    Split one subset into (header, storms):
      header -- bulletin-level fields before the first storm
      storms -- one {descriptor_id: value} dict per storm
    """
    header: dict[int, Any] = {}
    storms: list[dict[int, Any]] = []
    current: Optional[dict[int, Any]] = None

    for descriptor_id, _name, value in records:
        if descriptor_id == D_STORM_NAME:
            current = {}
            storms.append(current)
        if current is None:
            header.setdefault(descriptor_id, value)
        else:
            current[descriptor_id] = value
    return header, storms


def decode_text(value: Any) -> Optional[str]:
    """CCITT IA5 fields come back as padded bytes -- decode and strip them."""
    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.decode("ascii", errors="replace")
    return value.strip() if isinstance(value, str) else value


def storm_identity(storm: dict[int, Any]) -> tuple[Optional[str], Optional[str]]:
    """Stable (name, international_number) key, for de-duplicating storms across files."""
    return decode_text(storm.get(D_STORM_NAME)), decode_text(storm.get(D_INTL_NUMBER))


def decode_storms(raw: bytes) -> list[tuple[dict[int, Any], dict[int, Any]]]:
    """
    Convenience: decode one BUFR file straight into [(header, storm), ...],
    one entry per storm across every subset.
    """
    result = []
    for records in decode_bufr(raw):
        header, storms = group_storms(records)
        result.extend((header, storm) for storm in storms)
    return result
