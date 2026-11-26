"""Release consistency: version numbers, generated web data and citation metadata agree."""
import json
import re
from pathlib import Path

import dentindices as di
from dentindices._registry import registry

ROOT = Path(__file__).resolve().parents[1]


def _pyproject_version():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    return re.search(r'^version = "([^"]+)"', text, re.M).group(1)


def test_versions_agree():
    v = _pyproject_version()
    assert di.__version__ == v
    cff = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    assert re.search(r'^version: "([^"]+)"', cff, re.M).group(1) == v
    assert f"## {v}" in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    web = (ROOT / "docs" / "indices-data.js").read_text(encoding="utf-8")
    assert f'"package_version": "{v}"' in web or f'"package_version":"{v}"' in web


def test_zenodo_metadata_is_valid_json_with_all_sources():
    z = json.loads((ROOT / ".zenodo.json").read_text(encoding="utf-8"))
    assert z["upload_type"] == "software" and z["license"] == "mit"
    assert z["creators"][0]["orcid"] == "0009-0007-8481-0498"
    refs = " ".join(z["references"])
    for key, s in registry()["sources"].items():
        if s.get("doi"):
            assert s["doi"] in refs, key


def test_every_source_is_in_readme_and_paper_bib():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    bib = (ROOT / "paper.bib").read_text(encoding="utf-8")
    for key, s in registry()["sources"].items():
        assert re.search(r"@\w+\{" + re.escape(key) + ",", bib), key
        if s.get("doi"):
            assert s["doi"] in readme, key


def test_paper_citations_resolve():
    paper = (ROOT / "paper.md").read_text(encoding="utf-8")
    bib = (ROOT / "paper.bib").read_text(encoding="utf-8")
    keys = set(re.findall(r"@(\w+)", paper)) - {"misc", "article", "book"}
    for k in keys:
        assert re.search(r"@\w+\{" + re.escape(k) + ",", bib), k


def test_every_index_is_documented_and_exported():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    spec = (ROOT / "docs" / "INDICES.md").read_text(encoding="utf-8")
    for info in di.list_indices():
        name = info["id"]
        assert callable(getattr(di, name)), name
        assert f"`{name}()" in readme, name
        assert f"`{name}()" in spec, name


def test_web_app_files_present_and_csp_blocks_network():
    html = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
    assert "connect-src 'none'" in html
    for f in ("app.js", "dentindices.js", "indices-data.js", "examples-data.js"):
        assert f'src="{f}"' in html
        assert (ROOT / "docs" / f).exists()
    for f in ("social-preview.png", "apple-touch-icon.png", "robots.txt", "sitemap.xml"):
        assert (ROOT / "docs" / f).exists(), f
