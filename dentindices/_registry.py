"""The index registry: codes, thresholds, sources and verification status.

Every rule DentIndices applies is read from ``data/indices.json`` so that the Python package and the
browser app share one cited definition. This module loads it once and offers small helpers.
"""
from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Any

from ._errors import InputError


class UnknownIdError(InputError, KeyError):
    """An index or source id that is not in the registry (both an InputError and a KeyError)."""

    def __str__(self) -> str:  # KeyError would add quotes around the message
        return str(self.args[0]) if self.args else ""

__all__ = [
    "registry",
    "codes",
    "index_info",
    "source",
    "cite",
    "list_indices",
    "require_verified",
    "IndexNotVerifiedError",
    "band",
]

VERIFIED_LEVELS = ("primary", "secondary")


class IndexNotVerifiedError(RuntimeError):
    """Raised when an index has not been verified against its source and is therefore switched off."""


@lru_cache(maxsize=1)
def registry() -> dict[str, Any]:
    """Return the parsed registry (``data/indices.json``)."""
    text = resources.files("dentindices.data").joinpath("indices.json").read_text(encoding="utf-8")
    return json.loads(text)


def codes(name: str) -> dict[str, Any]:
    """Return a code table / threshold block from the registry by name (e.g. ``"bpe"``)."""
    try:
        return registry()["codes"][name]
    except KeyError:
        raise KeyError(f"No code table named {name!r} in the registry") from None


def index_info(index_id: str) -> dict[str, Any]:
    """Return the registry entry for an index (name, family, sources, verification)."""
    reg = registry()["indices"]
    if not isinstance(index_id, str) or index_id not in reg:
        raise UnknownIdError(f"Unknown index {index_id!r}. Known indices: {', '.join(sorted(reg))}")
    return reg[index_id]


def list_indices() -> list[dict[str, Any]]:
    """List every index with its id, name, family, level and verification status."""
    out = []
    for key, info in registry()["indices"].items():
        out.append({
            "id": key,
            "name": info["name"],
            "family": info["family"],
            "level": info["level"],
            "verification": info["verification"]["status"],
            "sources": list(info["sources"]),
        })
    return out


def source(source_id: str) -> dict[str, Any]:
    """Return a bibliographic record from the registry."""
    reg = registry()["sources"]
    if not isinstance(source_id, str) or source_id not in reg:
        raise UnknownIdError(f"Unknown source {source_id!r}")
    return reg[source_id]


def _format_source(rec: dict[str, Any]) -> str:
    parts = [f"{rec['authors']} ({rec['year']}). {rec['title']}."]
    if rec.get("container"):
        loc = rec["container"]
        if rec.get("volume"):
            loc += f" {rec['volume']}"
            if rec.get("issue"):
                loc += f"({rec['issue']})"
        if rec.get("pages"):
            loc += f":{rec['pages']}"
        parts.append(loc + ".")
    elif rec.get("publisher"):
        parts.append(rec["publisher"] + ".")
    if rec.get("doi"):
        parts.append(f"https://doi.org/{rec['doi']}")
    elif rec.get("url"):
        parts.append(rec["url"])
    elif rec.get("pmid"):
        parts.append(f"PMID {rec['pmid']}")
    return " ".join(parts)


def cite(index_or_source: str) -> list[str]:
    """Formatted references for an index id (all its sources) or for a single source id."""
    reg = registry()
    if not isinstance(index_or_source, str):
        raise UnknownIdError(f"{index_or_source!r} is neither an index nor a source id")
    if index_or_source in reg["indices"]:
        return [_format_source(reg["sources"][s]) for s in reg["indices"][index_or_source]["sources"]]
    if index_or_source in reg["sources"]:
        return [_format_source(reg["sources"][index_or_source])]
    raise UnknownIdError(f"{index_or_source!r} is neither an index nor a source id "
                         f"(see dentindices.list_indices())")


def require_verified(index_id: str) -> None:
    """Refuse to compute an index whose definition has not been verified against its source."""
    status = index_info(index_id)["verification"]["status"]
    if status not in VERIFIED_LEVELS:
        raise IndexNotVerifiedError(
            f"{index_id} is not verified against its source (status: {status}); it is switched off."
        )


def band(value: float | None, bands: list[dict[str, Any]], round_to: int | None = None) -> str | None:
    """Return the label of the first band whose upper limit (``upto``, inclusive) holds ``value``.

    Published bands are usually written to one decimal place (e.g. 0.1-0.9, 1.0-1.9). When
    ``round_to`` is given the value is rounded half-up to that many decimals before comparison, so a
    mean of 0.95 is read as 1.0, exactly as a reader of the published table would.
    """
    if value is None:
        return None
    v = _round_half_up(value, round_to) if round_to is not None else value
    for b in bands:
        if b["upto"] is None or v <= b["upto"] + 1e-12:
            return b["label"]
    return bands[-1]["label"]


def band_entry(value: float, bands: list[dict[str, Any]], round_to: int | None = None) -> dict[str, Any]:
    v = _round_half_up(value, round_to) if round_to is not None else value
    for b in bands:
        if b["upto"] is None or v <= b["upto"] + 1e-12:
            return b
    return bands[-1]


def _round_half_up(value: float, digits: int) -> float:
    """Round half away from zero (what readers of published tables expect), not banker's rounding."""
    from decimal import ROUND_HALF_UP, Decimal

    q = Decimal(1).scaleb(-digits)
    return float(Decimal(repr(value)).quantize(q, rounding=ROUND_HALF_UP))
