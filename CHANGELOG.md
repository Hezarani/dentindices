# Changelog

## 1.0.0 — 2026-11-23

First public release.

### Added
- **Cited registry** (`dentindices/data/indices.json`): code tables, thresholds and interpretation
  bands for 26 indices, 35 sources (27 with DOIs), a verification level (primary or secondary)
  for every index, and 17 documented decisions where sources are silent or disagree.
- **Caries**: DMFT/dmft and DMFS/dmfs with WHO 2013 codes (age-30 M rule, mixed dentition, same-space
  rule, optional third-molar exclusion), PUFA/pufa, SiC (and SiC10, four rounding modes), SaC, Care
  Index, Restorative Index, D/M/F component shares, WHO caries-experience levels.
- **Periodontal screening**: BPE (BSP 2019) by sextant or by tooth, simplified BPE for under-18s
  (BSP/BSPD 2021), CPITN with treatment need, WHO 2013 modified CPI and loss of attachment.
- **Hygiene and gingival indices**: Plaque Index, Gingival Index, Plaque Control Record, OHI-S with
  tooth substitution.
- **Tooth wear, fluorosis, occlusion**: BEWE by sextant or by tooth, Dean's index (WHO or Dean
  scale), Community Fluorosis Index, Dental Aesthetic Index.
- **Periodontitis case definitions**: CDC/AAP (Eke 2012, with options for the two ambiguous details
  of the mild definition) and ACES (Holtfreter 2024) with stage, extent and grade for completed and
  planned surveys, plus continuous summary measures; a warning when a partial-mouth chart is staged
  without `teeth_present`.
- **Surveys**: CSV reading and writing (comma, semicolon or tab; any line ending; UTF-8, or
  Windows-1252/1254 for older spreadsheet exports; empty rows skipped; duplicate columns rejected;
  "NA" and "-" read as not recorded; cells that could run as spreadsheet formulas are escaped), `batch()` and
  `batch_perio()` (ACES and CDC/AAP options) with per-row error capture, `summarize()` and `summary_table()` (mean, SD, SE,
  t-based CI, median, prevalence with Wilson CI, and SiC and SaC for caries columns, by group).
- **Command-line tool**: `dentindices list | cite | dmft | batch | perio | summary | examples | info`.
- **Web app** (GitHub Pages): calculators for every index family and whole-survey processing, all on
  the device (no network requests), keyboard and screen-reader support, dark mode, reduced motion.
- **Tests**: 261 checks, including 2,100 randomised Python ↔ JavaScript parity cases per run that
  compare values, components, categories, warnings and every line of the calculation trace;
  GitHub Actions on Python 3.10–3.14 and PyPI Trusted Publishing on release.
- **Independent review** before release: every DOI checked against Crossref, the definitions checked
  against the openly available sources, and the software, web app and release files audited; all
  findings were fixed and are covered by regression tests (`tests/test_audit_fixes.py`).
