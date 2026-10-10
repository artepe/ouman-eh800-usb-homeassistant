"""Single source of truth for EH-800 USB controller properties.

Raw limits retain the tested legacy YAML integration's values. Only IDs
56 (P), 57 (I), and 58 (D) are removed from writable controls.
A property being listed here is NOT a guarantee that the physical controller
will accept or apply a change. Always verify the physical controller.
"""
from __future__ import annotations

import re
from pathlib import Path

# id, stable object id, label, min raw, max raw, step raw, scale, initial raw
PROPS = [
    (54, "l1_supply_minimum", "L1 Supply minimum", 50, 950, 10, 10, 140),
    (55, "l1_supply_maximum", "L1 Supply maximum", 50, 950, 10, 10, 890),
    (56, "l1_p_band", "L1 P band", 2, 600, 1, 1, 250),
    (57, "l1_i_time", "L1 I time", 5, 300, 1, 1, 50),
    (58, "l1_d_time", "L1 D time", 0, 100, 1, 1, 0),
    (67, "l1_curve_minus_20c", "L1 Curve -20C", 0, 1000, 10, 10, 900),
    (69, "l1_curve_minus_10c", "L1 Curve -10C", 0, 1000, 10, 10, 700),
    (71, "l1_curve_0c", "L1 Curve 0C", 0, 1000, 10, 10, 550),
    (73, "l1_curve_plus_10c", "L1 Curve +10C", 0, 1000, 10, 10, 490),
    (75, "l1_curve_plus_20c", "L1 Curve +20C", 0, 1000, 10, 10, 180),
    (91, "l1_summer_shutoff", "L1 Summer shutoff", 5, 95, 1, 1, 24),
    (92, "l1_manual_valve_position", "L1 Manual valve position", 0, 100, 1, 1, 81),
    (126, "l1_max_supply_change_rate", "L1 Max supply change rate", 1, 50, 1, 1, 40),
    (127, "l1_supply_setpoint", "L1 Supply setpoint", 0, 950, 10, 10, 150),
    (134, "l1_fine_adjustment", "L1 Fine adjustment", -40, 40, 1, 10, 0),
]


PID_IDS = frozenset({56, 57, 58})
PID_PROPS = tuple(p for p in PROPS if p[0] in PID_IDS)
WRITABLE_PROPS = tuple(p for p in PROPS if p[0] not in PID_IDS)
WRITABLE_RAW_RANGES = {p[0]: (p[3], p[4]) for p in WRITABLE_PROPS}

# Previously captured 269-property backups use this form. Never issue
# SET PROPERTY to read values. These are snapshots, NOT live values.
_SNAPSHOT_RE = re.compile(
    r"PROPERTY\(\s*(\d+)\s*\):'[^']+'\([^)]*\)\s*=\s*(-?\d+)",
    re.IGNORECASE,
)


def decode_signed_raw(raw: int) -> int:
    """Interpret the controller's unsigned 16-bit negative representation."""
    return raw - 65536 if 32768 <= raw <= 65535 else raw


def load_property_snapshot(path: str | Path) -> dict[int, int]:
    """Read an existing offline snapshot without touching the controller."""
    source = Path(path)
    if not source.is_file():
        return {}
    # Size cap prevents accidentally parsing huge/unrelated files.
    if source.stat().st_size > 1_000_000:
        raise ValueError("Ouman property snapshot exceeds 1 MB")
    text = source.read_text(encoding="latin1")
    return {
        int(match.group(1)): decode_signed_raw(int(match.group(2)))
        for match in _SNAPSHOT_RE.finditer(text)
    }
