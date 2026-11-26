import pytest

import dentindices as di
from dentindices import InputError


# ---------------- BPE / sBPE / CPITN / CPI / LOA ----------------
def test_bpe_basic():
    r = di.bpe(["3*", 2, 1, "-", 0, "2"])
    assert r.value == 3 and r.category == "Code 3*" and r["furcation"] and r["furcation_sextants"] == ["S1"]
    assert r["code3_sextants"] == ["S1"] and not r["full_chart_indicated"] and r["excluded_sextants"] == ["S4"]
    assert "6-point pocket chart in that sextant" in r.guidance and "Furcation" in r.guidance
    r4 = di.bpe({"UR": 4, "UA": 0, "UL": 0, "LL": 0, "LA": 0, "LR": 0})
    assert r4["full_chart_indicated"] and "entire dentition" in r4.guidance


@pytest.mark.parametrize("bad", [[5, 0, 0, 0, 0, 0], ["*", 0, 0, 0, 0, 0], [0, 0, 0], ["-"] * 6])
def test_bpe_invalid(bad):
    with pytest.raises(InputError):
        di.bpe(bad)


def test_bpe_from_teeth_sextant_rules():
    present = [17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 34, 35, 36, 37, 33, 32, 31, 41, 42, 43,
               44, 18, 28, 48]
    codes = {16: 2, 18: 4, 26: 1, 28: 4, 44: 3, 48: 2, 31: 1}
    r = di.bpe_from_teeth(codes, teeth_present=present)
    s = r["sextants"]
    assert s["S1"] == "2"               # 18 ignored: 16 and 17 present
    assert s["S3"] == "1"               # 28 ignored too
    assert s["S6"] == "3"               # 45/46/47 missing -> 48 included; 44 + 48 = 2 teeth
    assert s["S4"] is None              # teeth present but none scored
    r2 = di.bpe_from_teeth({44: 2, 31: 1}, teeth_present=[44, 31, 32])
    assert r2["sextants"]["S6"] is None  # single tooth: fewer than two teeth
    assert r2["sextants"]["S5"] == "1"


def test_sbpe_age_rules():
    r = di.sbpe({16: 1, 11: 0, 26: 2, 36: 1, 31: 0, 46: 1}, age=9)
    assert r.value == 2 and "6 months" in r.guidance
    with pytest.raises(InputError):
        di.sbpe({16: 3}, age=10)                     # codes 3-4 not used at 7-11
    t = di.sbpe({16: "3*", 11: 0}, age=15)
    assert t.category == "Code 3*" and "Unusual" in t.guidance and t.warnings
    with pytest.raises(InputError):
        di.sbpe({16: 1}, age=18)
    with pytest.raises(InputError):
        di.sbpe({17: 1}, age=12)


@pytest.mark.parametrize("codes,tn", [([0] * 6, "TN0"), ([1, 0, 0, 0, 0, 0], "TN1"), ([2, 1, 0, 0, 0, 0], "TN2"),
                                      ([3, 2, 0, 0, 0, "X"], "TN2"), ([4, 3, 0, 0, 9, 0], "TN3")])
def test_cpitn_treatment_need(codes, tn):
    assert di.cpitn(codes).category == tn


def test_cpitn_children_and_counts():
    r = di.cpitn([3, 2, "X", 9, 1, 0], age=12)
    assert r.warnings and r["sextants_code3"] == 1 and r["sextants_excluded"] == 1 and r["sextants_not_recorded"] == 1
    assert r["index_teeth"]["S1"] == [16]
    assert di.cpitn([0] * 6, age=35)["index_teeth"]["S1"] == [17, 16]


def test_cpi_modified():
    bleeding = {16: 1, 11: 0, 26: 1, 36: 9, 46: "X", 31: 0}
    pockets = {16: 2, 11: 0, 26: 1, 36: 9, 46: "X", 31: 0}
    r = di.cpi_modified(bleeding, pockets, age=40)
    assert r["teeth_present"] == 5 and r["teeth_examined"] == 4 and r["bleeding_teeth"] == 2
    assert r["bleeding_percent_of_present"] == pytest.approx(40) and r["bleeding_percent_of_examined"] == pytest.approx(50)
    assert r["pocket_max_score"] == 2 and r["deep_pocket_teeth"] == 1 and r["shallow_pocket_teeth"] == 1
    assert r.category.startswith("Deep")
    child = di.cpi_modified({16: 1}, {16: 1}, age=12)
    assert "pocket_max_score" not in child.components and child.warnings


def test_loss_of_attachment():
    r = di.loss_of_attachment([0, 1, 2, "X", 9, 4], age=50)
    assert r.value == 4 and r["sextants_score4"] == 1 and r["sextants_excluded"] == 1
    with pytest.raises(InputError):
        di.loss_of_attachment([0] * 6, age=14)


