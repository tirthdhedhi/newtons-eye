"""Wording variety for generated questions: ask framings, units, object names, distractors.

The parser has to cope with how people actually write problems, not one template per family. These
helpers vary the *surface form* (sentence order, how the asked quantities are introduced, units,
names, irrelevant sentences) without changing the physics, so the gold scene stays the same.
"""

from __future__ import annotations

import random
import re
from typing import Any

BODY_WORDS = ["block", "block", "box", "crate", "sled", "cart", "trolley", "trunk", "package"]
BALL_WORDS = ["ball", "ball", "stone", "rock", "pebble", "coconut"]

NOISE = [
    "The {w} is painted blue.",
    "Assume the experiment is done at sea level.",
    "This is problem 7 from the practice set.",
    "The surface was wiped clean beforehand.",
    "Air resistance is negligible.",
    "A camera records the motion at 30 frames per second.",
    "The {w} was bought for 12 dollars.",
    "The lab is on the 3rd floor.",
    "Treat the {w} as a point particle.",
]


def pick(rng: random.Random, options: list[Any]) -> Any:
    return options[rng.randrange(len(options))]


def fmt(x: float) -> str:
    return f"{x:.6g}"


def join(items: list[str]) -> str:
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + (", and " if len(items) > 2 else " and ") + items[-1]


def be(count: int) -> str:
    return "is" if count == 1 else "are"


def upper_first(text: str) -> str:
    return text[:1].upper() + text[1:]


def lower_first(text: str) -> str:
    return text[:1].lower() + text[1:]


# --- quantities with unit variety ---------------------------------------------------------------


def mass(m: float, rng: random.Random) -> tuple[str, str]:
    """(text in the question, text in the scene): grams sometimes, kilograms otherwise."""
    grams = round(m * 1000)
    if m < 1 and abs(grams - m * 1000) < 1e-9 and rng.random() < 0.45:
        return f"{grams} g", f"{grams} g"
    return f"{fmt(m)} kg", f"{fmt(m)} kg"


def speed(v: float, rng: random.Random) -> tuple[str, str]:
    """m/s, or km/h when that is a whole number (5 m/s = 18 km/h)."""
    kmh = v * 3.6
    if abs(kmh - round(kmh)) < 1e-9 and rng.random() < 0.25:
        return f"{round(kmh)} km/h", f"{round(kmh)} km/h"
    return f"{fmt(v)} m/s", f"{fmt(v)} m/s"


def distance(d: float, rng: random.Random, cm_ok: bool = True) -> tuple[str, str]:
    cm = d * 100
    if cm_ok and abs(cm - round(cm)) < 1e-9 and rng.random() < 0.15:
        return f"{round(cm)} cm", f"{round(cm)} cm"
    return f"{fmt(d)} m", f"{fmt(d)} m"


def angle_text(a: float, rng: random.Random) -> str:
    return pick(rng, [f"{fmt(a)} degrees", f"{fmt(a)} degrees", f"{fmt(a)}°", f"{fmt(a)} deg"])


# --- when clauses and ask framings --------------------------------------------------------------


def when_options(rng: random.Random, t: float, event: str) -> str:
    """A lowercase time clause such as 'at t = 2 s after release'."""
    if t == 0:
        return pick(
            rng,
            [f"at the instant of {event}", f"right at {event}", "at t = 0", "at t = 0 s"],
        )
    ts = fmt(t)
    secs = f"{ts} second" if ts == "1" else f"{ts} seconds"
    return pick(
        rng,
        [
            f"at t = {ts} s",
            f"at t = {ts} s after {event}",
            f"{ts} s after {event}",
            f"after {secs}",
            f"{secs} after {event}",
            f"at time t = {ts} s",
            f"when t = {ts} s",
        ],
    )


def textbook_ask(rng: random.Random, asks: list[str], when: str | None) -> str:
    trail = f" {when}" if when else ""
    lead = f"{upper_first(when)}, " if when else ""
    n = len(asks)
    options = [
        f"{lead}find {join(asks)}." if when else f"Find {join(asks)}.",
        f"Find {join(asks)}{trail}.",
        f"{lead}determine {join(asks)}." if when else f"Determine {join(asks)}.",
        f"Calculate {join(asks)}{trail}.",
        f"What {be(n)} {join(asks)}{trail}?",
        f"{lead}compute {join(asks)}." if when else f"Compute {join(asks)}.",
    ]
    if n >= 2:
        parts = "; ".join(f"({chr(97 + i)}) find {a}" for i, a in enumerate(asks))
        options.append(f"{upper_first(when) + ': ' if when else ''}{parts}.")
        options.append(f"{lead}find {join(asks[:-1])}. Also find {asks[-1]}.")
        options.append(f"Find {asks[0]}{trail}. Then find {join(asks[1:])}.")
    return pick(rng, options)


def casual_ask(rng: random.Random, asks: list[str], when: str | None) -> str:
    trail = f" {when}" if when else ""
    lead = f"{upper_first(when)}, " if when else ""
    n = len(asks)
    options = [
        f"{lead}what {be(n)} {join(asks)}?" if when else f"What {be(n)} {join(asks)}?",
        f"What {be(n)} {join(asks)}{trail}?",
        f"Can you tell me {join(asks)}{trail}?",
        f"I need {join(asks)}{trail}.",
        f"Help me find {join(asks)}{trail}.",
        f"{lead}I want to know {join(asks)}.",
    ]
    if n >= 2:
        options.append(f"{lead}what {be(n)} {join(asks[:-1])}? And {asks[-1]}?")
    return pick(rng, options)


def terse_ask(rng: random.Random, asks: list[str], t: float | None) -> str:
    items = ", ".join(asks)
    if t is None:
        return pick(rng, [f"{upper_first(items)}.", f"Find: {items}.", f"Need {items}."])
    ts = fmt(t)
    prefix = pick(rng, [f"At t = {ts} s: ", f"t = {ts} s: ", f"@ t={ts}s: ", f"After {ts} s: "])
    return f"{prefix}{items}."


def assemble(
    rng: random.Random,
    givens: list[str],
    ask: str,
    word: str,
    noise_p: float = 0.2,
    ask_first_p: float = 0.15,
) -> str:
    """Givens in order, plus the ask sentence (sometimes first) and an optional distractor."""
    sentences = list(givens)
    if rng.random() < noise_p:
        sentences.insert(rng.randrange(len(sentences) + 1), pick(rng, NOISE).format(w=word))
    sentences = [ask, *sentences] if rng.random() < ask_first_p else [*sentences, ask]
    return re.sub(r"\s+", " ", " ".join(sentences)).strip()
