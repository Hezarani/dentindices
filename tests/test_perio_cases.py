import pytest

import dentindices as di
from dentindices import InputError

SITES = ("MB", "B", "DB", "ML", "L", "DL")
TEETH28 = [q * 10 + p for q in (1, 2, 3, 4) for p in range(1, 8)]


def chart(teeth=TEETH28, pd=2, cal=0, bop=False, **overrides):
    """Healthy chart; overrides like t16_MB=(pd, cal) or t16_MB=(pd, cal, bop)."""
    c = {t: {"pd": {s: pd for s in SITES}, "cal": {s: cal for s in SITES}, "bop": {s: bop for s in SITES}}
         for t in teeth}
    for key, val in overrides.items():
        t, s = key[1:].split("_")
        t = int(t)
        c[t]["pd"][s], c[t]["cal"][s] = val[0], val[1]
        if len(val) > 2:
            c[t]["bop"][s] = val[2]
    return c


# ---------------------------------------------------------------- chart parsing
def test_chart_formats_equivalent():
    nested = {16: {"pd": {"MB": 4, "P": 3}, "cal": {"mesiobuccal": 3}, "bop": {"MB": 1}}}
    rows = [{"tooth": 16, "site": "MB", "pd": 4, "cal": 3, "bop": "yes"}, {"Tooth": "16", "Site": "DP", "PD": 3}]
    a, b = di.perio_chart(nested), di.perio_chart(rows)
    assert a.pd[16] == {"MB": 4.0, "L": 3.0} and a.cal[16] == {"MB": 3.0} and a.bop[16] == {"MB": True}
    assert b.pd[16] == {"MB": 4.0, "DL": 3.0} and b.bop[16] == {"MB": True}


@pytest.mark.parametrize("bad", [
    {16: {"pd": {"XX": 3}}}, {16: {"pd": {"MB": -1}}}, {16: {"cal": {"MB": -1}}}, {16: {"foo": {}}},
    {55: {"pd": {"MB": 2}}}, [{"tooth": 16, "site": "MB", "pd": 3}, {"tooth": 16, "site": "MB", "pd": 4}],
    {16: {"bop": {"MB": "maybe"}}}])
def test_chart_rejects(bad):
    with pytest.raises(InputError):
        di.perio_chart(bad)


# ---------------------------------------------------------------- CDC/AAP
def test_cdc_aap_no_periodontitis_and_edentulous():
    assert di.cdc_aap(chart()).value == "no periodontitis"
    assert di.cdc_aap({}, teeth_present=[]).value == "edentulous"
    assert di.cdc_aap(chart(teeth=[16])).value == "non-classified"


def test_cdc_aap_severe():
    c = chart(t16_MB=(5, 6), t26_DB=(4, 6))
    r = di.cdc_aap(c)
    assert r.value == "severe" and r["total_periodontitis"] and r["moderate_or_severe"]


def test_cdc_aap_severe_needs_two_teeth():
    # two CAL>=6 sites on the SAME tooth do not count as severe; they do count as moderate (CAL>=4 on 1 tooth? no)
    c = chart(t16_MB=(5, 6), t16_DB=(5, 6))
    r = di.cdc_aap(c)
    assert r.value != "severe"
    assert r["teeth_cal6"] == 1


def test_cdc_aap_moderate_by_cal_or_pd():
    assert di.cdc_aap(chart(t16_MB=(3, 4), t36_DL=(3, 4))).value == "moderate"
    assert di.cdc_aap(chart(t16_MB=(5, 1), t36_DL=(5, 1))).value == "moderate"
    # PD >= 5 at two sites of one tooth is not moderate
    r = di.cdc_aap(chart(t16_MB=(5, 1), t16_DB=(5, 1)))
    assert r.value != "moderate"


def test_cdc_aap_mild_and_ambiguity_option():
    # CAL>=3 at two sites on different teeth, PD>=4 at two teeth
    assert di.cdc_aap(chart(t16_MB=(4, 3), t26_MB=(4, 3))).value == "mild"
    # or one PD>=5 site
    assert di.cdc_aap(chart(t16_MB=(5, 3), t26_MB=(2, 3))).value == "mild"
    # CAL>=3 sites on the same tooth: not mild by default, mild with the looser reading
    c = chart(t16_MB=(4, 3), t16_DB=(2, 3), t26_MB=(4, 1))
    assert di.cdc_aap(c).value == "no periodontitis"
    assert di.cdc_aap(c, mild_cal_distinct_teeth=False).value == "mild"


