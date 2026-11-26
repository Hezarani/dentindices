"""DentIndices: open, tested, source-cited oral-health epidemiology indices.

Every index follows a named publication (WHO, BSP, CDC/AAP, ACES ...); every result carries its
reasoning trace and sources. Rules live in ``dentindices/data/indices.json``, shared with the
browser app. Research and education tool: not a diagnosis and not a substitute for clinical judgement.

>>> from dentindices import dmft_permanent
>>> r = dmft_permanent({16: 1, 26: 3, 36: 4, 46: 0}, age=12)
>>> r.value, r["DT"], r["MT"], r["FT"]
(3, 1, 1, 1)
"""
from __future__ import annotations

from ._errors import InputError
from ._registry import IndexNotVerifiedError, cite, index_info, list_indices, registry
from ._result import IndexResult
from ._teeth import ToothError
from .batch import batch, batch_perio, decode_text, read_csv, summary_table, write_csv
from .caries import caries_experience, dmfs_permanent, dmfs_primary, dmft_permanent, dmft_primary, pufa
from .fluorosis import community_fluorosis_index, dean_index
from .hygiene import gingival_index, ohi_s, plaque_control_record, plaque_index
from .occlusion import dai
from .perio_cases import PerioChart, aces, cdc_aap, perio_chart, perio_summary
from .perio_screening import bpe, bpe_from_teeth, cpi_modified, cpitn, loss_of_attachment, sbpe
from .population import (
    care_index,
    component_percentages,
    restorative_index,
    sac,
    sic,
    summarize,
    who_caries_level,
)
from .wear import bewe, bewe_from_teeth

__version__ = "1.0.0"

__all__ = [
    "__version__",
    # caries
    "dmft_permanent", "dmft_primary", "dmfs_permanent", "dmfs_primary", "caries_experience", "pufa",
    # population
    "summarize", "sic", "sac", "care_index", "restorative_index", "component_percentages", "who_caries_level",
    # periodontal screening
    "bpe", "bpe_from_teeth", "sbpe", "cpitn", "cpi_modified", "loss_of_attachment",
    # hygiene and gingival
    "plaque_index", "gingival_index", "plaque_control_record", "ohi_s",
    # wear, fluorosis, occlusion
    "bewe", "bewe_from_teeth", "dean_index", "community_fluorosis_index", "dai",
    # periodontitis case definitions
    "PerioChart", "perio_chart", "cdc_aap", "aces", "perio_summary",
    # survey processing
    "batch", "batch_perio", "summary_table", "read_csv", "write_csv",
    # registry and types
    "IndexResult", "InputError", "ToothError", "IndexNotVerifiedError", "registry", "list_indices", "index_info",
    "cite",
]
