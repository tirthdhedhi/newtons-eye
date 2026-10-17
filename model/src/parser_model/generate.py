"""Synthetic training problems: question text + authoring scene + closed-form answers.

Every problem is a template family with randomised, round-number parameters. The gold scene is the
authoring JSON a person would write; the expected answers come from closed-form physics and are
checked against the real solver (``verify``), so a template can only enter the dataset if the
solver agrees with the textbook formula. Questions are written in three styles (textbook, casual,
terse) and never say what happens ("it slides"); they give every needed quantity and ask for
exactly the scene's queries. ``g`` is the solver's 9.81 and is never mentioned.

Families: floor-push, incline, sliding-stop, projectile, free-fall, spring-block.
"""

from __future__ import annotations

import json
import math
import random
import re
import sys
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .solve import solve_scene

G = 9.81
STYLES = ("textbook", "casual", "terse")


def fmt(x: float) -> str:
    """Round-number text: 5.0 -> '5', 0.25 -> '0.25'."""
    return f"{x:.6g}"


def pick(rng: random.Random, options: list[Any]) -> Any:
    return options[rng.randrange(len(options))]


def deg(angle: float, rng: random.Random) -> str:
    return pick(rng, [f"{fmt(angle)} degrees", f"{fmt(angle)} degrees", f"{fmt(angle)}°"])


@dataclass
class Problem:
    family: str
    questions: dict[str, str]
    scene: dict[str, Any]
    expected: dict[str, Any]  # query id -> number | [x, y, z]
    compare: dict[str, str]  # query id -> "norm" | "x" | "value"


def join(items: list[str]) -> str:
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + (", and " if len(items) > 2 else " and ") + items[-1]


def fix_articles(text: str) -> str:
    """'a 8 kg' -> 'an 8 kg' (numbers read aloud with a vowel: 8, 80, 11, 18)."""
    return re.sub(r"\b([Aa]) (?=(?:8[\d.]*|11|18)\b)", lambda m: m.group(1) + "n ", text)


def be(count: int) -> str:
    return "is" if count == 1 else "are"


def pick_queries(rng: random.Random, names: list[str], low: int = 1) -> list[str]:
    k = rng.randint(low, len(names))
    chosen = rng.sample(names, k)
    return [n for n in names if n in chosen]


def friction_pair(rng: random.Random) -> tuple[float, float]:
    mu_s = pick(rng, [0.3, 0.4, 0.5, 0.6, 0.7, 0.8])
    mu_k = round(mu_s - pick(rng, [0.1, 0.1, 0.2]), 1)
    return mu_s, max(mu_k, 0.1)


def surface_friction(mu_s: float, mu_k: float) -> dict[str, Any]:
    return {"static": mu_s, "kinetic": mu_k}


def body_word(rng: random.Random) -> str:
    return pick(rng, ["block", "block", "box", "crate", "sled"])


def ball_word(rng: random.Random) -> str:
    return pick(rng, ["ball", "stone", "rock"])


def query(qid: str, ask: str, body: str, **extra: Any) -> dict[str, Any]:
    return {"id": qid, "ask": ask, "body": body, **extra}


# --- floor push ---------------------------------------------------------------------------------


