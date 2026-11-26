"""The browser engine (docs/dentindices.js) must give exactly what the Python package gives.

Runs a few thousand calls (hand-picked edge cases plus seeded random inputs) through both engines
via Node and compares value, components, category, guidance and warnings.
"""
import json
import math
import random
import shutil
import subprocess
from importlib import resources
from pathlib import Path

import pytest

import dentindices as di
from scripts.build_web_data import render, render_examples

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="Node.js is needed for the browser-engine parity tests")

SITES = ("MB", "B", "DB", "ML", "L", "DL")
PERM = [q * 10 + p for q in (1, 2, 3, 4) for p in range(1, 9)]
PRIM = [q * 10 + p for q in (5, 6, 7, 8) for p in range(1, 6)]


def run_js(cases):
    proc = subprocess.run([NODE, str(ROOT / "tests" / "js" / "run_engine.js")], input=json.dumps(cases),
                          capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def run_py(case):
    fn = getattr(di, case["fn"])
    try:
        r = fn(**case["args"])
    except (di.InputError, di.ToothError, ValueError) as e:
        return {"ok": False, "error": str(e)}
    if isinstance(r, dict) and "permanent" in r:
        return {"ok": True, "result": {k: json.loads(json.dumps(v.to_dict())) for k, v in r.items()}}
    if isinstance(r, di.IndexResult):
        return {"ok": True, "result": json.loads(json.dumps(r.to_dict()))}
    return {"ok": True, "result": json.loads(json.dumps(r))}


def same(a, b, path="$"):
    if isinstance(a, bool) or isinstance(b, bool):
        assert a is b or a == b and type(a) is type(b), f"{path}: {a!r} != {b!r}"
        return
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        assert math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9), f"{path}: {a!r} != {b!r}"
        return
    if isinstance(a, dict) and isinstance(b, dict):
        assert set(a) == set(b), f"{path}: keys differ {sorted(set(a) ^ set(b))}"
        for k in a:
            same(a[k], b[k], f"{path}.{k}")
        return
    if isinstance(a, list) and isinstance(b, list):
        assert len(a) == len(b), f"{path}: lengths {len(a)} != {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            same(x, y, f"{path}[{i}]")
        return
    assert a == b, f"{path}: {a!r} != {b!r}"


def compare(cases):
    js = run_js(cases)
    assert len(js) == len(cases)
    for case, j in zip(cases, js):
        p = run_py(case)
        label = f"{case['fn']} {json.dumps(case['args'])[:300]}"
        assert p["ok"] == j["ok"], f"{label}: python {p.get('error')} | js {j.get('error')}"
        if not p["ok"]:
            continue
        pr, jr = p["result"], j["result"]
        if case["fn"] == "caries_experience":
            for k in ("permanent", "primary"):
                for f in ("value", "components", "category", "guidance", "warnings", "trace"):
                    same(pr[k][f], jr[k][f], f"{label} {k}.{f}")
        elif "index" in pr:
            for f in ("value", "components", "category", "guidance", "warnings", "trace", "sources"):
                same(pr[f], jr[f], f"{label} .{f}")
        else:
            same(pr, jr, label)


def test_embedded_registry_is_current():
    assert (ROOT / "docs" / "indices-data.js").read_text(encoding="utf-8") == render(), \
        "docs/indices-data.js is stale: run python scripts/build_web_data.py"
    assert (ROOT / "docs" / "examples-data.js").read_text(encoding="utf-8") == render_examples(), \
        "docs/examples-data.js is stale: run python scripts/build_web_data.py"