# ---------------- hygiene ----------------
def test_plaque_index_and_bands():
    scores = {16: [1, 1, 1, 1], 21: {"D": 0, "B": 1, "M": 1, "L": 1}, 24: [2, 2, 1, 1]}
    r = di.plaque_index(scores)
    assert r.value == pytest.approx((1 + 0.75 + 1.5) / 3)
    assert r["areas_scored"] == 12 and r["ramfjord_teeth_only"] is True
    assert r.category == "Fair"
    assert di.plaque_index({16: [0, 0, 0, 0]}).category == "Excellent"
    assert di.plaque_index({16: [3, 3, 3, 3]}).category == "Poor"
    with pytest.raises(InputError):
        di.plaque_index({16: [4, 0, 0, 0]})
    with pytest.raises(InputError):
        di.plaque_index({16: [1, 1]})


@pytest.mark.parametrize("scores,label", [([0, 0, 0, 0], "Normal"), ([1, 0, 0, 0], "Mild gingivitis"),
                                          ([1, 1, 1, 1], "Mild gingivitis"), ([1, 1, 1, 2], "Moderate gingivitis"),
                                          ([2, 2, 2, 2], "Moderate gingivitis"), ([2, 2, 2, 3], "Severe gingivitis")])
def test_gingival_index_bands(scores, label):
    assert di.gingival_index({16: scores}).category == label


def test_plaque_control_record():
    r = di.plaque_control_record({16: "MD", 11: [], 26: {"M": 1, "B": True, "D": 0}}, teeth_present=[16, 11, 26, 36])
    assert r["surfaces_examined"] == 16 and r["surfaces_with_plaque"] == 4 and r.value == pytest.approx(25)
    assert not r["at_or_below_10_percent"]
    with pytest.raises(InputError):
        di.plaque_control_record({16: "MX"})
    with pytest.raises(InputError):
        di.plaque_control_record({16: "M"}, teeth_present=[11])


def test_ohi_s_worked_example_and_substitution():
    debris = {16: 1, 11: 0, 27: 2, 36: 1, 41: 0, 46: 2}     # 27 replaces 26, 41 replaces 31
    calculus = {16: 0, 11: 0, 27: 1, 36: 1, 41: 0, 46: 1}
    r = di.ohi_s(debris, calculus)
    assert r["DI_S"] == pytest.approx(1.0) and r["CI_S"] == pytest.approx(0.5) and r.value == pytest.approx(1.5)
    assert r.category == "Fair" and r["DI_S_category"] == "Fair" and r["CI_S_category"] == "Good"
    assert any("UL->27" in t for t in r.trace)
    assert di.ohi_s({"UR": 0, "LL": 0}, {"UR": 0, "LL": 1}).category == "Good"
    with pytest.raises(InputError):
        di.ohi_s({16: 1})                                  # fewer than two surfaces
    with pytest.raises(InputError):
        di.ohi_s({16: 1, 17: 2, 11: 0})                    # two teeth for one site
    with pytest.raises(InputError):
        di.ohi_s({15: 1, 11: 0})                           # not an OHI-S tooth
    d_only = di.ohi_s({16: 1, 11: 1})
    assert d_only.value == 1 and d_only.warnings


@pytest.mark.parametrize("total,label", [(1.2, "Good"), (1.24, "Good"), (1.25, "Fair"), (3.0, "Fair"), (3.1, "Poor")])
def test_ohi_s_bands(total, label):
    from dentindices._registry import band, codes
    tab = codes("ohi_s")
    assert band(total, tab["bands"], tab["round_to"]) == label


# ---------------- BEWE ----------------
@pytest.mark.parametrize("scores,level", [([0, 0, 0, 0, 1, 1], "None"), ([1, 1, 1, 0, 0, 0], "Low"),
                                          ([2, 2, 2, 2, 0, 0], "Low"), ([2, 2, 2, 2, 1, 0], "Medium"),
                                          ([3, 3, 3, 2, 2, 0], "Medium"), ([3, 3, 3, 3, 2, 0], "High"),
                                          ([3] * 6, "High")])
def test_bewe_risk_levels(scores, level):
    r = di.bewe(scores)
    assert r.category == level and r.value == sum(scores)


def test_bewe_guidance_and_partial():
    r = di.bewe([1, 1, 1, None, "-", 0])
    assert r.value == 3 and r["sextants_scored"] == 4 and any("Only 4 of 6" in w for w in r.warnings)
    assert "2-year" in r.guidance
    with pytest.raises(InputError):
        di.bewe([4, 0, 0, 0, 0, 0])


def test_bewe_from_teeth_rules():
    scores = {
        16: {"B": 1, "O": 2, "L": 0}, 15: 1,
        11: {"B": 3, "O": 1}, 21: 0,
        26: 1, 25: 0, 28: 3,                      # 28 ignored: 27 present
        27: 0,
        36: 1,                                    # single tooth in S4 -> added to S5
        33: 2, 32: 0, 31: 0,
        47: 1, 45: 0, 48: 3,                      # 48 ignored, 47 present
    }
    r = di.bewe_from_teeth(scores)
    s = r["sextants"]
    assert s == {"S1": 2, "S2": 3, "S3": 1, "S4": None, "S5": 2, "S6": 1}
    assert any("single tooth (36)" in t for t in r.trace)
    r2 = di.bewe_from_teeth({16: 1, 18: 3, 15: 0}, teeth_present=[16, 15, 18])
    assert r2["sextants"]["S1"] == 3                   # 18 replaces missing 17