def floor_push(rng: random.Random) -> Problem:
    m = pick(rng, [2, 3, 4, 5, 8, 10, 12, 15, 20, 25, 40])
    mu_s, mu_k = (0.0, 0.0) if rng.random() < 0.12 else friction_pair(rng)
    angle = 0 if rng.random() < 0.6 else pick(rng, [20, 30, 35, 37, 40, 45])
    below = angle and rng.random() < 0.4
    weight = m * G
    f_push = round(weight * rng.uniform(0.15, 0.9) / 5) * 5 or 5
    t = pick(rng, [1, 2, 3, 4, 5])
    theta = -angle if below else angle
    fx = f_push * math.cos(math.radians(theta))
    n_force = weight - f_push * math.sin(math.radians(theta))
    if mu_s > 0 and fx <= mu_s * n_force:
        accel, friction = 0.0, fx
    else:
        friction = mu_k * n_force
        accel = (fx - friction) / m
    names = pick_queries(rng, ["a", "f", "N"])
    word = body_word(rng)
    asks = {
        "a": ["the acceleration of the {w}", "how fast the {w} accelerates", "its acceleration"],
        "f": ["the friction force on the {w}", "the friction force on it", "the friction force"],
        "N": ["the normal force on the {w}", "the normal force on it", "the normal force"],
    }
    force = {
        "id": "push",
        "kind": "applied",
        "body": "block",
        "magnitude": f"{fmt(f_push)} N",
        "directionAngle": f"{fmt(theta)} deg",
        "relativeTo": "floor",
    }
    scene = {
        "version": 1.1,
        "bodies": [{"id": "block", "mass": f"{fmt(m)} kg"}],
        "surfaces": [{"id": "floor", "kind": "plane", "friction": surface_friction(mu_s, mu_k)}],
        "contacts": [{"body": "block", "surface": "floor"}],
        "forces": [force],
        "queries": [],
    }
    qmap = {"a": "acceleration", "f": "friction", "N": "normal"}
    for n in names:
        if n == "a":
            scene["queries"].append(query("a", "acceleration", "block", at=t))
        else:
            scene["queries"].append(
                {"id": n, "ask": "force", "force": qmap[n], "body": "block", "at": t}
            )
    answers = {"a": [accel, 0, 0], "f": friction, "N": n_force}
    expected = {n: answers[n] for n in names}
    compare = {"a": "norm", "f": "value", "N": "value"}

    def asked(style: str) -> list[str]:
        return [pick(rng, asks[n]).format(w=word) for n in names]

    mu_text = (
        "The floor is frictionless."
        if mu_s == 0
        else f"The coefficients of static and kinetic friction are {fmt(mu_s)} and {fmt(mu_k)}."
    )
    if angle:
        direction = f"at {deg(angle, rng)} {'below' if below else 'above'} the horizontal"
        push_text = f"a {fmt(f_push)} N force {direction}"
    else:
        push_text = f"a horizontal force of {fmt(f_push)} N"
    casual_mu = (
        "No friction on this floor."
        if mu_s == 0
        else f"The floor has mu_s = {fmt(mu_s)} and mu_k = {fmt(mu_k)}."
    )
    terse_mu = "frictionless floor" if mu_s == 0 else f"floor mu_s {fmt(mu_s)} mu_k {fmt(mu_k)}"
    if angle:
        side = "below" if below else "above"
        terse_push = f"push {fmt(f_push)} N at {fmt(angle)} deg {side} horizontal"
    else:
        terse_push = f"push {fmt(f_push)} N horizontal"
    qs = {
        "textbook": (
            f"A {fmt(m)} kg {word} rests on a horizontal floor. {mu_text} "
            f"The {word} is pushed with {push_text}. "
            f"At t = {t} s after the push begins, find {join(asked('t'))}."
        ),
        "casual": (
            f"I'm pushing a {fmt(m)} kg {word} along the floor with {push_text}. {casual_mu} "
            f"{t} seconds in, what {be(len(names))} {join(asked('c'))}?"
        ),
        "terse": (
            f"{fmt(m)} kg {word}, {terse_mu}, {terse_push}. At t = {t} s: {', '.join(asked('x'))}."
        ),
    }
    return Problem("floor-push", qs, scene, expected, compare)


# --- incline ------------------------------------------------------------------------------------


