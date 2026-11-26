"""FDI (ISO 3950) tooth helpers used by every index.

DentIndices identifies teeth by their two-digit FDI number (11-48 permanent, 51-85 primary).
Use ToothNotation (https://pypi.org/project/toothnotation/) to convert from Universal or Palmer.
"""
from __future__ import annotations

import math
import numbers
from typing import Iterable

from ._errors import InputError

PERMANENT = tuple(q * 10 + p for q in (1, 2, 3, 4) for p in range(1, 9))
PRIMARY = tuple(q * 10 + p for q in (5, 6, 7, 8) for p in range(1, 6))
THIRD_MOLARS = (18, 28, 38, 48)
SECOND_MOLARS = (17, 27, 37, 47)

# Arch order (patient's right to left) used for positional adjacency.
UPPER_ARCH = (18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28)
LOWER_ARCH = (48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38)

# WHO / CPI sextants (S1 upper right ... S6 lower right) for the permanent dentition.
SEXTANTS = {
    "S1": (18, 17, 16, 15, 14),
    "S2": (13, 12, 11, 21, 22, 23),
    "S3": (24, 25, 26, 27, 28),
    "S4": (38, 37, 36, 35, 34),
    "S5": (33, 32, 31, 41, 42, 43),
    "S6": (44, 45, 46, 47, 48),
}
SEXTANT_ORDER = ("S1", "S2", "S3", "S4", "S5", "S6")
SEXTANT_NAMES = {"S1": "upper right", "S2": "upper anterior", "S3": "upper left",
                 "S4": "lower left", "S5": "lower anterior", "S6": "lower right"}
# Short anatomical aliases accepted wherever a sextant is named.
SEXTANT_ALIASES = {"UR": "S1", "UA": "S2", "UL": "S3", "LL": "S4", "LA": "S5", "LR": "S6",
                   "1": "S1", "2": "S2", "3": "S3", "4": "S4", "5": "S5", "6": "S6"}


class ToothError(InputError):
    """An invalid FDI tooth number or a tooth used where it does not belong."""


def parse_tooth(tooth: object) -> int:
    """Accept 16, "16" or "1.6" and return the FDI number as an int; raise ToothError otherwise."""
    if isinstance(tooth, bool):
        raise ToothError(f"Not a tooth number: {tooth!r}")
    if isinstance(tooth, numbers.Integral):
        n = int(tooth)
    elif isinstance(tooth, numbers.Real) and math.isfinite(float(tooth)) and float(tooth).is_integer():
        n = int(float(tooth))  # 16.0 from spreadsheets and data frames
    elif isinstance(tooth, str):
        s = tooth.strip().replace(".", "")
        if s.lower().startswith("t"):
            s = s[1:]
        if not (s.isascii() and s.isdigit()):
            raise ToothError(f"Not an FDI tooth number: {tooth!r} (use two digits such as 16 or 55)")
        n = int(s)
    else:
        raise ToothError(f"Not a tooth number: {tooth!r}")
    if n not in PERMANENT and n not in PRIMARY:
        raise ToothError(f"{tooth!r} is not a valid FDI tooth (11-48 permanent, 51-85 primary)")
    return n


def is_permanent(t: int) -> bool:
    return t in PERMANENT


def is_primary(t: int) -> bool:
    return t in PRIMARY


def position(t: int) -> int:
    return t % 10


def quadrant(t: int) -> int:
    return t // 10


def is_upper(t: int) -> bool:
    return quadrant(t) in (1, 2, 5, 6)


def is_anterior(t: int) -> bool:
    """Incisors and canines (positions 1-3) in either dentition."""
    return position(t) <= 3


def is_third_molar(t: int) -> bool:
    return t in THIRD_MOLARS


def primary_at_position(t: int) -> int | None:
    """The primary tooth that occupies the same space as permanent tooth ``t`` (11 -> 51, 15 -> 55)."""
    if t in PERMANENT and position(t) <= 5:
        return (quadrant(t) + 4) * 10 + position(t)
    return None


def permanent_at_position(t: int) -> int:
    """The permanent successor of primary tooth ``t`` (55 -> 15)."""
    return (quadrant(t) - 4) * 10 + position(t)


def sextant_of(t: int) -> str:
    """WHO sextant (S1-S6) of a permanent tooth."""
    for key, teeth in SEXTANTS.items():
        if t in teeth:
            return key
    raise ToothError(f"Tooth {t} is not a permanent tooth")


def parse_sextant(key: object) -> str:
    k = str(key).strip().upper()
    if k in SEXTANTS:
        return k
    if k in SEXTANT_ALIASES:
        return SEXTANT_ALIASES[k]
    raise InputError(f"Unknown sextant {key!r}; use S1-S6 or UR, UA, UL, LL, LA, LR")


def adjacent(a: int, b: int) -> bool:
    """True if two permanent teeth are neighbours by arch position (11 and 21 are adjacent)."""
    for arch in (UPPER_ARCH, LOWER_ARCH):
        if a in arch and b in arch:
            return abs(arch.index(a) - arch.index(b)) == 1
    return False


def has_non_adjacent_pair(teeth: Iterable[int]) -> bool:
    """True if the set contains at least two teeth that are not neighbours of each other."""
    ts = sorted(set(teeth))
    for i in range(len(ts)):
        for j in range(i + 1, len(ts)):
            if not adjacent(ts[i], ts[j]):
                return True
    return False


def antagonist(t: int) -> int:
    """The anatomically opposing permanent tooth (16 <-> 46, 21 <-> 31)."""
    q = quadrant(t)
    opp = {1: 4, 4: 1, 2: 3, 3: 2}[q]
    return opp * 10 + position(t)


def opposing_pairs(present: Iterable[int]) -> int:
    """Number of pairs of opposing natural teeth (third molars excluded), as defined in ACES 2024."""
    s = {t for t in present if t in PERMANENT and not is_third_molar(t)}
    return sum(1 for t in s if is_upper(t) and antagonist(t) in s)
