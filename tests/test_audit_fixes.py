"""Regression tests for the issues found by the independent pre-release reviews."""
import math

import pytest

import dentindices as di
from dentindices import InputError
from test_perio_cases import TEETH28, chart

FULL = TEETH28


# ---------------------------------------------------------------- ACES
def test_aces_grade_from_root_length_uses_interdental_cal_only():
    # buccal recession of 6 mm on 31 must not drive the grade; worst interdental CAL is 3 mm on 16
    c = chart(t16_MB=(4, 3), t26_DB=(4, 3), t31_B=(2, 6))
    r = di.aces(c, age=30, root_length_mm={31: 12, 16: 13}, bleeding_percent=5)
    assert r.value == "periodontitis"
    assert r["bone_loss_age_ratio"] == pytest.approx(100 * 3 / 13 / 30)
    assert r["grade"] == "B"


def test_aces_partial_mouth_without_teeth_present_warns():
    half = [t for t in FULL if t // 10 in (1, 3)]  # quadrants 1 and 3 charted only
    c = chart(teeth=half, **{f"t{t}_MB": (6, 5) for t in half})
    r = di.aces(c)
    assert r["stage"] == "IV" and any("teeth_present" in w for w in r.warnings)
    full = di.aces(c, teeth_present=FULL)
    assert full["stage"] == "III" and not any("teeth_present" in w for w in full.warnings)


def test_aces_planned_survey_applies_stage_iv_complexity_consistently():
    few = [11, 12, 13, 14, 21, 22, 23, 31, 32, 33, 41, 42]  # < 10 opposing pairs? (6 pairs)
    stage1 = chart(teeth=few, t11_MB=(3, 2), t13_MB=(3, 2))
    stage2 = chart(teeth=few, t11_MB=(4, 3), t13_MB=(4, 3))
    for c in (stage1, stage2):
        r = di.aces(c, survey="planned", teeth_lost_to_periodontitis="1-4", teeth_present=few)
        assert r["opposing_pairs"] < 10 and r["stage"] == "IV"
    r = di.aces(chart(t11_MB=(3, 2), t13_MB=(3, 2)), survey="planned", teeth_lost_to_periodontitis="1-4")
    assert r["stage"] == "III"
    r = di.aces(chart(t11_MB=(4, 3), t13_MB=(4, 3)), survey="planned", teeth_lost_to_periodontitis=0,
                mobility_degree2_at_2_teeth=True)
    assert r["stage"] == "II"  # mobility applies only once stage III is reached


def test_aces_molar_incisor_note_is_a_warning_not_part_of_category():
    r = di.aces(chart(t16_MB=(4, 2), t26_MB=(4, 2)), bleeding_percent=5)
    assert r["molar_incisor_pattern_possible"] and "(" not in r.category


# ---------------------------------------------------------------- CDC/AAP
def test_cdc_aap_mild_pd5_any_site_option():
    c = chart(t16_MB=(3, 3), t26_DB=(3, 3), t36_B=(5, 0))
    assert di.cdc_aap(c).value == "no periodontitis"
    r = di.cdc_aap(c, mild_pd5_any_site=True)
    assert r.value == "mild" and r["mild_pd5_any_site"] is True


# ---------------------------------------------------------------- WHO levels, verification
def test_secondary_definition_and_relabelled_indices():
    info = {i["id"]: i for i in di.list_indices()}
    assert info["sic"]["verification"] == "secondary" and info["sac"]["verification"] == "secondary"
    assert "abstract" in di.registry()["verification_levels"]["secondary"]


# ---------------------------------------------------------------- BEWE
def test_bewe_single_tooth_rule_counts_present_teeth_not_scored_teeth():
    # S1 has 16 (scored) and 17 present but unscorable -> two teeth present, no move to S2
    scores = {16: 2, 17: None, 13: 1, 11: 1, 21: 1, 23: 1}
    r = di.bewe_from_teeth(scores)
    assert r["BEWE"] == 3 and not any("single tooth" in t for t in r.trace)
    r2 = di.bewe_from_teeth({16: 2, 13: 1, 11: 1, 21: 1, 23: 1})  # 16 alone in S1 -> scored with S2
    assert any("single tooth (16)" in t for t in r2.trace)


# ---------------------------------------------------------------- input robustness
@pytest.mark.parametrize("call", [
    lambda: di.bpe(None), lambda: di.bpe(5), lambda: di.cpitn("abc"), lambda: di.bewe(None),
    lambda: di.community_fluorosis_index(None), lambda: di.summarize(None), lambda: di.care_index(None),
    lambda: di.summarize([1, 2], confidence="0.9x"), lambda: di.sic([1, 2], fraction="x"),
    lambda: di.cdc_aap({16: {"cal": {"MB": 1}}}, teeth_present=5),
    lambda: di.bpe_from_teeth({16: 1, 17: 2}, teeth_present="16"),
    lambda: di.plaque_control_record({16: ["M"]}, teeth_present=16),
    lambda: di.bewe_from_teeth({16: 1}, teeth_present=5),
    lambda: di.batch(None, "bpe"), lambda: di.batch([1, 2], "bpe"), lambda: di.batch([{"16": 1}], ["bpe"]),
    lambda: di.summary_table([{"x": 1}], "x", by=5), lambda: di.cite(None), lambda: di.index_info([]),
    lambda: di.dmft_permanent({16: "16²"}), lambda: di.dmft_permanent({"16²": 1}),
    lambda: di.dmft_permanent({16: float("inf")}), lambda: di.dmft_permanent({16: 1}, age="1_0"),
    lambda: di.dmft_permanent({16: 1}, age="0x1E"),
])
def test_bad_inputs_raise_input_error(call):
    with pytest.raises(InputError):
        call()


def test_tooth_error_and_unknown_ids_are_input_errors():
    assert issubclass(di.ToothError, InputError)
    with pytest.raises(KeyError):           # still a KeyError for dict-style callers
        di.index_info("nope")
    with pytest.raises(InputError) as e:
        di.cite("foo")
    assert not str(e.value).startswith('"')


def test_numeric_tooth_keys_and_nan_from_data_frames():
    r = di.dmft_permanent({16.0: 1, 26: 3.0, 36: float("nan")}, age=12.0)
    assert r.value == 2 and r["teeth_present"] == 2
    assert di.summarize([1, "NA", "-", None, float("nan"), 3])["n"] == 2


def test_formatting_helpers_match_javascript():
    from dentindices._common import fmt_fixed, fmt_g, js_str
    assert fmt_fixed(56.25, 1) == "56.3" and fmt_fixed(0.125, 2) == "0.13"
    assert js_str(3e-7) == "3e-7" and js_str(1.5e-6) == "0.0000015" and js_str(1e21) == "1e+21"
    assert fmt_g(12345.678) == "12350" and fmt_g(1 / 3) == "0.3333" and fmt_g(1.0) == "1"


# ---------------------------------------------------------------- CSV and survey processing
def test_read_csv_skips_blank_rows_strips_bom_and_rejects_duplicate_headers(tmp_path):
    text = "﻿id,age,16\n1,12,1\n,,\n\n2,13,0\n"
    rows = di.read_csv(text, text=True)
    assert [r["id"] for r in rows] == ["1", "2"] and "id" in rows[0]
    with pytest.raises(InputError):
        di.read_csv("id,16,16\n1,1,2\n", text=True)
    p = tmp_path / "latin.csv"
    p.write_bytes("id;note;16\n1;caf\xe9;1\n".encode("cp1252"))
    assert di.read_csv(str(p))[0]["note"] == "caf\xe9"
    with pytest.raises(InputError):
        di.read_csv(str(tmp_path / "missing.csv"))


def test_read_csv_keeps_a_stray_quote_inside_a_field():
    rows = di.read_csv('id,note,16\n1,5" crown,1\n2,x,0\n3,y,3\n', text=True)
    assert len(rows) == 3 and rows[0]["note"] == '5" crown'


def test_batch_rejects_two_columns_for_the_same_tooth_or_sextant():
    out = di.batch([{"id": 1, "16": "1", "1.6": "0"}], "dmft_permanent")
    assert "same tooth" in out[0]["error"]
    out = di.batch([{"S1": "4", "UR": "0", "S2": "0", "S3": "0", "S4": "0", "S5": "0", "S6": "0"}], "bpe")
    assert "same sextant" in out[0]["error"]


def test_batch_perio_requires_tooth_and_site_columns_and_merges_options():
    with pytest.raises(InputError):
        di.batch_perio([{"id": "A", "fdi": 16, "site": "MB", "pd": 3, "cal": 1}])
    rows = [{"id": "A", "age": 40, "tooth": t, "site": s, "pd": 2, "cal": 0} for t in (16, 26) for s in ("MB", "B")]
    out = di.batch_perio(rows, age=50)          # explicit option and an age column: no TypeError
    assert "error" not in out[0]


def test_summary_table_sic_only_for_caries_columns_and_checks_group_column():
    rows = [{"g": "a", "DMFT": 1, "mean_cal": 2.5}, {"g": "a", "DMFT": 0, "mean_cal": 1.0}]
    assert "SiC" in di.summary_table(rows, "DMFT")[0]
    assert "SiC" not in di.summary_table(rows, "mean_cal")[0]
    assert "SiC" in di.summary_table(rows, "mean_cal", include_sic=True)[0]
    with pytest.raises(InputError):
        di.summary_table(rows, "DMFT", by="sex")


def test_write_csv_guards_against_spreadsheet_formulas():
    text = di.write_csv([{"note": "=HYPERLINK(1)", "n": -3, "x": "-"}])
    assert "'=HYPERLINK(1)" in text and ",-3," in text


# ---------------------------------------------------------------- CLI
def test_cli_errors_are_clean(tmp_path, capsys):
    from dentindices.cli import main
    assert main(["dmft", "16=1,16=2"]) == 2
    assert "more than once" in capsys.readouterr().err
    assert main(["cite", "foo"]) == 2
    err = capsys.readouterr().err
    assert "error: 'foo' is neither" in err
    assert main(["examples", str(tmp_path)]) == 0
    capsys.readouterr()
    assert main(["batch", "dmft_permanent", str(tmp_path / "caries_survey.csv"), "-o", str(tmp_path)]) == 2
    assert "error" in capsys.readouterr().err


# ---------------------------------------------------------------- final verification pass
@pytest.mark.parametrize("age", ["۱۲", "١٢", "１２", "1_0", "0x1E", "inf"])
def test_non_ascii_and_exotic_numbers_are_rejected(age):
    with pytest.raises(InputError):
        di.dmft_permanent({16: 1, 17: 5}, age=age)


def test_teeth_lost_requires_ascii_digits():
    c = chart(t11_MB=(4, 3), t13_MB=(4, 3))
    for bad in ("٣", "²"):
        with pytest.raises(InputError):
            di.aces(c, survey="planned", teeth_lost_to_periodontitis=bad)
    assert di.aces(c, survey="planned", teeth_lost_to_periodontitis="3")["teeth_lost_to_periodontitis"] == "1-4"


def test_numpy_values_are_accepted_and_nan_is_blank():
    np = pytest.importorskip("numpy")
    r = di.dmft_permanent({np.int64(16): np.int64(1), np.float64(26.0): 3}, age=np.float32(12))
    assert r.value == 2
    assert di.summarize([1, np.float32("nan"), np.float64("nan"), 3])["n"] == 2


def test_partial_mouth_warning_only_when_the_pairs_rule_raised_the_stage():
    few = [11, 12, 13, 14, 15, 16, 17, 21, 22, 23, 24, 25, 26, 27]  # upper arch only: 0 opposing pairs
    stage1 = di.aces(chart(teeth=few, t11_MB=(3, 2), t13_MB=(3, 2)))
    assert stage1["stage"] == "I" and not any("teeth_present" in w for w in stage1.warnings)
    stage4 = di.aces(chart(teeth=few, t11_MB=(6, 5), t13_MB=(6, 5)))
    assert stage4["stage"] == "IV" and any("teeth_present" in w for w in stage4.warnings)
    mob = di.aces(chart(teeth=few, t11_MB=(4, 3), t13_MB=(4, 3)), survey="planned",
                  teeth_lost_to_periodontitis="1-4", mobility_degree2_at_2_teeth=True)
    assert mob["stage"] == "IV" and not any("teeth_present" in w for w in mob.warnings)


def test_root_length_rejects_the_same_tooth_twice():
    with pytest.raises(InputError):
        di.aces(chart(t16_MB=(4, 3), t26_DB=(4, 3)), age=40, root_length_mm={"1.6": 10, "16": 20})


def test_read_csv_handles_old_mac_line_endings_and_turkish_code_page(tmp_path):
    rows = di.read_csv("id,16\r1,2\r3,4\r", text=True)
    assert [r["16"] for r in rows] == ["2", "4"]
    p = tmp_path / "tr.csv"
    p.write_bytes("id;grup;16\n1;şehir ığ;1\n".encode("cp1254"))
    assert di.read_csv(str(p))[0]["grup"] == "şehir ığ"
    p.write_bytes("id;grup;16\n1;şehir;1\n".encode("cp1254"))
    assert di.read_csv(str(p), encoding="cp1254")[0]["grup"] == "şehir"
    assert di.decode_text("caf\xe9".encode("cp1252")) == "caf\xe9"


def test_batch_perio_passes_cdc_options_and_rejects_unknown_options():
    rows = [{"id": "A", "tooth": t, "site": s, "pd": pd, "cal": cal}
            for t, s, pd, cal in [(16, "MB", 3, 3), (26, "DB", 3, 3), (36, "B", 5, 0), (11, "MB", 2, 0)]]
    assert di.batch_perio(rows)[0]["cdc_aap"] == "no periodontitis"
    assert di.batch_perio(rows, cdc_options={"mild_pd5_any_site": True})[0]["cdc_aap"] == "mild"
    with pytest.raises(InputError):
        di.batch_perio(rows, mild_pd5_any_site=True)        # a CDC option given as an ACES option
    with pytest.raises(InputError):
        di.batch_perio(rows, teeth_present=[16, 26])
    with pytest.raises(InputError):
        di.batch_perio(rows, cdc_options={"nope": 1})


def test_formula_guard_covers_leading_minus_but_not_numbers_or_blank():
    text = di.write_csv([{"a": "-2+3+cmd|' /C calc'!A0", "b": "-3.5", "c": "-"}])
    assert "'-2+3" in text and ",-3.5," in text and text.rstrip().endswith(",-")


def test_cli_perio_cdc_flags(tmp_path, capsys):
    from dentindices.cli import main
    p = tmp_path / "c.csv"
    p.write_text("id,tooth,site,pd,cal\nA,16,MB,3,3\nA,26,DB,3,3\nA,36,B,5,0\n")
    out = tmp_path / "o.csv"
    assert main(["perio", str(p), "-o", str(out)]) == 0
    assert "no periodontitis" in out.read_text()
    assert main(["perio", str(p), "-o", str(out), "--mild-pd5-any-site"]) == 0
    assert ",mild," in out.read_text()