def incline(rng: random.Random) -> Problem:
    m = pick(rng, [1, 2, 3, 4, 5, 6, 8, 10, 15])
    theta = pick(rng, [15, 20, 25, 30, 35, 37, 40, 45, 50, 53, 60])
    length = pick(rng, [1.5, 2, 2.5, 3, 4, 5, 6])
    frictionless = rng.random() < 0.25
    if frictionless:
        mu_s = mu_k = 0.0
    else:
        mu_s, mu_k = friction_pair(rng)
        stick_mu = round(math.tan(math.radians(theta)) + pick(rng, [0.1, 0.2, 0.3]), 1)
        if rng.random() < 0.4 and stick_mu <= 1.0:  # force the sticking case
            mu_s, mu_k = stick_mu, max(round(stick_mu - 0.2, 1), 0.1)
    t_ang = math.tan(math.radians(theta))
    slides = t_ang > mu_s
    cos, sin = math.cos(math.radians(theta)), math.sin(math.radians(theta))
    n_force = m * G * cos
    accel = G * (sin - mu_k * cos) if slides else 0.0
    friction = mu_k * n_force if slides else m * G * sin
    t_edge = math.sqrt(2 * length / accel) if slides and accel > 0 else None
    # "time until edge" only exists inside the default simulation window (at least 2 s)
    edge_ok = t_edge is not None and t_edge < 1.9
    names = ["a", "f", "N"] + (["t_edge"] if edge_ok else []) + ([] if frictionless else ["mu_min"])
    names = pick_queries(rng, names)
    t = None
    if any(n in names for n in ("a", "f", "N")):
        limit = (t_edge * 0.9) if t_edge else 3.0
        t = pick(rng, [x for x in (0, 0.5, 1, 1.5, 2) if x < limit] or [0])
    word = body_word(rng)
    scene: dict[str, Any] = {
        "version": 1.1,
        "bodies": [
            {"id": "block", "mass": f"{fmt(m)} kg", "placement": {"on": "ramp", "at": "top"}}
        ],
        "surfaces": [
            {
                "id": "ramp",
                "kind": "plane",
                "angle": f"{fmt(theta)} deg",
                "extent": {"length": f"{fmt(length)} m"},
                "friction": surface_friction(mu_s, mu_k),
            }
        ],
        "contacts": [{"body": "block", "surface": "ramp"}],
        "queries": [],
    }
    expected: dict[str, Any] = {}
    for n in names:
        if n == "a":
            scene["queries"].append(query("a", "acceleration", "block", at=t))
            expected["a"] = [accel, 0, 0]
        elif n == "f":
            scene["queries"].append(
                {"id": "f", "ask": "force", "force": "friction", "body": "block", "at": t}
            )
            expected["f"] = friction
        elif n == "N":
            scene["queries"].append(
                {"id": "N", "ask": "force", "force": "normal", "body": "block", "at": t}
            )
            expected["N"] = n_force
        elif n == "t_edge":
            scene["queries"].append(
                {"id": "t_edge", "ask": "time", "until": {"event": "edge"}, "body": "block"}
            )
            expected["t_edge"] = t_edge
        else:
            scene["queries"].append(query("mu_min", "min_mu_s", "block"))
            expected["mu_min"] = t_ang
    compare = {"a": "norm", "f": "value", "N": "value", "t_edge": "value", "mu_min": "value"}
    asks = {
        "a": ["the acceleration of the {w}", "its acceleration", "how fast it accelerates"],
        "f": ["the friction force on the {w}", "the friction force on it", "the friction force"],
        "N": ["the normal force on the {w}", "the normal force on it", "the normal force"],
        "t_edge": [
            "how long the {w} takes to reach the bottom edge of the incline",
            "how long it takes to reach the bottom edge",
            "the time for it to reach the bottom edge",
        ],
        "mu_min": [
            "the minimum coefficient of static friction needed to keep the {w} from sliding",
            "the smallest mu_s that would keep it from sliding",
            "the minimum static friction coefficient that stops it sliding",
        ],
    }

    def asked() -> list[str]:
        out = []
        for n in names:
            text = pick(rng, asks[n]).format(w=word)
            if n in ("a", "f", "N") and t is not None and rng.random() < 0.0:
                text += f" at t = {t} s"
            out.append(text)
        return out

    mu_sentence = (
        "The incline is frictionless."
        if frictionless
        else f"The coefficients of static and kinetic friction are {fmt(mu_s)} and {fmt(mu_k)}."
    )
    mu_short = "frictionless" if frictionless else f"mu_s {fmt(mu_s)}, mu_k {fmt(mu_k)}"
    mu_casual = (
        "It's totally frictionless."
        if frictionless
        else f"mu_s = {fmt(mu_s)} and mu_k = {fmt(mu_k)}."
    )
    if t is None:
        lead, after, terse_at = "Find", "", ""
    elif t == 0:
        lead, after, terse_at = (
            "At the instant of release, find",
            " At the instant I let go,",
            "At t = 0: ",
        )
    else:
        lead = f"At t = {fmt(t)} s after release, find"
        after, terse_at = f" After {fmt(t)} s,", f"At t = {fmt(t)} s: "
    qs = {
        "textbook": (
            f"A {fmt(m)} kg {word} is released from rest at the top of an incline "
            f"{fmt(length)} m long that makes an angle of {deg(theta, rng)} with the horizontal. "
            f"{mu_sentence} {lead} {join(asked())}."
        ),
        "casual": (
            f"There's a {fmt(m)} kg {word} at the top of a {fmt(length)} m ramp tilted at "
            f"{deg(theta, rng)}, and I let go of it. {mu_casual}{after} "
            f"what {be(len(names))} {join(asked())}?"
        )
        .replace(". what", ". What")
        .replace(", what", ", what"),
        "terse": (
            f"{fmt(m)} kg {word}, top of {fmt(theta)} deg incline, length {fmt(length)} m, "
            f"{mu_short}, released from rest. "
            f"{terse_at}{', '.join(asked())}."
        ),
    }
    return Problem("incline", qs, scene, expected, compare)


