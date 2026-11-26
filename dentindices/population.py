"""Population summaries: WHO-style means and prevalences, SiC, SaC, Care and Restorative indices."""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from typing import Any

from ._common import InputError, fmt_fixed, fmt_g, is_blank, number, psum, seq
from ._registry import _round_half_up, band, codes, require_verified
from ._result import IndexResult
from ._stats import t_quantile, wilson

__all__ = ["summarize", "sic", "sac", "care_index", "restorative_index", "component_percentages",
           "who_caries_level"]


def _values(values: Iterable[Any], what: str = "values") -> list[float]:
    out: list[float] = []
    for v in seq(values, what):
        if isinstance(v, IndexResult):
            v = v.value
        if is_blank(v):
            continue
        out.append(number(v, what))
    return out


def _r(x: float | None, nd: int = 10) -> float | None:
    return None if x is None else round(x, nd)


def summarize(values: Iterable[Any], *, weights: Iterable[Any] | None = None, confidence: float = 0.95,
              label: str = "value") -> dict[str, Any]:
    """Descriptive statistics in the form WHO 2013 asks for: n, mean, SD, SE and a t-based confidence
    interval for the mean; median and range; and the prevalence of values above zero (e.g. DMFT > 0)
    with a Wilson interval.

    ``weights`` gives survey-weighted point estimates (mean and prevalence) only. Standard errors for
    complex samples (strata, clusters) need design-based methods; use survey software for those.
    Missing values (None or blank) are dropped.
    """
    confidence = number(confidence, "confidence")
    if not 0 < confidence < 1:
        raise InputError("confidence must be between 0 and 1")
    vals = seq(values, "values")
    if weights is not None:
        w = seq(weights, "weights")
        if len(w) != len(vals):
            raise InputError("weights must have the same length as values")
        vals = [v.value if isinstance(v, IndexResult) else v for v in vals]
        pairs = [(v, ww) for v, ww in zip(vals, w) if not is_blank(v)]
        x = _values([p[0] for p in pairs])
        wv = [number(p[1], "weight", 0) for p in pairs]
    else:
        x = _values(vals)
        wv = None
    n = len(x)
    out: dict[str, Any] = {"label": label, "n": n}
    if n == 0:
        out.update({"mean": None, "sd": None, "se": None, "ci_low": None, "ci_high": None, "median": None,
                    "min": None, "max": None, "n_positive": 0, "prevalence": None, "prevalence_ci_low": None,
                    "prevalence_ci_high": None})
        return out
    mean = psum(x) / n
    sd = math.sqrt(psum((v - mean) ** 2 for v in x) / (n - 1)) if n > 1 else None
    se = sd / math.sqrt(n) if sd is not None else None
    if se is not None:
        tq = t_quantile(1 - (1 - confidence) / 2, n - 1)
        lo, hi = mean - tq * se, mean + tq * se
    else:
        lo = hi = None
    s = sorted(x)
    median = s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2
    pos = sum(1 for v in x if v > 0)
    plo, phi = wilson(pos, n, confidence)
    out.update({"mean": _r(mean), "sd": _r(sd), "se": _r(se), "ci_low": _r(lo), "ci_high": _r(hi),
                "median": median, "min": s[0], "max": s[-1], "n_positive": pos,
                "prevalence": _r(100 * pos / n), "prevalence_ci_low": _r(100 * plo),
                "prevalence_ci_high": _r(100 * phi), "confidence": confidence})
    if wv is not None:
        tw = psum(wv)
        if tw <= 0:
            raise InputError("weights must not all be zero")
        out["weighted_mean"] = _r(psum(v * ww for v, ww in zip(x, wv)) / tw)
        out["weighted_prevalence"] = _r(100 * psum(ww for v, ww in zip(x, wv) if v > 0) / tw)
        out["weights_note"] = ("Weighted point estimates only; use design-based methods for standard errors "
                               "of complex survey samples.")
    return out


