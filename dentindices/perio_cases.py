"""Periodontitis case definitions for surveys: CDC/AAP (Eke et al. 2012) and ACES (Holtfreter et al.
2024, the 2018 EFP/AAP classification applied to epidemiological data), plus continuous summary
measures. All work on a full-mouth chart of probing depth (PD), clinical attachment level (CAL)
and bleeding on probing (BOP) at up to six sites per tooth."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from ._common import (
    InputError, age_value, fmt_fixed, fmt_g, is_blank, items, number, psum, teeth_list, teeth_set, tooth_map,
)
from ._registry import codes, require_verified
from ._result import IndexResult
from ._teeth import (
    SECOND_MOLARS,
    has_non_adjacent_pair,
    is_permanent,
    is_third_molar,
    opposing_pairs,
    parse_tooth,
    position,
)

__all__ = ["PerioChart", "perio_chart", "cdc_aap", "aces", "perio_summary"]

SITES = ("MB", "B", "DB", "ML", "L", "DL")
INTERPROXIMAL = ("MB", "DB", "ML", "DL")
MID = ("B", "L")
_SITE_ALIASES = {
    "MB": "MB", "MF": "MB", "MESIOBUCCAL": "MB", "MESIOFACIAL": "MB",
    "B": "B", "F": "B", "MB_MID": "B", "BUCCAL": "B", "FACIAL": "B", "MIDBUCCAL": "B", "MIDFACIAL": "B",
    "DB": "DB", "DF": "DB", "DISTOBUCCAL": "DB", "DISTOFACIAL": "DB",
    "ML": "ML", "MP": "ML", "MO": "ML", "MESIOLINGUAL": "ML", "MESIOPALATAL": "ML", "MESIO-ORAL": "ML",
    "L": "L", "P": "L", "O": "L", "LINGUAL": "L", "PALATAL": "L", "ORAL": "L", "MIDLINGUAL": "L", "MIDORAL": "L",
    "DL": "DL", "DP": "DL", "DO": "DL", "DISTOLINGUAL": "DL", "DISTOPALATAL": "DL", "DISTO-ORAL": "DL",
}


def _site(s: Any) -> str:
    key = str(s).strip().upper().replace(" ", "")
    if key not in _SITE_ALIASES:
        raise InputError(f"Unknown probing site {s!r}; use MB, B, DB, ML, L, DL")
    return _SITE_ALIASES[key]


def _bool(v: Any, what: str) -> bool | None:
    if is_blank(v):
        return None
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in ("1", "true", "yes", "y", "+"):
        return True
    if s in ("0", "false", "no", "n"):
        return False
    raise InputError(f"{what}: {v!r} is not yes/no (use True/False or 1/0)")


class PerioChart:
    """A periodontal chart: per tooth and site, PD (mm), CAL (mm) and BOP.

    Build it with :func:`perio_chart` from either
    ``{tooth: {"pd": {site: mm}, "cal": {site: mm}, "bop": {site: True/False}}}`` or a list of rows
    ``{"tooth": 16, "site": "MB", "pd": 4, "cal": 3, "bop": 1}`` (long format, e.g. from a CSV file).
    Sites: MB, B, DB, ML, L, DL (aliases such as MP, DP, P for palatal are accepted).
    """

    def __init__(self) -> None:
        self.pd: dict[int, dict[str, float]] = {}
        self.cal: dict[int, dict[str, float]] = {}
        self.bop: dict[int, dict[str, bool]] = {}

    @property
    def teeth(self) -> list[int]:
        return sorted(set(self.pd) | set(self.cal) | set(self.bop))

    def _put(self, store: dict, t: int, s: str, v: Any) -> None:
        d = store.setdefault(t, {})
        if s in d:
            raise InputError(f"Tooth {t} site {s} is recorded twice")
        d[s] = v

    def add(self, tooth: Any, site: Any, pd: Any = None, cal: Any = None, bop: Any = None) -> None:
        t = parse_tooth(tooth)
        if not is_permanent(t):
            raise InputError(f"Periodontal charts here use permanent teeth; {t} is a primary tooth")
        s = _site(site)
        if not is_blank(pd):
            self._put(self.pd, t, s, number(pd, f"PD tooth {t} {s}", 0, 20))
        if not is_blank(cal):
            c = number(cal, f"CAL tooth {t} {s}", None, 25)
            if c < 0:
                raise InputError(f"CAL tooth {t} {s}: {cal!r} is negative; record attachment loss as 0 when the "
                                 f"CEJ is not exposed (as NHANES does)")
            self._put(self.cal, t, s, c)
        b = _bool(bop, f"BOP tooth {t} {s}")
        if b is not None:
            self._put(self.bop, t, s, b)

    def without_third_molars(self) -> "PerioChart":
        c = PerioChart()
        c.pd = {t: dict(v) for t, v in self.pd.items() if not is_third_molar(t)}
        c.cal = {t: dict(v) for t, v in self.cal.items() if not is_third_molar(t)}
        c.bop = {t: dict(v) for t, v in self.bop.items() if not is_third_molar(t)}
        return c


def perio_chart(data: Any) -> PerioChart:
    """Build a :class:`PerioChart` from a nested mapping or long-format rows (see the class doc)."""
    if isinstance(data, PerioChart):
        return data
    ch = PerioChart()
    if isinstance(data, Mapping):
        for k, v in data.items():
            if not isinstance(v, Mapping):
                raise InputError(f"Tooth {k}: expected {{'pd': {{site: mm}}, 'cal': {{...}}, 'bop': {{...}}}}")
            keys = {str(x).lower(): x for x in v}
            unknown = [x for x in keys if x not in ("pd", "cal", "bop")]
            if unknown:
                raise InputError(f"Tooth {k}: unknown measures {unknown}; use pd, cal, bop")
            sites: set[str] = set()
            per: dict[str, dict[str, Any]] = {}
            for m in ("pd", "cal", "bop"):
                if m in keys:
                    block = v[keys[m]]
                    if not isinstance(block, Mapping):
                        raise InputError(f"Tooth {k} {m}: expected a mapping of site -> value")
                    for sk, sv in block.items():
                        s = _site(sk)
                        if s in per.get(m, {}):
                            raise InputError(f"Tooth {k} {m}: site {s} given twice")
                        per.setdefault(m, {})[s] = sv
                        sites.add(s)
            for s in sites:
                ch.add(k, s, per.get("pd", {}).get(s), per.get("cal", {}).get(s), per.get("bop", {}).get(s))
        return ch
    if isinstance(data, Iterable) and not isinstance(data, (str, bytes)):
        for row in data:
            if not isinstance(row, Mapping):
                raise InputError("Each row must be a mapping with tooth, site, pd, cal, bop")
            r = {str(k).strip().lower(): v for k, v in row.items()}
            if "tooth" not in r or "site" not in r:
                raise InputError("Each row needs 'tooth' and 'site'")
            ch.add(r["tooth"], r["site"], r.get("pd"), r.get("cal"), r.get("bop"))
        return ch
    raise InputError("Give the chart as a mapping per tooth or as a list of rows")


def _present(chart: PerioChart, teeth_present: Any) -> set[int]:
    if teeth_present is None:
        return set(chart.teeth)
    out = {t for t in teeth_set(teeth_present) if is_permanent(t)}
    missing = [t for t in chart.teeth if t not in out]
    if missing:
        raise InputError(f"Teeth {teeth_list(missing)} have measurements but are not in teeth_present")
    return out


def _sites_over(store: dict[int, dict[str, float]], sites: tuple[str, ...], threshold: float,
                strict: bool = False) -> list[tuple[int, str]]:
    out = []
    for t, d in store.items():
        for s in sites:
            if s in d and (d[s] > threshold if strict else d[s] >= threshold - 1e-9):
                out.append((t, s))
    return out


def _teeth(sites: list[tuple[int, str]]) -> set[int]:
    return {t for t, _ in sites}


# --------------------------------------------------------------------------------------------
def perio_summary(chart: Any, *, include_third_molars: bool = False) -> IndexResult:
    """Continuous measures recommended alongside case definitions (Holtfreter 2015, 2024): mean and
    maximum PD and CAL, and the percentage of sites at or above common thresholds."""
    require_verified("perio_summary")
    ch = perio_chart(chart)
    if not include_third_molars:
        ch = ch.without_third_molars()
    pds = [v for d in ch.pd.values() for v in d.values()]
    cals = [v for d in ch.cal.values() for v in d.values()]
    bops = [v for d in ch.bop.values() for v in d.values()]

    def pct(xs: list[float], th: float) -> float | None:
        return round(100 * sum(1 for x in xs if x >= th - 1e-9) / len(xs), 10) if xs else None

    comps = {
        "teeth": len(ch.teeth), "sites_pd": len(pds), "sites_cal": len(cals), "sites_bop": len(bops),
        "mean_pd": round(psum(pds) / len(pds), 10) if pds else None, "max_pd": max(pds) if pds else None,
        "mean_cal": round(psum(cals) / len(cals), 10) if cals else None, "max_cal": max(cals) if cals else None,
        "percent_sites_pd_4plus": pct(pds, 4), "percent_sites_pd_6plus": pct(pds, 6),
        "percent_sites_cal_3plus": pct(cals, 3), "percent_sites_cal_5plus": pct(cals, 5),
        "percent_sites_bop": round(100 * sum(bops) / len(bops), 10) if bops else None,
        "third_molars_included": include_third_molars,
    }
    trace = [f"{len(ch.teeth)} teeth; {len(pds)} PD, {len(cals)} CAL and {len(bops)} BOP site measurements"
             f"{'' if include_third_molars else ' (third molars excluded)'}."]
    return IndexResult("perio_summary", comps["mean_cal"], comps, None, None, tuple(trace), (),
                       ("holtfreter2015", "holtfreter2024"))


# --------------------------------------------------------------------------------------------
def cdc_aap(chart: Any, *, teeth_present: Any = None, mild_cal_distinct_teeth: bool = True,
            mild_pd5_any_site: bool = False) -> IndexResult:
    """CDC/AAP case definitions for population surveillance (Page & Eke 2007; Eke et al. 2012).

    Interproximal sites (MB, DB, ML, DL) only; third molars excluded.

    * Severe: >=2 interproximal sites with CAL >= 6 mm (not on the same tooth) and >=1 interproximal
      site with PD >= 5 mm.
    * Moderate: >=2 interproximal sites with CAL >= 4 mm (not on the same tooth), or >=2 interproximal
      sites with PD >= 5 mm (not on the same tooth).
    * Mild: >=2 interproximal sites with CAL >= 3 mm and >=2 interproximal sites with PD >= 4 mm (not
      on the same tooth), or one site with PD >= 5 mm.

    By default the two CAL >= 3 mm sites of the mild definition must also be on different teeth;
    set ``mild_cal_distinct_teeth=False`` for the looser, literal reading, which gives a slightly
    higher prevalence. The "one site with PD >= 5 mm" of the mild definition is read as an
    interproximal site, like every other criterion; ``mild_pd5_any_site=True`` counts buccal and
    lingual sites too (see the registry's discrepancies).
    People with no teeth are 'edentulous'; fewer than two teeth with interproximal CAL are
    'non-classified'.
    """
    require_verified("cdc_aap")
    tab = codes("cdc_aap")
    ch0 = perio_chart(chart)
    present = {t for t in _present(ch0, teeth_present) if not is_third_molar(t)}
    ch = ch0.without_third_molars()
    ip = tuple(tab["interproximal_sites"])
    trace = ["Interproximal sites only (MB, DB, ML, DL); third molars excluded."]
    teeth_with_cal = {t for t, d in ch.cal.items() if any(s in d for s in ip)}

    def result(value: str, category: str, comps: dict[str, Any], warn: tuple[str, ...] = ()) -> IndexResult:
        comps.setdefault("total_periodontitis", value in ("mild", "moderate", "severe"))
        comps.setdefault("moderate_or_severe", value in ("moderate", "severe"))
        return IndexResult("cdc_aap", value, comps, category, None, tuple(trace), warn, ("page2007", "eke2012"))

    if not present:
        trace.append("No natural teeth (third molars aside): edentulous.")
        return result("edentulous", "Edentulous", {"teeth_with_interproximal_cal": 0})
    if len(teeth_with_cal) < 2:
        trace.append(f"Only {len(teeth_with_cal)} tooth/teeth with interproximal CAL: non-classified.")
        return result("non-classified", "Non-classified", {"teeth_with_interproximal_cal": len(teeth_with_cal)})
    sv, md, ml = tab["severe"], tab["moderate"], tab["mild"]
    cal6 = _sites_over(ch.cal, ip, sv["cal_mm"])
    pd5 = _sites_over(ch.pd, ip, sv["pd_mm"])
    cal4 = _sites_over(ch.cal, ip, md["cal_mm"])
    cal3 = _sites_over(ch.cal, ip, ml["cal_mm"])
    pd4 = _sites_over(ch.pd, ip, ml["pd_mm"])
    severe = len(_teeth(cal6)) >= sv["cal_teeth"] and len(pd5) >= sv["pd_sites"]
    moderate = len(_teeth(cal4)) >= md["cal_teeth"] or len(_teeth(pd5)) >= md["pd_teeth"]
    cal3_ok = (len(_teeth(cal3)) if mild_cal_distinct_teeth else len(cal3)) >= ml["cal_sites"]
    pd5_mild = _sites_over(ch.pd, tuple(SITES), sv["pd_mm"]) if mild_pd5_any_site else pd5
    mild = cal3_ok and (len(_teeth(pd4)) >= ml["pd_teeth"] or len(pd5_mild) >= 1)
    trace.append(f"Teeth with interproximal CAL >= 6: {teeth_list(_teeth(cal6))}; sites with PD >= 5: {len(pd5)}.")
    trace.append(f"Teeth with interproximal CAL >= 4: {teeth_list(_teeth(cal4))}; teeth with PD >= 5: "
                 f"{teeth_list(_teeth(pd5))}.")
    trace.append(f"CAL >= 3: {len(cal3)} sites on {len(_teeth(cal3))} teeth; teeth with PD >= 4: "
                 f"{teeth_list(_teeth(pd4))}.")
    if severe:
        value, cat = "severe", "Severe periodontitis"
    elif moderate:
        value, cat = "moderate", "Moderate periodontitis"
    elif mild:
        value, cat = "mild", "Mild periodontitis"
    else:
        value, cat = "no periodontitis", "No periodontitis"
    trace.append(f"Classification: {cat} (severe {severe}, moderate {moderate}, mild {mild}).")
    comps = {"severe_criteria": severe, "moderate_criteria": moderate, "mild_criteria": mild,
             "teeth_with_interproximal_cal": len(teeth_with_cal),
             "teeth_cal6": len(_teeth(cal6)), "sites_pd5": len(pd5), "teeth_cal4": len(_teeth(cal4)),
             "teeth_pd5": len(_teeth(pd5)), "sites_cal3": len(cal3), "teeth_cal3": len(_teeth(cal3)),
             "teeth_pd4": len(_teeth(pd4)), "mild_cal_distinct_teeth": bool(mild_cal_distinct_teeth),
             "mild_pd5_any_site": bool(mild_pd5_any_site)}
    warn = ()
    sites_per_tooth = [len([s for s in ip if s in d]) for d in ch.cal.values()]
    if sites_per_tooth and min(sites_per_tooth) < 4:
        warn = ("Some teeth have fewer than four interproximal sites recorded (partial recording lowers "
                "CDC/AAP prevalence).",)
    return result(value, cat, comps, warn)


# --------------------------------------------------------------------------------------------
_LOSS = {"0": 0, "NONE": 0, "1-4": 1, "1–4": 1, ">=5": 5, "≥5": 5, "5+": 5, "UNKNOWN": None}


def _teeth_lost(v: Any) -> int | None:
    """Teeth lost to periodontitis: an int, '0', '1-4', '>=5' or 'unknown' -> 0, 1 (1-4), 5 (>=5) or None."""
    if v is None:
        return None
    if isinstance(v, bool):
        raise InputError("teeth_lost_to_periodontitis must be a number or '0', '1-4', '>=5', 'unknown'")
    if isinstance(v, int):
        if v < 0 or v > 28:
            raise InputError("teeth_lost_to_periodontitis must be 0-28")
        return 0 if v == 0 else (1 if v <= 4 else 5)
    s = str(v).strip().upper().replace(" ", "")
    if s in _LOSS:
        return _LOSS[s]
    if s.isascii() and s.isdigit():
        return _teeth_lost(int(s))
    raise InputError(f"teeth_lost_to_periodontitis: {v!r}; use a number or '0', '1-4', '>=5', 'unknown'")


def _grade(base_ratio: float | None, cigarettes: Any, smoker: Any, diabetes: Any, hba1c: Any,
           trace: list[str], warnings: list[str]) -> tuple[str, str, bool]:
    g = codes("grade")
    order = "ABC"
    if base_ratio is None:
        grade = g["default"]
        basis = "assumed grade B (no evidence of progression available)"
        assumed = True
        trace.append("Grade: no bone-loss/age evidence, so grade B is assumed (Tonetti 2018).")
    else:
        r = g["bone_loss_age_ratio"]
        grade = "A" if base_ratio < r["A_below"] else ("B" if base_ratio <= r["B_upto"] + 1e-12 else "C")
        basis = f"bone loss/age ratio {fmt_fixed(base_ratio, 3)}"
        assumed = False
        trace.append(f"Grade from indirect evidence: %bone loss / age = {fmt_fixed(base_ratio, 3)} -> grade {grade} "
                     f"(A < {fmt_g(r['A_below'])}, B {fmt_g(r['A_below'])}-{fmt_g(r['B_upto'])}, C > {fmt_g(r['B_upto'])}).")
    # smoking modifier
    cig = None
    if cigarettes is not None and not is_blank(cigarettes):
        cig = number(cigarettes, "cigarettes per day", 0, 200)
    sm = _bool(smoker, "smoker") if smoker is not None else None
    if cig is None and sm is True:
        warnings.append("Smoker without cigarettes per day: the smoking modifier needs the daily amount; "
                        "grade B is the minimum applied.")
        mod = "B"
    elif cig is None:
        mod = None
    else:
        mod = "A" if cig == 0 else ("B" if cig < g["smoking_cigarettes_per_day_C"] else "C")
    if mod and order.index(mod) > order.index(grade):
        trace.append(f"Smoking ({'unknown amount' if cig is None else f'{fmt_g(cig)}/day'}) raises the grade to {mod}.")
        grade = mod
    # diabetes modifier
    dm = _bool(diabetes, "diabetes") if diabetes is not None else None
    hb = number(hba1c, "HbA1c (%)", 3, 20) if hba1c is not None and not is_blank(hba1c) else None
    if dm:
        if hb is None:
            warnings.append("Diabetes without HbA1c: grade B is the minimum applied; give HbA1c to apply the "
                            "full modifier.")
            dmod = "B"
        else:
            dmod = "B" if hb < g["hba1c_percent_C"] else "C"
        if order.index(dmod) > order.index(grade):
            trace.append(f"Diabetes (HbA1c {'unknown' if hb is None else f'{fmt_g(hb)}%'}) raises the grade to {dmod}.")
            grade = dmod
    return grade, basis, assumed


def aces(chart: Any, *, survey: str = "completed", teeth_present: Any = None, age: Any = None,
         bleeding_percent: Any = None, furcation_class_2_3: Any = None, vertical_bone_loss_3mm: Any = None,
         teeth_lost_to_periodontitis: Any = None, mobility_degree2_at_2_teeth: Any = None,
         bite_collapse_drifting_flaring: Any = None, bone_loss_percent: Any = None,
         root_length_mm: Any = None, cigarettes_per_day: Any = None, smoker: Any = None,
         diabetes: Any = None, hba1c: Any = None) -> IndexResult:
    """ACES (Holtfreter et al. 2024): the 2018 EFP/AAP classification applied to survey data.

    Classifies a person as edentulous, non-classified, periodontal health, localized or generalized
    gingivitis, or periodontitis with stage (I-IV), extent and grade (A-C).

    * ``survey="completed"`` (default) follows ACES Figure 2: stage from maximum interdental CAL,
      upstaged II -> III by PD >= 6 mm at >= 2 non-adjacent teeth (third molars and distal sites of
      second molars disregarded), furcation class II/III or vertical bone loss >= 3 mm, and III -> IV
      when fewer than 10 opposing pairs of natural teeth remain. Tooth loss is not used.
    * ``survey="planned"`` follows ACES Figure 3 and also uses teeth lost to periodontitis
      (0, 1-4, >=5 or unknown), tooth mobility degree >= 2 at >= 2 teeth and bite collapse, drifting
      or flaring.

    Health vs gingivitis needs bleeding: ``bleeding_percent`` (BoP or GI >= 2, % of sites) or BOP in
    the chart. Grade uses ``bone_loss_percent`` (radiographic, worst tooth) or ``root_length_mm``
    (tooth -> root length, to compute relative CAL) with ``age``; then smoking
    (``cigarettes_per_day``) and diabetes (``diabetes``, ``hba1c``) can raise it. Without evidence
    grade B is assumed.
    """
    require_verified("aces")
    tab = codes("aces")
    if survey not in ("completed", "planned"):
        raise InputError("survey must be 'completed' or 'planned'")
    ch0 = perio_chart(chart)
    present = {t for t in _present(ch0, teeth_present) if not is_third_molar(t)}
    ch = ch0.without_third_molars()
    ids = tuple(tab["interdental_sites"])
    mids = tuple(tab["mid_sites"])
    trace = ["Six-site chart, third molars excluded (ACES 2024)."]
    warnings: list[str] = []
    src = ("holtfreter2024", "tonetti2018", "papapanou2018", "chapple2018")

    def out(status: str, category: str, comps: dict[str, Any]) -> IndexResult:
        comps.setdefault("status", status)
        return IndexResult("aces", status, comps, category, None, tuple(trace), tuple(warnings), src)

    if not present:
        trace.append("No natural teeth: edentulous (ACES asks that edentulism always be reported).")
        return out("edentulous", "Edentulous", {"stage": None, "grade": None})

    interdental_teeth = {t for t, d in ch.cal.items() if any(s in d for s in ids)}
    mid_teeth = {t for t in ch.teeth if any(s in ch.cal.get(t, {}) and s in ch.pd.get(t, {}) for s in mids)}
    can_interdental = has_non_adjacent_pair(interdental_teeth)
    can_mid = len(mid_teeth) >= tab["case"]["min_teeth_mid"]

    c = tab["case"]
    idcal = _teeth(_sites_over(ch.cal, ids, c["interdental_cal_mm"]))
    crit_a = has_non_adjacent_pair(idcal)
    mid_hits = set()
    for t in ch.teeth:
        for s in mids:
            cv = ch.cal.get(t, {}).get(s)
            pv = ch.pd.get(t, {}).get(s)
            if cv is not None and pv is not None and cv >= c["mid_cal_mm"] - 1e-9 and pv > c["mid_pd_over_mm"]:
                mid_hits.add(t)
    crit_b = len(mid_hits) >= c["min_teeth_mid"]
    trace.append(f"Interdental CAL >= 1 mm at {teeth_list(idcal)} -> non-adjacent pair: {crit_a}.")
    trace.append(f"Buccal/oral CAL >= 3 mm with PD > 3 mm at the same site: {teeth_list(mid_hits)} -> "
                 f">= 2 teeth: {crit_b}.")
    if not (crit_a or crit_b) and not (can_interdental and can_mid):
        trace.append("No case criterion met, and fewer than two non-adjacent teeth with interdental CAL or fewer "
                     "than two teeth with buccal/oral CAL and PD: non-classified.")
        return out("non-classified", "Non-classified", {"stage": None, "grade": None,
                   "non_classified_reason": "too few qualifying teeth"})

    # bleeding (for health/gingivitis)
    bp = None
    if bleeding_percent is not None and not is_blank(bleeding_percent):
        bp = number(bleeding_percent, "bleeding_percent", 0, 100)
        bsrc = "given"
    else:
        bops = [v for d in ch.bop.values() for v in d.values()]
        if bops:
            bp = 100 * sum(bops) / len(bops)
            bsrc = f"{sum(bops)} of {len(bops)} sites"
    pds = [v for d in ch.pd.values() for v in d.values()]
    max_pd = max(pds) if pds else None

    if not (crit_a or crit_b):
        hb = tab["bleeding_bands_percent"]
        comps: dict[str, Any] = {"stage": None, "grade": None, "bleeding_percent": None if bp is None else round(bp, 10),
                                 "max_pd": max_pd, "pseudo_pockets": bool(max_pd is not None and max_pd >= 4)}
        if max_pd is not None and max_pd >= 4:
            trace.append("PD >= 4 mm without attachment loss (pseudo-pockets): classified by gingival inflammation.")
        if bp is None:
            trace.append("Not a periodontitis case; no bleeding data, so health and gingivitis cannot be separated.")
            return out("health or gingivitis", "Periodontal health or gingivitis (no bleeding data)", comps)
        if bp < hb["health_below"]:
            st, cat = "health", "Periodontal health"
        elif bp <= hb["localized_upto"] + 1e-9:
            st, cat = "localized gingivitis", "Localized gingivitis"
        else:
            st, cat = "generalized gingivitis", "Generalized gingivitis"
        trace.append(f"Not a periodontitis case; bleeding at {fmt_fixed(bp, 1)}% of sites ({bsrc}) -> {cat} "
                     f"(<10% health, 10-30% localized, >30% generalized).")
        return out(st, cat, comps)

    # ---- periodontitis: stage ----
    id_vals = [v for d in ch.cal.values() for s, v in d.items() if s in ids]
    max_idcal = max(id_vals) if id_vals else 0.0
    bands = tab["stage_cal_bands_mm"]
    if max_idcal >= bands["III"][0] - 1e-9:
        band_stage = "III"
    elif max_idcal >= bands["II"][0] - 1e-9:
        band_stage = "II"
    else:
        band_stage = "I"
        if max_idcal < bands["I"][0] - 1e-9:
            warnings.append("Case met through the buccal/oral criterion while maximum interdental CAL is below "
                            "1 mm; stage I assigned (interpretation).")
    trace.append(f"Maximum interdental CAL {fmt_g(max_idcal)} mm -> initial stage {band_stage} "
                 f"(1-2 mm I, 3-4 mm II, >= 5 mm III).")
    cx = tab["complexity"]
    pd6_sites = []
    for t, d in ch.pd.items():
        for s, v in d.items():
            if t in SECOND_MOLARS and s in ("DB", "DL"):
                continue
            if v >= cx["pd_mm"] - 1e-9:
                pd6_sites.append((t, s))
    pd6 = has_non_adjacent_pair(_teeth(pd6_sites))
    opp = opposing_pairs(present)
    fi = _bool(furcation_class_2_3, "furcation_class_2_3") if furcation_class_2_3 is not None else None
    vbl = _bool(vertical_bone_loss_3mm, "vertical_bone_loss_3mm") if vertical_bone_loss_3mm is not None else None
    stage3_complexity = bool(pd6 or fi or vbl)
    trace.append(f"PD >= 6 mm at non-adjacent teeth (third molars, distal sites of second molars disregarded): "
                 f"{pd6} ({teeth_list(_teeth(pd6_sites))}); furcation II/III: {fi}; vertical bone loss >= 3 mm: {vbl}.")
    trace.append(f"Opposing pairs of natural teeth: {opp} ({'< 10' if opp < cx['min_opposing_pairs'] else '>= 10'}).")
    few_pairs = opp < cx["min_opposing_pairs"]
    pairs_decided = False  # did the fewer-than-10-pairs rule alone raise the stage to IV?
    lost = None
    if survey == "completed":
        if teeth_lost_to_periodontitis is not None:
            warnings.append("Teeth lost to periodontitis are not used for completed surveys (ACES Figure 2); "
                            "use survey='planned' if this was collected with validated questions.")
        if band_stage == "I":
            stage = "I"
        elif band_stage == "II":
            stage = "III" if stage3_complexity else "II"
        else:
            stage = "IV" if few_pairs else "III"
            pairs_decided = few_pairs
    else:
        lost = _teeth_lost(teeth_lost_to_periodontitis)
        mob = _bool(mobility_degree2_at_2_teeth, "mobility_degree2_at_2_teeth") if mobility_degree2_at_2_teeth is not None else None
        bite = _bool(bite_collapse_drifting_flaring, "bite_collapse_drifting_flaring") if bite_collapse_drifting_flaring is not None else None
        lost_txt = {None: "unknown", 0: "none", 1: "1-4", 5: "5 or more"}[lost]
        trace.append(f"Teeth lost to periodontitis: {lost_txt}; mobility >= 2 at >= 2 teeth: {mob}; "
                     f"bite collapse/drifting/flaring: {bite}.")
        if band_stage == "I":
            if lost == 1:
                stage = "III"
            elif lost == 5:
                stage = "IV"
                warnings.append("Interdental CAL 1-2 mm with 5 or more teeth lost to periodontitis is not covered "
                                "by ACES Figure 3; stage IV assigned from the tooth-loss criterion (Tonetti 2018).")
            else:
                stage = "I"
        elif band_stage == "II":
            if lost == 5:
                stage = "IV"
            elif lost == 1 or stage3_complexity:
                stage = "III"
            else:
                stage = "II"
        else:
            stage = "IV" if lost == 5 else "III"
        if stage == "III" and (mob or bite or few_pairs):
            pairs_decided = bool(few_pairs and not (mob or bite))
            stage = "IV"
            trace.append("Stage IV complexity (mobility, bite collapse/drifting/flaring or < 10 opposing pairs) "
                         "applied to stage III.")
    trace.append(f"Stage {stage} ({survey} survey).")
    if pairs_decided and teeth_present is None:
        warnings.append("Opposing pairs were counted from the charted teeth because teeth_present was not given. "
                        "For a partial-mouth recording, give teeth_present (every natural tooth present); "
                        "otherwise the fewer-than-10-pairs rule can wrongly raise the stage to IV.")

    # ---- extent ----
    thr = tab["extent_severity_cal_mm"][band_stage]
    tooth_max_id = {t: max(v for s, v in d.items() if s in ids) for t, d in ch.cal.items() if any(s in d for s in ids)}
    affected = sorted(t for t, m in tooth_max_id.items() if m >= thr - 1e-9)
    ext_pct = 100 * len(affected) / len(tooth_max_id) if tooth_max_id else None
    extent = None
    if ext_pct is not None:
        extent = "generalized" if ext_pct >= tab["extent_generalized_percent"] - 1e-9 else "localized"
    mip = bool(affected) and all(position(t) in (1, 2, 6) for t in affected)
    trace.append(f"Extent: {len(affected)} of {len(tooth_max_id)} teeth with interdental CAL >= {thr} mm "
                 f"({fmt_fixed(ext_pct, 1)}%) -> {extent} (< 30% localized)." if ext_pct is not None else "Extent: no data.")

    # ---- grade ----
    a = age_value(age)
    ratio = None
    grade_evidence = None
    if bone_loss_percent is not None and not is_blank(bone_loss_percent):
        blp = number(bone_loss_percent, "bone_loss_percent", 0, 100)
        if a is None or a <= 0:
            warnings.append("bone_loss_percent needs the age to compute bone loss / age.")
        else:
            ratio = blp / a
            grade_evidence = f"radiographic bone loss {fmt_g(blp)}% at the worst tooth"
    elif root_length_mm is not None:
        if not isinstance(root_length_mm, Mapping):
            raise InputError("root_length_mm must map teeth to root lengths in mm")
        rl = {t: number(v, f"root length {t}", 1, 40) for t, v in tooth_map(root_length_mm, "root_length_mm").items()}
        rel = {t: 100 * max(v for k, v in ch.cal[t].items() if k in ids) / rl[t]
               for t in rl if t in ch.cal and any(k in ids for k in ch.cal[t])}
        if rel and a is not None and a > 0:
            worst = min(rel, key=lambda t: (-rel[t], t))  # ties: lowest tooth number
            ratio = rel[worst] / a
            grade_evidence = f"worst interdental CAL is {fmt_fixed(rel[worst], 1)}% of the root length at tooth {worst}"
        elif rel:
            warnings.append("Relative CAL needs the age to compute the bone loss / age ratio.")
    if grade_evidence:
        trace.append(f"Indirect evidence: {grade_evidence}.")
    grade, basis, assumed = _grade(ratio, cigarettes_per_day, smoker, diabetes, hba1c, trace, warnings)

    category = f"Stage {stage}" + (f", {extent}" if extent else "") + f", grade {grade}"
    if mip:
        warnings.append("All affected teeth are incisors or first molars: consider the molar-incisor pattern "
                        "(Papapanou 2018).")
    comps = {
        "stage": stage, "stage_cal_only": band_stage if band_stage != "III" else "III/IV",
        "extent": extent, "extent_percent": None if ext_pct is None else round(ext_pct, 10),
        "affected_teeth": affected, "molar_incisor_pattern_possible": mip,
        "grade": grade, "grade_basis": basis, "grade_assumed": assumed,
        "bone_loss_age_ratio": None if ratio is None else round(ratio, 10),
        "max_interdental_cal": max_idcal, "case_interdental": crit_a, "case_buccal_oral": crit_b,
        "pd6_non_adjacent": pd6, "furcation_class_2_3": fi, "vertical_bone_loss_3mm": vbl,
        "opposing_pairs": opp, "survey": survey,
        "teeth_lost_to_periodontitis": None if survey == "completed" else {None: "unknown", 0: "0", 1: "1-4", 5: ">=5"}[lost],
        "bleeding_percent": None if bp is None else round(bp, 10), "max_pd": max_pd,
    }
    return out("periodontitis", category, comps)
