"""Periodontal screening: BPE (BSP 2019), simplified BPE for under-18s (BSP/BSPD 2021), CPITN
(Ainamo 1982 / WHO 1997 CPI), and the WHO 2013 CPI-modified and loss-of-attachment scores."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ._common import InputError, age_value, fmt_g, is_blank, items, norm_code, seq, teeth_list, teeth_set
from ._registry import codes, require_verified
from ._result import IndexResult
from ._teeth import (
    SEXTANT_NAMES,
    SEXTANT_ORDER,
    is_permanent,
    is_third_molar,
    parse_sextant,
    parse_tooth,
)

__all__ = ["bpe", "bpe_from_teeth", "sbpe", "cpitn", "cpi_modified", "loss_of_attachment"]

_EXCLUDED = ("X", "-", "/", "EXCLUDED")


def _sextant_values(sextants: Any, what: str) -> dict[str, Any]:
    """Six sextant values from a list (WHO order S1-S6: UR, UA, UL, LL, LA, LR) or a mapping."""
    if isinstance(sextants, Mapping):
        out: dict[str, Any] = {}
        for k, v in sextants.items():
            s = parse_sextant(k)
            if s in out:
                raise InputError(f"{what}: sextant {s} given twice")
            out[s] = v
        return {s: out.get(s) for s in SEXTANT_ORDER}
    vals = seq(sextants, f"{what} sextants")
    if len(vals) != 6:
        raise InputError(f"{what}: give six sextant values in the order UR, UA, UL, LL, LA, LR "
                         f"(upper right 18-14, upper anterior 13-23, upper left 24-28, lower left 38-34, "
                         f"lower anterior 33-43, lower right 44-48)")
    return dict(zip(SEXTANT_ORDER, vals))


def _bpe_code(v: Any, what: str) -> tuple[int, bool] | None:
    if is_blank(v) or norm_code(v) in _EXCLUDED:
        return None
    s = norm_code(v)
    fur = s.endswith("*")
    core = s.rstrip("*").strip()
    if core not in ("0", "1", "2", "3", "4"):
        raise InputError(f"{what}: {v!r} is not a BPE code (0-4, with * for furcation involvement, e.g. '3*')")
    return int(core), fur


def bpe(sextants: Any) -> IndexResult:
    """Basic Periodontal Examination (British Society of Periodontology, 2019).

    ``sextants``: six codes in the order UR, UA, UL, LL, LA, LR (or a mapping with those names), each
    0-4 with an optional ``*`` for furcation involvement (e.g. ``"3*"``); use ``None``, ``"-"`` or
    ``"X"`` for a sextant with fewer than two teeth.
    """
    require_verified("bpe")
    tab = codes("bpe")
    vals = _sextant_values(sextants, "BPE")
    parsed = {s: _bpe_code(v, f"BPE sextant {s}") for s, v in vals.items()}
    scored = {s: p for s, p in parsed.items() if p is not None}
    if not scored:
        raise InputError("BPE: no sextant was scored")
    max_code = max(p[0] for p in scored.values())
    fur = any(p[1] for p in scored.values())
    fur_sextants = [s for s, p in scored.items() if p[1]]
    code3 = [s for s, p in scored.items() if p[0] == 3]
    code4 = [s for s, p in scored.items() if p[0] == 4]
    excluded = [s for s, p in parsed.items() if p is None]
    grid = {s: (None if p is None else f"{p[0]}{'*' if p[1] else ''}") for s, p in parsed.items()}
    trace = ["Highest code per sextant: " + ", ".join(f"{s} {grid[s] or '-'}" for s in SEXTANT_ORDER) + ".",
             f"Highest code overall: {max_code}{' with furcation involvement' if fur else ''}."]
    guidance = tab["guidance"][str(max_code)]
    if fur:
        guidance += " Furcation involvement (*): " + tab["guidance"]["*"]
    guidance += " " + tab["recording"]
    if code4:
        trace.append("A code 4 is present, so a 6-point pocket chart of the entire dentition is indicated.")
    elif code3:
        trace.append("Code 3 sextant(s) " + ", ".join(code3) + ": after initial therapy, record a 6-point chart "
                     "in those sextants.")
    warnings = []
    if excluded:
        trace.append("Sextants not scored (fewer than two teeth): " + ", ".join(excluded) + ".")
    category = f"Code {max_code}{'*' if fur else ''}"
    comps = {"max_code": max_code, "furcation": fur, "furcation_sextants": fur_sextants,
             "sextants": grid, "code3_sextants": code3, "code4_sextants": code4,
             "excluded_sextants": excluded, "full_chart_indicated": bool(code4),
             "radiographs_indicated_sextants": code3 + code4}
    return IndexResult("bpe", max_code, comps, category, guidance, tuple(trace), tuple(warnings), ("bsp2019",))


def bpe_from_teeth(tooth_codes: Any, teeth_present: Any = None) -> IndexResult:
    """BPE from the worst code found at each tooth: groups teeth into the BSP sextants (third molars
    only when the first and/or second molar of that sextant is missing) and requires at least two
    teeth for a sextant to be scored.

    ``teeth_present`` lists every tooth present (scored or not); by default the scored teeth.
    """
    require_verified("bpe")
    tab = codes("bpe")
    tc: dict[int, tuple[int, bool]] = {}
    for k, v in items(tooth_codes):
        t = parse_tooth(k)
        if not is_permanent(t):
            raise InputError(f"BPE is recorded on permanent teeth; {t} is a primary tooth")
        p = _bpe_code(v, f"BPE tooth {t}")
        if p is not None:
            if t in tc:
                raise InputError(f"Tooth {t} appears more than once")
            tc[t] = p
    present = teeth_set(teeth_present) if teeth_present is not None else set(tc)
    missing_codes = [t for t in tc if t not in present]
    if missing_codes:
        raise InputError(f"Teeth {teeth_list(missing_codes)} have codes but are not in teeth_present")
    names = {"UR": "S1", "UA": "S2", "UL": "S3", "LL": "S4", "LA": "S5", "LR": "S6"}
    third = {"S1": 18, "S3": 28, "S4": 38, "S6": 48}
    grid: dict[str, Any] = {}
    trace: list[str] = []
    for name, teeth in tab["sextants"].items():
        s = names[name]
        members = [t for t in teeth if t in present]
        if s in third:
            molars = [t for t in teeth if t % 10 in (6, 7)]
            if any(m not in present for m in molars) and third[s] in present:
                members.append(third[s])
                trace.append(f"{s}: third molar {third[s]} included because a first/second molar is missing.")
        if len(members) < tab["min_teeth_per_sextant"]:
            grid[s] = None
            continue
        scored = [tc[t] for t in members if t in tc]
        if not scored:
            grid[s] = None
            trace.append(f"{s}: teeth present but none scored.")
            continue
        mx = max(c for c, _ in scored)
        fur = any(f for _, f in scored)
        grid[s] = f"{mx}{'*' if fur else ''}"
    res = bpe(grid)
    return IndexResult("bpe", res.value, res.components, res.category, res.guidance,
                       tuple(trace) + res.trace, res.warnings, res.sources)


def sbpe(index_teeth: Any, age: Any) -> IndexResult:
    """Simplified BPE for children and adolescents (BSP/BSPD 2021): index teeth 16, 11, 26, 36, 31, 46.
    Codes 0-2 only for ages 7-11 (mixed dentition); full codes 0-4 and * for ages 12-17."""
    require_verified("sbpe")
    tab = codes("sbpe")
    a = age_value(age)
    if a is None:
        raise InputError("sBPE needs the age (7-17 years)")
    if a < 7 or a >= 18:
        raise InputError("The simplified BPE is for ages 7 to 17; use bpe() from age 18")
    allowed = tab["codes_by_age"]["7-11" if a < 12 else "12-17"]
    tm = {}
    for k, v in items(index_teeth):
        t = parse_tooth(k)
        if t not in tab["index_teeth"]:
            raise InputError(f"Tooth {t} is not an sBPE index tooth (16, 11, 26, 36, 31, 46)")
        if t in tm:
            raise InputError(f"Tooth {t} appears more than once")
        tm[t] = _bpe_code(v, f"sBPE tooth {t}")
    scored = {t: p for t, p in tm.items() if p is not None}
    if not scored:
        raise InputError("sBPE: no index tooth was scored")
    for t, (c, f) in scored.items():
        if str(c) not in allowed or (f and "*" not in allowed):
            raise InputError(f"Tooth {t}: at age {fmt_g(a)} the sBPE uses codes {', '.join(allowed)} only "
                             f"(7- to 11-year-olds: 0-2)")
    mx = max(c for c, _ in scored.values())
    fur = any(f for _, f in scored.values())
    unscored = [t for t in tab["index_teeth"] if t not in scored]
    warnings = [f"Index teeth not scored: {teeth_list(unscored)}."] if unscored else []
    guidance = tab["guidance"]["*"] if fur else tab["guidance"][str(mx)]
    trace = [f"Age {fmt_g(a)}: codes allowed {', '.join(allowed)}.",
             "Index teeth: " + ", ".join(f"{t} {c}{'*' if f else ''}" for t, (c, f) in sorted(scored.items())) + ".",
             f"Highest code: {mx}{'*' if fur else ''}."]
    comps = {"max_code": mx, "furcation": fur, "teeth": {t: f"{c}{'*' if f else ''}" for t, (c, f) in scored.items()},
             "age_band": "7-11" if a < 12 else "12-17", "unscored_index_teeth": unscored}
    return IndexResult("sbpe", mx, comps, f"Code {mx}{'*' if fur else ''}", guidance, tuple(trace),
                       tuple(warnings), ("bsp2021",))


def _score(v: Any, allowed: tuple[str, ...], what: str) -> str | None:
    if is_blank(v):
        return None
    c = norm_code(v)
    if c == "-":
        c = "X"
    if c not in allowed:
        raise InputError(f"{what}: {v!r} is not one of {', '.join(allowed)}")
    return c


def cpitn(sextants: Any, age: Any = None) -> IndexResult:
    """CPITN (Ainamo et al. 1982) / CPI (WHO 1997): one code per sextant (0 healthy, 1 bleeding,
    2 calculus, 3 pocket 4-5 mm, 4 pocket >= 6 mm; X excluded sextant, 9 not recorded), giving the
    person's highest code and treatment need (TN0-TN3)."""
    require_verified("cpitn")
    tab = codes("cpitn")
    a = age_value(age)
    vals = _sextant_values(sextants, "CPITN")
    parsed = {s: _score(v, ("0", "1", "2", "3", "4", "X", "9"), f"CPITN sextant {s}") for s, v in vals.items()}
    scored = {s: int(c) for s, c in parsed.items() if c is not None and c not in ("X", "9")}
    warnings: list[str] = []
    if not scored:
        raise InputError("CPITN: no sextant was scored")
    if a is not None and a < tab["pockets_not_recorded_under_age"] and any(c >= 3 for c in scored.values()):
        warnings.append("Pockets (codes 3 and 4) are not recorded in children under 15 (WHO 1997); only bleeding "
                        "and calculus should be scored.")
    mx = max(scored.values())
    tn = tab["treatment_need"][str(mx)]
    counts = {f"sextants_code{k}": sum(1 for c in scored.values() if c == k) for k in range(5)}
    trace = ["Sextant codes: " + ", ".join(f"{s} {parsed[s] or '-'}" for s in SEXTANT_ORDER) + ".",
             f"Highest code {mx} -> treatment need {tn} ({tab['treatment_need_labels'][tn]})."]
    index_set = "20_and_over" if (a is None or a >= 20) else "under_20"
    comps = {"max_code": mx, "treatment_need": tn, **counts, "sextants_scored": len(scored),
             "sextants_excluded": sum(1 for c in parsed.values() if c == "X"),
             "sextants_not_recorded": sum(1 for c in parsed.values() if c == "9"),
             "index_teeth": tab["index_teeth"][index_set], "sextants": parsed}
    return IndexResult("cpitn", mx, comps, tn, tab["treatment_need_labels"][tn], tuple(trace), tuple(warnings),
                       ("ainamo1982", "who1997"))