def sic(values: Iterable[Any], *, fraction: float = 1 / 3, rounding: str = "nearest") -> IndexResult:
    """Significant Caries Index (Bratthall 2000): the mean DMFT of the third of the group with the
    highest DMFT. ``fraction=0.1`` gives the SiC10 variant (top tenth).

    ``rounding`` sizes the group when ``n x fraction`` is not whole: ``"nearest"`` (default, halves
    up), ``"ceil"``, ``"floor"``, or ``"fractional"`` (the boundary person counts with a partial weight).
    """
    require_verified("sic")
    x = _values(values, "DMFT")
    fraction = number(fraction, "fraction")
    if not 0 < fraction <= 1:
        raise InputError("fraction must be in (0, 1]")
    if rounding not in ("nearest", "ceil", "floor", "fractional"):
        raise InputError("rounding must be 'nearest', 'ceil', 'floor' or 'fractional'")
    n = len(x)
    if n == 0:
        raise InputError("SiC needs at least one value")
    s = sorted(x, reverse=True)
    exact = n * fraction
    warnings: list[str] = []
    trace = [f"{n} values sorted from highest to lowest; {fmt_g(fraction)} of the group = {fmt_g(exact)} people."]
    if rounding == "fractional":
        whole = int(math.floor(exact + 1e-12))
        part = exact - whole
        total = psum(s[:whole]) + (part * s[whole] if part > 1e-12 and whole < n else 0.0)
        value = total / exact
        k = exact
        group = s[: whole + (1 if part > 1e-12 else 0)]
        trace.append(f"Top {whole} values plus {fmt_g(part)} of the next one, divided by {fmt_g(exact)}.")
    else:
        if rounding == "nearest":
            k = int(math.floor(exact + 0.5 + 1e-12))
        elif rounding == "ceil":
            k = int(math.ceil(exact - 1e-12))
        else:
            k = int(math.floor(exact + 1e-12))
        k = max(1, min(n, k))
        group = s[:k]
        value = psum(group) / k
        trace.append(f"Group size {k} ({rounding}); SiC = mean of the top {k} = {fmt_g(value)}.")
    zeros = sum(1 for v in group if v == 0)
    if zeros:
        warnings.append(f"The top group includes {zeros} caries-free people (DMFT = 0): caries prevalence is "
                        f"below {fraction:.0%}. Report the SaC as well (Schmoeckel 2019).")
    comps = {"SiC": _r(value), "n": n, "group_size": k, "fraction": fraction, "rounding": rounding,
             "group_min": min(group), "caries_free_in_group": zeros}
    return IndexResult("sic", _r(value), comps, None, None, tuple(trace), tuple(warnings),
                       ("bratthall2000", "nishi2002"))


def sac(values: Iterable[Any]) -> IndexResult:
    """Specific affected Caries Index (Schmoeckel 2019): mean DMFT among people with DMFT > 0."""
    require_verified("sac")
    x = _values(values, "DMFT")
    if not x:
        raise InputError("SaC needs at least one value")
    affected = [v for v in x if v > 0]
    n = len(x)
    value = psum(affected) / len(affected) if affected else None
    trace = [f"{len(affected)} of {n} people have DMFT > 0 ({fmt_fixed(100 * len(affected) / n, 1)}%).",
             (f"SaC = mean DMFT of the affected = {fmt_g(value)}." if value is not None else
              "SaC is undefined: nobody has caries experience.")]
    comps = {"SaC": _r(value), "n": n, "n_affected": len(affected), "prevalence": _r(100 * len(affected) / n)}
    return IndexResult("sac", _r(value), comps, None, None, tuple(trace), (), ("schmoeckel2019",))


def _dmf_parts(records: Iterable[Any]) -> tuple[float, float, float, int, str]:
    sd = sm = sf = 0.0
    n = 0
    kind = None
    for rec in seq(records, "records"):
        if isinstance(rec, IndexResult):
            rec = rec.components
        if not isinstance(rec, Mapping):
            raise InputError("Give DMFT results (from dmft_permanent/dmft_primary) or mappings with DT, MT, FT")
        if all(k in rec for k in ("DT", "MT", "FT")):
            keys, k2 = ("DT", "MT", "FT"), "permanent"
        elif all(k in rec for k in ("dt", "mt", "ft")):
            keys, k2 = ("dt", "mt", "ft"), "primary"
        elif all(k in rec for k in ("D", "M", "F")):
            keys, k2 = ("D", "M", "F"), "permanent"
        else:
            raise InputError("Each record needs DT, MT and FT (or dt, mt, ft)")
        if kind is None:
            kind = k2
        elif kind != k2:
            raise InputError("Do not mix permanent and primary records")
        sd += number(rec[keys[0]], keys[0], 0)
        sm += number(rec[keys[1]], keys[1], 0)
        sf += number(rec[keys[2]], keys[2], 0)
        n += 1
    if n == 0:
        raise InputError("No records given")
    return sd, sm, sf, n, kind or "permanent"


