"""Erosive tooth wear: Basic Erosive Wear Examination (BEWE; Bartlett, Ganss & Lussi 2008)."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ._common import InputError, int_score, is_blank, items, norm_code, seq, teeth_list, teeth_set
from ._registry import band_entry, codes, require_verified
from ._result import IndexResult
from ._teeth import SEXTANT_ORDER, parse_sextant, parse_tooth, quadrant

__all__ = ["bewe", "bewe_from_teeth"]

_SURF = {"B": "B", "F": "B", "BUCCAL": "B", "FACIAL": "B", "LABIAL": "B",
         "O": "O", "I": "O", "OCCLUSAL": "O", "INCISAL": "O",
         "L": "L", "P": "L", "LINGUAL": "L", "PALATAL": "L", "ORAL": "L"}


def bewe(sextants: Any) -> IndexResult:
    """BEWE from the highest score (0-3) in each of the six sextants (17-14, 13-23, 24-27, 37-34,
    33-43, 44-47), given in that order or as a mapping (S1-S6 or UR, UA, UL, LL, LA, LR). Use None
    or "-" for a sextant that cannot be scored. The cumulative score (0-18) sets the risk level and
    the management guidance of Bartlett et al. (2008)."""
    require_verified("bewe")
    tab = codes("bewe")
    if isinstance(sextants, Mapping):
        vals: dict[str, Any] = {}
        for k, v in sextants.items():
            s = parse_sextant(k)
            if s in vals:
                raise InputError(f"BEWE: sextant {s} given twice")
            vals[s] = v
        vals = {s: vals.get(s) for s in SEXTANT_ORDER}
    else:
        lst = seq(sextants, "BEWE sextants")
        if len(lst) != 6:
            raise InputError("BEWE: give six sextant scores (17-14, 13-23, 24-27, 37-34, 33-43, 44-47)")
        vals = dict(zip(SEXTANT_ORDER, lst))
    scores: dict[str, int | None] = {}
    for s, v in vals.items():
        if is_blank(v) or norm_code(v) in ("X", "-"):
            scores[s] = None
        else:
            scores[s] = int_score(v, 0, 3, f"BEWE sextant {s}")
    scored = {s: v for s, v in scores.items() if v is not None}
    if not scored:
        raise InputError("BEWE: no sextant was scored")
    total = sum(scored.values())
    level = band_entry(total, tab["risk_levels"])
    warnings = [tab["cutoff_caveat"]]
    if len(scored) < 6:
        warnings.append(f"Only {len(scored)} of 6 sextants were scored; the risk levels assume all six.")
    trace = ["Sextant scores: " + ", ".join(f"{s} {scores[s] if scores[s] is not None else '-'}"
                                            for s in SEXTANT_ORDER) + ".",
             f"Cumulative BEWE = {total} -> risk level {level['label']}."]
    comps = {"BEWE": total, "risk_level": level["label"], "sextants": scores, "sextants_scored": len(scored),
             "max_sextant_score": max(scored.values()), "repeat": level["repeat"]}
    guidance = f"{level['management']} {level['repeat']}"
    return IndexResult("bewe", total, comps, level["label"], guidance, tuple(trace), tuple(warnings),
                       ("bartlett2008", "aranguiz2020"))


def bewe_from_teeth(scores: Any, teeth_present: Any = None) -> IndexResult:
    """BEWE from tooth-surface scores. ``scores`` maps each tooth to ``{surface: score}`` with surfaces
    B (buccal/facial), O (occlusal/incisal) and L (lingual/palatal), or to one score (the tooth's
    highest). Use None for a surface that cannot be scored (a restoration covering more than half of it).

    Following Aránguiz et al. (2020): third molars count only when they replace a missing second
    molar, and a single tooth left in a sextant is added to the adjacent sextant (posterior -> the
    anterior sextant of the same arch; anterior -> the posterior sextant on the tooth's side).
    """
    require_verified("bewe")
    tab = codes("bewe")
    tooth_max: dict[int, int] = {}
    seen: set[int] = set()
    for k, v in items(scores):
        t = parse_tooth(k)
        if t in seen:
            raise InputError(f"Tooth {t} appears more than once")
        seen.add(t)
        if t > 48:
            raise InputError(f"BEWE is scored on permanent teeth here; {t} is a primary tooth")
        if isinstance(v, Mapping):
            vals = []
            for sk, sv in v.items():
                key = str(sk).strip().upper()
                if key not in _SURF:
                    raise InputError(f"Tooth {t}: unknown surface {sk!r} (use B, O, L)")
                if not is_blank(sv):
                    vals.append(int_score(sv, 0, 3, f"BEWE tooth {t} {_SURF[key]}"))
            if vals:
                tooth_max[t] = max(vals)
        elif not is_blank(v):
            tooth_max[t] = int_score(v, 0, 3, f"BEWE tooth {t}")
    if teeth_present is not None:
        present = teeth_set(teeth_present)
    else:
        present = set(seen)  # every tooth listed, scored or not (None = present but unscorable)
    trace: list[str] = []
    members: dict[str, list[int]] = {}
    third = {"S1": (18, 17), "S3": (28, 27), "S4": (38, 37), "S6": (48, 47)}
    for s, teeth in tab["sextants"].items():
        ts = [t for t in teeth if t in tooth_max]
        if s in third:
            m3, m2 = third[s]
            if m3 in tooth_max and m2 not in present:
                ts.append(m3)
                trace.append(f"{s}: third molar {m3} scored because it replaces the missing second molar {m2}.")
        members[s] = ts
    # teeth present per sextant (scored or not) decide the single-tooth rule
    in_sextant: dict[str, list[int]] = {}
    for s, teeth in tab["sextants"].items():
        ps = [t for t in teeth if t in present]
        if s in third and third[s][0] in present and third[s][1] not in present:
            ps.append(third[s][0])
        in_sextant[s] = ps
    ignored3 = [t for t in (18, 28, 38, 48) if t in tooth_max and not any(t in m for m in members.values())]
    if ignored3:
        trace.append(f"Third molars not scored (second molar present): {teeth_list(ignored3)}.")
    # single tooth in a sextant -> adjacent sextant
    target = {"S1": "S2", "S3": "S2", "S4": "S5", "S6": "S5"}
    for s in SEXTANT_ORDER:
        if len(in_sextant[s]) == 1 and in_sextant[s][0] in members[s]:
            t = in_sextant[s][0]
            dest = target[s] if s in target else {1: "S1", 2: "S3", 3: "S4", 4: "S6"}[quadrant(t)]
            if len(in_sextant[dest]) >= 2:
                members[dest] = members[dest] + [t]
                members[s] = []
                trace.append(f"{s} has a single tooth ({t}); its score is added to {dest}.")
            else:
                trace.append(f"{s} has a single tooth ({t}) and the adjacent sextant {dest} has fewer than two "
                             f"teeth, so {s} is scored on that tooth.")
    sext = {s: (max(tooth_max[t] for t in ts) if ts else None) for s, ts in members.items()}
    res = bewe(sext)
    return IndexResult("bewe", res.value, res.components, res.category, res.guidance, tuple(trace) + res.trace,
                       res.warnings, res.sources)
