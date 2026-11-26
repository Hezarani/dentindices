"""Whole-survey processing: one row per person in, one row of indices per person out, plus grouped
summaries (n, mean, SD, 95% CI, prevalence, SiC, SaC, Care Index) in the WHO 2013 reporting style.

Tooth columns are recognised by their FDI number ("16", "t16" or "1.6"); sextant columns by S1-S6
or UR, UA, UL, LL, LA, LR; periodontal charts come in long format (one row per site).
"""
from __future__ import annotations

import csv
import io
import re
from collections.abc import Iterable, Mapping
from typing import Any, Callable

from ._common import _NUMBER_RE, InputError, is_blank, seq
from ._result import IndexResult
from ._teeth import ToothError, parse_sextant, parse_tooth
from . import caries, fluorosis, occlusion, perio_cases, perio_screening, population, wear

__all__ = ["read_csv", "write_csv", "decode_text", "batch", "batch_perio", "summary_table", "TOOTH_INDICES", "SEXTANT_INDICES"]

TOOTH_INDICES = {"dmft_permanent", "dmft_primary", "caries_experience", "pufa", "dean_index"}
SEXTANT_INDICES = {"bpe", "bewe", "cpitn", "loss_of_attachment"}
OTHER_INDICES = {"dai"}


# Bytes that Windows-1252 reads as Ð Ý Þ ð ý þ are Ğ İ Ş ğ ı ş in the Turkish code page (1254).
_TURKISH_HINT = set("ÐÝÞðýþ")


def decode_text(raw: bytes, encoding: str | None = None) -> str:
    """Decode file bytes: UTF-8 (with or without byte-order mark) or, for files saved by older
    spreadsheet programs, Windows-1252 -- or Windows-1254 when the text is evidently Turkish.
    The browser app uses the same rule."""
    if encoding:
        try:
            return raw.decode(encoding)
        except (LookupError, UnicodeDecodeError) as e:
            raise InputError(f"Cannot decode the file as {encoding}: {e}") from None
    try:
        return raw.decode("utf-8-sig")  # a byte-order mark is dropped, as browsers do
    except UnicodeDecodeError:
        text = raw.decode("cp1252", errors="replace")
        return raw.decode("cp1254", errors="replace") if _TURKISH_HINT & set(text) else text


def read_csv(path_or_text: str, *, text: bool = False, encoding: str | None = None) -> list[dict[str, str]]:
    """Read a CSV file (or CSV text with ``text=True``) into a list of dicts.

    Detects comma, semicolon or tab delimiters and any line ending (Windows, Unix, old Mac); reads
    UTF-8 or, for older spreadsheet exports, Windows-1252/1254 (see :func:`decode_text`; pass
    ``encoding`` to choose); skips empty rows; and rejects headers that name a column twice."""
    if text:
        data = str(path_or_text)
    else:
        try:
            with open(path_or_text, "rb") as f:
                raw = f.read()
        except OSError as e:
            raise InputError(f"Cannot read {path_or_text!r}: {e.strerror or e}") from None
        data = decode_text(raw, encoding)
    data = data.lstrip("\ufeff")
    sample = data[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        delim = dialect.delimiter
    except csv.Error:
        delim = ","
    try:
        records = [r for r in csv.reader(io.StringIO(data, newline=""), delimiter=delim) if any(c.strip() for c in r)]
    except csv.Error as e:
        raise InputError(f"The file is not valid CSV: {e}") from None
    if not records:
        return []
    head = [h.strip() for h in records[0]]
    dup = sorted({h for h in head if h and head.count(h) > 1})
    if dup:
        raise InputError(f"The header names these columns more than once: {', '.join(dup)}")
    rows = []
    for rec in records[1:]:
        rows.append({h: (rec[i].strip() if i < len(rec) else "") for i, h in enumerate(head)})
    return rows


def write_csv(rows: list[Mapping[str, Any]], path: str | None = None) -> str:
    """Write rows to CSV (UTF-8). Returns the CSV text; also writes it to ``path`` if given."""
    cols: list[str] = []
    for r in rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({k: _fmt(r.get(k)) for k in cols})
    out = buf.getvalue()
    if path:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(out)
    return out


def _fmt(v: Any) -> Any:
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, float):
        return f"{v:.6g}" if abs(v) < 1e6 else repr(v)
    if v is None:
        return ""
    if isinstance(v, str) and (v[:1] in ("=", "+", "@", "\t", "\r")
                               or (v[:1] == "-" and len(v) > 1 and not _NUMBER_RE.fullmatch(v))):
        return "'" + v  # keep spreadsheet programs from running a cell as a formula
    return v