# --- sliding to a stop --------------------------------------------------------------------------


def sliding_stop(rng: random.Random) -> Problem:
    m = pick(rng, [1, 2, 3, 4, 5, 6, 8, 10])
    v0 = pick(rng, [4, 5, 6, 8, 10, 12, 15, 20])
    mu_s, mu_k = friction_pair(rng)
    t_stop = v0 / (mu_k * G)
    dist = v0**2 / (2 * mu_k * G)
    window = math.ceil(t_stop) + pick(rng, [1, 2, 3])
    work = -0.5 * m * v0**2
    names = pick_queries(rng, ["t_stop", "d", "W"])
    long_stop = "t_stop" in names and t_stop >= 1.9
    if ("d" in names or long_stop) and "W" not in names:  # a work window sets the duration
        names.append("W")
    word = body_word(rng)
    scene = {
        "version": 1.1,
        "bodies": [
            {
                "id": "block",
                "mass": f"{fmt(m)} kg",
                "velocity": {"speed": f"{fmt(v0)} m/s", "angle": "0 deg"},
            }
        ],
        "surfaces": [{"id": "floor", "kind": "plane", "friction": surface_friction(mu_s, mu_k)}],
        "contacts": [{"body": "block", "surface": "floor"}],
        "queries": [],
    }
    expected = {}
    for n in names:
        if n == "t_stop":
            scene["queries"].append(
                {"id": "t_stop", "ask": "time", "until": {"event": "stop"}, "body": "block"}
            )
            expected[n] = t_stop
        elif n == "d":
            scene["queries"].append(query("d", "distance", "block"))
            expected[n] = dist
        else:
            scene["queries"].append(query("W", "work", "block", **{"from": 0, "to": f"{window} s"}))
            expected[n] = work
    compare = {"t_stop": "value", "d": "value", "W": "value"}
    asks = {
        "t_stop": [
            "the time at which the {w} comes to rest",
            "when it comes to a stop",
            "how long it takes to stop",
        ],
        "d": [
            "the distance it travels before stopping",
            "how far it travels",
            "the distance it travels",
        ],
        "W": [
            f"the total work done on the {{w}} between t = 0 and t = {window} s",
            f"the work done on it from t = 0 to t = {window} s",
            f"the net work done on it from t = 0 to t = {window} s",
        ],
    }

    def asked() -> list[str]:
        return [pick(rng, asks[n]).format(w=word) for n in names]

    qs = {
        "textbook": (
            f"A {fmt(m)} kg {word} moves with an initial speed of {fmt(v0)} m/s along a "
            f"horizontal floor. The coefficients of static and kinetic friction between the "
            f"{word} and the floor are {fmt(mu_s)} and {fmt(mu_k)}. Find {join(asked())}."
        ),
        "casual": (
            f"A {fmt(m)} kg {word} is sliding along the floor at {fmt(v0)} m/s, and the floor has "
            f"mu_s = {fmt(mu_s)}, mu_k = {fmt(mu_k)}. What {be(len(names))} {join(asked())}?"
        ),
        "terse": (
            f"{fmt(m)} kg {word} moving at {fmt(v0)} m/s on a floor, mu_s {fmt(mu_s)} "
            f"mu_k {fmt(mu_k)}. {', '.join(asked()).capitalize()}."
        ),
    }
    return Problem("sliding-stop", qs, scene, expected, compare)