def test_cdc_aap_ignores_mid_sites_and_third_molars():
    c = chart(t16_B=(6, 6), t26_L=(6, 6))
    assert di.cdc_aap(c).value == "no periodontitis"
    c2 = chart(teeth=TEETH28 + [18, 28])
    c2[18]["pd"]["MB"], c2[18]["cal"]["MB"] = 6, 6
    c2[28]["pd"]["MB"], c2[28]["cal"]["MB"] = 6, 6
    assert di.cdc_aap(c2).value == "no periodontitis"


def test_cdc_aap_partial_recording_warning():
    c = {16: {"cal": {"MB": 1}, "pd": {"MB": 2}}, 26: {"cal": {"MB": 1}, "pd": {"MB": 2}}}
    assert di.cdc_aap(c).warnings


# ---------------------------------------------------------------- ACES: status
def test_aces_health_gingivitis_thresholds():
    teeth = TEETH28  # 168 sites
    def with_bleeding(n):
        c = chart(teeth)
        k = 0
        for t in teeth:
            for s in SITES:
                if k < n:
                    c[t]["bop"][s] = True
                    k += 1
        return c
    assert di.aces(with_bleeding(16)).value == "health"                  # 9.5%
    assert di.aces(with_bleeding(17)).value == "localized gingivitis"    # 10.1%
    assert di.aces(chart(), bleeding_percent=10).value == "localized gingivitis"
    assert di.aces(chart(), bleeding_percent=30).value == "localized gingivitis"
    assert di.aces(chart(), bleeding_percent=30.1).value == "generalized gingivitis"
    assert di.aces(chart(), bleeding_percent=9.99).value == "health"
    nobop = {t: {"pd": {s: 2 for s in SITES}, "cal": {s: 0 for s in SITES}} for t in TEETH28}
    assert di.aces(nobop).value == "health or gingivitis"


def test_aces_pseudo_pockets_are_not_periodontitis():
    r = di.aces(chart(t16_MB=(5, 0), t26_MB=(5, 0)), bleeding_percent=40)
    assert r.value == "generalized gingivitis" and r["pseudo_pockets"]


def test_aces_edentulous_and_non_classified():
    assert di.aces({}, teeth_present=[]).value == "edentulous"
    assert di.aces({}, teeth_present=[18, 28]).value == "edentulous"       # third molars do not count
    interdental_only = {t: {"cal": {"MB": 0, "DB": 0}, "pd": {"MB": 2, "DB": 2}} for t in (11, 21)}
    r = di.aces(interdental_only)
    assert r.value == "non-classified"                                     # two adjacent teeth, no mid sites
    # Tay et al. 2025 (restating ACES): non-classified with fewer than two non-adjacent teeth with CAL
    # OR fewer than two teeth with buccal/oral CAL and PD -- applied only when no case criterion is met.
    assert di.aces(chart(teeth=[11, 21])).value == "non-classified"        # adjacent teeth only
    assert di.aces(chart(teeth=[11, 13]), bleeding_percent=0).value == "health"
    assert di.aces({t: {"cal": {"MB": 0}, "pd": {"MB": 2}} for t in (11, 13)}).value == "non-classified"
    case_no_mid = {t: {"cal": {"MB": 4, "DB": 4}, "pd": {"MB": 5, "DB": 5}} for t in (16, 26)}
    assert di.aces(case_no_mid, teeth_present=list(range(11, 18)) + list(range(21, 28))
                   + list(range(31, 38)) + list(range(41, 48))).value == "periodontitis"


