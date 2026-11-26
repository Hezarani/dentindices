"""The result object every index function returns."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator

from ._registry import cite, index_info


@dataclass(frozen=True)
class IndexResult:
    """The outcome of one index calculation.

    Attributes
    ----------
    index : registry id of the index (e.g. ``"dmft_permanent"``).
    value : the headline score (number or category).
    components : the named parts of the score (e.g. ``{"D": 2, "M": 1, "F": 3}``).
    category : interpretation band or classification label, if the index has one.
    guidance : short paraphrase of the published clinical guidance, if any.
    trace : the reasoning steps, in order, so a reader can check every rule applied.
    warnings : data problems and judgement calls the user should know about.
    sources : registry source ids behind the rules used.
    """

    index: str
    value: Any
    components: dict[str, Any] = field(default_factory=dict)
    category: str | None = None
    guidance: str | None = None
    trace: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()

    # -- convenience -------------------------------------------------------------------------
    @property
    def name(self) -> str:
        return index_info(self.index)["name"]

    def references(self) -> list[str]:
        """Formatted references for the sources behind this result."""
        refs: list[str] = []
        for s in self.sources:
            for r in cite(s):
                if r not in refs:
                    refs.append(r)
        return refs

    def to_dict(self) -> dict[str, Any]:
        """A plain dictionary (JSON-serialisable) of the full result."""
        return {
            "index": self.index,
            "value": self.value,
            "components": dict(self.components),
            "category": self.category,
            "guidance": self.guidance,
            "trace": list(self.trace),
            "warnings": list(self.warnings),
            "sources": list(self.sources),
        }

    def row(self) -> dict[str, Any]:
        """A flat row (value, category and components) for building tables or CSV files."""
        out: dict[str, Any] = {self.index: self.value}
        if self.category is not None:
            out[f"{self.index}_category"] = self.category
        for k, v in self.components.items():
            if isinstance(v, (int, float, str, bool)) or v is None:
                out[k] = v
        return out

    def __getitem__(self, key: str) -> Any:
        if key in self.components:
            return self.components[key]
        if key in ("value", "category", "guidance", "index"):
            return getattr(self, key)
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return iter(self.to_dict())

    def __str__(self) -> str:
        lines = [f"{self.name}: {self.value}" + (f" ({self.category})" if self.category else "")]
        for k, v in self.components.items():
            if isinstance(v, (int, float, str, bool)) or v is None:
                lines.append(f"  {k}: {v}")
        if self.guidance:
            lines.append(f"  guidance: {self.guidance}")
        for w in self.warnings:
            lines.append(f"  warning: {w}")
        return "\n".join(lines)