# ---------------- fluorosis ----------------
def test_dean_index_two_most_affected():
    r = di.dean_index({11: 4, 21: 3, 16: 2, 26: 0, 36: 8})
    assert r["who_code"] == "3" and r.category == "Mild" and r["dean_weight"] == 2
    assert di.dean_index({11: 4, 21: 4}).category == "Moderate"
    assert di.dean_index({11: "questionable", 21: "normal"}).category == "Normal"
    assert di.dean_index({11: 0.5, 21: 1}, scale="dean")["who_code"] == "1"
    single = di.dean_index({11: 5})
    assert single.value == 5 and single.warnings
    with pytest.raises(InputError):
        di.dean_index({11: 6})


@pytest.mark.parametrize("codes,cfi,label", [
    ([0, 0, 0, 0, 1, 1, 1, 1, 0, 0], 0.2, "Negative"),
    ([1, 1, 1, 1, 1, 1, 1, 1, 0, 0], 0.4, "Negative"),          # end point belongs to the lower band
    ([2, 2, 2, 2, 0, 0, 0, 0, 0, 1], 0.45, "Borderline"),
    ([2, 2, 2, 2, 2, 2, 0, 0, 0, 0], 0.6, "Borderline"),
    ([3, 2, 2, 2, 2, 2, 0, 0, 0, 0], 0.7, "Slight"),
    ([3, 3, 3, 3, 3, 3, 3, 3, 3, 3], 2.0, "Medium"),
    ([4, 4, 4, 4, 4, 4, 4, 4, 4, 4], 3.0, "Marked"),
    ([5, 5, 5, 5, 5, 5, 5, 5, 5, 4], 3.9, "Very marked")])
def test_cfi_bands(codes, cfi, label):
    r = di.community_fluorosis_index(codes)
    assert r.value == pytest.approx(cfi) and r.category == label


def test_cfi_public_health_flag_and_results_input():
    persons = [di.dean_index({11: 3, 21: 3}), di.dean_index({11: 0, 21: 0}), 9, 8, 4]
    r = di.community_fluorosis_index(persons)
    assert r["n"] == 3 and r.value == pytest.approx((2 + 0 + 3) / 3) and r["public_health_problem"]


# ---------------- DAI ----------------
def _dai(**k):
    base = dict(missing_visible_teeth=0, crowding=0, spacing=0, diastema_mm=0, max_anterior_irregularity_mm=0,
                mand_anterior_irregularity_mm=0, max_overjet_mm=0, mand_overjet_mm=0, openbite_mm=0, molar_relation=0)
    base.update(k)
    return di.dai(**base)


def test_dai_equation_weights():
    assert _dai().value == 13
    assert _dai(missing_visible_teeth=1).value == 19
    assert _dai(diastema_mm=2).value == 19
    assert _dai(max_overjet_mm=3).value == 19
    assert _dai(mand_overjet_mm=1, openbite_mm=1).value == 21
    assert _dai(molar_relation=2).value == 19
    assert _dai(crowding=2, spacing=1, max_anterior_irregularity_mm=2, mand_anterior_irregularity_mm=1).value == 19


@pytest.mark.parametrize("overjet,label", [(6, "No abnormality or minor malocclusion"), (7, "Definite malocclusion"),
                                           (8, "Definite malocclusion"), (9, "Severe malocclusion"),
                                           (11, "Severe malocclusion")])
def test_dai_bands(overjet, label):
    # 13 + 2 x overjet: 6 -> 25, 7 -> 27, 8 -> 29, 9 -> 31, 11 -> 35
    assert _dai(max_overjet_mm=overjet).category == label


def test_dai_boundaries_exact():
    assert _dai(max_overjet_mm=6, crowding=0).value == 25
    assert _dai(max_overjet_mm=6, crowding=1).category == "Definite malocclusion"       # 26
    assert _dai(max_overjet_mm=8, crowding=2).value == 31
    assert _dai(max_overjet_mm=8, crowding=2).category == "Severe malocclusion"
    r36 = _dai(max_overjet_mm=10, crowding=2, spacing=1)
    assert r36.value == 36 and r36.category.startswith("Very severe")


def test_dai_validation():
    with pytest.raises(InputError):
        _dai(crowding=3)
    with pytest.raises(InputError):
        _dai(max_overjet_mm=2.5)
    assert _dai(max_overjet_mm=2.0).value == 17
    assert _dai(max_overjet_mm=1, mand_overjet_mm=1).warnings
    assert _dai(age=9).warnings