# ------------------------------------------------------------------ hand-picked cases
HAND = [
    ("dmft_permanent", {"codes": {"16": 1, "26": 2, "36": 3, "46": 4, "17": 5, "37": 6, "47": 7, "18": 8, "28": 9, "11": 0}, "age": 25}),
    ("dmft_permanent", {"codes": {"16": 1, "17": 5}}),
    ("dmft_permanent", {"codes": {"16": 1, "17": 5}, "age": 30, "include_third_molars": False}),
    ("dmft_permanent", {"codes": {"16": 1, "17": 5}, "age": 10, "m_rule": "any_reason"}),
    ("dmft_permanent", {"codes": {"55": "B"}}),
    ("dmft_permanent", {"codes": {"16": "B"}}),
    ("dmft_permanent", {"codes": {"16": "x"}}),
    ("dmft_primary", {"codes": {"55": "B", "54": "c", "64": "E", "11": "A", "74": "D", "85": "F", "84": "G"}}),
    ("caries_experience", {"codes": {"16": 1, "55": "B", "15": 0, "64": "D"}, "age": 10}),
    ("caries_experience", {"codes": {"15": 8, "55": "B"}}),
    ("dmfs_permanent", {"surfaces": {"16": 4, "11": 4, "36": {"O": 1, "M": 3, "D": 0, "B": 0, "L": 0},
                                     "21": {"M": 2, "D": 0, "B": 0, "L": 3}, "46": {"O": 6, "M": 0}}, "age": 20}),
    ("dmfs_permanent", {"surfaces": {"11": {"O": 1}}}),
    ("dmfs_primary", {"surfaces": {"55": "E", "51": "E", "54": {"O": "B", "M": "D", "D": "A", "B": "A", "L": "A"}}}),
    ("pufa", {"codes": {"16": "P", "36": "a", "55": "p", "74": "F", "26": "", "46": 0}, "decayed_teeth": 8}),
    ("pufa", {"codes": {"16": "PA"}}),
    ("summarize", {"values": [0, 0, 1, 2, 3, 5, 8, None, ""]}),
    ("summarize", {"values": [0, 2, 4], "weights": [1, 1, 2]}),
    ("summarize", {"values": [3]}),
    ("summarize", {"values": []}),
    ("sic", {"values": [0, 0, 0, 1, 1, 2, 3, 5, 8, 9]}),
    ("sic", {"values": [0, 0, 0, 1, 1, 2, 3, 5, 8, 9], "rounding": "fractional"}),
    ("sic", {"values": [0] * 8 + [2], "fraction": 0.1}),
    ("sac", {"values": [0, 0, 2, 3]}),
    ("care_index", {"records": [{"DT": 2, "MT": 1, "FT": 1}, {"DT": 1, "MT": 0, "FT": 2}]}),
    ("restorative_index", {"records": [{"dt": 2, "mt": 1, "ft": 1}]}),
    ("component_percentages", {"records": [{"DT": 2, "MT": 1, "FT": 1}]}),
    ("who_caries_level", {"mean_dmft": 1.15, "age_group": "12"}),
    ("who_caries_level", {"mean_dmft": 13.95, "age_group": "35-44"}),
    ("who_caries_level", {"mean_dmft": 2.65, "age_group": "12"}),
    ("who_caries_level", {"mean_dmft": 6.52, "age_group": "12"}),
    ("who_caries_level", {"mean_dmft": 8.94, "age_group": "35-44"}),
    ("bpe", {"sextants": ["3*", 2, 1, "-", 0, "2"]}),
    ("bpe", {"sextants": {"UR": 4, "LL": "1*"}}),
    ("bpe", {"sextants": [5, 0, 0, 0, 0, 0]}),
    ("bpe_from_teeth", {"tooth_codes": {"16": 2, "18": 4, "26": 1, "28": 4, "44": 3, "48": 2, "31": 1},
                        "teeth_present": [17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 34, 35, 36, 37,
                                          33, 32, 31, 41, 42, 43, 44, 18, 28, 48]}),
    ("sbpe", {"index_teeth": {"16": 1, "11": 0, "26": 2, "36": 1, "31": 0, "46": 1}, "age": 9}),
    ("sbpe", {"index_teeth": {"16": "3*", "11": 0}, "age": 15}),
    ("sbpe", {"index_teeth": {"16": 3}, "age": 10}),
    ("cpitn", {"sextants": [3, 2, "X", 9, 1, 0], "age": 12}),
    ("cpitn", {"sextants": [0, 0, 0, 0, 0, 4], "age": 45}),
    ("cpi_modified", {"bleeding": {"16": 1, "11": 0, "26": 1, "36": 9, "46": "X", "31": 0},
                      "pockets": {"16": 2, "11": 0, "26": 1, "36": 9, "46": "X", "31": 0}, "age": 40}),
    ("cpi_modified", {"bleeding": {"16": 1}, "pockets": {"16": 1}, "age": 12}),
    ("loss_of_attachment", {"sextants": [0, 1, 2, "X", 9, 4], "age": 50}),
    ("loss_of_attachment", {"sextants": [0] * 6, "age": 14}),
    ("plaque_index", {"scores": {"16": [1, 1, 1, 1], "21": {"D": 0, "B": 1, "M": 1, "L": 1}, "24": [2, 2, 1, 1]}}),
    ("gingival_index", {"scores": {"16": [1, 1, 1, 2], "36": {"MB": 2, "L": 1}}}),
    ("plaque_control_record", {"plaque": {"16": "MD", "11": [], "26": {"M": 1, "B": True, "D": 0}}, "teeth_present": [16, 11, 26, 36]}),
    ("ohi_s", {"debris": {"16": 1, "11": 0, "27": 2, "36": 1, "41": 0, "46": 2}, "calculus": {"16": 0, "11": 0, "27": 1, "36": 1, "41": 0, "46": 1}}),
    ("ohi_s", {"debris": {"16": 1, "11": 1}}),
    ("ohi_s", {"debris": {"16": 1}}),
    ("bewe", {"sextants": [1, 1, 1, None, "-", 0]}),
    ("bewe", {"sextants": {"S1": 3, "S2": 3, "S3": 3, "S4": 3, "S5": 2, "S6": 0}}),
    ("bewe_from_teeth", {"scores": {"16": {"B": 1, "O": 2, "L": 0}, "15": 1, "11": {"B": 3, "O": 1}, "21": 0, "26": 1,
                                    "25": 0, "28": 3, "27": 0, "36": 1, "33": 2, "32": 0, "31": 0, "47": 1, "45": 0, "48": 3}}),
    ("bewe_from_teeth", {"scores": {"16": 1, "18": 3, "15": 0}, "teeth_present": [16, 15, 18]}),
    ("dean_index", {"teeth": {"11": 4, "21": 3, "16": 2, "26": 0, "36": 8}}),
    ("dean_index", {"teeth": {"11": 0.5, "21": 1}, "scale": "dean"}),
    ("dean_index", {"teeth": {"11": "questionable", "21": "normal"}}),
    ("community_fluorosis_index", {"person_scores": [0, 1, 2, 3, 3, 1, 8, 9]}),
    ("dai", {"missing_visible_teeth": 0, "crowding": 1, "spacing": 0, "diastema_mm": 2, "max_anterior_irregularity_mm": 3,
             "mand_anterior_irregularity_mm": 1, "max_overjet_mm": 4, "mand_overjet_mm": 0, "openbite_mm": 0,
             "molar_relation": 1, "age": 10}),
]


