"""Dental fluorosis: Dean's index person score (WHO 2013 coding) and the Community Fluorosis Index."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ._common import InputError, fmt_g, is_blank, items, norm_code, seq, teeth_list
from ._registry import band, codes, require_verified
from ._result import IndexResult
from ._teeth import parse_tooth

__all__ = ["dean_index", "community_fluorosis_index"]

_LABEL_TO_WHO = {"NORMAL": "0", "QUESTIONABLE": "1", "VERY MILD": "2", "VERYMILD": "2", "MILD": "3",
                 "MODERATE": "4", "SEVERE": "5"}
_DEAN_TO_WHO = {"0": "0", "0.0": "0", "0.5": "1", "1": "2", "1.0": "2", "2": "3", "2.0": "3", "3": "4",
                "3.0": "4", "4": "5", "4.0": "5"}


def _who_code(v: Any, scale: str, what: str) -> str | None:
    """Return a WHO 2013 fluorosis code 0-5, or None for 8 (excluded), 9 (not recorded) or blank."""
    if is_blank(v):
        return None
    if isinstance(v, IndexResult):
        return v.components["who_code"]
    if scale == "dean" and isinstance(v, (int, float)) and not isinstance(v, bool):
        key = repr(float(v))
        if key in _DEAN_TO_WHO:
            return _DEAN_TO_WHO[key]
        raise InputError(f"{what}: {v!r} is not a Dean weight (0, 0.5, 1, 2, 3, 4)")
    s = norm_code(v)
    if s in _LABEL_TO_WHO:
        return _LABEL_TO_WHO[s]
    if scale == "who":
        if s in ("8", "9"):
            return None
        if s in ("0", "1", "2", "3", "4", "5"):
            return s
        raise InputError(f"{what}: {v!r} is not a WHO 2013 fluorosis code (0-5, 8, 9)")
    if scale == "dean":
        if s in _DEAN_TO_WHO:
            return _DEAN_TO_WHO[s]
        raise InputError(f"{what}: {v!r} is not a Dean weight (0, 0.5, 1, 2, 3, 4)")
    raise InputError("scale must be 'who' (codes 0-5) or 'dean' (weights 0, 0.5, 1, 2, 3, 4)")


def dean_index(teeth: Any, *, scale: str = "who") -> IndexResult:
    """Person score of Dean's fluorosis index from per-tooth scores (WHO 2013 recording rule).

    ``teeth`` maps teeth to WHO codes (0 normal, 1 questionable, 2 very mild, 3 mild, 4 moderate,
    5 severe; 8 excluded, 9 not recorded) or, with ``scale="dean"``, to Dean's weights. The score is
    based on the two most affected teeth; if they differ, the less affected of the two is recorded.
    """
    require_verified("dean_index")
    tab = codes("dean")
    scored: dict[int, str] = {}
    for k, v in items(teeth):
        t = parse_tooth(k)
        if t in scored:
            raise InputError(f"Tooth {t} appears more than once")
        c = _who_code(v, scale, f"tooth {t}")
        if c is not None:
            scored[t] = c
    if not scored:
        raise InputError("Dean's index: no tooth was scored")
    ranked = sorted(scored.items(), key=lambda kv: (-int(kv[1]), kv[0]))
    warnings: list[str] = []
    if len(ranked) == 1:
        code = ranked[0][1]
        warnings.append("Only one tooth was scored; Dean's index is based on the two most affected teeth.")
        trace = [f"Single tooth scored: {ranked[0][0]} = {code}."]
    else:
        (t1, c1), (t2, c2) = ranked[0], ranked[1]
        code = c2
        trace = [f"Two most affected teeth: {t1} ({tab['who_codes'][c1]}) and {t2} ({tab['who_codes'][c2]}).",
                 f"Person score = the less affected of the two = {code} ({tab['who_codes'][code]})."]
    weight = tab["dean_weights"][code]
    comps = {"who_code": code, "dean_weight": weight, "label": tab["who_codes"][code],
             "teeth_scored": len(scored), "fluorosis_present": int(code) >= 2}
    return IndexResult("dean_index", int(code), comps, tab["who_codes"][code], None, tuple(trace),
                       tuple(warnings), ("who2013", "dean1934", "dean1942"))


def community_fluorosis_index(person_scores: Iterable[Any], *, scale: str = "who") -> IndexResult:
    """Community Fluorosis Index (Dean 1942): the mean of the person scores weighted 0 (normal),
    0.5 (questionable), 1 (very mild), 2 (mild), 3 (moderate) and 4 (severe), with Dean's public-health
    reading (negative <=0.4, borderline <=0.6, slight <=1.0, medium <=2.0, marked <=3.0, very marked
    <=4.0). A CFI above 0.6 indicates a public-health problem.

    ``person_scores``: one WHO code (0-5) per person, results of :func:`dean_index`, or Dean weights
    with ``scale="dean"``. Codes 8 and 9 are left out.
    """
    require_verified("community_fluorosis_index")
    tab = codes("cfi")
    weights = codes("dean")["dean_weights"]
    labels = codes("dean")["who_codes"]
    cs = [c for c in (_who_code(v, scale, "person score") for v in seq(person_scores, "person_scores")) if c is not None]
    if not cs:
        raise InputError("CFI: no person scores")
    n = len(cs)
    total = sum(weights[c] for c in cs)
    cfi = total / n
    category = band(cfi, tab["bands"])
    dist = {labels[c]: sum(1 for x in cs if x == c) for c in ("0", "1", "2", "3", "4", "5")}
    trace = ["Counts: " + ", ".join(f"{k} {v}" for k, v in dist.items()) + ".",
             f"CFI = sum of weights / n = {fmt_g(total)}/{n} = {fmt_g(cfi)} -> {category}."]
    comps = {"CFI": round(cfi, 10), "n": n, "distribution": dist,
             "public_health_problem": cfi > tab["public_health_problem_above"]}
    return IndexResult("community_fluorosis_index", round(cfi, 10), comps, category, None, tuple(trace), (),
                       ("dean1942", "who2013"))


_ = teeth_list
