import json
import subprocess
import sys
from importlib import resources

import pytest

import dentindices as di
from dentindices.cli import main


def example(name):
    return str(resources.files("dentindices.data").joinpath("examples", name))


def test_read_csv_semicolon_and_text():
    rows = di.read_csv("id;16;26\nA;1;3\n", text=True)
    assert rows == [{"id": "A", "16": "1", "26": "3"}]


def test_batch_dmft_on_example_survey():
    rows = di.read_csv(example("caries_survey.csv"))
    out = di.batch(rows, "dmft_permanent")
    assert len(out) == 120 and not any("error" in r for r in out)
    assert all("16" not in r for r in out)          # tooth columns are not copied
    assert out[0]["id"] == "P001" and "age_group" in out[0]
    # the batch value equals a direct call
    r0 = rows[60]
    teeth = {k: v for k, v in r0.items() if k.isdigit() and v}
    assert out[60]["dmft_permanent"] == di.dmft_permanent(teeth, r0["age"]).value


def test_batch_records_errors_and_raise_mode():
    rows = [{"id": "x", "16": "Q"}, {"id": "y", "16": "1"}]
    out = di.batch(rows, "dmft_permanent")
    assert "error" in out[0] and out[1]["dmft_permanent"] == 1
    with pytest.raises(di.InputError):
        di.batch(rows, "dmft_permanent", on_error="raise")
    with pytest.raises(di.InputError):
        di.batch(rows, "aces")


def test_batch_sextant_indices_and_dai():
    assert di.batch(di.read_csv(example("bpe_survey.csv")), "bpe")[0]["bpe"] in range(5)
    b = di.batch(di.read_csv(example("bewe_survey.csv")), "bewe")
    assert all(0 <= r["BEWE"] <= 18 for r in b)
    rows = [{"id": 1, "missing_visible_teeth": 0, "crowding": 1, "spacing": 0, "diastema_mm": 0,
             "max_anterior_irregularity_mm": 0, "mand_anterior_irregularity_mm": 0, "max_overjet_mm": 3,
             "mand_overjet_mm": 0, "openbite_mm": 0, "molar_relation": 0}]
    assert di.batch(rows, "dai")[0]["dai"] == 20
    assert "error" in di.batch([{"id": 1}], "dai")[0]


def test_batch_perio_example():
    out = di.batch_perio(di.read_csv(example("perio_chart_long.csv")))
    by = {r["id"]: r for r in out}
    assert by["A01"]["aces_status"] == "health" and by["A01"]["cdc_aap"] == "no periodontitis"
    assert by["A02"]["aces_status"] == "generalized gingivitis"
    assert by["A03"]["aces_stage"] == "II"
    assert by["A04"]["aces_stage"] == "III" and by["A04"]["aces_grade"] == "C"      # 15 cigarettes/day
    assert by["A05"]["aces_stage"] == "IV" and by["A05"]["aces_grade"] == "C"       # HbA1c 8.1
    assert by["A06"]["aces_status"] == "edentulous" and by["A06"]["cdc_aap"] == "edentulous"


def test_summary_table_groups_and_overall():
    rows = di.batch(di.read_csv(example("caries_survey.csv")), "dmft_permanent")
    table = di.summary_table(rows, "DMFT", by="age_group")
    labels = [r["age_group"] for r in table]
    assert labels == ["5", "12", "35-44", "65-74", "All"]
    twelve = table[1]
    vals = [r["DMFT"] for r in rows if r["age_group"] == "12"]
    assert twelve["n"] == 40 and twelve["mean"] == pytest.approx(sum(vals) / 40)
    assert twelve["SiC"] == pytest.approx(di.sic(vals).value)
    with pytest.raises(di.InputError):
        di.summary_table(rows, "nope")


def test_write_csv_roundtrip(tmp_path):
    p = tmp_path / "o.csv"
    text = di.write_csv([{"a": 1, "b": True, "c": None, "d": 0.123456789}], str(p))
    assert p.read_text() == text == "a,b,c,d\n1,TRUE,,0.123457\n"


def test_cli_commands(tmp_path, capsys):
    assert main(["list"]) == 0
    assert "aces" in capsys.readouterr().out
    assert main(["cite", "bewe"]) == 0
    assert "10.1007/s00784-007-0181-5" in capsys.readouterr().out
    assert main(["dmft", "16=1,26=3,36=4,55=B", "--age", "12"]) == 0
    out = capsys.readouterr().out
    assert "DMFT" in out and "dmft" in out
    assert main(["dmft", "16=1", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["permanent"]["value"] == 1
    assert main(["dmft", "16-1"]) == 2
    assert main(["examples", str(tmp_path)]) == 0
    assert (tmp_path / "caries_survey.csv").exists()
    o = tmp_path / "out.csv"
    assert main(["batch", "dmft_permanent", str(tmp_path / "caries_survey.csv"), "-o", str(o),
                 "--exclude-third-molars"]) == 0
    s = tmp_path / "s.csv"
    assert main(["summary", str(o), "--column", "DMFT", "--by", "age_group", "-o", str(s)]) == 0
    assert "SiC" in s.read_text()
    assert main(["perio", str(tmp_path / "perio_chart_long.csv")]) == 0
    assert "aces_stage" in capsys.readouterr().out
    assert main(["info"]) == 0
    assert "indices" in capsys.readouterr().out


def test_module_entry_point():
    r = subprocess.run([sys.executable, "-m", "dentindices", "--version"], capture_output=True, text=True)
    assert r.returncode == 0 and di.__version__ in r.stdout