def test_hand_picked_cases():
    compare([{"fn": f, "args": a} for f, a in HAND])


# ------------------------------------------------------------------ random cases
def rand_dentition(rng):
    codes = {}
    for t in PERM:
        if rng.random() < 0.8:
            codes[str(t)] = rng.choice("0001123345678899")
    for t in PRIM:
        if rng.random() < 0.2:
            codes[str(t)] = rng.choice("AAABBCDEFG")
    return codes


def rand_chart(rng):
    teeth = [t for t in PERM if rng.random() < 0.85]
    if rng.random() < 0.05:
        teeth = []
    chart = {}
    sev = rng.random()
    for t in teeth:
        pd, cal, bop = {}, {}, {}
        for s in SITES:
            if rng.random() < 0.95:
                c = max(0, int(rng.gauss(sev * 4, 1.5)))
                cal[s] = c
                pd[s] = max(1, min(12, c + rng.choice([-1, 0, 0, 1, 2])))
                bop[s] = rng.random() < sev * 0.6
        chart[str(t)] = {"pd": pd, "cal": cal, "bop": bop}
    return chart


def random_cases(seed, n):
    rng = random.Random(seed)
    cases = []
    for _ in range(n):
        k = rng.randrange(16)
        if k == 0:
            cases.append({"fn": "dmft_permanent", "args": {"codes": rand_dentition(rng), "age": rng.choice([None, 8, 29, 30, 45.5]),
                                                          "include_third_molars": rng.random() < 0.7,
                                                          "m_rule": rng.choice(["who2013", "caries_only", "any_reason"])}})
        elif k == 1:
            cases.append({"fn": "caries_experience", "args": {"codes": rand_dentition(rng), "age": rng.choice([None, 9, 35])}})
        elif k == 2:
            surf = {}
            for t in rng.sample(PERM, 6):
                ant = t % 10 <= 3
                ss = ["M", "B", "D", "L"] + ([] if ant else ["O"])
                if rng.random() < 0.2:
                    surf[str(t)] = rng.choice("45")
                else:
                    surf[str(t)] = {s: rng.choice("0001236") for s in ss if rng.random() < 0.9}
            cases.append({"fn": "dmfs_permanent", "args": {"surfaces": surf, "age": rng.choice([None, 20, 40])}})
        elif k == 3:
            cases.append({"fn": "pufa", "args": {"codes": {str(t): rng.choice(["P", "u", "F", "A", "", 0]) for t in rng.sample(PERM + PRIM, 8)},
                                                "decayed_teeth": rng.choice([None, 0, 4, 12])}})
        elif k == 4:
            vals = [rng.choice([0, 0, 0, 1, 2, 3, 4, 6, 9]) for _ in range(rng.randrange(1, 40))]
            fn = rng.choice(["summarize", "sic", "sac"])
            args = {"values": vals}
            if fn == "sic":
                args.update(rounding=rng.choice(["nearest", "ceil", "floor", "fractional"]), fraction=rng.choice([1 / 3, 0.1, 0.5]))
            cases.append({"fn": fn, "args": args})
        elif k == 5:
            cases.append({"fn": "bpe", "args": {"sextants": [rng.choice(["0", "1", "2", "3", "4", "3*", "4*", "-", None]) for _ in range(6)]}})
        elif k == 6:
            cases.append({"fn": "cpitn", "args": {"sextants": [rng.choice(["0", "1", "2", "3", "4", "X", "9"]) for _ in range(6)],
                                                 "age": rng.choice([None, 12, 18, 40])}})
        elif k == 7:
            teeth = rng.sample(PERM, 12)
            cases.append({"fn": "cpi_modified", "args": {"bleeding": {str(t): rng.choice("0119X") for t in teeth},
                                                        "pockets": {str(t): rng.choice("00129X") for t in teeth},
                                                        "age": rng.choice([None, 13, 40])}})
        elif k == 8:
            teeth = rng.sample(PERM, rng.randrange(1, 10))
            fn = rng.choice(["plaque_index", "gingival_index"])
            cases.append({"fn": fn, "args": {"scores": {str(t): [rng.choice([0, 1, 2, 3, None]) for _ in range(4)] for t in teeth}}})
        elif k == 9:
            sites = {"UR": [16, 17], "UA": [11, 21], "UL": [26, 27], "LL": [36, 37], "LA": [31, 41], "LR": [46, 47]}
            chosen = rng.sample(list(sites), rng.randrange(1, 7))
            deb = {str(rng.choice(sites[s])): rng.randrange(4) for s in chosen}
            cal = {t: rng.randrange(4) for t in deb} if rng.random() < 0.8 else None
            cases.append({"fn": "ohi_s", "args": {"debris": deb, "calculus": cal}})
        elif k == 10:
            cases.append({"fn": "bewe", "args": {"sextants": [rng.choice([0, 1, 2, 3, None]) for _ in range(6)]}})
        elif k == 11:
            sc = {str(t): rng.randrange(4) for t in PERM if rng.random() < 0.6}
            cases.append({"fn": "bewe_from_teeth", "args": {"scores": sc}})
        elif k == 12:
            cases.append({"fn": "dean_index", "args": {"teeth": {str(t): rng.choice("0123458") for t in rng.sample(PERM, 6)}}})
            cases.append({"fn": "community_fluorosis_index", "args": {"person_scores": [rng.choice("0123459") for _ in range(rng.randrange(1, 30))]}})
        elif k == 13:
            cases.append({"fn": "dai", "args": {"missing_visible_teeth": rng.randrange(3), "crowding": rng.randrange(3), "spacing": rng.randrange(3),
                                               "diastema_mm": rng.randrange(4), "max_anterior_irregularity_mm": rng.randrange(5),
                                               "mand_anterior_irregularity_mm": rng.randrange(5), "max_overjet_mm": rng.randrange(9),
                                               "mand_overjet_mm": rng.choice([0, 0, 0, 2]), "openbite_mm": rng.choice([0, 0, 1, 3]),
                                               "molar_relation": rng.randrange(3)}})
        else:
            ch = rand_chart(rng)
            if k == 14:
                cases.append({"fn": "cdc_aap", "args": {"chart": ch, "mild_cal_distinct_teeth": rng.random() < 0.7,
                                                        "mild_pd5_any_site": rng.random() < 0.3}})
                cases.append({"fn": "perio_summary", "args": {"chart": ch}})
            else:
                args = {"chart": ch, "survey": rng.choice(["completed", "planned"]), "age": rng.choice([None, 35, 62]),
                        "furcation_class_2_3": rng.choice([None, True, False]), "teeth_lost_to_periodontitis": rng.choice([None, 0, 3, "1-4", ">=5", "unknown"]),
                        "mobility_degree2_at_2_teeth": rng.choice([None, True]), "cigarettes_per_day": rng.choice([None, 0, 5, 20]),
                        "diabetes": rng.choice([None, True, False]), "hba1c": rng.choice([None, 6.2, 8.4]),
                        "bone_loss_percent": rng.choice([None, 20, 55])}
                if rng.random() < 0.3:
                    args["bleeding_percent"] = rng.choice([5, 10, 25, 30, 45])
                if args["bone_loss_percent"] is None and rng.random() < 0.3:
                    args["root_length_mm"] = {str(t): rng.choice([11, 13, 15, 22]) for t in rng.sample(PERM, 5)}
                if rng.random() < 0.3:
                    args["teeth_present"] = list(PERM)
                cases.append({"fn": "aces", "args": args})
    return cases


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_random_parity(seed):
    compare(random_cases(seed, 700))