def care_index(records: Iterable[Any]) -> IndexResult:
    """Care Index (Walsh 1970): FT / DMFT x 100 for a group (or one person): the share of caries
    experience that has been restored."""
    require_verified("care_index")
    d, m, f, n, kind = _dmf_parts(records)
    total = d + m + f
    value = _r(100 * f / total) if total else None
    lbl = "ft/dmft" if kind == "primary" else "FT/DMFT"
    trace = [f"{n} records: sum D = {fmt_g(d)}, M = {fmt_g(m)}, F = {fmt_g(f)}.",
             (f"Care Index = {lbl} x 100 = {fmt_g(f)}/{fmt_g(total)} x 100 = {fmt_fixed(value, 1)}%." if value is not None
              else "Care Index is undefined (no caries experience).")]
    return IndexResult("care_index", value, {"care_index": value, "n": n, "F": f, "DMF": total, "dentition": kind},
                       None, None, tuple(trace), (), ("walsh1970", "gupta2017"))


def restorative_index(records: Iterable[Any]) -> IndexResult:
    """Restorative Index (Jackson 1973): FT / (DT + FT) x 100: the share of decayed-or-filled teeth
    that are filled (missing teeth left out)."""
    require_verified("restorative_index")
    d, m, f, n, kind = _dmf_parts(records)
    den = d + f
    value = _r(100 * f / den) if den else None
    trace = [f"{n} records: sum D = {fmt_g(d)}, F = {fmt_g(f)}.",
             (f"Restorative Index = F/(D+F) x 100 = {fmt_g(f)}/{fmt_g(den)} x 100 = {fmt_fixed(value, 1)}%." if value is not None
              else "Restorative Index is undefined (no decayed or filled teeth).")]
    return IndexResult("restorative_index", value, {"restorative_index": value, "n": n, "D": d, "F": f,
                       "dentition": kind}, None, None, tuple(trace), (), ("jackson1973", "gupta2017"))


def component_percentages(records: Iterable[Any]) -> dict[str, Any]:
    """WHO 2013 'contribution of each component': %D/DMFT, %M/DMFT and %F/DMFT for a group."""
    d, m, f, n, kind = _dmf_parts(records)
    total = d + m + f
    if not total:
        return {"n": n, "dentition": kind, "percent_D": None, "percent_M": None, "percent_F": None}
    return {"n": n, "dentition": kind, "percent_D": _r(100 * d / total), "percent_M": _r(100 * m / total),
            "percent_F": _r(100 * f / total)}


def _printed_band(b: dict[str, Any]) -> str:
    if "below" in b:
        return f"< {fmt_fixed(b['below'], 1)}"
    if "above" in b:
        return f"> {fmt_fixed(b['above'], 1)}"
    return f"{fmt_fixed(b['from'], 1)}-{fmt_fixed(b['upto'], 1)}"


def _who_level(x: float, bands: list[dict[str, Any]]) -> dict[str, Any] | None:
    for b in bands:
        if ("below" in b and x < b["below"]) or ("above" in b and x > b["above"]) or \
                ("from" in b and b["from"] - 1e-12 <= x <= b["upto"] + 1e-12):
            return b
    return None


def who_caries_level(mean_dmft: Any, age_group: str = "12") -> IndexResult:
    """WHO 2013 level of caries experience for a group mean DMFT: 12-year-olds (very low < 1.2 ...
    very high > 6.5) or adults aged 35-44 (very low < 5.0 ... high > 13.9). The unrounded mean is
    compared with the printed limits; a mean between two printed bands is read to one decimal."""
    require_verified("who_caries_level")
    tab = codes("who_caries_levels")
    key = str(age_group).replace("\u2013", "-").strip()
    if key not in ("12", "35-44"):
        raise InputError("age_group must be '12' or '35-44' (the WHO indicator ages with published levels)")
    v = number(mean_dmft, "mean DMFT", 0)
    b = _who_level(v, tab[key])
    if b is None:
        rv = _round_half_up(v, tab["gap_round_to"])
        b = _who_level(rv, tab[key])
        trace = [f"Mean DMFT {fmt_g(v)} falls between two printed WHO 2013 bands, so it is read to one decimal as "
                 f"{fmt_fixed(rv, 1)}: {_printed_band(b)} -> {b['label']} (age {key})."]
    else:
        trace = [f"Mean DMFT {fmt_g(v)} is in the WHO 2013 band {_printed_band(b)} -> {b['label']} (age {key})."]
    label = b["label"]
    return IndexResult("who_caries_level", label, {"mean_dmft": v, "age_group": key}, label, None,
                       tuple(trace), (), ("who2013",))