# --- projectile ---------------------------------------------------------------------------------


def projectile(rng: random.Random) -> Problem:
    m = pick(rng, [0.1, 0.2, 0.5, 1, 2, 3])
    speed = pick(rng, [8, 10, 12, 15, 20, 25, 30])
    angle = pick(rng, [0, 15, 30, 37, 45, 53, 60, 75])
    h = 0 if rng.random() < 0.6 else pick(rng, [5, 10, 20, 45, 80])
    if h and angle > 45:
        angle = pick(rng, [0, 0, 30])
    vx, vy = speed * math.cos(math.radians(angle)), speed * math.sin(math.radians(angle))
    t = pick(rng, [0.5, 1, 1.5, 2, 2.5, 3])
    if h:
        t = min(t, math.floor(math.sqrt(2 * h / G) * 2) / 2 or 0.5)
    names = pick_queries(rng, ["p", "v"])
    word = ball_word(rng)
    body: dict[str, Any] = {
        "id": "ball",
        "mass": f"{fmt(m)} kg",
        "velocity": {"speed": f"{fmt(speed)} m/s", "angle": f"{fmt(angle)} deg"},
    }
    if h:
        body["position"] = [0, h, 0]
    scene = {"version": 1.1, "bodies": [body], "queries": []}
    expected: dict[str, Any] = {}
    for n in names:
        scene["queries"].append(query(n, "position" if n == "p" else "velocity", "ball", at=t))
    expected["p"] = [vx * t, h + vy * t - 0.5 * G * t * t, 0]
    expected["v"] = [vx, vy - G * t, 0]
    expected = {n: expected[n] for n in names}
    compare = {"p": "xy", "v": "xy"}
    ask_words = {
        "p": ["the position", "where it is (its position)", "its position"],
        "v": [
            "the velocity",
            "how fast and in what direction it moves (its velocity)",
            "its velocity",
        ],
    }
    asked = [pick(rng, ask_words[n]) for n in names]
    origin = (
        f"from a point {fmt(h)} m above the ground, taken as y = {fmt(h)} m with the launch point "
        f"above the origin"
        if h
        else "from the origin"
    )
    launch = (
        f"horizontally at {fmt(speed)} m/s"
        if angle == 0
        else f"at {fmt(speed)} m/s and {deg(angle, rng)} above the horizontal"
    )
    qs = {
        "textbook": (
            f"A {fmt(m)} kg {word} is launched {launch} {origin}. Neglecting air resistance, "
            f"find {join(asked)} of the {word} at t = {fmt(t)} s."
        ),
        "casual": (
            f"I throw a {fmt(m)} kg {word} {launch} {origin}. No air resistance. "
            f"After {fmt(t)} seconds, what {be(len(names))} {join(asked)}?"
        ),
        "terse": (
            f"{fmt(m)} kg {word}, {launch}, {origin}, no drag. "
            f"At t = {fmt(t)} s: {', '.join(asked)}."
        ),
    }
    if h:  # the wordy "taken as y" clause is not natural; keep it simple
        origin_simple = f"from a height of {fmt(h)} m"
        qs = {k: v.replace(origin, origin_simple) for k, v in qs.items()}
    return Problem("projectile", qs, scene, expected, compare)


# --- free fall ----------------------------------------------------------------------------------


