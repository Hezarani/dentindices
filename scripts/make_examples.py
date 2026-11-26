"""Generate the synthetic example datasets shipped with DentIndices (no real people).

    python scripts/make_examples.py

Writes the same files to dentindices/data/examples/ (used by `dentindices examples` and the tests)
and examples/ (for readers browsing the repository). The generator is seeded, so the files are
byte-for-byte reproducible.
"""
from __future__ import annotations

import csv
import io
import random
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dentindices" / "data" / "examples"
# WHO form order: upper 18-11, 21-28; lower 48-41, 31-38.
PERM = [18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28,
        48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38]
PRIM = [55, 54, 53, 52, 51, 61, 62, 63, 64, 65, 85, 84, 83, 82, 81, 71, 72, 73, 74, 75]


def write(name: str, rows: list[dict], cols: list[str]) -> None:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({c: r.get(c, "") for c in cols})
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(buf.getvalue(), encoding="utf-8")


def caries_survey(rng: random.Random) -> None:
    rows = []
    groups = [("5", 5, 30), ("12", 12, 40), ("35-44", None, 30), ("65-74", None, 20)]
    pid = 0
    for label, fixed_age, n in groups:
        for _ in range(n):
            pid += 1
            age = fixed_age if fixed_age is not None else rng.randint(int(label[:2]), int(label[-2:]))
            r: dict = {"id": f"P{pid:03d}", "age_group": label, "age": age, "sex": rng.choice(["F", "M"])}
            risk = rng.random()
            if label == "5":
                for t in PRIM:
                    u = rng.random()
                    r[str(t)] = ("B" if u < 0.25 * risk * 1.6 else "D" if u < 0.33 * risk * 1.6 else
                                 "E" if u < 0.36 * risk * 1.6 else "A")
                for t in PERM:
                    if t % 10 == 6 and rng.random() < 0.4:
                        r[str(t)] = "0"
            elif label == "12":
                for t in PERM:
                    p = t % 10
                    if p == 8:
                        r[str(t)] = "8"
                    elif p == 7 and rng.random() < 0.3:
                        r[str(t)] = "8"
                    else:
                        u = rng.random()
                        mol = p in (6, 7)
                        r[str(t)] = ("1" if u < (0.10 if mol else 0.02) * risk * 2 else
                                     "3" if u < (0.16 if mol else 0.03) * risk * 2 else
                                     "6" if (mol and u > 0.85) else "0")
            else:
                older = label == "65-74"
                for t in PERM:
                    u = rng.random()
                    p = t % 10
                    if p == 8 and rng.random() < 0.6:
                        r[str(t)] = "5" if rng.random() < 0.7 else "4"
                        continue
                    miss = (0.30 if older else 0.06) * (1 + risk)
                    r[str(t)] = ("4" if u < miss * 0.6 else "5" if u < miss else
                                 "1" if u < miss + 0.04 * (1 + risk) else
                                 "2" if u < miss + 0.05 * (1 + risk) else
                                 "3" if u < miss + 0.17 * (1 + risk) else
                                 "7" if u < miss + 0.19 * (1 + risk) else "0")
            rows.append(r)
    cols = ["id", "age_group", "age", "sex"] + [str(t) for t in PERM] + [str(t) for t in PRIM]
    write("caries_survey.csv", rows, cols)


SITES = ("MB", "B", "DB", "ML", "L", "DL")


def perio_chart(rng: random.Random) -> None:
    people = [
        ("A01", 34, 0, "no", "", "healthy"),
        ("A02", 29, 0, "no", "", "gingivitis"),
        ("A03", 47, 0, "no", "", "stage2"),
        ("A04", 55, 15, "no", "", "stage3"),
        ("A05", 68, 0, "yes", "8.1", "stage4"),
        ("A06", 72, 0, "no", "", "edentulous"),
    ]
    rows = []
    teeth = [t for t in PERM if t % 10 != 8]
    for pid, age, cig, dm, hb, kind in people:
        base = {"id": pid, "age": age, "cigarettes_per_day": cig, "diabetes": dm, "hba1c": hb}
        if kind == "edentulous":
            rows.append({**base, "teeth_present": ""})
            continue
        present = list(teeth)
        if kind == "stage4":
            present = [t for t in teeth if t not in (17, 16, 15, 26, 27, 25, 36, 37, 46, 47, 45, 35, 14, 24)]
        for t in present:
            for s in SITES:
                pd, cal, bop = 2, 0, 0
                ip = s in ("MB", "DB", "ML", "DL")
                if kind == "gingivitis":
                    bop = 1 if rng.random() < 0.4 else 0
                    pd = 3 if rng.random() < 0.3 else 2
                elif kind == "healthy":
                    bop = 1 if rng.random() < 0.04 else 0
                elif kind == "stage2":
                    if ip and t in (16, 26, 36, 46, 11, 21, 31, 41, 14, 24, 34, 44):
                        cal = rng.choice([2, 3, 3, 4])
                        pd = cal + rng.choice([0, 1])
                    bop = 1 if rng.random() < 0.2 else 0
                elif kind == "stage3":
                    if ip:
                        cal = rng.choice([2, 3, 4, 5, 6])
                        pd = max(2, cal - rng.choice([0, 1]))
                    bop = 1 if rng.random() < 0.35 else 0
                elif kind == "stage4":
                    if ip:
                        cal = rng.choice([4, 5, 6, 7])
                        pd = max(3, cal - 1)
                    bop = 1 if rng.random() < 0.4 else 0
                rows.append({**base, "tooth": t, "site": s, "pd": pd, "cal": cal, "bop": bop})
    write("perio_chart_long.csv", rows, ["id", "age", "cigarettes_per_day", "diabetes", "hba1c", "teeth_present",
                                         "tooth", "site", "pd", "cal", "bop"])


def screening(rng: random.Random) -> None:
    bpe_rows, bewe_rows = [], []
    for i in range(1, 41):
        age = rng.randint(18, 75)
        sev = rng.random()
        codes = []
        for _ in range(6):
            u = rng.random() * (0.6 + sev)
            c = 0 if u < 0.2 else 1 if u < 0.45 else 2 if u < 0.85 else 3 if u < 1.2 else 4
            star = "*" if c >= 3 and rng.random() < 0.15 else ""
            codes.append(f"{c}{star}")
        if rng.random() < 0.1:
            codes[rng.randrange(6)] = "-"
        bpe_rows.append({"id": f"S{i:03d}", "age": age, **dict(zip(("UR", "UA", "UL", "LL", "LA", "LR"), codes))})
        wear = rng.random()
        scores = [min(3, int(rng.random() * (1 + 3 * wear))) for _ in range(6)]
        bewe_rows.append({"id": f"S{i:03d}", "age": age, **dict(zip(("S1", "S2", "S3", "S4", "S5", "S6"), scores))})
    write("bpe_survey.csv", bpe_rows, ["id", "age", "UR", "UA", "UL", "LL", "LA", "LR"])
    write("bewe_survey.csv", bewe_rows, ["id", "age", "S1", "S2", "S3", "S4", "S5", "S6"])


def main() -> None:
    rng = random.Random(20261122)
    caries_survey(rng)
    perio_chart(rng)
    screening(rng)
    dst = ROOT / "examples"
    dst.mkdir(exist_ok=True)
    for f in sorted(OUT.glob("*.csv")):
        shutil.copyfile(f, dst / f.name)
        print("wrote", f.relative_to(ROOT))


if __name__ == "__main__":
    main()
