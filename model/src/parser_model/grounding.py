"""Check that every number in a model's scene comes from the question.

The question is scanned for numbers with units (``5 kg``, ``72 km/h``, ``30 degrees``) and bare
numbers (``mu_s = 0.4``). Quantities with units are converted to SI, because that is what the
solver sees. Every number in the scene (strings such as ``"30 deg"`` are unit-parsed the same way)
must then match one of them, compared by absolute value, or be in ``DEFAULTS``.

Documented allowances:

* ``DEFAULTS``: ``g = 9.81``, ``0`` (zero friction, offset or angle) and 90 degrees ("straight up").
* Derived values: for any two question quantities of the same dimension, ``hypot`` of the pair and
  ``atan2`` of the pair (radians) are allowed, so "10 m/s across and 10 m/s up" may be written as
  ``14.142 m/s at 45 deg``.
* Number words: ``one`` to ``twelve`` and ``half a`` followed by a unit ("half a second").
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from itertools import permutations
from typing import Any

DEFAULTS: tuple[float, ...] = (9.81, 0.0, math.pi / 2)
REL_TOL = 1e-3
ABS_TOL = 1e-9

# unit text -> (dimension, factor to SI). Lookup is exact first, then lower-case.
_UNITS: dict[str, tuple[str, float]] = {}


def _add(dim: str, factor: float, *names: str) -> None:
    for name in names:
        _UNITS[name] = (dim, factor)


_add("mass", 1.0, "kg", "kilogram", "kilograms")
_add("mass", 1e-3, "g", "gram", "grams")
_add("mass", 1e-6, "mg")
_add("length", 1.0, "m", "meter", "meters", "metre", "metres")
_add("length", 1e-2, "cm", "centimeter", "centimeters", "centimetre", "centimetres")
_add("length", 1e-3, "mm", "millimeter", "millimeters")
_add("length", 1e3, "km", "kilometer", "kilometers", "kilometre", "kilometres")
_add("time", 1.0, "s", "sec", "secs", "second", "seconds")
_add("time", 1e-3, "ms")
_add("time", 60.0, "min", "mins", "minute", "minutes")
_add("time", 3600.0, "h", "hr", "hrs", "hour", "hours")
_add("angle", math.pi / 180, "deg", "degree", "degrees", "°")
_add("angle", 1.0, "rad", "radian", "radians")
_add("speed", 1.0, "m/s")
_add("speed", 1e-2, "cm/s")
_add("speed", 1 / 3.6, "km/h", "kph", "kmh")
_add("speed", 0.44704, "mph")
_add("accel", 1.0, "m/s^2", "m/s²", "m/s2", "m/s/s")
_add("force", 1.0, "N", "newton", "newtons")
_add("force", 1e3, "kN")
_add("stiffness", 1.0, "N/m")
_add("stiffness", 100.0, "N/cm")
_add("stiffness", 1e3, "kN/m")
_add("energy", 1.0, "J", "joule", "joules")
_add("energy", 1e3, "kJ")

_NUM = r"[-+−]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"
_NUMBER_WORDS = [
    *("zero", "one", "two", "three", "four", "five"),
    *("six", "seven", "eight", "nine", "ten", "eleven", "twelve"),
]
_WORDS = {
    **{w: float(i) for i, w in enumerate(_NUMBER_WORDS)},
    "half a": 0.5,
    "half an": 0.5,
    "a half": 0.5,
}
_UNIT_ALT = "|".join(re.escape(u) for u in sorted(_UNITS, key=len, reverse=True))
_TAIL = r"(?![A-Za-z0-9_^²/])"
_NUM_RE = re.compile(_NUM)
_QTY_RE = re.compile(rf"(?P<num>{_NUM})\s*(?P<unit>{_UNIT_ALT}){_TAIL}", re.IGNORECASE)
_WORD_RE = re.compile(
    rf"\b(?P<num>{'|'.join(sorted(map(re.escape, _WORDS), key=len, reverse=True))})\s+"
    rf"(?P<unit>{_UNIT_ALT}){_TAIL}",
    re.IGNORECASE,
)
_STR_QTY_RE = re.compile(rf"^\s*(?P<num>{_NUM})\s*(?P<unit>{_UNIT_ALT})\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class Quantity:
    """A number from the question, in SI. ``dim`` is ``"none"`` for a bare number."""

    value: float
    dim: str
    text: str


def _float(text: str) -> float:
    return float(text.replace("−", "-"))


def _unit(text: str) -> tuple[str, float]:
    return _UNITS.get(text) or _UNITS[text.lower()]


def parse_quantity_string(text: str) -> tuple[float, str] | None:
    """``"72 km/h"`` -> ``(20.0, "speed")``; ``None`` if ``text`` is not number + unit."""
    m = _STR_QTY_RE.match(text)
    if not m:
        return None
    dim, factor = _unit(m.group("unit"))
    return _float(m.group("num")) * factor, dim


def extract_quantities(question: str) -> list[Quantity]:
    """Numbers with units (converted to SI) and bare numbers found in the question."""
    found: list[Quantity] = []
    taken: list[tuple[int, int]] = []

    for m in _WORD_RE.finditer(question):
        dim, factor = _unit(m.group("unit"))
        value = _WORDS[m.group("num").lower()] * factor
        found.append(Quantity(value, dim, m.group(0)))
        taken.append(m.span())
    for m in _QTY_RE.finditer(question):
        dim, factor = _unit(m.group("unit"))
        found.append(Quantity(_float(m.group("num")) * factor, dim, m.group(0)))
        taken.append(m.span())
    for m in _NUM_RE.finditer(question):
        if any(s <= m.start() < e for s, e in taken):
            continue
        found.append(Quantity(_float(m.group(0)), "none", m.group(0)))
    return found


def allowed_values(question: str, extra: tuple[float, ...] = ()) -> list[float]:
    """Absolute SI values a scene may use: question numbers, derived pairs and defaults."""
    quantities = extract_quantities(question)
    values = [abs(q.value) for q in quantities]
    by_dim: dict[str, list[float]] = {}
    for q in quantities:
        if q.dim not in ("none", "mass", "time", "angle"):
            by_dim.setdefault(q.dim, []).append(abs(q.value))
    for vals in by_dim.values():
        for a, b in permutations(vals, 2):
            values.append(math.hypot(a, b))
            values.append(math.atan2(a, b))
    return values + [abs(v) for v in (*DEFAULTS, *extra)]


def scene_numbers(scene: Any) -> list[tuple[str, float]]:
    """Every number in the scene as ``(json path, SI value)``, except ``version`` and ``title``."""
    out: list[tuple[str, float]] = []

    def walk(node: Any, path: str) -> None:
        if isinstance(node, bool):
            return
        if isinstance(node, (int, float)):
            out.append((path, float(node)))
        elif isinstance(node, str):
            parsed = parse_quantity_string(node)
            if parsed:
                out.append((path, parsed[0]))
        elif isinstance(node, dict):
            for key, child in node.items():
                if path == "" and key in ("version", "title"):
                    continue
                walk(child, f"{path}.{key}" if path else key)
        elif isinstance(node, list):
            for i, child in enumerate(node):
                walk(child, f"{path}[{i}]")

    walk(scene, "")
    return out


@dataclass
class GroundingResult:
    grounded: bool
    ungrounded: list[dict[str, Any]] = field(default_factory=list)
    checked: int = 0


def check_grounding(
    question: str, scene: Any, extra_allowed: tuple[float, ...] = ()
) -> GroundingResult:
    allowed = allowed_values(question, extra_allowed)
    numbers = scene_numbers(scene)
    bad = [
        {"path": path, "value": value}
        for path, value in numbers
        if not any(math.isclose(abs(value), a, rel_tol=REL_TOL, abs_tol=ABS_TOL) for a in allowed)
    ]
    return GroundingResult(grounded=not bad, ungrounded=bad, checked=len(numbers))
