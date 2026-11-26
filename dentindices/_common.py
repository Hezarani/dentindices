"""Small shared helpers: input normalisation and validation."""
from __future__ import annotations

import math
import numbers
import re
from collections.abc import Iterable, Mapping
from decimal import ROUND_HALF_UP, Context, Decimal
from typing import Any

from ._errors import InputError
from ._teeth import parse_tooth

# Plain decimal numbers only, the same in the Python and JavaScript engines
# (no "1_0", "0x1E", "inf" or non-ASCII digits).
_NUMBER_RE = re.compile(r"[+-]?([0-9]+\.?[0-9]*|\.[0-9]+)([eE][+-]?[0-9]+)?")
# Text that means "not recorded" in survey files.
_BLANKS = ("", "-", ".", "NA", "N/A", "NAN")


def items(data: Any) -> list[tuple[Any, Any]]:
    """Accept a mapping or an iterable of (key, value) pairs."""
    if data is None:
        return []
    if isinstance(data, Mapping):
        return list(data.items())
    if isinstance(data, Iterable) and not isinstance(data, (str, bytes)):
        out = []
        for pair in data:
            if not isinstance(pair, (tuple, list)) or len(pair) != 2:
                raise InputError(f"Expected (tooth, value) pairs, got {pair!r}")
            out.append((pair[0], pair[1]))
        return out
    raise InputError(f"Expected a mapping of tooth -> value, got {type(data).__name__}")


def tooth_map(data: Any, what: str = "value") -> dict[int, Any]:
    """Parse tooth keys; reject duplicates such as 16 and "16" in one input."""
    out: dict[int, Any] = {}
    for k, v in items(data):
        t = parse_tooth(k)
        if t in out:
            raise InputError(f"Tooth {t} appears more than once in the {what} input")
        out[t] = v
    return out


def is_blank(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, str):
        return v.strip().upper() in _BLANKS
    if isinstance(v, numbers.Real) and not isinstance(v, bool):
        try:
            return math.isnan(float(v))  # float, numpy float32/64 ...
        except (TypeError, ValueError, OverflowError):
            return False
    return False


def js_str(x: float) -> str:
    """Format a float exactly as JavaScript's String(number) does (shortest round-trip digits)."""
    x = float(x)
    if x == 0:
        return "0"
    if x.is_integer() and abs(x) < 1e21:
        return str(int(x))
    sign, digits, exp = Decimal(repr(x)).normalize().as_tuple()
    ds = "".join(map(str, digits))
    k = len(ds)
    n = exp + k  # position of the decimal point relative to the digits
    if k <= n <= 21:
        body = ds + "0" * (n - k)
    elif 0 < n <= 21:
        body = ds[:n] + "." + ds[n:]
    elif -6 < n <= 0:
        body = "0." + "0" * (-n) + ds
    else:
        e = n - 1
        body = ds[0] + ("." + ds[1:] if k > 1 else "") + "e" + ("+" if e >= 0 else "-") + str(abs(e))
    return ("-" if sign else "") + body


def psum(xs: Iterable[Any]) -> Any:
    """Left-to-right addition, as JavaScript does. (Python 3.12+ sum() compensates rounding errors,
    which would make results depend on the Python version.)"""
    total: Any = 0
    for x in xs:
        total = total + x
    return total


def fmt_g(x: Any) -> str:
    """Four significant digits, as the JavaScript engine's fmtG: String(Number(x.toPrecision(4)))."""
    x = float(x)
    if x.is_integer():
        return js_str(x)
    return js_str(float(Context(prec=4, rounding=ROUND_HALF_UP).plus(Decimal(x))))


def fmt_fixed(x: Any, digits: int = 1) -> str:
    """Fixed decimals rounded half away from zero on the exact value, as JavaScript's toFixed()."""
    return str(Decimal(float(x)).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP))


def norm_code(v: Any) -> str:
    """Normalise a code to an upper-case string: 3 -> "3", " b " -> "B", "x" -> "X"."""
    if isinstance(v, bool):
        raise InputError(f"Not a valid code: {v!r}")
    if isinstance(v, numbers.Integral):
        v = int(v)
    elif isinstance(v, numbers.Real):
        if not math.isfinite(float(v)) or not float(v).is_integer():
            raise InputError(f"Not a valid code: {v!r}")
        v = int(float(v))
    return str(v).strip().upper()


def int_score(v: Any, lo: int, hi: int, what: str) -> int:
    """Validate an integer score within [lo, hi]."""
    if isinstance(v, bool):
        raise InputError(f"{what}: {v!r} is not a score")
    if isinstance(v, numbers.Integral):
        v = int(v)
    elif isinstance(v, numbers.Real):
        if not math.isfinite(float(v)) or not float(v).is_integer():
            raise InputError(f"{what}: {v!r} must be a whole number")
        v = int(float(v))
    if isinstance(v, str):
        s = v.strip()
        if not re.fullmatch(r"-?[0-9]+", s):
            raise InputError(f"{what}: {v!r} is not a whole number")
        v = int(s)
    if not isinstance(v, int) or v < lo or v > hi:
        raise InputError(f"{what}: {v!r} must be a whole number from {lo} to {hi}")
    return v


def number(v: Any, what: str, lo: float | None = None, hi: float | None = None) -> float:
    if isinstance(v, bool):
        raise InputError(f"{what}: {v!r} is not a number")
    if isinstance(v, str):
        if not _NUMBER_RE.fullmatch(v.strip()):
            raise InputError(f"{what}: {v!r} is not a number")
        x = float(v.strip())
    elif isinstance(v, numbers.Real):
        x = float(v)
    else:
        raise InputError(f"{what}: {v!r} is not a number")
    if x != x or x in (float("inf"), float("-inf")):
        raise InputError(f"{what}: {v!r} is not a finite number")
    if lo is not None and x < lo:
        raise InputError(f"{what}: {v!r} must be at least {lo}")
    if hi is not None and x > hi:
        raise InputError(f"{what}: {v!r} must be at most {hi}")
    return x


def age_value(age: Any) -> float | None:
    if age is None or (isinstance(age, str) and not age.strip()):
        return None
    return number(age, "age", 0, 130)


def seq(data: Any, what: str) -> list[Any]:
    """A list from any iterable except text and mappings; anything else is an InputError."""
    if isinstance(data, (str, bytes, Mapping)) or not isinstance(data, Iterable):
        raise InputError(f"{what} must be a list (got {type(data).__name__})")
    return list(data)


def teeth_set(teeth: Any, what: str = "teeth_present") -> set[int]:
    """A list (or set) of tooth numbers; a single number or text is rejected with a clear message."""
    if isinstance(teeth, (str, bytes, Mapping)) or not isinstance(teeth, Iterable):
        raise InputError(f"{what} must be a list of tooth numbers, for example [11, 12, 16]")
    return {parse_tooth(t) for t in teeth}


def teeth_list(ts: Iterable[int]) -> str:
    ts = sorted(ts)
    return ", ".join(str(t) for t in ts) if ts else "none"