def test_aces_case_definition_non_adjacent():
    # interdental CAL >= 1 at two ADJACENT teeth is not a case
    r = di.aces(chart(t11_MB=(2, 1), t21_MB=(2, 1)), bleeding_percent=0)
    assert r.value == "health"
    r2 = di.aces(chart(t11_MB=(2, 1), t22_MB=(2, 1)))
    assert r2.value == "periodontitis" and r2["stage"] == "I"
    # buccal/oral criterion: CAL >= 3 with PD > 3 at the same mid site, >= 2 teeth (adjacency not required)
    r3 = di.aces(chart(t11_B=(4, 3), t21_B=(4, 3)))
    assert r3.value == "periodontitis" and r3["case_buccal_oral"] and not r3["case_interdental"]
    assert any("buccal/oral criterion" in w for w in r3.warnings)
    # PD exactly 3 at the mid site is not "> 3 mm"
    assert di.aces(chart(t11_B=(3, 3), t21_B=(3, 3)), bleeding_percent=0).value == "health"


# ---------------------------------------------------------------- ACES: staging (completed surveys, Figure 2)
def test_aces_stage_bands_completed():
    assert di.aces(chart(t16_MB=(3, 2), t26_MB=(3, 2)))["stage"] == "I"
    assert di.aces(chart(t16_MB=(4, 4), t26_MB=(3, 1)))["stage"] == "II"
    assert di.aces(chart(t16_MB=(5, 5), t26_MB=(3, 1)))["stage"] == "III"


def test_aces_stage2_upstaging():
    base = dict(t16_MB=(6, 4), t26_MB=(3, 1))
    assert di.aces(chart(**base))["stage"] == "II"                    # one tooth with PD 6
    assert di.aces(chart(**base, t36_MB=(6, 3)))["stage"] == "III"    # PD>=6 at 2 non-adjacent teeth
    assert di.aces(chart(**base, t15_MB=(6, 3)))["stage"] == "II"     # 15 is adjacent to 16
    assert di.aces(chart(**base, t17_DB=(6, 3)))["stage"] == "II"     # distal of second molar disregarded
    assert di.aces(chart(**base, t17_MB=(6, 3), t11_MB=(6, 2)))["stage"] == "III"
    assert di.aces(chart(**base), furcation_class_2_3=True)["stage"] == "III"
    assert di.aces(chart(**base), vertical_bone_loss_3mm="yes")["stage"] == "III"


def test_aces_stage3_vs_4_opposing_pairs():
    c = chart(t16_MB=(6, 6), t26_MB=(3, 1))
    assert di.aces(c)["stage"] == "III" and di.aces(c)["opposing_pairs"] == 14
    few = [11, 12, 13, 14, 15, 16, 41, 42, 43, 44, 45, 26, 27, 33]        # 9 pairs (11-41 ... 15-45 = 5)
    c2 = chart(teeth=few, t16_MB=(6, 6), t26_MB=(3, 1))
    r = di.aces(c2)
    assert r["opposing_pairs"] == 5 and r["stage"] == "IV"


def test_aces_completed_ignores_tooth_loss():
    r = di.aces(chart(t16_MB=(3, 2), t26_MB=(3, 2)), teeth_lost_to_periodontitis=6)
    assert r["stage"] == "I" and any("not used for completed surveys" in w for w in r.warnings)


# ---------------------------------------------------------------- ACES: staging (planned surveys, Figure 3)
@pytest.mark.parametrize("cal,lost,extra,stage", [
    (2, 0, {}, "I"), (2, "unknown", {}, "I"), (2, "1-4", {}, "III"), (2, ">=5", {}, "IV"),
    (4, 0, {}, "II"), (4, 0, {"furcation_class_2_3": True}, "III"), (4, "1-4", {}, "III"),
    (4, ">=5", {}, "IV"), (6, 0, {}, "III"), (6, 3, {"mobility_degree2_at_2_teeth": True}, "IV"),
    (6, None, {"bite_collapse_drifting_flaring": True}, "IV"), (6, 5, {}, "IV"),
])
def test_aces_planned(cal, lost, extra, stage):
    c = chart(t16_MB=(min(cal + 1, 5), cal), t26_MB=(3, 1))
    r = di.aces(c, survey="planned", teeth_lost_to_periodontitis=lost, **extra)
    assert r["stage"] == stage
    assert r["stage_cal_only"] == {2: "I", 4: "II", 6: "III/IV"}[cal]


def test_aces_planned_stage2_with_tooth_loss_and_few_pairs():
    few = [11, 12, 13, 14, 15, 16, 41, 42, 43, 44, 45, 26, 27, 33]
    c = chart(teeth=few, t16_MB=(4, 4), t26_MB=(3, 1))
    assert di.aces(c, survey="planned", teeth_lost_to_periodontitis="1-4")["stage"] == "IV"


