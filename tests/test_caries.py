import pytest

import dentindices as di
from dentindices import InputError

ALL32 = [q * 10 + p for q in (1, 2, 3, 4) for p in range(1, 9)]


def test_who2013_components_worked_example():
    # 16 caries (1), 26 filled with caries (2), 36 filled (3), 46 missing due to caries (4),
    # 17 missing other reason (5), 37 sealant (6), 47 crown/abutment (7), 18 unerupted (8), 28 not recorded (9)
    codes = {16: 1, 26: 2, 36: 3, 46: 4, 17: 5, 37: 6, 47: 7, 18: 8, 28: 9, 11: 0}
    r = di.dmft_permanent(codes, age=25)
    assert (r["DT"], r["MT"], r["FT"], r.value) == (2, 1, 1, 4)
    assert r["sealed"] == 1 and r["abutment_crown_veneer"] == 1 and r["unerupted"] == 1 and r["not_recorded"] == 1
    assert r["missing_other_reason_not_counted"] == 1
    assert r["teeth_present"] == 7      # codes 0,1,2,3,6,7,9
    assert r["D_teeth"] == [16, 26]
    r30 = di.dmft_permanent(codes, age=30)
    assert r30["MT"] == 2 and r30.value == 5   # from 30, code 5 counts too


def test_age_threshold_boundary():
    codes = {17: 5, 16: 4}
    assert di.dmft_permanent(codes, age=29.99)["MT"] == 1
    assert di.dmft_permanent(codes, age=30)["MT"] == 2


def test_missing_age_with_code5_warns():
    r = di.dmft_permanent({17: 5, 16: 4})
    assert r["MT"] == 1
    assert any("Age not given" in w for w in r.warnings)
    assert not di.dmft_permanent({16: 4}).warnings


def test_m_rule_options():
    codes = {17: 5, 16: 4}
    assert di.dmft_permanent(codes, age=50, m_rule="caries_only")["MT"] == 1
    assert di.dmft_permanent(codes, age=10, m_rule="any_reason")["MT"] == 2
    with pytest.raises(InputError):
        di.dmft_permanent(codes, m_rule="whatever")


def test_third_molars():
    codes = {18: 1, 28: 3, 16: 1}
    assert di.dmft_permanent(codes).value == 3
    r = di.dmft_permanent(codes, include_third_molars=False)
    assert r.value == 1 and r["third_molars_included"] is False


def test_edentulous_adult():
    codes = {t: (4 if t % 10 < 6 else 5) for t in ALL32}
    r = di.dmft_permanent(codes, age=70)
    assert r.value == 32 and r["edentulous"] and r["teeth_present"] == 0
    young = di.dmft_permanent(codes, age=25)
    assert young.value == 20  # only code 4 (positions 1-5) counts under 30


def test_no_permanent_teeth_is_undefined():
    r = di.dmft_permanent({55: "B"})
    assert r.value is None and r["DMFT"] is None
    assert di.population.summarize([r, 2, 4])["n"] == 2


def test_primary_codes_and_positions():
    r = di.dmft_primary({55: "B", 54: "c", 64: "E", 11: "A", 74: "D", 85: "F", 84: "G"})
    assert (r["dt"], r["mt"], r["ft"], r.value) == (2, 1, 1, 4)
    assert r["d_teeth"] == [54, 55] and r["sealed"] == 1 and r["teeth_present"] == 6
    # letter code keyed by the permanent space 15 means primary tooth 55
    assert di.dmft_primary({15: "B"})["d_teeth"] == [55]


def test_mixed_dentition_and_same_space():
    both = di.caries_experience({16: 1, 55: "B", 15: 0, 64: "D"}, age=10)
    assert both["permanent"].value == 1
    assert both["primary"].value == 1      # 55 ignored: permanent 15 occupies the space
    assert any("permanent tooth only" in w for w in both["primary"].warnings)
    # code 8 with a primary tooth in the space: the primary tooth is kept
    r = di.caries_experience({15: 8, 55: "B"})
    assert r["primary"].value == 1 and any("code 8" in w for w in r["primary"].warnings)


@pytest.mark.parametrize("codes", [{16: "B"}, {55: 1}, {16: "Z"}, {16: 10}, {16: 1, "16": 2}, {15: "B", 55: "A"}])
def test_invalid_codes(codes):
    with pytest.raises(InputError):
        di.dmft_permanent(codes)


def test_blank_codes_skipped():
    r = di.dmft_permanent({16: "", 26: None, 36: "1"})
    assert r.value == 1 and r["teeth_present"] == 1


def test_dmfs_missing_surfaces_and_surface_codes():
    surfaces = {
        16: 4,                                   # missing due to caries: 5 surfaces
        11: 4,                                   # anterior: 4 surfaces
        36: {"O": 1, "M": 3, "D": 0, "B": 0, "L": 0},
        21: {"M": 2, "D": 0, "B": 0, "L": 3},
        46: {"O": 6, "M": 0, "D": 0, "B": 0, "L": 0},
    }
    r = di.dmfs_permanent(surfaces, age=20)
    assert (r["DS"], r["MS"], r["FS"], r.value) == (2, 9, 2, 13)


def test_dmfs_errors_and_warnings():
    with pytest.raises(InputError):
        di.dmfs_permanent({11: {"O": 1}})                 # no occlusal surface on anterior teeth (WHO form)
    with pytest.raises(InputError):
        di.dmfs_permanent({16: {"O": 4, "M": 1}})         # whole-tooth code mixed with surface codes
    r = di.dmfs_permanent({16: {"O": 1, "M": 0}})
    assert any("not recorded" in w for w in r.warnings)
    assert di.dmfs_permanent({17: 5}, age=40)["MS"] == 5
    assert di.dmfs_permanent({17: 5}, age=20)["MS"] == 0


def test_dmfs_primary():
    r = di.dmfs_primary({55: "E", 51: "E", 54: {"O": "B", "M": "D", "D": "A", "B": "A", "L": "A"}})
    assert (r["ds"], r["ms"], r["fs"], r.value) == (1, 9, 1, 11)


def test_pufa():
    r = di.pufa({16: "P", 36: "a", 55: "p", 74: "F", 26: "", 46: 0}, decayed_teeth=8)
    assert r["PUFA"] == 2 and r["pufa"] == 2 and r.value == 4
    assert r["P"] == 1 and r["A"] == 1 and r["p"] == 1 and r["f"] == 1
    assert r["percent_decayed_progressed"] == 50
    with pytest.raises(InputError):
        di.pufa({16: "PA"})
    with pytest.raises(InputError):
        di.pufa({16: "X"})
    w = di.pufa({16: "P"}, decayed_teeth=0)
    assert w["percent_decayed_progressed"] is None and w.warnings


def test_result_helpers():
    r = di.dmft_permanent({16: 1}, age=12)
    d = r.to_dict()
    assert d["value"] == 1 and d["index"] == "dmft_permanent" and d["sources"] == ["who2013"]
    row = r.row()
    assert row["dmft_permanent"] == 1 and "D_teeth" not in row
    assert "DMFT" in str(r) and r.references()
    with pytest.raises(KeyError):
        r["nope"]