# ------------------------------------------------------------------ whole-survey processing
def _example(name):
    return di.read_csv(str(resources.files("dentindices.data").joinpath("examples", name)))


def test_batch_parity_on_examples():
    js_cases = []
    py = []
    for index, name in [("dmft_permanent", "caries_survey.csv"), ("dmft_primary", "caries_survey.csv"),
                        ("caries_experience", "caries_survey.csv"), ("bpe", "bpe_survey.csv"), ("bewe", "bewe_survey.csv")]:
        rows = _example(name)
        js_cases.append({"fn": "batch", "args": {"rows": rows, "index": index}})
        py.append(di.batch(rows, index))
    rows = _example("perio_chart_long.csv")
    js_cases.append({"fn": "batch_perio", "args": {"rows": rows}})
    py.append(di.batch_perio(rows))
    out = di.batch(_example("caries_survey.csv"), "dmft_permanent")
    js_cases.append({"fn": "summary_table", "args": {"rows": out, "column": "DMFT", "by": "age_group"}})
    py.append(di.summary_table(out, "DMFT", by="age_group"))
    js = run_js(js_cases)
    for p, j, c in zip(py, js, js_cases):
        assert j["ok"], j
        same(json.loads(json.dumps(p)), j["result"], c["fn"])


@pytest.mark.parametrize("text", [
    'id;16;note\nA;1;"x; y"\nB;;"say ""hi"""\n',
    'id,note,16\n1,5" crown,1\n\n,,\n2,x,0\n3,"a\nb",3\n',
    '\ufeffid\t16\t26\n1\t1\t\n2\t\t3\n'])