def test_aces_teeth_lost_parsing():
    with pytest.raises(InputError):
        di.aces(chart(t16_MB=(3, 2), t26_MB=(3, 2)), survey="planned", teeth_lost_to_periodontitis="lots")
    with pytest.raises(InputError):
        di.aces(chart(), survey="later")


# ---------------------------------------------------------------- ACES: extent and grade
def test_aces_extent():
    over = {f"t{t}_MB": (4, 3) for t in (11, 13, 15, 17, 21, 23, 25, 27, 31)}   # 9 of 28 teeth = 32%
    r = di.aces(chart(**over))
    assert r["stage"] == "II" and r["extent"] == "generalized" and r["extent_percent"] == pytest.approx(100 * 9 / 28)
    over8 = {f"t{t}_MB": (4, 3) for t in (11, 13, 15, 17, 21, 23, 25, 27)}      # 8 of 28 = 28.6%
    assert di.aces(chart(**over8))["extent"] == "localized"


def test_aces_molar_incisor_flag():
    r = di.aces(chart(t16_MB=(5, 5), t26_MB=(5, 5), t11_MB=(3, 1)))
    assert r["molar_incisor_pattern_possible"] and "molar-incisor" not in r.category
    assert any("molar-incisor" in w for w in r.warnings)


def test_aces_grade_rules():
    c = chart(t16_MB=(5, 5), t26_MB=(3, 1))
    assert di.aces(c)["grade"] == "B" and di.aces(c)["grade_assumed"]
    assert di.aces(c, age=60, bone_loss_percent=12)["grade"] == "A"          # 0.2
    assert di.aces(c, age=40, bone_loss_percent=10)["grade"] == "B"          # 0.25 -> B (inclusive)
    assert di.aces(c, age=40, bone_loss_percent=40)["grade"] == "B"          # 1.0 -> B (inclusive)
    assert di.aces(c, age=30, bone_loss_percent=40)["grade"] == "C"          # 1.33
    assert di.aces(c, age=60, bone_loss_percent=12, cigarettes_per_day=5)["grade"] == "B"
    assert di.aces(c, age=60, bone_loss_percent=12, cigarettes_per_day=10)["grade"] == "C"
    assert di.aces(c, age=60, bone_loss_percent=12, cigarettes_per_day=0)["grade"] == "A"
    assert di.aces(c, age=60, bone_loss_percent=12, diabetes=True, hba1c=6.5)["grade"] == "B"
    assert di.aces(c, age=60, bone_loss_percent=12, diabetes=True, hba1c=7.0)["grade"] == "C"
    assert di.aces(c, age=60, bone_loss_percent=12, diabetes=False, hba1c=9)["grade"] == "A"
    w = di.aces(c, age=60, bone_loss_percent=12, diabetes=True)
    assert w["grade"] == "B" and w.warnings
    s = di.aces(c, age=60, bone_loss_percent=12, smoker=True)
    assert s["grade"] == "B" and s.warnings
    # modifiers never lower the grade
    assert di.aces(c, age=30, bone_loss_percent=40, cigarettes_per_day=0, diabetes=False)["grade"] == "C"


def test_aces_grade_from_root_length():
    c = chart(t16_MB=(5, 5), t26_MB=(3, 1))
    r = di.aces(c, age=50, root_length_mm={16: 12.5, 26: 12.5})
    # relative CAL at 16 = 100 * 5 / 12.5 = 40% -> 40 / 50 = 0.8 -> B
    assert r["bone_loss_age_ratio"] == pytest.approx(0.8) and r["grade"] == "B" and not r["grade_assumed"]
    r2 = di.aces(c, age=30, root_length_mm={16: 12.5})
    assert r2["grade"] == "C"


def test_perio_summary():
    r = di.perio_summary(chart(t16_MB=(6, 5, True)))
    assert r["teeth"] == 28 and r["sites_pd"] == 168 and r["max_pd"] == 6 and r["max_cal"] == 5
    assert r["percent_sites_pd_6plus"] == pytest.approx(100 / 168)
    assert r["percent_sites_bop"] == pytest.approx(100 / 168)
    assert r["mean_cal"] == pytest.approx(5 / 168)
