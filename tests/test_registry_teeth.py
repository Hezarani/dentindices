import pytest

import dentindices as di
from dentindices import _teeth as T
from dentindices._registry import IndexNotVerifiedError, band, codes, registry, require_verified


def test_registry_integrity():
    reg = registry()
    sources = reg["sources"]
    assert set(reg["verification_levels"]) == {"primary", "secondary", "interpretation"}
    for key, info in reg["indices"].items():
        assert info["verification"]["status"] in ("primary", "secondary"), key
        for s in info["sources"]:
            assert s in sources, (key, s)
    for name, block in reg["codes"].items():
        if "source" in block:
            assert block["source"] in sources, name
    for d in reg["discrepancies"]:
        assert d["index"] in reg["indices"]
        for s in d["sources"]:
            assert s in sources
    for sid, rec in sources.items():
        assert rec["authors"] and rec["year"] and rec["title"], sid
        assert rec.get("doi") or rec.get("url") or rec.get("pmid") or rec.get("access"), sid


def test_every_index_has_a_public_function():
    names = set(di.__all__)
    for key in registry()["indices"]:
        assert key in names, key


def test_cite_and_list():
    refs = di.cite("bewe")
    assert any("10.1007/s00784-007-0181-5" in r for r in refs)
    rows = di.list_indices()
    assert len(rows) == len(registry()["indices"])
    with pytest.raises(KeyError):
        di.cite("nope")


def test_verification_gate(monkeypatch):
    reg = registry()
    monkeypatch.setitem(reg["indices"]["bewe"]["verification"], "status", "unverified")
    with pytest.raises(IndexNotVerifiedError):
        require_verified("bewe")
    with pytest.raises(IndexNotVerifiedError):
        di.bewe([0, 0, 0, 0, 0, 0])


def test_band_rounding_half_up():
    bands = codes("plaque_index")["bands"]
    assert band(0.0, bands, 1) == "Excellent"
    assert band(0.04, bands, 1) == "Excellent"     # reads as 0.0
    assert band(0.05, bands, 1) == "Good"          # reads as 0.1
    assert band(0.94, bands, 1) == "Good"
    assert band(0.95, bands, 1) == "Fair"          # reads as 1.0, half up
    assert band(1.95, bands, 1) == "Poor"
    assert band(None, bands, 1) is None


@pytest.mark.parametrize("raw,expected", [(16, 16), ("16", 16), ("1.6", 16), ("t46", 46), (" 55 ", 55)])
def test_parse_tooth(raw, expected):
    assert T.parse_tooth(raw) == expected


@pytest.mark.parametrize("raw", [19, "10", 0, "ab", 86, True, 1.6, None])
def test_parse_tooth_rejects(raw):
    with pytest.raises(T.ToothError):
        T.parse_tooth(raw)


def test_adjacency_and_pairs():
    assert T.adjacent(11, 21) and T.adjacent(31, 41) and T.adjacent(16, 17)
    assert not T.adjacent(14, 16) and not T.adjacent(11, 41) and not T.adjacent(18, 28)
    assert T.has_non_adjacent_pair([11, 13])
    assert not T.has_non_adjacent_pair([11, 21])
    assert not T.has_non_adjacent_pair([16])
    full = [q * 10 + p for q in (1, 2, 3, 4) for p in range(1, 9)]
    assert T.opposing_pairs(full) == 14            # third molars never count
    assert T.opposing_pairs([16, 46, 26]) == 1
    assert T.antagonist(16) == 46 and T.antagonist(21) == 31


def test_positions():
    assert T.primary_at_position(15) == 55 and T.primary_at_position(16) is None
    assert T.permanent_at_position(74) == 34
    assert T.sextant_of(18) == "S1" and T.sextant_of(43) == "S5" and T.sextant_of(38) == "S4"
    assert T.parse_sextant("ur") == "S1" and T.parse_sextant(6) == "S6"
