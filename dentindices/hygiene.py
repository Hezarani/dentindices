"""Oral hygiene and gingival indices: Plaque Index (Silness & Löe 1964), Gingival Index (Löe &
Silness 1963), Plaque Control Record (O'Leary 1972) and OHI-S (Greene & Vermillion 1964)."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from ._common import InputError, fmt_fixed, fmt_g, int_score, is_blank, items, teeth_list, teeth_set
from ._registry import _round_half_up, band, codes, require_verified
from ._result import IndexResult
from ._teeth import parse_tooth

__all__ = ["plaque_index", "gingival_index", "plaque_control_record", "ohi_s"]

_FOUR_AREA = {"D": "D", "DB": "D", "DF": "D", "DISTAL": "D", "DISTOFACIAL": "D", "DISTOBUCCAL": "D",
              "B": "B", "F": "B", "BUCCAL": "B", "FACIAL": "B", "LABIAL": "B", "V": "B", "VESTIBULAR": "B",
              "M": "M", "MB": "M", "MF": "M", "MESIAL": "M", "MESIOFACIAL": "M", "MESIOBUCCAL": "M",
              "L": "L", "P": "L", "O": "L", "LINGUAL": "L", "PALATAL": "L", "ORAL": "L"}


def _area(k: Any) -> str:
    key = str(k).strip().upper()
    if key not in _FOUR_AREA:
        raise InputError(f"Unknown area {k!r}: use D (distofacial), B (facial), M (mesiofacial) or L (lingual)")
    return _FOUR_AREA[key]


def _four_area_scores(data: Any, what: str) -> dict[int, dict[str, int]]:
    out: dict[int, dict[str, int]] = {}
    for k, v in items(data):
        t = parse_tooth(k)
        if t in out:
            raise InputError(f"{what}: tooth {t} appears more than once")
        if isinstance(v, Mapping):
            areas: dict[str, int] = {}
            for ak, av in v.items():
                if is_blank(av):
                    continue
                a = _area(ak)
                if a in areas:
                    raise InputError(f"{what}: tooth {t} area {a} given twice")
                areas[a] = int_score(av, 0, 3, f"{what} tooth {t} area {a}")
        elif isinstance(v, (list, tuple)):
            if len(v) != 4:
                raise InputError(f"{what}: tooth {t}: give four scores in the order D, B, M, L")
            areas = {a: int_score(s, 0, 3, f"{what} tooth {t} area {a}")
                     for a, s in zip(("D", "B", "M", "L"), v) if not is_blank(s)}
        elif is_blank(v):
            continue
        else:
            raise InputError(f"{what}: tooth {t}: give a mapping of areas or four scores (D, B, M, L)")
        if areas:
            out[t] = areas
    if not out:
        raise InputError(f"{what}: no scores given")
    return out


def _area_index(index_id: str, data: Any, what: str, table: str, source_ids: tuple[str, ...]) -> IndexResult:
    require_verified(index_id)
    tab = codes(table)
    scores = _four_area_scores(data, what)
    tooth_means = {t: sum(a.values()) / len(a) for t, a in scores.items()}
    # Exact mean of the tooth means: every tooth has 1-4 integer area scores, so with a common
    # denominator of 12 the numerator is an integer and one division gives the correctly rounded value
    # (the same in every Python version and in the browser engine).
    person = sum(sum(a.values()) * (12 // len(a)) for a in scores.values()) / (12 * len(scores))
    n_areas = sum(len(a) for a in scores.values())
    surface_mean = sum(sum(a.values()) for a in scores.values()) / n_areas
    warnings = []
    incomplete = [t for t, a in scores.items() if len(a) < 4]
    if incomplete:
        warnings.append(f"Teeth with fewer than four areas scored: {teeth_list(incomplete)} "
                        f"(tooth score = mean of the areas scored).")
    ram = set(tab["ramfjord_teeth"])
    teeth_used = sorted(scores)
    trace = [f"{len(scores)} teeth, {n_areas} areas scored; tooth score = mean of its areas (0-3).",
             f"{what} = mean of tooth scores = {fmt_g(person)} (read as {fmt_fixed(_round_half_up(person, tab['round_to']), 1)})."]
    category = band(person, tab["bands"], tab["round_to"])
    comps = {what: round(person, 10), "mean_of_all_areas": round(surface_mean, 10), "teeth_scored": len(scores),
             "areas_scored": n_areas, "tooth_scores": {t: round(m, 10) for t, m in tooth_means.items()},
             "ramfjord_teeth_only": set(teeth_used) <= ram}
    return IndexResult(index_id, round(person, 10), comps, category, None, tuple(trace), tuple(warnings), source_ids)


def plaque_index(scores: Any) -> IndexResult:
    """Silness & Löe (1964) Plaque Index. ``scores`` maps each tooth to four area scores (0-3):
    distofacial (D), facial (B), mesiofacial (M) and lingual (L), as a mapping or a list in that
    order. Use all teeth or the six Ramfjord teeth (16, 21, 24, 36, 41, 44). The interpretation
    bands (excellent 0, good 0.1-0.9, fair 1.0-1.9, poor 2.0-3.0) are conventional, not from the
    1964 paper."""
    r = _area_index("plaque_index", scores, "PlI", "plaque_index", ("silness1964", "loe1967", "delia2023"))
    return IndexResult(r.index, r.value, r.components, r.category, None, r.trace,
                       r.warnings + ("Interpretation bands are a textbook convention, not part of the original index.",),
                       r.sources)


def gingival_index(scores: Any) -> IndexResult:
    """Löe & Silness (1963) Gingival Index: same four areas per tooth, scores 0-3. Interpretation
    (Löe 1967): 0.1-1.0 mild, 1.1-2.0 moderate, 2.1-3.0 severe gingivitis."""
    return _area_index("gingival_index", scores, "GI", "gingival_index", ("loe1963", "loe1967"))


_PCR_AREAS = {"M": "M", "MESIAL": "M", "D": "D", "DISTAL": "D", "B": "B", "F": "B", "FACIAL": "B", "BUCCAL": "B",
              "LABIAL": "B", "L": "L", "P": "L", "LINGUAL": "L", "PALATAL": "L", "ORAL": "L"}


def plaque_control_record(plaque: Any, teeth_present: Iterable[Any] | None = None) -> IndexResult:
    """O'Leary, Drake & Naylor (1972) Plaque Control Record: the percentage of tooth surfaces
    (mesial, distal, facial, lingual of every tooth present) with plaque after disclosing.

    ``plaque`` maps each tooth to the surfaces with plaque (e.g. ``{16: "MD", 11: []}``) or to a
    mapping of surface -> True/False. Teeth listed in ``teeth_present`` but missing from ``plaque``
    count as plaque-free.
    """
    require_verified("plaque_control_record")
    tab = codes("plaque_control_record")
    marked: dict[int, set[str]] = {}
    for k, v in items(plaque):
        t = parse_tooth(k)
        if t in marked:
            raise InputError(f"Tooth {t} appears more than once")
        s: set[str] = set()
        if isinstance(v, Mapping):
            for a, flag in v.items():
                key = str(a).strip().upper()
                if key not in _PCR_AREAS:
                    raise InputError(f"Tooth {t}: unknown surface {a!r} (use M, D, B/F, L)")
                if flag in (True, 1, "1", "yes", "Y", "y", "true", "True"):
                    s.add(_PCR_AREAS[key])
                elif flag not in (False, 0, "0", "no", "N", "n", "false", "False", None, ""):
                    raise InputError(f"Tooth {t} surface {a}: {flag!r} is not yes/no")
        elif isinstance(v, str):
            for ch in v.replace(",", "").replace(" ", "").upper():
                if ch not in _PCR_AREAS:
                    raise InputError(f"Tooth {t}: unknown surface {ch!r} (use M, D, B/F, L)")
                s.add(_PCR_AREAS[ch])
        elif isinstance(v, Iterable):
            for a in v:
                key = str(a).strip().upper()
                if key not in _PCR_AREAS:
                    raise InputError(f"Tooth {t}: unknown surface {a!r} (use M, D, B/F, L)")
                s.add(_PCR_AREAS[key])
        elif v is None:
            pass
        else:
            raise InputError(f"Tooth {t}: give the surfaces with plaque")
        marked[t] = s
    present = teeth_set(teeth_present) if teeth_present is not None else set(marked)
    extra = [t for t in marked if t not in present]
    if extra:
        raise InputError(f"Teeth {teeth_list(extra)} have plaque recorded but are not in teeth_present")
    if not present:
        raise InputError("No teeth present")
    n_surfaces = 4 * len(present)
    n_plaque = sum(len(s) for s in marked.values())
    pct = round(100 * n_plaque / n_surfaces, 10)
    trace = [f"{len(present)} teeth present x 4 surfaces = {n_surfaces} surfaces.",
             f"Surfaces with plaque = {n_plaque}; PCR = {n_plaque}/{n_surfaces} x 100 = {fmt_fixed(pct, 1)}%."]
    notes = [r["note"] for r in tab["reference_points"]]
    comps = {"PCR_percent": pct, "surfaces_with_plaque": n_plaque, "surfaces_examined": n_surfaces,
             "teeth_present": len(present), "at_or_below_10_percent": pct <= 10}
    return IndexResult("plaque_control_record", pct, comps, None, " ".join(notes), tuple(trace), (),
                       ("oleary1972", "delia2023"))


def _ohi_component(data: Any, what: str, sites: dict[str, Any]) -> dict[str, tuple[int, int]]:
    """site -> (tooth used, score)."""
    tooth_to_site = {t: s for s, d in sites.items() for t in d["teeth"]}
    out: dict[str, tuple[int, int]] = {}
    for k, v in items(data):
        key = str(k).strip().upper()
        if key in sites:
            site, tooth = key, sites[key]["teeth"][0]
        else:
            tooth = parse_tooth(k)
            if tooth not in tooth_to_site:
                raise InputError(f"{what}: tooth {tooth} is not an OHI-S tooth (16/17/18, 11/21, 26/27/28, "
                                 f"36/37/38, 31/41, 46/47/48)")
            site = tooth_to_site[tooth]
        if is_blank(v):
            continue
        if site in out:
            raise InputError(f"{what}: two scores for the {site} site (teeth {out[site][0]} and {tooth}); "
                             f"score one tooth per site")
        out[site] = (tooth, int_score(v, 0, 3, f"{what} {site}"))
    return out


def ohi_s(debris: Any, calculus: Any = None) -> IndexResult:
    """Simplified Oral Hygiene Index (Greene & Vermillion 1964).

    Six surfaces: buccal of the upper first molars (16, 26), labial of 11 and 31, lingual of the lower
    first molars (36, 46). Where a first molar is not fully erupted or is crowned, the next fully
    erupted molar is scored (17/18, 27/28, 37/38, 47/48); 21 and 41 replace 11 and 31. Give scores
    keyed by tooth number (or site name UR, UA, UL, LL, LA, LR). At least two surfaces are needed.
    DI-S and CI-S = sum / surfaces scored; OHI-S = DI-S + CI-S.
    """
    require_verified("ohi_s")
    tab = codes("ohi_s")
    sites = tab["sites"]
    deb = _ohi_component(debris, "Debris", sites)
    cal = _ohi_component(calculus, "Calculus", sites) if calculus is not None else {}
    trace: list[str] = []
    warnings: list[str] = []
    comps: dict[str, Any] = {}

    def comp(name: str, d: dict[str, tuple[int, int]]) -> float | None:
        if not d:
            return None
        if len(d) < tab["min_surfaces"]:
            raise InputError(f"{name}: at least two of the six surfaces must be scored (Greene & Vermillion 1964)")
        val = sum(s for _, s in d.values()) / len(d)
        trace.append(f"{name} = {sum(s for _, s in d.values())}/{len(d)} surfaces = {fmt_g(val)} "
                     f"(teeth: {', '.join(str(t) for t in sorted(t for t, _ in d.values()))}).")
        return val

    dis = comp("DI-S", deb)
    if dis is None:
        raise InputError("OHI-S needs debris scores for at least two surfaces")
    cis = comp("CI-S", cal)
    comps["DI_S"] = round(dis, 10)
    comps["DI_S_category"] = band(dis, tab["component_bands"], tab["round_to"])
    comps["surfaces_debris"] = len(deb)
    subs = [f"{s}->{deb[s][0]}" for s in sites if s in deb and deb[s][0] != sites[s]["teeth"][0]]
    if subs:
        trace.append("Substituted teeth: " + ", ".join(subs) + ".")
    if cis is None:
        warnings.append("Calculus scores not given: only DI-S is reported.")
        return IndexResult("ohi_s", round(dis, 10), comps, comps["DI_S_category"], None, tuple(trace),
                           tuple(warnings), ("greene1964",))
    comps["CI_S"] = round(cis, 10)
    comps["CI_S_category"] = band(cis, tab["component_bands"], tab["round_to"])
    comps["surfaces_calculus"] = len(cal)
    sd, nd = sum(s for _, s in deb.values()), len(deb)
    sc, nc = sum(s for _, s in cal.values()), len(cal)
    total = (sd * nc + sc * nd) / (nd * nc)  # DI-S + CI-S with a single exact division
    comps["OHI_S"] = round(total, 10)
    trace.append(f"OHI-S = DI-S + CI-S = {fmt_g(total)} (read as {fmt_fixed(_round_half_up(total, 1), 1)}).")
    category = band(total, tab["bands"], tab["round_to"])
    warnings.append("Interpretation bands (good/fair/poor) are a textbook convention, not part of the original index.")
    return IndexResult("ohi_s", round(total, 10), comps, category, None, tuple(trace), tuple(warnings), ("greene1964",))
