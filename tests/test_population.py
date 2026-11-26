import math
import statistics

import pytest

import dentindices as di
from dentindices import InputError
from dentindices._stats import betainc, normal_quantile, t_cdf, t_quantile, wilson


@pytest.mark.parametrize("df,expected", [(1, 12.706204736174698), (2, 4.302652729749464), (10, 2.2281388519862744),
                                         (30, 2.0422724563012373), (1000, 1.9623390808264078)])
def test_t_quantile_reference_values(df, expected):
    # reference values: scipy.stats.t.ppf(0.975, df)
    assert t_quantile(0.975, df) == pytest.approx(expected, abs=1e-9)


def test_normal_quantile_and_t_cdf():
    assert normal_quantile(0.975) == pytest.approx(1.959963984540054, abs=1e-8)
    assert normal_quantile(0.5) == pytest.approx(0.0, abs=1e-12)
    assert normal_quantile(0.001) == pytest.approx(-3.090232306167813, abs=1e-7)
    assert t_cdf(0.0, 5) == pytest.approx(0.5)
    assert betainc(2, 3, 0.4) == pytest.approx(0.5248, abs=1e-12)   # closed form: 1-(0.6^4)(1+4*0.4)... = 0.5248


def test_wilson_reference():
    lo, hi = wilson(25, 40)
    # reference: statsmodels proportion_confint(25, 40, method="wilson")
    assert lo == pytest.approx(0.470324, abs=1e-6) and hi == pytest.approx(0.757770, abs=1e-6)
    assert wilson(0, 10)[0] == 0.0


def test_summarize_matches_statistics_module():
    vals = [0, 0, 1, 2, 3, 5, 8, None, ""]
    s = di.summarize(vals)
    x = [0, 0, 1, 2, 3, 5, 8]
    assert s["n"] == 7
    assert s["mean"] == pytest.approx(statistics.mean(x))
    assert s["sd"] == pytest.approx(statistics.stdev(x))
    assert s["se"] == pytest.approx(statistics.stdev(x) / math.sqrt(7))
    tq = t_quantile(0.975, 6)
    assert s["ci_low"] == pytest.approx(statistics.mean(x) - tq * s["se"])
    assert s["median"] == 2 and s["min"] == 0 and s["max"] == 8
    assert s["n_positive"] == 5 and s["prevalence"] == pytest.approx(500 / 7)
    assert di.summarize([])["mean"] is None
    one = di.summarize([3])
    assert one["sd"] is None and one["ci_low"] is None


def test_summarize_weights():
    s = di.summarize([0, 2, 4], weights=[1, 1, 2])
    assert s["weighted_mean"] == pytest.approx(10 / 4)
    assert s["weighted_prevalence"] == pytest.approx(75)
    with pytest.raises(InputError):
        di.summarize([1, 2], weights=[1])


def test_sic_rounding_modes():
    vals = [0, 0, 0, 1, 1, 2, 3, 5, 8, 9]          # n = 10, a third = 3.33
    assert di.sic(vals).value == pytest.approx((9 + 8 + 5) / 3)          # nearest -> 3
    assert di.sic(vals, rounding="ceil").value == pytest.approx((9 + 8 + 5 + 3) / 4)
    assert di.sic(vals, rounding="floor")["group_size"] == 3
    frac = di.sic(vals, rounding="fractional").value
    assert frac == pytest.approx((9 + 8 + 5 + 3 * (10 / 3 - 3)) / (10 / 3))
    assert di.sic(vals, fraction=0.1).value == 9                         # SiC10
    with pytest.raises(InputError):
        di.sic([])


def test_sic_warns_when_caries_free_in_top_third():
    r = di.sic([0] * 8 + [2])
    assert r["caries_free_in_group"] == 2 and r.warnings


def test_sac_matches_schmoeckel_2019_illustration():
    # Schmoeckel 2019: in 2016, prevalence 21.2% and mean DMFT ~0.4 gave SaC 2.1.
    vals = [0] * 788 + [2] * 190 + [3] * 22     # 212 affected of 1000, total 446
    s = di.sac(vals)
    assert s["prevalence"] == pytest.approx(21.2)
    assert s.value == pytest.approx(446 / 212) and round(s.value, 1) == 2.1
    assert di.sac([0, 0]).value is None


def test_care_restorative_and_components():
    recs = [{"DT": 2, "MT": 1, "FT": 1}, di.dmft_permanent({16: 3, 26: 3, 36: 1}, age=12)]
    ci = di.care_index(recs)
    assert ci.value == pytest.approx(100 * 3 / 7)
    ri = di.restorative_index(recs)
    assert ri.value == pytest.approx(100 * 3 / 6)
    cp = di.component_percentages(recs)
    assert cp["percent_D"] == pytest.approx(300 / 7) and cp["percent_M"] == pytest.approx(100 / 7)
    assert di.care_index([{"DT": 0, "MT": 0, "FT": 0}]).value is None
    with pytest.raises(InputError):
        di.care_index([{"DT": 1, "MT": 0, "FT": 0}, {"dt": 1, "mt": 0, "ft": 0}])
    assert di.care_index([di.dmft_primary({55: "D", 54: "B"})]).value == 50


@pytest.mark.parametrize("mean,group,label", [
    (1.1, "12", "Very low"), (1.14, "12", "Very low"), (1.15, "12", "Very low"), (1.19, "12", "Very low"),
    (1.2, "12", "Low"), (2.6, "12", "Low"), (2.64, "12", "Low"), (2.65, "12", "Moderate"),
    (2.7, "12", "Moderate"), (4.4, "12", "Moderate"), (4.45, "12", "High"), (4.5, "12", "High"),
    (6.5, "12", "High"), (6.52, "12", "Very high"), (6.55, "12", "Very high"),
    (4.9, "35-44", "Very low"), (4.95, "35-44", "Very low"), (5.0, "35-44", "Low"), (8.9, "35-44", "Low"),
    (8.94, "35-44", "Low"), (8.95, "35-44", "Moderate"), (13.9, "35-44", "Moderate"),
    (13.95, "35-44", "High"), (14.0, "35-44", "High")])
def test_who_caries_levels(mean, group, label):
    assert di.who_caries_level(mean, group).value == label


def test_who_caries_level_rejects_other_ages():
    with pytest.raises(InputError):
        di.who_caries_level(2.0, "15")
