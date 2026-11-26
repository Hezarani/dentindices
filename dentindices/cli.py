"""Command-line interface: ``dentindices --help``."""
from __future__ import annotations

import argparse
import json
import sys
from importlib import resources
from pathlib import Path

from . import __version__
from ._errors import InputError
from ._registry import cite, list_indices, registry
from .batch import SEXTANT_INDICES, TOOTH_INDICES, batch, batch_perio, read_csv, summary_table, write_csv
from .caries import caries_experience

EXAMPLES = ("caries_survey.csv", "perio_chart_long.csv", "bpe_survey.csv", "bewe_survey.csv")


def _parse_codes(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in text.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part and ":" not in part:
            raise InputError(f"Use tooth=code pairs such as 16=1,26=3 (got {part!r})")
        k, v = part.replace(":", "=").split("=", 1)
        if k.strip() in out:
            raise InputError(f"Tooth {k.strip()} is given more than once")
        out[k.strip()] = v.strip()
    return out


def _emit(rows: list[dict], out: str | None) -> None:
    text = write_csv(rows, out)
    if not out:
        sys.stdout.write(text)
    else:
        print(f"Wrote {len(rows)} rows to {out}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="dentindices", description="Oral-health epidemiology indices with cited, "
                                "tested rules (WHO, BSP, CDC/AAP, ACES ...). Research and education use.")
    p.add_argument("--version", action="version", version=f"dentindices {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="list the indices with their verification status")
    c = sub.add_parser("cite", help="print the references for an index")
    c.add_argument("index")

    d = sub.add_parser("dmft", help="DMFT/dmft for one person from tooth=code pairs (WHO 2013 codes)")
    d.add_argument("codes", help='e.g. "16=1,26=3,36=4,55=B"')
    d.add_argument("--age", type=float)
    d.add_argument("--exclude-third-molars", action="store_true")
    d.add_argument("--json", action="store_true", help="print the full result as JSON")

    b = sub.add_parser("batch", help="compute an index for every row of a CSV file")
    b.add_argument("index", choices=sorted(TOOTH_INDICES | SEXTANT_INDICES | {"dai"}))
    b.add_argument("input")
    b.add_argument("-o", "--output")
    b.add_argument("--age-col", default="age")
    b.add_argument("--exclude-third-molars", action="store_true")
    b.add_argument("--m-rule", choices=("who2013", "caries_only", "any_reason"))

    pp = sub.add_parser("perio", help="CDC/AAP, ACES and summary measures from a long-format periodontal chart")
    pp.add_argument("input")
    pp.add_argument("-o", "--output")
    pp.add_argument("--id-col", default="id")
    pp.add_argument("--survey", choices=("completed", "planned"), default="completed")
    pp.add_argument("--mild-cal-same-tooth", action="store_true",
                    help="CDC/AAP mild: allow the two CAL >= 3 mm sites on the same tooth (literal reading)")
    pp.add_argument("--mild-pd5-any-site", action="store_true",
                    help="CDC/AAP mild: count one PD >= 5 mm site at any site, not only interproximal")

    s = sub.add_parser("summary", help="group summaries (n, mean, SD, CI, prevalence, SiC, SaC) of a column")
    s.add_argument("input")
    s.add_argument("--column", required=True)
    s.add_argument("--by", nargs="*")
    s.add_argument("--no-sic", action="store_true")
    s.add_argument("-o", "--output")

    e = sub.add_parser("examples", help="write example CSV files to a folder")
    e.add_argument("folder", nargs="?", default=".")

    sub.add_parser("info", help="version and registry details")

    a = p.parse_args(argv)
    try:
        if a.cmd == "list":
            for i in list_indices():
                print(f"{i['id']:<28} {i['verification']:<10} {i['family']:<32} {i['name']}")
        elif a.cmd == "cite":
            for r in cite(a.index):
                print(r)
        elif a.cmd == "dmft":
            res = caries_experience(_parse_codes(a.codes), a.age, include_third_molars=not a.exclude_third_molars)
            if a.json:
                print(json.dumps({k: v.to_dict() for k, v in res.items()}, indent=2, default=str))
            else:
                for r in res.values():
                    print(r)
                    for line in r.trace:
                        print(f"  - {line}")
        elif a.cmd == "batch":
            opts = {}
            if a.index in ("dmft_permanent", "caries_experience"):
                if a.exclude_third_molars:
                    opts["include_third_molars"] = False
                if a.m_rule:
                    opts["m_rule"] = a.m_rule
            _emit(batch(read_csv(a.input), a.index, age_col=a.age_col, **opts), a.output)
        elif a.cmd == "perio":
            cdc = {"mild_cal_distinct_teeth": not a.mild_cal_same_tooth, "mild_pd5_any_site": a.mild_pd5_any_site}
            _emit(batch_perio(read_csv(a.input), id_col=a.id_col, survey=a.survey, cdc_options=cdc), a.output)
        elif a.cmd == "summary":
            _emit(summary_table(read_csv(a.input), a.column, by=a.by, include_sic=False if a.no_sic else None), a.output)
        elif a.cmd == "examples":
            folder = Path(a.folder)
            folder.mkdir(parents=True, exist_ok=True)
            for name in EXAMPLES:
                text = resources.files("dentindices.data").joinpath("examples", name).read_text(encoding="utf-8")
                (folder / name).write_text(text, encoding="utf-8")
                print(f"Wrote {folder / name}")
        elif a.cmd == "info":
            reg = registry()
            print(f"dentindices {__version__}")
            print(f"registry schema {reg['schema_version']}, verified on {reg['verified_on']}")
            print(f"{len(reg['indices'])} indices, {len(reg['sources'])} sources, "
                  f"{len(reg['discrepancies'])} documented source discrepancies")
    except (InputError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: {exc.strerror or exc}: {exc.filename or ''}".rstrip(": "), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