def free_fall(rng: random.Random) -> Problem:
    m = pick(rng, [0.2, 0.5, 1, 2, 5])
    h = pick(rng, [10, 20, 30, 45, 80, 100])
    v_up = pick(rng, [0, 0, 5, 8, 10, 15])
    t = pick(rng, [0.5, 1, 1.5, 2, 2.5, 3])
    t_hit = (v_up + math.sqrt(v_up**2 + 2 * G * h)) / G
    t = min(t, math.floor(t_hit * 2) / 2 or 0.5)
    names = pick_queries(rng, ["y", "v"])
    word = ball_word(rng)
    body: dict[str, Any] = {"id": "ball", "mass": f"{fmt(m)} kg", "position": [0, h, 0]}
    if v_up:
        body["velocity"] = {"speed": f"{fmt(v_up)} m/s", "angle": "90 deg"}
    scene = {"version": 1.1, "bodies": [body], "queries": []}
    for n in names:
        scene["queries"].append(query(n, "position" if n == "y" else "velocity", "ball", at=t))
    expected = {"y": [0, h + v_up * t - 0.5 * G * t * t, 0], "v": [0, v_up - G * t, 0]}
    expected = {n: expected[n] for n in names}
    compare = {"y": "xy", "v": "xy"}
    asks = {
        "y": ["its height above the ground", "how high it is above the ground", "its position"],
        "v": ["its velocity", "its velocity (with sign)", "its velocity"],
    }
    asked = [pick(rng, asks[n]) for n in names]
    start = (
        f"dropped from rest from a height of {fmt(h)} m"
        if not v_up
        else f"thrown straight up at {fmt(v_up)} m/s from a height of {fmt(h)} m"
    )
    qs = {
        "textbook": (
            f"A {fmt(m)} kg {word} is {start}. Neglecting air resistance, find {join(asked)} "
            f"at t = {fmt(t)} s after it is released. Take up as positive."
        ),
        "casual": (
            f"A {fmt(m)} kg {word} gets {start}, no air resistance. "
            f"{fmt(t)} seconds later, what {be(len(names))} {join(asked)}? Up is positive."
        ),
        "terse": (
            f"{fmt(m)} kg {word}, {start}, no drag. At t = {fmt(t)} s: {', '.join(asked)}. "
            f"Up positive."
        ),
    }
    return Problem("free-fall", qs, scene, expected, compare)


# --- spring block -------------------------------------------------------------------------------


def spring_block(rng: random.Random) -> Problem:
    m = pick(rng, [0.5, 1, 2, 4, 5, 8])
    k = pick(rng, [20, 50, 100, 200, 400])
    amp = pick(rng, [0.1, 0.2, 0.25, 0.3, 0.5])
    t = pick(rng, [0.5, 1, 2, 3, 5])
    w = math.sqrt(k / m)
    names = pick_queries(rng, ["x", "v"])
    word = body_word(rng)
    scene = {
        "version": 1.1,
        "bodies": [
            {"id": "block", "mass": f"{fmt(m)} kg", "placement": {"on": "floor", "offset": 0}}
        ],
        "surfaces": [{"id": "floor", "kind": "plane"}],
        "contacts": [{"body": "block", "surface": "floor"}],
        "forces": [
            {
                "id": "spring",
                "kind": "spring",
                "body": "block",
                "anchor": {"fixed": True, "stretch": f"{fmt(amp)} m"},
                "k": f"{fmt(k)} N/m",
                "restLength": 0,
            }
        ],
        "queries": [],
    }
    for n in names:
        scene["queries"].append(query(n, "position" if n == "x" else "velocity", "block", at=t))
    expected = {"x": [amp * math.cos(w * t), 0, 0], "v": [-amp * w * math.sin(w * t), 0, 0]}
    expected = {n: expected[n] for n in names}
    compare = {"x": "x", "v": "x"}
    asks = {
        "x": ["the position of the {w}", "where the {w} is", "its position"],
        "v": ["the velocity of the {w}", "how fast it is moving (its velocity)", "its velocity"],
    }
    asked = [pick(rng, asks[n]).format(w=word) for n in names]
    qs = {
        "textbook": (
            f"A {fmt(m)} kg {word} rests on a frictionless horizontal floor and is attached to a "
            f"fixed wall by a spring of spring constant {fmt(k)} N/m. The spring is stretched "
            f"{fmt(amp)} m from its natural length and the {word} is released from rest. "
            f"Find {join(asked)} at t = {fmt(t)} s, measured from the equilibrium position."
        ),
        "casual": (
            f"A {fmt(m)} kg {word} sits on a frictionless floor, hooked to a wall with a "
            f"{fmt(k)} N/m spring. I pull it out so the spring is stretched {fmt(amp)} m, then let "
            f"go. {fmt(t)} seconds later, what {be(len(names))} {join(asked)}?"
        ),
        "terse": (
            f"{fmt(m)} kg {word}, frictionless floor, spring k = {fmt(k)} N/m fixed to wall, "
            f"stretched {fmt(amp)} m then released from rest. At t = {fmt(t)} s: "
            f"{', '.join(asked)}."
        ),
    }
    return Problem("spring-block", qs, scene, expected, compare)