def test_js_csv_parser_matches_python(text):
    js = subprocess.run([NODE, "-e", "require('./docs/indices-data.js');const D=require('./docs/dentindices.js');"
                         "process.stdout.write(JSON.stringify(D.parseCSV(require('fs').readFileSync(0,'utf8'))))"],
                        input=text, capture_output=True, text=True, cwd=ROOT)
    assert json.loads(js.stdout) == di.read_csv(text, text=True)


def test_js_csv_parser_rejects_duplicate_headers_like_python():
    text = "id,16,16\n1,1,2\n"
    js = subprocess.run([NODE, "-e", "require('./docs/indices-data.js');const D=require('./docs/dentindices.js');"
                         "try{D.parseCSV(require('fs').readFileSync(0,'utf8'));process.stdout.write('ok')}"
                         "catch(e){process.stdout.write(e.name)}"], input=text, capture_output=True, text=True, cwd=ROOT)
    assert js.stdout == "InputError"
    with pytest.raises(di.InputError):
        di.read_csv(text, text=True)


def test_audit_cases_parity():
    from test_perio_cases import TEETH28, chart
    half = [t for t in TEETH28 if t // 10 in (1, 3)]
    few = [11, 12, 13, 14, 21, 22, 23, 31, 32, 33, 41, 42]
    compare([
        {"fn": "aces", "args": {"chart": chart(t16_MB=(4, 3), t26_DB=(4, 3), t31_B=(2, 6)), "age": 30,
                                "root_length_mm": {"31": 12, "16": 13}, "bleeding_percent": 5}},
        {"fn": "aces", "args": {"chart": chart(teeth=half, **{f"t{t}_MB": (6, 5) for t in half})}},
        {"fn": "aces", "args": {"chart": chart(teeth=few, t11_MB=(3, 2), t13_MB=(3, 2)), "survey": "planned",
                                "teeth_lost_to_periodontitis": "1-4", "teeth_present": few}},
        {"fn": "aces", "args": {"chart": chart(t16_MB=(4, 2), t26_MB=(4, 2)), "bleeding_percent": 5}},
        {"fn": "aces", "args": {"chart": chart(teeth=[11, 21])}},
        {"fn": "cdc_aap", "args": {"chart": chart(t16_MB=(3, 3), t26_DB=(3, 3), t36_B=(5, 0)), "mild_pd5_any_site": True}},
        {"fn": "bewe_from_teeth", "args": {"scores": {"16": 2, "17": None, "13": 1, "11": 1, "21": 1, "23": 1}}},
        {"fn": "summarize", "args": {"values": [1, "NA", "-", None, 3]}},
        {"fn": "summarize", "args": {"values": [9, 7], "confidence": "0.9"}},
        {"fn": "bpe", "args": {"sextants": None}},
        {"fn": "dmft_permanent", "args": {"codes": {"16": 1}, "age": "0x1E"}},
        {"fn": "dmft_permanent", "args": {"codes": {"16": 1}, "age": "1e1"}},
        {"fn": "summary_table", "args": {"rows": [{"g": "a", "mean_cal": 1.5}, {"g": "b", "mean_cal": 0}], "column": "mean_cal", "by": "g"}},
    ])


def _node(code, stdin=""):
    js = subprocess.run([NODE, "-e", "require('./docs/indices-data.js');const D=require('./docs/dentindices.js');" + code],
                        input=stdin, capture_output=True, text=True, cwd=ROOT)
    assert js.returncode == 0, js.stderr
    return js.stdout


def test_js_decode_text_matches_python():
    samples = ["caf\xe9 na\xefve".encode("cp1252"), "şehir ığ İstanbul".encode("cp1254"),
               "şehir ü".encode("utf-8"), "﻿id,16\n".encode("utf-8"), b"plain ascii"]
    for raw in samples:
        out = _node("process.stdout.write(D.decodeText(Buffer.from(process.argv[1], 'hex')))".replace(
            "process.argv[1]", repr(raw.hex())))
        assert out == di.decode_text(raw), raw


def test_js_to_csv_matches_python_write_csv():
    rows = [{"id": "A", "note": "=HYPERLINK(1)", "n": -3, "m": "-2+3", "x": "-", "y": None, "z": 'say "hi", ok'},
            {"id": "B", "note": "@x", "n": 2.5, "extra": "+1"}]
    js = _node("process.stdout.write(D.toCSV(JSON.parse(require('fs').readFileSync(0,'utf8'))))", json.dumps(rows))
    assert js == di.write_csv(rows)


def test_js_batch_perio_options_and_validation_match_python():
    rows = [{"id": "A", "tooth": t, "site": s, "pd": pd, "cal": cal}
            for t, s, pd, cal in [(16, "MB", 3, 3), (26, "DB", 3, 3), (36, "B", 5, 0), (11, "MB", 2, 0)]]
    code = ("const a=JSON.parse(require('fs').readFileSync(0,'utf8'));const out=[];"
            "for(const o of a){try{out.push(D.batch_perio(o)[0].cdc_aap)}catch(e){out.push(e.name)}}"
            "process.stdout.write(JSON.stringify(out))")
    calls = [{"rows": rows}, {"rows": rows, "cdc_options": {"mild_pd5_any_site": True}},
             {"rows": rows, "aces_options": {"mild_pd5_any_site": True}}, {"rows": rows, "cdc_options": {"nope": 1}},
             {"rows": 5}, {"rows": [1, 2]}]
    js = json.loads(_node(code, json.dumps(calls)))
    py = []
    for c in calls:
        try:
            py.append(di.batch_perio(c["rows"], cdc_options=c.get("cdc_options"), **c.get("aces_options", {}))[0]["cdc_aap"])
        except di.InputError:
            py.append("InputError")
    assert js == py == ["no periodontitis", "mild", "InputError", "InputError", "InputError", "InputError"]