def cpi_modified(bleeding: Any, pockets: Any = None, age: Any = None) -> IndexResult:
    """WHO 2013 Community Periodontal Index, modified: gingival bleeding (0/1) and pocket scores
    (0 none, 1 = 4-5 mm, 2 = 6 mm or more) for every tooth present; 9 = tooth excluded, X = tooth not
    present. Pockets are not recorded under age 15."""
    require_verified("cpi_modified")
    tab = codes("cpi_modified")
    a = age_value(age)
    b = {}
    for k, v in items(bleeding):
        t = parse_tooth(k)
        if t in b:
            raise InputError(f"Tooth {t} appears more than once (bleeding)")
        c = _score(v, tuple(tab["bleeding"]), f"bleeding tooth {t}")
        if c is not None:
            b[t] = c
    p = {}
    warnings: list[str] = []
    if pockets is not None:
        if a is not None and a < tab["pockets_not_recorded_under_age"]:
            warnings.append("Pockets are not recorded under age 15 (WHO 2013); pocket scores were ignored.")
        else:
            for k, v in items(pockets):
                t = parse_tooth(k)
                if t in p:
                    raise InputError(f"Tooth {t} appears more than once (pockets)")
                c = _score(v, tuple(tab["pocket"]), f"pocket tooth {t}")
                if c is not None:
                    p[t] = c
    present_b = [t for t, c in b.items() if c != "X"]
    bleed = [t for t, c in b.items() if c == "1"]
    no_bleed = [t for t, c in b.items() if c == "0"]
    excl_b = [t for t, c in b.items() if c == "9"]
    examined = len(bleed) + len(no_bleed)
    comps: dict[str, Any] = {
        "teeth_present": len(present_b), "teeth_examined": examined, "teeth_excluded": len(excl_b),
        "bleeding_teeth": len(bleed), "bleeding": bool(bleed),
        "bleeding_percent_of_present": round(100 * len(bleed) / len(present_b), 10) if present_b else None,
        "bleeding_percent_of_examined": round(100 * len(bleed) / examined, 10) if examined else None,
    }
    trace = [f"Bleeding: {len(bleed)} of {len(present_b)} teeth present ({teeth_list(bleed)})."]
    value: Any = len(bleed)
    category = "Bleeding" if bleed else ("No bleeding" if examined else None)
    if p:
        present_p = [t for t, c in p.items() if c != "X"]
        shallow = [t for t, c in p.items() if c == "1"]
        deep = [t for t, c in p.items() if c == "2"]
        none_ = [t for t, c in p.items() if c == "0"]
        mx = 2 if deep else (1 if shallow else (0 if none_ else None))
        comps.update({
            "pocket_max_score": mx, "shallow_pocket_teeth": len(shallow), "deep_pocket_teeth": len(deep),
            "shallow_pocket_percent_of_present": round(100 * len(shallow) / len(present_p), 10) if present_p else None,
            "deep_pocket_percent_of_present": round(100 * len(deep) / len(present_p), 10) if present_p else None,
            "pocket_teeth_excluded": sum(1 for c in p.values() if c == "9"),
        })
        trace.append(f"Pockets 4-5 mm: {teeth_list(shallow)}; 6 mm or more: {teeth_list(deep)}.")
        if mx is not None:
            category = {0: "No pockets", 1: "Shallow pockets (4-5 mm)", 2: "Deep pockets (6 mm or more)"}[mx]
            trace.append(f"Highest pocket score: {mx}.")
    return IndexResult("cpi_modified", value, comps, category, None, tuple(trace), tuple(warnings), ("who2013",))


