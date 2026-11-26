"""Caries indices: DMFT/dmft, DMFS/dmfs (WHO 2013 coding) and PUFA/pufa (Monse 2010)."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ._common import InputError, age_value, fmt_fixed, fmt_g, is_blank, items, norm_code, teeth_list
from ._registry import codes as _codes
from ._registry import require_verified
from ._result import IndexResult
from ._teeth import (
    is_anterior,
    is_permanent,
    is_primary,
    is_third_molar,
    parse_tooth,
    permanent_at_position,
    primary_at_position,
)

__all__ = ["dmft_permanent", "dmft_primary", "dmfs_permanent", "dmfs_primary", "caries_experience", "pufa"]

M_RULES = ("who2013", "caries_only", "any_reason")


def _tables() -> dict[str, Any]:
    return _codes("who2013_dentition")


# --------------------------------------------------------------------------------------------
# Input normalisation
# --------------------------------------------------------------------------------------------
def _split_dentition(codes: Any) -> tuple[dict[int, str], dict[int, str], list[str]]:
    """Split WHO 2013 tooth codes into permanent (0-9) and primary (A-G) dentitions.

    Letter codes may be keyed by the primary tooth (55) or by the tooth space it shares with its
    permanent successor (15), as on the WHO form, where both use the same box.
    """
    tab = _tables()
    perm_codes = set(tab["permanent"])
    prim_codes = set(tab["primary"])
    permanent: dict[int, str] = {}
    primary: dict[int, str] = {}
    warnings: list[str] = []
    seen: set[int] = set()
    for key, raw in items(codes):
        t = parse_tooth(key)
        if t in seen:
            raise InputError(f"Tooth {t} appears more than once")
        seen.add(t)
        if is_blank(raw):
            continue
        c = norm_code(raw)
        if is_permanent(t):
            if c in perm_codes:
                permanent[t] = c
            elif c in prim_codes:
                p = primary_at_position(t)
                if p is None:
                    raise InputError(f"Tooth {t}: letter code {c!r} means a primary tooth, but no primary tooth "
                                     f"occupies the space of a permanent molar")
                if p in primary:
                    raise InputError(f"Primary tooth {p} is coded twice (as {p} and via space {t})")
                primary[p] = c
            else:
                raise InputError(f"Tooth {t}: {raw!r} is not a WHO 2013 dentition code (0-9, or A-G for primary teeth)")
        else:  # primary tooth number
            if c in prim_codes:
                if t in primary:
                    raise InputError(f"Primary tooth {t} is coded twice")
                primary[t] = c
            elif c in perm_codes:
                raise InputError(f"Tooth {t} is a primary tooth: WHO 2013 codes primary teeth with letters A-G, not {c!r}")
            else:
                raise InputError(f"Tooth {t}: {raw!r} is not a WHO 2013 primary-tooth code (A-G)")
    # WHO: if a permanent and a primary tooth occupy the same space, record the permanent tooth only.
    for p in sorted(primary):
        s = permanent_at_position(p)
        if s in permanent:
            if permanent[s] == "8":
                warnings.append(f"Space {s}: code 8 (unerupted) is only for spaces without a primary tooth; "
                                f"primary tooth {p} was kept and the code 8 ignored.")
                del permanent[s]
            else:
                warnings.append(f"Space {s}: both the permanent and primary tooth {p} were coded; WHO records the "
                                f"permanent tooth only, so {p} was ignored.")
                del primary[p]
    return permanent, primary, warnings


def _m_codes(age: float | None, m_rule: str, has_code5: bool, warnings: list[str], trace: list[str]) -> list[str]:
    tab = _tables()
    threshold = tab["m_age_threshold"]
    if m_rule not in M_RULES:
        raise InputError(f"m_rule must be one of {M_RULES}")
    if m_rule == "caries_only":
        trace.append("M rule: only code 4 (missing due to caries) counts (m_rule='caries_only').")
        return tab["permanent_components"]["M_under_threshold"]
    if m_rule == "any_reason":
        trace.append("M rule: codes 4 and 5 (missing for any reason) count (m_rule='any_reason').")
        return tab["permanent_components"]["M_at_or_over_threshold"]
    if age is None:
        if has_code5:
            warnings.append("Age not given: teeth coded 5 (missing for another reason) were not counted in M. "
                            "WHO 2013 counts them from age 30; give the age to apply the rule.")
        trace.append("M rule (WHO 2013): age not given, so only code 4 counts.")
        return tab["permanent_components"]["M_under_threshold"]
    if age >= threshold:
        trace.append(f"M rule (WHO 2013): age {fmt_g(age)} is {threshold} or over, so codes 4 and 5 count "
                     f"(missing due to caries or any other reason).")
        return tab["permanent_components"]["M_at_or_over_threshold"]
    trace.append(f"M rule (WHO 2013): age {fmt_g(age)} is under {threshold}, so only code 4 counts.")
    return tab["permanent_components"]["M_under_threshold"]


# --------------------------------------------------------------------------------------------
# DMFT / dmft
# --------------------------------------------------------------------------------------------
def dmft_permanent(codes: Any, age: Any = None, *, include_third_molars: bool = True,
                   m_rule: str = "who2013") -> IndexResult:
    """DMFT for the permanent dentition from WHO 2013 tooth codes.

    Parameters
    ----------
    codes : mapping of FDI tooth -> WHO 2013 code (0-9; letters A-G for primary teeth are accepted
        and ignored here, see :func:`dmft_primary`). Teeth left out are treated as not recorded.
    age : age in years. WHO 2013 counts code 5 (missing for another reason) in M from age 30.
    include_third_molars : WHO counts all 32 teeth (default). Set False to report on 28 teeth.
    m_rule : ``"who2013"`` (default, age-dependent), ``"caries_only"`` (code 4) or ``"any_reason"`` (4 and 5).
    """
    require_verified("dmft_permanent")
    tab = _tables()
    comp = tab["permanent_components"]
    a = age_value(age)
    permanent, _primary, warnings = _split_dentition(codes)
    trace: list[str] = []
    if not include_third_molars:
        dropped = [t for t in permanent if is_third_molar(t)]
        permanent = {t: c for t, c in permanent.items() if not is_third_molar(t)}
        trace.append(f"Third molars excluded (basis 28 teeth); dropped: {teeth_list(dropped)}.")
    else:
        trace.append("Basis 32 teeth, third molars included (WHO 2013).")
    m_codes = _m_codes(a, m_rule, any(c == "5" for c in permanent.values()), warnings, trace)
    d_t = [t for t, c in permanent.items() if c in comp["D"]]
    m_t = [t for t, c in permanent.items() if c in m_codes]
    f_t = [t for t, c in permanent.items() if c in comp["F"]]
    present = [t for t, c in permanent.items() if c in comp["present"]]
    trace.append(f"D = teeth coded 1 or 2: {teeth_list(d_t)} -> {len(d_t)}.")
    trace.append(f"M = teeth coded {' or '.join(m_codes)}: {teeth_list(m_t)} -> {len(m_t)}.")
    trace.append(f"F = teeth coded 3: {teeth_list(f_t)} -> {len(f_t)}.")
    sealed = [t for t, c in permanent.items() if c == "6"]
    special = [t for t, c in permanent.items() if c == "7"]
    if sealed or special:
        trace.append(f"Codes 6 (sealant: {teeth_list(sealed)}) and 7 (abutment/crown/veneer/implant: "
                     f"{teeth_list(special)}) are not counted in DMFT.")
    unerupted = [t for t, c in permanent.items() if c == "8"]
    not_rec = [t for t, c in permanent.items() if c == "9"]
    if not_rec:
        warnings.append(f"Teeth coded 9 (present but not examined) are excluded from caries counts: {teeth_list(not_rec)}.")
    if not permanent:
        warnings.append("No permanent teeth were recorded: DMFT is undefined (left out of group summaries).")
    missing_other = [t for t, c in permanent.items() if c == "5" and t not in m_t]
    d, m, f = len(d_t), len(m_t), len(f_t)
    total = d + m + f
    n_missing = sum(1 for c in permanent.values() if c in comp["missing"])
    components = {
        "DT": d, "MT": m, "FT": f, "DMFT": total, "DFT": d + f,
        "teeth_present": len(present), "teeth_missing": n_missing, "unerupted": len(unerupted),
        "not_recorded": len(not_rec), "sealed": len(sealed), "abutment_crown_veneer": len(special),
        "missing_other_reason_not_counted": len(missing_other),
        "caries_free": total == 0, "untreated_caries": d > 0,
        "edentulous": len(present) == 0 and n_missing > 0,
        "D_teeth": sorted(d_t), "M_teeth": sorted(m_t), "F_teeth": sorted(f_t),
        "age": a, "third_molars_included": include_third_molars,
    }
    trace.append(f"DMFT = {d} + {m} + {f} = {total}.")
    if not permanent:
        components["DMFT"] = None
        components["caries_free"] = None
        components["untreated_caries"] = None
        total = None  # type: ignore[assignment]
    return IndexResult("dmft_permanent", total, components, None, None, tuple(trace), tuple(warnings),
                       ("who2013",))


def dmft_primary(codes: Any) -> IndexResult:
    """dmft for the primary dentition from WHO 2013 letter codes (A-G).

    Code E (missing due to caries) should only be used when normal exfoliation cannot explain the
    absence (WHO 2013); DentIndices counts every E it is given.
    """
    require_verified("dmft_primary")
    comp = _tables()["primary_components"]
    _perm, primary, warnings = _split_dentition(codes)
    trace = ["Primary teeth use letter codes A-G (WHO 2013)."]
    d_t = [t for t, c in primary.items() if c in comp["d"]]
    m_t = [t for t, c in primary.items() if c in comp["m"]]
    f_t = [t for t, c in primary.items() if c in comp["f"]]
    present = [t for t, c in primary.items() if c in comp["present"]]
    trace.append(f"d = teeth coded B or C: {teeth_list(d_t)} -> {len(d_t)}.")
    trace.append(f"m = teeth coded E: {teeth_list(m_t)} -> {len(m_t)}.")
    trace.append(f"f = teeth coded D: {teeth_list(f_t)} -> {len(f_t)}.")
    if not primary:
        warnings.append("No primary teeth were recorded: dmft is undefined (left out of group summaries).")
    d, m, f = len(d_t), len(m_t), len(f_t)
    total = d + m + f
    trace.append(f"dmft = {d} + {m} + {f} = {total}.")
    components = {
        "dt": d, "mt": m, "ft": f, "dmft": total, "dft": d + f, "teeth_present": len(present),
        "sealed": sum(1 for c in primary.values() if c == "F"),
        "caries_free": total == 0, "untreated_caries": d > 0,
        "d_teeth": sorted(d_t), "m_teeth": sorted(m_t), "f_teeth": sorted(f_t),
    }
    if not primary:
        components.update({"dmft": None, "caries_free": None, "untreated_caries": None})
        total = None  # type: ignore[assignment]
    return IndexResult("dmft_primary", total, components, None, None, tuple(trace), tuple(warnings), ("who2013",))


def caries_experience(codes: Any, age: Any = None, *, include_third_molars: bool = True,
                      m_rule: str = "who2013") -> dict[str, IndexResult]:
    """Both dentitions at once (mixed dentition): ``{"permanent": DMFT result, "primary": dmft result}``."""
    return {
        "permanent": dmft_permanent(codes, age, include_third_molars=include_third_molars, m_rule=m_rule),
        "primary": dmft_primary(codes),
    }


# --------------------------------------------------------------------------------------------
# DMFS / dmfs
# --------------------------------------------------------------------------------------------
_SURFACE_ALIASES = {
    "O": "O", "OCC": "O", "OCCLUSAL": "O",
    "M": "M", "MES": "M", "MESIAL": "M",
    "D": "D", "DIS": "D", "DISTAL": "D",
    "B": "B", "BUC": "B", "BUCCAL": "B", "F": "B", "FAC": "B", "FACIAL": "B", "LAB": "B", "LABIAL": "B",
    "L": "L", "LI": "L", "LING": "L", "LINGUAL": "L", "P": "L", "PAL": "L", "PALATAL": "L", "ORAL": "L",
}


def _surface(name: Any) -> str:
    key = str(name).strip().upper()
    if key not in _SURFACE_ALIASES:
        raise InputError(f"Unknown surface {name!r}; use O, M, D, B (buccal/labial) or L (lingual/palatal)")
    return _SURFACE_ALIASES[key]


def _sort_key(k: Any) -> int:
    try:
        return parse_tooth(k)
    except Exception:
        return 0


def _surfaces_for(t: int) -> list[str]:
    s = _tables()["surfaces"]
    return list(s["anterior"] if is_anterior(t) else s["posterior"])


def _surface_codes(data: Any, dentition: str) -> tuple[dict[int, dict[str, str]], list[str]]:
    """Parse tooth -> code (whole tooth) or tooth -> {surface: code}."""
    tab = _tables()
    valid = set(tab["permanent"]) if dentition == "permanent" else set(tab["primary"])
    whole_tooth = {"4", "5", "8"} if dentition == "permanent" else {"E"}
    out: dict[int, dict[str, str]] = {}
    warnings: list[str] = []
    seen: set[int] = set()
    for key, raw in sorted(items(data), key=lambda kv: _sort_key(kv[0])):
        t0 = parse_tooth(key)
        if t0 in seen:
            raise InputError(f"Tooth {t0} appears more than once")
        seen.add(t0)
        raw_vals = [v for v in (raw.values() if isinstance(raw, Mapping) else [raw]) if not is_blank(v)]
        if not raw_vals:
            continue
        kinds = {"primary" if norm_code(v).isalpha() and norm_code(v) not in ("X",) else "permanent"
                 for v in raw_vals}
        if len(kinds) > 1:
            raise InputError(f"Tooth {t0}: mixes permanent (digit) and primary (letter) codes")
        kind = kinds.pop()
        if kind != dentition:
            continue
        t = t0
        if dentition == "primary" and is_permanent(t0):
            p = primary_at_position(t0)
            if p is None:
                raise InputError(f"Tooth {t0}: letter codes mean a primary tooth, but no primary tooth "
                                 f"occupies a permanent molar space")
            t = p
        if dentition == "permanent" and is_primary(t0):
            raise InputError(f"Tooth {t0} is a primary tooth: use letter codes A-G")
        if t in out:
            raise InputError(f"Tooth {t} appears more than once")
        allowed = _surfaces_for(t)
        if isinstance(raw, Mapping):
            surf: dict[str, str] = {}
            for sk, sv in raw.items():
                if is_blank(sv):
                    continue
                s = _surface(sk)
                if s not in allowed:
                    raise InputError(f"Tooth {t}: WHO 2013 surface forms record {', '.join(allowed)} for this tooth, not {sk!r}")
                c = norm_code(sv)
                if c not in valid:
                    raise InputError(f"Tooth {t} surface {s}: {sv!r} is not a valid {dentition} code")
                if s in surf:
                    raise InputError(f"Tooth {t}: surface {s} is given twice")
                surf[s] = c
            if not surf:
                continue
            tooth_level = {c for c in surf.values() if c in whole_tooth}
            if tooth_level and (len(set(surf.values())) > 1):
                raise InputError(f"Tooth {t}: codes {', '.join(sorted(tooth_level))} describe the whole tooth and "
                                 f"cannot be mixed with other surface codes")
            if tooth_level and len(surf) < len(allowed):
                surf = {s: next(iter(tooth_level)) for s in allowed}
            missing_s = [s for s in allowed if s not in surf]
            if missing_s:
                warnings.append(f"Tooth {t}: surface(s) {', '.join(missing_s)} not recorded and not counted.")
            sealant_off = [s for s, c in surf.items() if c in ("6", "F") and s != "O"]
            if sealant_off:
                warnings.append(f"Tooth {t}: sealant code on non-occlusal surface(s) {', '.join(sealant_off)}.")
            out[t] = surf
        else:
            if is_blank(raw):
                continue
            c = norm_code(raw)
            if c not in valid:
                raise InputError(f"Tooth {t}: {raw!r} is not a valid {dentition} code")
            out[t] = {s: c for s in allowed}
    return out, warnings


def dmfs_permanent(surfaces: Any, age: Any = None, *, include_third_molars: bool = True,
                   m_rule: str = "who2013") -> IndexResult:
    """DMFS for the permanent dentition (WHO 2013 surface forms).

    ``surfaces`` maps each tooth either to one WHO code for the whole tooth (e.g. ``{36: 4}`` for a
    tooth missing due to caries) or to ``{surface: code}`` with surfaces O, M, D, B, L (posterior)
    and M, D, B, L (incisors and canines). A missing tooth counts 5 surfaces (posterior) or 4
    (anterior), the number of surfaces on the WHO form.
    """
    require_verified("dmfs_permanent")
    a = age_value(age)
    data, warnings = _surface_codes(surfaces, "permanent")
    trace: list[str] = []
    if not include_third_molars:
        data = {t: s for t, s in data.items() if not is_third_molar(t)}
        trace.append("Third molars excluded.")
    comp = _tables()["permanent_components"]
    m_codes = _m_codes(a, m_rule, any("5" in s.values() for s in data.values()), warnings, trace)
    ds = fs = ms = 0
    for t, s in sorted(data.items()):
        vals = list(s.values())
        if all(c in m_codes for c in vals):
            ms += len(vals)
            continue
        ds += sum(1 for c in vals if c in comp["D"])
        fs += sum(1 for c in vals if c in comp["F"])
    total = ds + ms + fs
    trace.append(f"DS (surfaces coded 1 or 2) = {ds}; MS (surfaces of teeth coded {' or '.join(m_codes)}: "
                 f"5 per posterior, 4 per anterior tooth) = {ms}; FS (surfaces coded 3) = {fs}.")
    trace.append(f"DMFS = {ds} + {ms} + {fs} = {total}.")
    comps = {"DS": ds, "MS": ms, "FS": fs, "DMFS": total, "DFS": ds + fs,
             "surfaces_recorded": sum(len(s) for s in data.values()), "teeth_recorded": len(data), "age": a}
    return IndexResult("dmfs_permanent", total, comps, None, None, tuple(trace), tuple(warnings),
                       ("who2013", "broadbent2005"))


def dmfs_primary(surfaces: Any) -> IndexResult:
    """dmfs for the primary dentition (letter codes A-G, WHO 2013 children's surface form)."""
    require_verified("dmfs_primary")
    data, warnings = _surface_codes(surfaces, "primary")
    comp = _tables()["primary_components"]
    ds = fs = ms = 0
    for t, s in sorted(data.items()):
        vals = list(s.values())
        if all(c in comp["m"] for c in vals):
            ms += len(vals)
            continue
        ds += sum(1 for c in vals if c in comp["d"])
        fs += sum(1 for c in vals if c in comp["f"])
    total = ds + ms + fs
    trace = [f"ds (B or C) = {ds}; ms (surfaces of teeth coded E) = {ms}; fs (D) = {fs}.",
             f"dmfs = {ds} + {ms} + {fs} = {total}."]
    comps = {"ds": ds, "ms": ms, "fs": fs, "dmfs": total, "dfs": ds + fs,
             "surfaces_recorded": sum(len(s) for s in data.values()), "teeth_recorded": len(data)}
    return IndexResult("dmfs_primary", total, comps, None, None, tuple(trace), tuple(warnings), ("who2013",))


# --------------------------------------------------------------------------------------------
# PUFA / pufa
# --------------------------------------------------------------------------------------------
def pufa(codes: Any, *, decayed_teeth: int | None = None) -> IndexResult:
    """PUFA/pufa index (Monse et al. 2010): teeth with visible pulpal involvement (P), ulceration from
    dislocated tooth fragments (U), fistula (F) or abscess (A). One score per tooth.

    ``codes`` maps tooth -> one of P, U, F, A (or blank/0 for none). Upper case is used for permanent
    and lower case for primary teeth; DentIndices sets the case from the tooth number. Give
    ``decayed_teeth`` (D + d) to get the share of decayed teeth that progressed to PUFA.
    """
    require_verified("pufa")
    letters = ("P", "U", "F", "A")
    perm: dict[int, str] = {}
    prim: dict[int, str] = {}
    for key, raw in items(codes):
        t = parse_tooth(key)
        if t in perm or t in prim:
            raise InputError(f"Tooth {t} appears more than once")
        if is_blank(raw) or norm_code(raw) in ("0", "N", "NONE"):
            continue
        c = norm_code(raw)
        if len(c) != 1 or c not in letters:
            raise InputError(f"Tooth {t}: {raw!r} is not a PUFA code; give one of P, U, F, A per tooth "
                             f"(PUFA assigns one score per tooth)")
        (perm if is_permanent(t) else prim)[t] = c
    counts = {k: sum(1 for c in perm.values() if c == k) for k in letters}
    counts_p = {k.lower(): sum(1 for c in prim.values() if c == k) for k in letters}
    total_perm = len(perm)
    total_prim = len(prim)
    total = total_perm + total_prim
    trace = [f"PUFA (permanent teeth with P, U, F or A) = {total_perm}: {teeth_list(perm)}.",
             f"pufa (primary teeth) = {total_prim}: {teeth_list(prim)}.",
             f"PUFA/pufa (both dentitions) = {total}."]
    warnings: list[str] = []
    comps: dict[str, Any] = {"PUFA": total_perm, "pufa": total_prim, "PUFA_pufa": total, **counts, **counts_p}
    if decayed_teeth is not None:
        if isinstance(decayed_teeth, bool) or not isinstance(decayed_teeth, int) or decayed_teeth < 0:
            raise InputError("decayed_teeth must be a whole number >= 0")
        if decayed_teeth == 0:
            ratio = None
            if total:
                warnings.append("PUFA teeth are also decayed teeth (D/d); decayed_teeth = 0 is inconsistent.")
        else:
            if total > decayed_teeth:
                warnings.append("More PUFA teeth than decayed teeth: check the D/d count.")
            ratio = round(100 * total / decayed_teeth, 10)
        comps["decayed_teeth"] = decayed_teeth
        comps["percent_decayed_progressed"] = ratio
        trace.append(f"Share of decayed teeth that progressed to PUFA = {total}/{decayed_teeth} x 100"
                     + (f" = {fmt_fixed(ratio, 1)}%." if ratio is not None else " (undefined)."))
    return IndexResult("pufa", total, comps, None, None, tuple(trace), tuple(warnings), ("monse2010",))
