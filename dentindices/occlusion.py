"""Malocclusion: Dental Aesthetic Index (DAI; Cons, Jenny & Kohout 1986, as adopted by WHO 1997)."""
from __future__ import annotations

from typing import Any

from ._common import InputError, age_value, int_score
from ._registry import band_entry, codes, require_verified
from ._result import IndexResult

__all__ = ["dai"]


def _mm(v: Any, what: str) -> int:
    """Whole millimetres, as the WHO protocol records them."""
    return int_score(v, 0, 30, what + " (whole millimetres)")


def dai(*, missing_visible_teeth: Any, crowding: Any, spacing: Any, diastema_mm: Any,
        max_anterior_irregularity_mm: Any, mand_anterior_irregularity_mm: Any, max_overjet_mm: Any,
        mand_overjet_mm: Any, openbite_mm: Any, molar_relation: Any, age: Any = None) -> IndexResult:
    """Dental Aesthetic Index: the WHO (1997) regression equation

    6 x missing visible teeth + crowding + spacing + 3 x diastema + largest anterior maxillary
    irregularity + largest anterior mandibular irregularity + 2 x anterior maxillary overjet +
    4 x anterior mandibular overjet + 4 x vertical anterior openbite + 3 x antero-posterior molar
    relation + 13.

    ``missing_visible_teeth`` counts missing incisors, canines and premolars in both arches;
    crowding and spacing are 0-2 (segments affected); molar relation is 0 normal, 1 half cusp,
    2 full cusp; measurements are whole millimetres. Intended from age 12 (no primary teeth).
    """
    require_verified("dai")
    tab = codes("dai")
    w = tab["weights"]
    comp = {
        "missing_visible_teeth": int_score(missing_visible_teeth, 0, 20, "missing visible teeth"),
        "crowding": int_score(crowding, 0, 2, "crowding (segments)"),
        "spacing": int_score(spacing, 0, 2, "spacing (segments)"),
        "diastema": _mm(diastema_mm, "midline diastema"),
        "max_anterior_irregularity": _mm(max_anterior_irregularity_mm, "largest anterior maxillary irregularity"),
        "mand_anterior_irregularity": _mm(mand_anterior_irregularity_mm, "largest anterior mandibular irregularity"),
        "max_overjet": _mm(max_overjet_mm, "anterior maxillary overjet"),
        "mand_overjet": _mm(mand_overjet_mm, "anterior mandibular overjet"),
        "openbite": _mm(openbite_mm, "vertical anterior openbite"),
        "molar_relation": int_score(molar_relation, 0, 2, "antero-posterior molar relation"),
    }
    weighted = {k: comp[k] * w[k] for k in comp}
    score = sum(weighted.values()) + tab["constant"]
    level = band_entry(score, tab["bands"])
    warnings: list[str] = []
    a = age_value(age)
    if a is not None and a < 12:
        warnings.append("WHO recommends the DAI from about age 12, when no primary teeth remain.")
    if comp["max_overjet"] and comp["mand_overjet"]:
        warnings.append("Both maxillary and mandibular overjet are recorded; check the incisor relationship.")
    trace = ["Weighted components: " + ", ".join(f"{k} {comp[k]} x {w[k]} = {weighted[k]}" for k in comp) + ".",
             f"DAI = {sum(weighted.values())} + {tab['constant']} = {score} -> {level['label']} "
             f"(treatment: {level['treatment']})."]
    comps = {"DAI": score, **comp, "treatment_indication": level["treatment"]}
    return IndexResult("dai", score, comps, level["label"], f"Treatment indication: {level['treatment']}.",
                       tuple(trace), tuple(warnings), ("cons1986", "jenny1996", "who1997"))


_ = InputError