def _tooth_columns(row: Mapping[str, Any]) -> dict[str, int]:
    out: dict[str, int] = {}
    for k in row:
        try:
            out[k] = parse_tooth(k)
        except InputError:
            continue
    return out


def _sextant_columns(row: Mapping[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for k in row:
        try:
            out[k] = parse_sextant(k)
        except InputError:
            continue
    return out


def _check_duplicates(cols: dict[str, Any], what: str) -> None:
    seen: dict[Any, str] = {}
    for k, v in cols.items():
        if v in seen:
            raise InputError(f"Columns {seen[v]!r} and {k!r} are the same {what} ({v})")
        seen[v] = k


def _rows(rows: Any) -> list[Mapping[str, Any]]:
    rows = seq(rows, "rows")
    for i, r in enumerate(rows):
        if not isinstance(r, Mapping):
            raise InputError(f"Row {i + 1} is not a mapping of column -> value (use read_csv() to read a file)")
    return rows


def _num_or_none(v: Any) -> Any:
    return None if is_blank(v) else v


def batch(rows: Iterable[Mapping[str, Any]], index: str, *, age_col: str = "age", keep: Iterable[str] | None = None,
          on_error: str = "record", **options: Any) -> list[dict[str, Any]]:
    """Compute one index for every person (row).

    ``index``: one of dmft_permanent, dmft_primary, caries_experience, pufa, dean_index (tooth
    columns), bpe, bewe, cpitn, loss_of_attachment (sextant columns), or dai (columns named like
    the :func:`dentindices.dai` arguments). ``keep`` chooses which input columns to copy to the
    output (default: every column that is not a tooth or sextant column). ``on_error="record"``
    writes the error message in an ``error`` column and carries on; ``"raise"`` stops.
    Extra keyword options are passed to the index function (e.g. ``include_third_molars=False``).
    """
    if not isinstance(index, str) or index not in TOOTH_INDICES | SEXTANT_INDICES | OTHER_INDICES:
        raise InputError(f"batch() does not handle {index!r}; use one of "
                         f"{', '.join(sorted(TOOTH_INDICES | SEXTANT_INDICES | OTHER_INDICES))} "
                         f"(periodontal charts: batch_perio())")
    rows = _rows(rows)
    out: list[dict[str, Any]] = []
    for i, row in enumerate(rows):
        tcols = _tooth_columns(row) if index in TOOTH_INDICES else {}
        scols = _sextant_columns(row) if index in SEXTANT_INDICES else {}
        skip = set(tcols) | set(scols)
        kept = {k: row[k] for k in (keep if keep is not None else [k for k in row if k not in skip]) if k in row}
        res_row: dict[str, Any] = dict(kept)
        try:
            _check_duplicates(tcols, "tooth")
            _check_duplicates(scols, "sextant")
            age = _num_or_none(row.get(age_col)) if age_col else None
            if index in TOOTH_INDICES:
                teeth = {t: row[k] for k, t in tcols.items() if not is_blank(row[k])}
                if index == "dmft_permanent":
                    r = caries.dmft_permanent(teeth, age, **options)
                elif index == "dmft_primary":
                    r = caries.dmft_primary(teeth)
                elif index == "pufa":
                    r = caries.pufa(teeth, **options)
                elif index == "dean_index":
                    r = fluorosis.dean_index(teeth, **options)
                else:
                    both = caries.caries_experience(teeth, age, **options)
                    res_row.update(both["permanent"].row())
                    res_row.update(both["primary"].row())
                    res_row["warnings"] = " | ".join(both["permanent"].warnings + both["primary"].warnings)
                    out.append(res_row)
                    continue
            elif index in SEXTANT_INDICES:
                sext = {s: row[k] for k, s in scols.items()}
                if index == "bpe":
                    r = perio_screening.bpe(sext)
                elif index == "bewe":
                    r = wear.bewe(sext)
                elif index == "cpitn":
                    r = perio_screening.cpitn(sext, age)
                else:
                    r = perio_screening.loss_of_attachment(sext, age)
            else:
                names = ("missing_visible_teeth", "crowding", "spacing", "diastema_mm",
                         "max_anterior_irregularity_mm", "mand_anterior_irregularity_mm", "max_overjet_mm",
                         "mand_overjet_mm", "openbite_mm", "molar_relation")
                lower = {str(k).strip().lower(): v for k, v in row.items()}
                missing = [n for n in names if n not in lower]
                if missing:
                    raise InputError(f"DAI columns missing: {', '.join(missing)}")
                r = occlusion.dai(**{n: lower[n] for n in names}, age=age)
            res_row.update(r.row())
            res_row["warnings"] = " | ".join(r.warnings)
        except (InputError, ToothError, ValueError) as e:
            if on_error == "raise":
                raise InputError(f"Row {i + 1}: {e}") from e
            res_row["error"] = str(e)
        out.append(res_row)
    return out


_CDC_OPTIONS = {"mild_cal_distinct_teeth", "mild_pd5_any_site"}
_ACES_OPTIONS = {"survey", "age", "bleeding_percent", "furcation_class_2_3", "vertical_bone_loss_3mm",
                 "teeth_lost_to_periodontitis", "mobility_degree2_at_2_teeth", "bite_collapse_drifting_flaring",
                 "bone_loss_percent", "root_length_mm", "cigarettes_per_day", "smoker", "diabetes", "hba1c"}


def batch_perio(rows: Iterable[Mapping[str, Any]], *, id_col: str = "id", indices: Iterable[str] = ("cdc_aap", "aces", "perio_summary"),
                on_error: str = "record", cdc_options: Mapping[str, Any] | None = None,
                **aces_options: Any) -> list[dict[str, Any]]:
    """Periodontal case definitions for every person in a long-format chart (one row per tooth and
    site with columns id, tooth, site, pd, cal, bop). Person-level columns repeated on the rows
    (age, cigarettes_per_day, diabetes, hba1c, bleeding_percent, teeth_present ...) are used for ACES.

    Keyword options are passed to :func:`aces` for everyone (for example ``survey="planned"``);
    ``cdc_options`` are passed to :func:`cdc_aap` (``mild_cal_distinct_teeth``, ``mild_pd5_any_site``).
    Teeth present come from a ``teeth_present`` column, one list per person.
    """
    bad = sorted(set(aces_options) - _ACES_OPTIONS)
    if bad:
        raise InputError(f"Unknown ACES option(s): {', '.join(bad)}"
                         + (" (teeth_present comes from the 'teeth_present' column)" if "teeth_present" in bad else ""))
    cdc_options = dict(cdc_options or {})
    bad = sorted(set(cdc_options) - _CDC_OPTIONS)
    if bad:
        raise InputError(f"Unknown CDC/AAP option(s): {', '.join(bad)}; use {', '.join(sorted(_CDC_OPTIONS))}")
    rows = _rows(rows)
    cols = {str(k).strip().lower() for r in rows for k in r}
    if rows and not {"tooth", "site"} <= cols:
        raise InputError("A periodontal chart needs 'tooth' and 'site' columns (one row per tooth and site), "
                         "plus 'pd', 'cal' and optionally 'bop'")
    groups: dict[str, list[Mapping[str, Any]]] = {}
    order: list[str] = []
    for row in rows:
        key = str(row.get(id_col, "")).strip()
        if not key:
            raise InputError(f"Every row needs a value in the {id_col!r} column")
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(row)
    person_fields = ("age", "cigarettes_per_day", "smoker", "diabetes", "hba1c", "bleeding_percent",
                     "bone_loss_percent", "furcation_class_2_3", "vertical_bone_loss_3mm",
                     "teeth_lost_to_periodontitis", "mobility_degree2_at_2_teeth", "bite_collapse_drifting_flaring")
    out = []
    for key in order:
        rws = groups[key]
        res: dict[str, Any] = {id_col: key}
        try:
            low = [{str(k).strip().lower(): v for k, v in r.items()} for r in rws]
            site_rows = [r for r in low if not is_blank(r.get("tooth")) and not is_blank(r.get("site"))]
            chart = perio_cases.perio_chart(site_rows)
            person: dict[str, Any] = {}
            for f in person_fields:
                for r in low:
                    if not is_blank(r.get(f)):
                        person[f] = r[f]
                        break
            present = None
            for r in low:
                if not is_blank(r.get("teeth_present")):
                    present = [p for p in str(r["teeth_present"]).replace(";", " ").replace(",", " ").split() if p]
                    break
            tl = str(person.get("teeth_lost_to_periodontitis", ""))
            if "teeth_lost_to_periodontitis" in person and tl.isascii() and tl.isdigit():
                person["teeth_lost_to_periodontitis"] = int(person["teeth_lost_to_periodontitis"])
            if "cdc_aap" in indices:
                r = perio_cases.cdc_aap(chart, teeth_present=present, **cdc_options)
                res["cdc_aap"] = r.value
            if "aces" in indices:
                r = perio_cases.aces(chart, teeth_present=present, **{**person, **aces_options})
                res["aces_status"] = r.value
                for k in ("stage", "extent", "extent_percent", "grade", "grade_assumed", "max_interdental_cal",
                          "opposing_pairs", "bleeding_percent"):
                    res[f"aces_{k}"] = r.components.get(k)
                res["aces_warnings"] = " | ".join(r.warnings)
            if "perio_summary" in indices:
                r = perio_cases.perio_summary(chart)
                for k, v in r.components.items():
                    if k != "third_molars_included":
                        res[k] = v
        except (InputError, ToothError, ValueError) as e:
            if on_error == "raise":
                raise InputError(f"Person {key}: {e}") from e
            res["error"] = str(e)
        out.append(res)
    return out


_CARIES_COLUMN = re.compile(r"(dmft|dmfs)(_permanent|_primary)?", re.I)


def summary_table(rows: Iterable[Mapping[str, Any]], column: str, *, by: str | Iterable[str] | None = None,
                  include_sic: bool | None = None, confidence: float = 0.95) -> list[dict[str, Any]]:
    """Group summaries of one numeric column (e.g. DMFT): n, mean, SD, SE, CI, median, range,
    prevalence of values > 0 with Wilson CI, and SiC and SaC. ``by`` names one or more grouping
    columns (e.g. "age_group" or ["age_group", "sex"]); an overall row is always added.
    ``include_sic`` defaults to adding SiC and SaC only for caries-experience columns (DMFT, dmft,
    DMFS, dmfs), where they are defined; pass True or False to choose."""
    rows = _rows(rows)
    if rows and column not in rows[0]:
        raise InputError(f"Column {column!r} not found")
    keys = [by] if isinstance(by, str) else (seq(by, "by") if by else [])
    if not all(isinstance(k, str) for k in keys):
        raise InputError("by must name one column or a list of column names")
    for k in keys:
        if rows and not any(k in r for r in rows):
            raise InputError(f"Grouping column {k!r} not found")
    if include_sic is None:
        include_sic = bool(_CARIES_COLUMN.fullmatch(str(column)))
    groups: dict[tuple, list[Any]] = {}  # insertion order = order of first appearance
    for r in rows:
        if r.get("error"):
            continue
        g = tuple(r.get(k, "") for k in keys)
        groups.setdefault(g, []).append(r.get(column))
    out = []

    def row_for(label: dict[str, Any], values: list[Any]) -> dict[str, Any]:
        s = population.summarize(values, confidence=confidence, label=column)
        rec = {**label, **{k: v for k, v in s.items() if k != "label"}}
        vals = [v for v in values if not is_blank(v)]
        if include_sic and vals:
            rec["SiC"] = population.sic(vals).value
            sc = population.sac(vals)
            rec["SaC"] = sc.value
        return rec

    if keys:
        for g in groups:
            out.append(row_for(dict(zip(keys, g)), groups[g]))
    out.append(row_for({k: "All" for k in keys} if keys else {"group": "All"},
                       [v for vs in groups.values() for v in vs]))
    return out


_: Callable = IndexResult