FAMILIES: dict[str, Callable[[random.Random], Problem]] = {
    "floor-push": floor_push,
    "incline": incline,
    "sliding-stop": sliding_stop,
    "projectile": projectile,
    "free-fall": free_fall,
    "spring-block": spring_block,
}
WEIGHTS = {
    "floor-push": 3,
    "incline": 4,
    "sliding-stop": 2,
    "projectile": 3,
    "free-fall": 2,
    "spring-block": 2,
}


# --- verification and dataset -------------------------------------------------------------------


def _component(kind: str, value: Any) -> Any:
    if kind == "norm":
        return math.hypot(*value)
    if kind == "x":
        return value[0]
    if kind == "xy":
        return value[:2]
    return value


def verify(problem: Problem, rel: float = 1e-3) -> list[str]:
    """Problems where the real solver disagrees with the closed-form answer (empty = fine)."""
    solved = solve_scene(problem.scene)
    if not solved.ok or solved.answers is None:
        return [f"solver exit {solved.exit_code}: {(solved.issues or solved.errors or ['?'])[0]}"]
    bad = []
    for qid, want in problem.expected.items():
        got = solved.answers.get(qid)
        kind = problem.compare[qid]
        if got is None:
            bad.append(f"{qid}: no answer")
            continue
        a, b = _component(kind, got), _component(kind, want)
        pairs = zip(a, b, strict=True) if isinstance(a, list) else [(a, b)]
        for x, y in pairs:
            if not math.isclose(x, y, rel_tol=rel, abs_tol=1e-6):
                bad.append(f"{qid}: solver {got} vs formula {want}")
                break
    return bad


def make_problems(n: int, seed: int) -> list[tuple[str, Problem]]:
    rng = random.Random(seed)
    names = [f for f, w in WEIGHTS.items() for _ in range(w)]
    seen: set[str] = set()
    out = []
    counters: dict[str, int] = {}
    while len(out) < n:
        family = pick(rng, names)
        problem = FAMILIES[family](rng)
        key = json.dumps(problem.scene, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        counters[family] = counters.get(family, 0) + 1
        out.append((f"syn-{family}-{counters[family]:04d}", problem))
    return out


def build(n: int, seed: int, out_path: Path, workers: int = 4) -> dict[str, Any]:
    problems = make_problems(n, seed)
    with ThreadPoolExecutor(workers) as pool:
        verdicts = list(pool.map(lambda item: verify(item[1]), problems))
    kept, dropped = 0, []
    with out_path.open("w") as fh:
        for (pid, problem), bad in zip(problems, verdicts, strict=True):
            if bad:
                dropped.append((pid, bad[0]))
                continue
            for style in STYLES:
                record = {
                    "id": f"{pid}/{style}",
                    "parent": pid,
                    "family": problem.family,
                    "style": style,
                    "source": "synthetic",
                    "question": fix_articles(problem.questions[style]),
                    "scene": problem.scene,
                    "expected": problem.expected,
                }
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            kept += 1
    return {"requested": n, "kept": kept, "dropped": dropped}


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    n = int(args[0]) if args else 50
    out = Path(args[1] if len(args) > 1 else "data/synthetic.jsonl")
    seed = int(args[2]) if len(args) > 2 else 0
    report = build(n, seed, out)
    print(f"kept {report['kept']}/{report['requested']} problems -> {out}")
    for pid, why in report["dropped"][:20]:
        print(f"  dropped {pid}: {why[:150]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