def loss_of_attachment(sextants: Any, age: Any = None) -> IndexResult:
    """WHO 2013 loss of attachment by sextant (index teeth 17/16, 11, 26/27, 36/37, 31, 46/47):
    0 = 0-3 mm, 1 = 4-5 mm, 2 = 6-8 mm, 3 = 9-11 mm, 4 = 12 mm or more; X excluded, 9 not recorded.
    Not recorded under age 15."""
    require_verified("loss_of_attachment")
    tab = codes("loa")
    a = age_value(age)
    if a is not None and a < tab["not_recorded_under_age"]:
        raise InputError("Loss of attachment is not recorded under age 15 (WHO 2013)")
    vals = _sextant_values(sextants, "Loss of attachment")
    parsed = {s: _score(v, tuple(tab["codes"]), f"LOA sextant {s}") for s, v in vals.items()}
    scored = {s: int(c) for s, c in parsed.items() if c is not None and c not in ("X", "9")}
    if not scored:
        raise InputError("Loss of attachment: no sextant was scored")
    mx = max(scored.values())
    counts = {f"sextants_score{k}": sum(1 for c in scored.values() if c == k) for k in range(5)}
    trace = ["Sextant scores: " + ", ".join(f"{s} {parsed[s] or '-'}" for s in SEXTANT_ORDER) + ".",
             f"Highest score {mx} ({tab['codes'][str(mx)]})."]
    comps = {"max_score": mx, **counts, "sextants_excluded": sum(1 for c in parsed.values() if c == "X"),
             "sextants_not_recorded": sum(1 for c in parsed.values() if c == "9"), "sextants": parsed}
    return IndexResult("loss_of_attachment", mx, comps, tab["codes"][str(mx)], None, tuple(trace), (), ("who2013",))


# keep names referenced for linters
_ = (SEXTANT_NAMES, is_third_molar)
