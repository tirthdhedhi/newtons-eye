"""Synthetic training problems: question text + authoring scene + closed-form answers.

Every problem is a template family with randomised, round-number parameters. The gold scene is the
authoring JSON a person would write; the expected answers come from closed-form physics and are
checked against the real solver (``verify``), so a template can only enter the dataset if the
solver agrees with the textbook formula. Questions come in three styles (textbook, casual, terse),
with varied wording (``phrasing``), units and distractor sentences. They never say what happens
("it slides"), give every needed quantity, and ask for exactly the scene's queries. ``g`` is the
solver's 9.81 and is never mentioned.

Families: floor-push, incline, sliding-stop, projectile, free-fall, spring-block, lift, ramp,
flight, spring-release (plus ``unsupported``: questions the parser must refuse).
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

from . import unsupported
from .asks import with_title
from .phrasing import (
    BALL_WORDS,
    BODY_WORDS,
    angle_text,
    assemble,
    casual_ask,
    distance,
    fmt,
    mass,
    pick,
    speed,
    terse_ask,
    textbook_ask,
    when_options,
)
from .solve import solve_scene

G = 9.81
STYLES = ("textbook", "casual", "terse")


@dataclass
class Problem:
    family: str
    questions: dict[str, str]
    scene: dict[str, Any]
    expected: dict[str, Any]  # query id -> number | [x, y, z]
    compare: dict[str, str]  # query id -> "norm" | "x" | "xy" | "value"


def fix_articles(text: str) -> str:
    """'a 8 kg' -> 'an 8 kg' (numbers read aloud with a vowel: 8, 80, 11, 18)."""
    return re.sub(r"\b([Aa]) (?=(?:8[\d.]*|11|18)\b)", lambda m: m.group(1) + "n ", text)


def mass_or_none(m: float, rng: random.Random, p_omit: float = 0.55) -> tuple[str, str | None]:
    """Projectile-type questions usually name no mass; then neither does the scene."""
    if rng.random() < p_omit:
        return "", None
    return mass(m, rng)


def pick_queries(rng: random.Random, names: list[str], low: int = 1) -> list[str]:
    """A random subset of ``names`` in canonical order, biased toward asking for several things."""
    sizes = list(range(low, len(names) + 1))
    k = rng.choices(sizes, weights=[1 + 2 * (n - low) for n in sizes])[0]
    chosen = rng.sample(names, k)
    return [n for n in names if n in chosen]


def friction_pair(rng: random.Random) -> tuple[float, float]:
    mu_s = pick(rng, [0.3, 0.4, 0.5, 0.6, 0.7, 0.8])
    mu_k = round(mu_s - pick(rng, [0.1, 0.1, 0.2]), 1)
    return mu_s, max(mu_k, 0.1)


def surface_friction(mu_s: float, mu_k: float) -> dict[str, Any]:
    return {"static": mu_s, "kinetic": mu_k}


def query(qid: str, ask: str, body: str, **extra: Any) -> dict[str, Any]:
    return {"id": qid, "ask": ask, "body": body, **extra}


def friction_given(rng: random.Random, mu_s: float, mu_k: float) -> tuple[float, float, str]:
    """How many coefficients the question states.

    ``both``: static and kinetic. ``kinetic``: only the kinetic one. ``single``: one generic
    "coefficient of friction". The solver needs both numbers, so with one stated value the scene
    uses it for both (static = kinetic); that is the convention the parser must learn.
    """
    if mu_s == 0 and mu_k == 0:
        return mu_s, mu_k, "both"
    r = rng.random()
    if r < 0.2:
        return mu_k, mu_k, "kinetic"
    if r < 0.3:
        return mu_k, mu_k, "single"
    return mu_s, mu_k, "both"


def mu_phrase(rng: random.Random, mu_s: float, mu_k: float, style: str, mode: str = "both") -> str:
    """How the friction coefficients are given (never reveals whether the body moves)."""
    if mu_s == 0 and mu_k == 0:
        return pick(rng, ["The surface is frictionless.", "There is no friction.", "It is smooth."])
    s, k = fmt(mu_s), fmt(mu_k)
    if mode == "kinetic":
        return pick(
            rng,
            [
                f"The coefficient of kinetic friction is {k}.",
                f"The coefficient of kinetic friction between the surfaces is {k}.",
                f"Take mu_k = {k}.",
                f"Kinetic friction coefficient: {k}.",
            ],
        )
    if mode == "single":
        return pick(
            rng,
            [
                f"The coefficient of friction is {k}.",
                f"The friction coefficient between the surfaces is {k}.",
                f"Take mu = {k}.",
                f"Friction coefficient: {k}.",
            ],
        )
    if style == "textbook":
        return pick(
            rng,
            [
                f"The coefficients of static and kinetic friction are {s} and {k}.",
                f"The coefficient of static friction is {s} and that of kinetic friction is {k}.",
                f"Take mu_s = {s} and mu_k = {k}.",
                f"The static and kinetic friction coefficients are {s} and {k}, respectively.",
            ],
        )
    return pick(
        rng,
        [
            f"mu_s = {s} and mu_k = {k}.",
            f"The friction coefficients are {s} (static) and {k} (kinetic).",
            f"Static friction coefficient {s}, kinetic {k}.",
        ],
    )


def mu_terse(mu_s: float, mu_k: float, mode: str, none: str = "frictionless") -> str:
    if mu_s == 0 and mu_k == 0:
        return none
    if mode == "kinetic":
        return f"mu_k {fmt(mu_k)}"
    if mode == "single":
        return f"mu {fmt(mu_k)}"
    return f"mu_s {fmt(mu_s)} mu_k {fmt(mu_k)}"


def finish(
    rng: random.Random,
    word: str,
    givens: dict[str, list[str]],
    terse: str,
    asks: list[str],
    when: str | None,
    t: float | None,
) -> dict[str, str]:
    """The three styled questions from per-style givens and the (shared) ask phrases."""
    terse = terse.strip()
    if len(asks) > 1 and rng.random() < 0.4:
        asks = rng.sample(asks, len(asks))  # the question need not follow the scene's query order
    return {
        "textbook": assemble(rng, givens["textbook"], textbook_ask(rng, asks, when), word),
        "casual": assemble(rng, givens["casual"], casual_ask(rng, asks, when), word),
        "terse": f"{terse} {terse_ask(rng, asks, t)}",
    }


# --- floor push ---------------------------------------------------------------------------------

FLOOR_BODY = ["block", "box", "crate", "sled", "cart", "trolley", "trunk", "package"]


def floor_push(rng: random.Random) -> Problem:
    m = pick(rng, [2, 3, 4, 5, 8, 10, 12, 15, 20, 25, 40])
    mu_s, mu_k = (0.0, 0.0) if rng.random() < 0.12 else friction_pair(rng)
    mu_s, mu_k, mode = friction_given(rng, mu_s, mu_k)
    angle = 0 if rng.random() < 0.6 else pick(rng, [20, 30, 35, 37, 40, 45])
    below = bool(angle) and rng.random() < 0.4
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
    word = pick(rng, FLOOR_BODY)
    m_text, m_scene = mass(m, rng)
    scene: dict[str, Any] = {
        "version": 1.1,
        "bodies": [{"id": "block", "mass": m_scene}],
        "surfaces": [{"id": "floor", "kind": "plane", "friction": surface_friction(mu_s, mu_k)}],
        "contacts": [{"body": "block", "surface": "floor"}],
        "forces": [
            {
                "id": "push",
                "kind": "applied",
                "body": "block",
                "magnitude": f"{fmt(f_push)} N",
                "directionAngle": f"{fmt(theta)} deg",
                "relativeTo": "floor",
            }
        ],
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
    ask_words = {
        "a": [
            "the acceleration of the {w}",
            "the acceleration of the {w}",
            "how fast the {w} is accelerating",
            "its acceleration",
            "the {w}'s acceleration",
            "whether the {w} moves and, if it does, its acceleration",
        ],
        "f": [
            "the friction force on the {w}",
            "the force of friction acting on it",
            "the friction force",
            "the magnitude of the friction force",
            "the frictional force acting on the {w}",
        ],
        "N": [
            "the normal force on the {w}",
            "the normal force the floor exerts on it",
            "the normal force",
            "the magnitude of the normal force",
            "the normal reaction of the floor",
        ],
    }
    asks = [pick(rng, ask_words[n]).format(w=word) for n in names]
    when = when_options(rng, t, "the push begins")
    side = "below" if below else "above"
    if angle:
        push = pick(
            rng,
            [
                f"a {fmt(f_push)} N force directed {angle_text(angle, rng)} {side} the horizontal",
                f"a force of {fmt(f_push)} N pointing {angle_text(angle, rng)} {side} horizontal",
            ],
        )
        terse_push = f"push {fmt(f_push)} N at {fmt(angle)} deg {side} horizontal"
    else:
        push = pick(
            rng,
            [
                f"a horizontal force of {fmt(f_push)} N",
                f"a {fmt(f_push)} N horizontal force",
                f"a horizontal push of {fmt(f_push)} N",
            ],
        )
        terse_push = f"push {fmt(f_push)} N horizontal"
    givens = {
        "textbook": [
            pick(
                rng,
                [
                    f"A {m_text} {word} rests on a horizontal floor.",
                    f"A {m_text} {word} is at rest on a level floor.",
                ],
            ),
            mu_phrase(rng, mu_s, mu_k, "textbook", mode),
            f"The {word} is pushed with {push}.",
        ],
        "casual": [
            f"I'm pushing a {m_text} {word} along the floor with {push}.",
            mu_phrase(rng, mu_s, mu_k, "casual", mode),
        ],
    }
    fric = mu_terse(mu_s, mu_k, mode, "frictionless floor")
    terse = f"{m_text} {word}, {fric}, {terse_push}."
    return Problem(
        "floor-push", finish(rng, word, givens, terse, asks, when, t), scene, expected, compare
    )


# --- incline ------------------------------------------------------------------------------------


def incline(rng: random.Random) -> Problem:
    m = pick(rng, [1, 2, 3, 4, 5, 6, 8, 10, 15])
    theta = pick(rng, [15, 20, 25, 30, 35, 37, 40, 45, 50, 53, 60])
    length = pick(rng, [1.5, 2, 2.5, 3, 4, 5, 6])
    frictionless = rng.random() < 0.25
    mode = "both"
    if frictionless:
        mu_s = mu_k = 0.0
    else:
        mu_s, mu_k = friction_pair(rng)
        stick_mu = round(math.tan(math.radians(theta)) + pick(rng, [0.1, 0.2, 0.3]), 1)
        if rng.random() < 0.4 and stick_mu <= 1.0:  # force the sticking case
            mu_s, mu_k = stick_mu, max(round(stick_mu - 0.2, 1), 0.1)
        else:
            mu_s, mu_k, mode = friction_given(rng, mu_s, mu_k)
    t_ang = math.tan(math.radians(theta))
    slides = t_ang > mu_s
    cos, sin = math.cos(math.radians(theta)), math.sin(math.radians(theta))
    n_force = m * G * cos
    accel = G * (sin - mu_k * cos) if slides else 0.0
    friction = mu_k * n_force if slides else m * G * sin
    t_edge = math.sqrt(2 * length / accel) if slides and accel > 0 else None
    # "time until edge" only exists inside the default simulation window (at least 2 s)
    edge_ok = t_edge is not None and t_edge < 1.9
    mu_min_ok = not frictionless and mode == "both"
    names = ["a", "f", "N"] + (["t_edge"] if edge_ok else []) + (["mu_min"] if mu_min_ok else [])
    names = pick_queries(rng, names)
    t = None
    if any(n in names for n in ("a", "f", "N")):
        limit = (t_edge * 0.9) if t_edge else 3.0
        t = pick(rng, [x for x in (0, 0.5, 1, 1.5, 2) if x < limit] or [0])
    word = pick(rng, BODY_WORDS)
    m_text, m_scene = mass(m, rng)
    len_text, len_scene = distance(length, rng)
    scene: dict[str, Any] = {
        "version": 1.1,
        "bodies": [{"id": "block", "mass": m_scene, "placement": {"on": "ramp", "at": "top"}}],
        "surfaces": [
            {
                "id": "ramp",
                "kind": "plane",
                "angle": f"{fmt(theta)} deg",
                "extent": {"length": len_scene},
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
    ask_words = {
        "a": [
            "the acceleration of the {w}",
            "the {w}'s acceleration",
            "its acceleration",
            "how fast the {w} accelerates",
        ],
        "f": [
            "the friction force on the {w}",
            "the force of friction acting on it",
            "the friction force",
            "the magnitude of the friction force",
        ],
        "N": [
            "the normal force on the {w}",
            "the normal force the incline exerts on it",
            "the normal force",
            "the normal reaction of the incline",
        ],
        "t_edge": [
            "how long the {w} takes to reach the bottom edge of the incline",
            "how long it takes to reach the bottom edge",
            "the time for it to reach the bottom edge",
            "the time the {w} takes to get to the end of the incline",
            "when it reaches the bottom of the incline",
        ],
        "mu_min": [
            "the minimum coefficient of static friction needed to keep the {w} from sliding",
            "the smallest mu_s that would keep it from sliding",
            "the minimum static friction coefficient that stops it sliding",
            "the least value of mu_s for which the {w} would not slide",
        ],
    }
    asks = [pick(rng, ask_words[n]).format(w=word) for n in names]
    when = when_options(rng, t, "release") if t is not None else None
    ang = angle_text(theta, rng)
    givens = {
        "textbook": [
            pick(
                rng,
                [
                    f"A {m_text} {word} is released from rest at the top of an incline "
                    f"{len_text} long that makes an angle of {ang} with the horizontal.",
                    f"A {m_text} {word} starts from rest at the top of a rough incline of length "
                    f"{len_text}, inclined at {ang} to the horizontal.",
                    f"An incline {len_text} long is inclined at {ang}. A {m_text} {word} is "
                    f"released from rest at its top.",
                ],
            ).replace("rough ", "" if frictionless else "rough "),
            mu_phrase(rng, mu_s, mu_k, "textbook", mode),
        ],
        "casual": [
            pick(
                rng,
                [
                    f"There's a {m_text} {word} at the top of a {len_text} ramp tilted at {ang}, "
                    f"and I let go of it.",
                    f"I let a {m_text} {word} go from the top of a {len_text} long ramp that is "
                    f"tilted {ang}.",
                ],
            ),
            mu_phrase(rng, mu_s, mu_k, "casual", mode),
        ],
    }
    fric = mu_terse(mu_s, mu_k, mode, "frictionless")
    terse = (
        f"{m_text} {word}, top of {fmt(theta)} deg incline, length {len_text}, {fric}, "
        f"released from rest."
    )
    return Problem(
        "incline", finish(rng, word, givens, terse, asks, when, t), scene, expected, compare
    )


# --- sliding to a stop --------------------------------------------------------------------------


def sliding_stop(rng: random.Random) -> Problem:
    m = pick(rng, [1, 2, 3, 4, 5, 6, 8, 10])
    v0 = pick(rng, [5, 10, 15, 20, 25, 4, 6, 8, 12])
    mu_s, mu_k = friction_pair(rng)
    mu_s, mu_k, mode = friction_given(rng, mu_s, mu_k)
    t_stop = v0 / (mu_k * G)
    dist = v0**2 / (2 * mu_k * G)
    window = math.ceil(t_stop) + pick(rng, [1, 2, 3])
    work = -0.5 * m * v0**2
    names = pick_queries(rng, ["t_stop", "d", "W"])
    long_stop = "t_stop" in names and t_stop >= 1.9
    if ("d" in names or long_stop) and "W" not in names:  # a work window sets the duration
        names.append("W")
    word = pick(rng, BODY_WORDS)
    m_text, m_scene = mass(m, rng)
    v_text, v_scene = speed(v0, rng)
    scene: dict[str, Any] = {
        "version": 1.1,
        "bodies": [
            {
                "id": "block",
                "mass": m_scene,
                "velocity": {"speed": v_scene, "angle": "0 deg"},
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
    ask_words = {
        "t_stop": [
            "the time at which the {w} comes to rest",
            "when it comes to a stop",
            "how long it takes to stop",
            "the time it takes for the {w} to stop",
        ],
        "d": [
            "the distance it travels before stopping",
            "how far it travels",
            "the distance the {w} covers",
            "how far the {w} goes",
        ],
        "W": [
            f"the total work done on the {{w}} between t = 0 and t = {window} s",
            f"the work done on it from t = 0 to t = {window} s",
            f"the net work done on the {{w}} from t = 0 to t = {window} s",
            f"the work done on it over the first {window} s",
        ],
    }
    asks = [pick(rng, ask_words[n]).format(w=word) for n in names]
    givens = {
        "textbook": [
            pick(
                rng,
                [
                    f"A {m_text} {word} moves with an initial speed of {v_text} along a "
                    f"horizontal floor.",
                    f"A {m_text} {word} is given an initial velocity of {v_text} along a "
                    f"level floor.",
                    f"A {m_text} {word} travels along a horizontal surface at {v_text}.",
                ],
            ),
            mu_phrase(rng, mu_s, mu_k, "textbook", mode),
        ],
        "casual": [
            pick(
                rng,
                [
                    f"A {m_text} {word} is sliding along the floor at {v_text}.",
                    f"I shove a {m_text} {word} along the floor and it leaves my hand at {v_text}.",
                ],
            ),
            mu_phrase(rng, mu_s, mu_k, "casual", mode),
        ],
    }
    terse = f"{m_text} {word} moving at {v_text} on a floor, {mu_terse(mu_s, mu_k, mode)}."
    return Problem(
        "sliding-stop",
        finish(rng, word, givens, terse, asks, None, None),
        scene,
        expected,
        compare,
    )


# --- projectile ---------------------------------------------------------------------------------


def projectile(rng: random.Random) -> Problem:
    m = pick(rng, [0.1, 0.2, 0.5, 1, 2, 3])
    sp = pick(rng, [8, 10, 12, 15, 20, 25, 30])
    angle = pick(rng, [0, 15, 30, 37, 45, 53, 60, 75])
    h = 0 if rng.random() < 0.6 else pick(rng, [5, 10, 20, 45, 80])
    if h and angle > 45:
        angle = pick(rng, [0, 0, 30])
    components = angle != 0 and rng.random() < 0.4
    vx, vy = sp * math.cos(math.radians(angle)), sp * math.sin(math.radians(angle))
    if components:  # whole-number components, e.g. 6 and 8, or 10 and 10
        vx, vy = pick(
            rng, [(6, 8), (8, 6), (10, 10), (12, 5), (5, 12), (9, 12), (15, 20), (20, 15)]
        )
    t = pick(rng, [0.5, 1, 1.5, 2, 2.5, 3])
    if h:
        t = min(t, math.floor(math.sqrt(2 * h / G) * 2) / 2 or 0.5)
    names = pick_queries(rng, ["p", "v"])
    word = pick(rng, BALL_WORDS)
    m_text, m_scene = mass_or_none(m, rng)
    sp_text, sp_scene = speed(sp, rng)
    body: dict[str, Any] = {"id": "ball", "mass": m_scene}
    if m_scene is None:
        body.pop("mass")
    if components:
        body["velocity"] = [vx, vy, 0]
    else:
        body["velocity"] = {"speed": sp_scene, "angle": f"{fmt(angle)} deg"}
    if h:
        body["position"] = [0, h, 0]
    scene: dict[str, Any] = {"version": 1.1, "bodies": [body], "queries": []}
    for n in names:
        scene["queries"].append(query(n, "position" if n == "p" else "velocity", "ball", at=t))
    expected = {
        "p": [vx * t, h + vy * t - 0.5 * G * t * t, 0],
        "v": [vx, vy - G * t, 0],
    }
    expected = {n: expected[n] for n in names}
    compare = {"p": "xy", "v": "xy"}
    ask_words = {
        "p": [
            "the position of the {w}",
            "where the {w} is (its position)",
            "its position",
            "the coordinates of the {w}",
        ],
        "v": [
            "the velocity of the {w}",
            "its velocity",
            "the velocity of the {w}, with direction",
            "how fast and in what direction it moves (its velocity)",
        ],
    }
    asks = [pick(rng, ask_words[n]).format(w=word) for n in names]
    when = when_options(rng, t, "launch")
    start = f"from a height of {fmt(h)} m" if h else "from the origin"
    if components:
        launch = pick(
            rng,
            [
                f"with a horizontal velocity component of {fmt(vx)} m/s and a vertical "
                f"component of {fmt(vy)} m/s upward",
                f"so that it initially moves {fmt(vx)} m/s horizontally and {fmt(vy)} m/s up",
                f"with vx = {fmt(vx)} m/s and vy = {fmt(vy)} m/s",
            ],
        )
        terse_launch = f"vx = {fmt(vx)} m/s, vy = {fmt(vy)} m/s up"
    elif angle == 0:
        launch = pick(rng, [f"horizontally at {sp_text}", f"horizontally with speed {sp_text}"])
        terse_launch = f"launched horizontally at {sp_text}"
    else:
        launch = pick(
            rng,
            [
                f"at {sp_text} and {angle_text(angle, rng)} above the horizontal",
                f"with speed {sp_text} at {angle_text(angle, rng)} above the horizontal",
            ],
        )
        terse_launch = f"launched at {sp_text}, {fmt(angle)} deg above horizontal"
    givens = {
        "textbook": [
            f"A {m_text} {word} is launched {launch} {start}.",
            pick(rng, ["Neglect air resistance.", "Ignore air resistance.", "There is no drag."]),
        ],
        "casual": [
            f"I throw a {m_text} {word} {launch} {start}.",
            pick(rng, ["No air resistance.", "Ignore drag.", "Assume there's no air resistance."]),
        ],
    }
    terse = f"{m_text} {word}, {terse_launch}, {start}, no drag."
    return Problem(
        "projectile", finish(rng, word, givens, terse, asks, when, t), scene, expected, compare
    )


# --- free fall ----------------------------------------------------------------------------------


def free_fall(rng: random.Random) -> Problem:
    m = pick(rng, [0.2, 0.5, 1, 2, 5])
    h = pick(rng, [10, 20, 30, 45, 80, 100])
    v_up = pick(rng, [0, 0, 5, 8, 10, 15])
    t = pick(rng, [0.5, 1, 1.5, 2, 2.5, 3])
    t_hit = (v_up + math.sqrt(v_up**2 + 2 * G * h)) / G
    t = min(t, math.floor(t_hit * 2) / 2 or 0.5)
    names = pick_queries(rng, ["y", "v"])
    word = pick(rng, BALL_WORDS)
    m_text, m_scene = mass_or_none(m, rng)
    body: dict[str, Any] = {"id": "ball", "mass": m_scene, "position": [0, h, 0]}
    if m_scene is None:
        body.pop("mass")
    if v_up:
        body["velocity"] = {"speed": f"{fmt(v_up)} m/s", "angle": "90 deg"}
    scene: dict[str, Any] = {"version": 1.1, "bodies": [body], "queries": []}
    for n in names:
        scene["queries"].append(query(n, "position" if n == "y" else "velocity", "ball", at=t))
    expected = {"y": [0, h + v_up * t - 0.5 * G * t * t, 0], "v": [0, v_up - G * t, 0]}
    expected = {n: expected[n] for n in names}
    compare = {"y": "xy", "v": "xy"}
    ask_words = {
        "y": [
            "its height above the ground",
            "how high it is above the ground",
            "its position",
            "the height of the {w}",
        ],
        "v": ["its velocity", "its velocity (with sign)", "the velocity of the {w}"],
    }
    asks = [pick(rng, ask_words[n]).format(w=word) for n in names]
    when = when_options(rng, t, "release" if not v_up else "it is thrown")
    if not v_up:
        start = pick(
            rng,
            [f"dropped from rest from a height of {fmt(h)} m", f"released from rest {fmt(h)} m up"],
        )
    else:
        start = pick(
            rng,
            [
                f"thrown straight up at {fmt(v_up)} m/s from a height of {fmt(h)} m",
                f"thrown vertically upward at {fmt(v_up)} m/s from {fmt(h)} m above the ground",
            ],
        )
    givens = {
        "textbook": [
            f"A {m_text} {word} is {start}.",
            "Neglect air resistance. Take up as positive.",
        ],
        "casual": [f"A {m_text} {word} gets {start}.", "No air resistance. Up is positive."],
    }
    terse = f"{m_text} {word}, {start}, no drag, up positive."
    return Problem(
        "free-fall", finish(rng, word, givens, terse, asks, when, t), scene, expected, compare
    )


# --- spring block -------------------------------------------------------------------------------


def spring_block(rng: random.Random) -> Problem:
    m = pick(rng, [0.5, 1, 2, 4, 5, 8])
    k = pick(rng, [20, 50, 100, 200, 400])
    amp = pick(rng, [0.1, 0.2, 0.25, 0.3, 0.5])
    t = pick(rng, [0.5, 1, 2, 3, 5])
    w = math.sqrt(k / m)
    names = pick_queries(rng, ["x", "v"])
    word = pick(rng, BODY_WORDS)
    m_text, m_scene = mass(m, rng)
    amp_text, amp_scene = distance(amp, rng)
    scene: dict[str, Any] = {
        "version": 1.1,
        "bodies": [{"id": "block", "mass": m_scene, "placement": {"on": "floor", "offset": 0}}],
        "surfaces": [{"id": "floor", "kind": "plane"}],
        "contacts": [{"body": "block", "surface": "floor"}],
        "forces": [
            {
                "id": "spring",
                "kind": "spring",
                "body": "block",
                "anchor": {"fixed": True, "stretch": amp_scene},
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
    ask_words = {
        "x": [
            "the position of the {w}",
            "where the {w} is, measured from the equilibrium position",
            "its position",
            "the displacement of the {w} from equilibrium",
        ],
        "v": [
            "the velocity of the {w}",
            "how fast it is moving (its velocity)",
            "its velocity",
            "the {w}'s velocity",
        ],
    }
    asks = [pick(rng, ask_words[n]).format(w=word) for n in names]
    when = when_options(rng, t, "release")
    givens = {
        "textbook": [
            pick(
                rng,
                [
                    f"A {m_text} {word} rests on a frictionless horizontal floor and is attached "
                    f"to a fixed wall by a spring of spring constant {fmt(k)} N/m.",
                    f"A {m_text} {word} on a smooth horizontal floor is connected to a wall by a "
                    f"spring with force constant {fmt(k)} N/m.",
                ],
            ),
            f"The spring is stretched {amp_text} from its natural length and the {word} is "
            f"released from rest.",
        ],
        "casual": [
            f"A {m_text} {word} sits on a frictionless floor, hooked to a wall with a "
            f"{fmt(k)} N/m spring.",
            f"I pull it out so the spring is stretched {amp_text}, then let go.",
        ],
    }
    terse = (
        f"{m_text} {word}, frictionless floor, spring k = {fmt(k)} N/m fixed to wall, "
        f"stretched {amp_text} then released from rest."
    )
    return Problem(
        "spring-block", finish(rng, word, givens, terse, asks, when, t), scene, expected, compare
    )


# --- lifted by a vertical force -----------------------------------------------------------------


def lift(rng: random.Random) -> Problem:
    m = pick(rng, [0.5, 1, 2, 3, 5, 8, 10, 20, 50])
    weight = m * G
    f_up = max(round(weight * rng.uniform(0.4, 2.2)), 1)
    t = pick(rng, [0, 1, 2, 3, 4, 5])
    a_y = f_up / m - G
    names = pick_queries(rng, ["a", "v", "y"] if t else ["a"])
    word = pick(rng, BODY_WORDS + BALL_WORDS)
    m_text, m_scene = mass(m, rng)
    scene: dict[str, Any] = {
        "version": 1.1,
        "bodies": [{"id": "body", "mass": m_scene}],
        "forces": [{"id": "pull", "kind": "applied", "body": "body", "vector": [0, f_up, 0]}],
        "queries": [],
    }
    ask_names = {"a": "acceleration", "v": "velocity", "y": "position"}
    for n in names:
        scene["queries"].append(query(n, ask_names[n], "body", at=t))
    expected = {
        "a": [0, a_y, 0],
        "v": [0, a_y * t, 0],
        "y": [0, 0.5 * a_y * t * t, 0],
    }
    expected = {n: expected[n] for n in names}
    compare = {"a": "xy", "v": "xy", "y": "xy"}
    ask_words = {
        "a": ["the acceleration of the {w}", "its acceleration", "the {w}'s acceleration"],
        "v": ["its velocity", "the velocity of the {w}", "its velocity (up is positive)"],
        "y": [
            "how far it has moved from its starting point (its position)",
            "its position relative to where it started",
            "its displacement",
        ],
    }
    asks = [pick(rng, ask_words[n]).format(w=word) for n in names]
    when = when_options(rng, t, "it starts moving")
    force = pick(
        rng,
        [
            f"a constant upward force of {fmt(f_up)} N",
            f"a steady vertical force of {fmt(f_up)} N directed upward",
            f"a {fmt(f_up)} N force pointing straight up",
        ],
    )
    givens = {
        "textbook": [
            f"A {m_text} {word}, initially at rest, is pushed straight upward by {force}.",
            "Take the starting point as the origin and up as positive.",
        ],
        "casual": [f"I lift a {m_text} {word} from rest with {force}. Up is positive."],
    }
    terse = f"{m_text} {word} from rest, {force}, up positive."
    return Problem(
        "lift", finish(rng, word, givens, terse, asks, when, t), scene, expected, compare
    )


# --- ramp, optionally pushed along the slope ----------------------------------------------------


def ramp(rng: random.Random) -> Problem:
    m = pick(rng, [1, 2, 3, 4, 5, 8, 10, 20, 50, 100, 250])
    theta = pick(rng, [10, 15, 17, 20, 25, 30, 37, 40, 45, 53])
    smooth = rng.random() < 0.35
    mu_s, mu_k = (0.0, 0.0) if smooth else friction_pair(rng)
    mu_s, mu_k, mode = friction_given(rng, mu_s, mu_k)
    cos, sin = math.cos(math.radians(theta)), math.sin(math.radians(theta))
    n_force = m * G * cos
    pushed = rng.random() < 0.75
    f_push = 0.0
    if pushed:
        f_push = max(round(m * G * sin * rng.uniform(0.2, 2.0) / 5) * 5, 5)
    net = f_push - m * G * sin  # along the slope, up positive, before friction
    if abs(net) <= mu_s * n_force:
        accel, friction = 0.0, abs(net)
    else:
        friction = mu_k * n_force
        accel = (abs(net) - friction) / m
    t = pick(rng, [0, 0, 1, 2])
    names = pick_queries(rng, ["a", "f", "N"])
    if smooth and "f" in names:
        names.remove("f")
        names = names or ["a"]
    word = pick(rng, BODY_WORDS)
    m_text, m_scene = mass(m, rng)
    scene: dict[str, Any] = {
        "version": 1.1,
        "bodies": [{"id": "block", "mass": m_scene}],
        "surfaces": [
            {
                "id": "ramp",
                "kind": "plane",
                "angle": f"{fmt(theta)} deg",
                "friction": surface_friction(mu_s, mu_k),
            }
        ],
        "contacts": [{"body": "block", "surface": "ramp"}],
        "queries": [],
    }
    if pushed:
        scene["forces"] = [
            {
                "id": "push",
                "kind": "applied",
                "body": "block",
                "magnitude": f"{fmt(f_push)} N",
                "directionAngle": "0 deg",
                "relativeTo": "ramp",
            }
        ]
    qmap = {"f": "friction", "N": "normal"}
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
    ask_words = {
        "a": [
            "the acceleration of the {w} down the plane",
            "its acceleration",
            "the {w}'s acceleration",
            "how fast it speeds up along the ramp (its acceleration)",
        ],
        "f": [
            "the friction force on the {w}",
            "the friction force acting on it",
            "the frictional force acting on it",
        ],
        "N": [
            "the normal force on the {w}",
            "the force the ramp exerts on the {w} (the normal force)",
            "the normal force",
            "the normal reaction of the ramp",
        ],
    }
    asks = [pick(rng, ask_words[n]).format(w=word) for n in names]
    when = (
        when_options(rng, t, "release")
        if t
        else pick(rng, ["at the start", "at the instant it is released", "at t = 0"])
    )
    ang = angle_text(theta, rng)
    surface = "smooth (frictionless)" if smooth else "rough"
    push = (
        pick(
            rng,
            [
                f"A force of {fmt(f_push)} N acts on it, parallel to the ramp and up the slope.",
                f"It is pushed up the slope by a {fmt(f_push)} N force parallel to the ramp.",
            ],
        )
        if pushed
        else "Nothing else acts on it."
    )
    givens = {
        "textbook": [
            f"A {m_text} {word} is placed at rest on a {surface} ramp that makes an angle of "
            f"{ang} with the horizontal.",
            *([] if smooth else [mu_phrase(rng, mu_s, mu_k, "textbook", mode)]),
            push,
        ],
        "casual": [
            f"A {m_text} {word} sits on a {surface} ramp tilted at {ang}.",
            *([] if smooth else [mu_phrase(rng, mu_s, mu_k, "casual", mode)]),
            push,
        ],
    }
    fric = mu_terse(mu_s, mu_k, mode, "smooth")
    tpush = f"push {fmt(f_push)} N up the slope" if pushed else "no other force"
    terse = f"{m_text} {word} at rest on {fmt(theta)} deg ramp, {fric}, {tpush}."
    return Problem(
        "ramp", finish(rng, word, givens, terse, asks, when, t), scene, expected, compare
    )


# --- flight: time of flight, maximum height, range, impact speed ----------------------------------


def flight(rng: random.Random) -> Problem:
    kind = pick(rng, ["ground", "ground", "up", "cliff", "cliff", "angled", "drop"])
    m = pick(rng, [0.1, 0.2, 0.5, 1, 2, 3, 5])
    h = {
        "ground": 0,
        "up": pick(rng, [10, 20, 30, 45, 60]),
        "cliff": pick(rng, [5, 10, 20, 45, 80, 100]),
        "angled": pick(rng, [10, 20, 45, 80]),
        "drop": pick(rng, [5, 10, 20, 45, 80, 100]),
    }[kind]
    sp = pick(rng, [5, 8, 10, 12, 15, 20, 25, 30, 40])
    angle = {
        "ground": pick(rng, [15, 20, 30, 35, 37, 40, 45, 53, 60, 75]),
        "up": 90,
        "cliff": 0,
        "angled": pick(rng, [15, 20, 30, 37, 45]),
        "drop": 0,
    }[kind]
    if kind == "drop":
        sp = 0
    vx, vy = sp * math.cos(math.radians(angle)), sp * math.sin(math.radians(angle))
    t_land = (vy + math.sqrt(vy * vy + 2 * G * h)) / G
    rng_x = vx * t_land
    top_ground = h + max(vy, 0) ** 2 / (2 * G)
    top_start = max(vy, 0) ** 2 / (2 * G)
    speed_land = math.hypot(vx, vy - G * t_land)
    options = ["T", "V"] + (["R"] if kind not in ("up", "drop") else []) + (["H"] if vy > 0 else [])
    names = pick_queries(rng, options)
    start_ref = h > 0 and "H" in names and rng.random() < 0.3 and vy > 0
    word = pick(rng, BALL_WORDS)
    m_text, m_scene = mass_or_none(m, rng)
    sp_text, sp_scene = speed(sp, rng)
    body: dict[str, Any] = {"id": "ball", "mass": m_scene, "shape": {"kind": "point"}}
    if m_scene is None:
        body.pop("mass")
    if h:
        body["position"] = [0, h, 0]
    if sp:
        body["velocity"] = {"speed": sp_scene, "angle": f"{fmt(angle)} deg"}
    scene: dict[str, Any] = {
        "version": 1.1,
        "bodies": [body],
        "surfaces": [{"id": "ground", "kind": "plane"}],
        "contacts": [{"body": "ball", "surface": "ground"}],
        "queries": [],
    }
    for n in names:
        if n == "T":
            scene["queries"].append(
                {"id": "T", "ask": "time", "until": {"event": "land"}, "body": "ball"}
            )
        elif n == "H":
            q = query("H", "max_height", "ball")
            if start_ref:
                q["above"] = "start"
            scene["queries"].append(q)
        elif n == "R":
            scene["queries"].append(query("R", "range", "ball"))
        else:
            scene["queries"].append(query("v", "velocity", "ball", at={"event": "land"}))
    answers = {
        "T": t_land,
        "H": top_start if start_ref else top_ground,
        "R": rng_x,
        "v": speed_land,
    }
    expected = {("v" if n == "V" else n): answers["v" if n == "V" else n] for n in names}
    compare = {"T": "value", "H": "value", "R": "value", "v": "norm_scalar"}
    ask_words = {
        "T": [
            "the time of flight",
            "how long the {w} is in the air",
            "the time it takes the {w} to reach the ground",
            "when the {w} hits the ground",
            "the total time to reach the ground",
            "the time taken to reach the ground",
        ],
        "H": (
            [
                "the maximum height above the launch point",
                "how high above the starting point it rises",
            ]
            if start_ref
            else (
                ["the maximum height reached", "how high the {w} goes", "its maximum height"]
                if h == 0
                else [
                    "the maximum height above the ground",
                    "the greatest height above the ground the {w} reaches",
                ]
            )
        ),
        "R": [
            "the horizontal range",
            "the horizontal distance the {w} travels",
            "how far from the launch point it lands, measured horizontally",
            "the horizontal distance travelled",
        ],
        "V": [
            "the speed with which it hits the ground",
            "the magnitude of its impact velocity",
            "its speed just before it lands",
            "the speed of impact",
            "its impact velocity",
        ],
    }
    asks = [pick(rng, ask_words[n]).format(w=word) for n in names]
    where = f"from a height of {fmt(h)} m above the ground" if h else "from level ground"
    if kind == "drop":
        givens = {
            "textbook": [
                f"A {m_text} {word} is dropped from rest {where}.",
                "Neglect air resistance.",
            ],
            "casual": [f"I drop a {m_text} {word} {where}.", "No air resistance."],
        }
        terse = f"{m_text} {word} dropped from rest, {fmt(h)} m above the ground, no drag."
    else:
        if angle == 90:
            launch = f"straight up at {sp_text}"
        elif angle == 0:
            launch = pick(rng, [f"horizontally at {sp_text}", f"horizontally with speed {sp_text}"])
        else:
            launch = pick(
                rng,
                [
                    f"at {sp_text} and {angle_text(angle, rng)} above the horizontal",
                    f"with speed {sp_text} at {angle_text(angle, rng)} above the horizontal",
                ],
            )
        verb = pick(rng, ["launched", "projected", "thrown"])
        givens = {
            "textbook": [
                f"A {m_text} {word} is {verb} {launch} {where}.",
                pick(rng, ["Neglect air resistance.", "Ignore air resistance."]),
            ],
            "casual": [
                f"I throw a {m_text} {word} {launch} {where}.",
                pick(rng, ["No air resistance.", "Ignore drag."]),
            ],
        }
        terse = f"{m_text} {word} {verb} {launch}, {where}, no drag."
    return Problem(
        "flight", finish(rng, word, givens, terse, asks, None, None), scene, expected, compare
    )


# --- spring released: initial force and acceleration --------------------------------------------


def spring_release(rng: random.Random) -> Problem:
    m = pick(rng, [0.5, 1, 2, 3, 4, 5, 8])
    k = pick(rng, [20, 50, 100, 150, 180, 200, 400, 500])
    amp = pick(rng, [0.05, 0.1, 0.12, 0.15, 0.2, 0.25, 0.3])
    rough = rng.random() < 0.4
    mu = pick(rng, [0.1, 0.2, 0.25, 0.3]) if rough else 0.0
    mu_s, mu_k, mode = (mu, mu, "kinetic") if rough else (0.0, 0.0, "both")
    if rough and rng.random() < 0.35:
        mu_s, mu_k, mode = (mu, mu, "single")
    if rough and k * amp <= mu * m * G * 1.5:
        amp = max(amp, round(mu * m * G * 2 / k, 2) + 0.05)
    spring_force = k * amp
    friction = mu_k * m * G if rough else 0.0
    net = spring_force - friction if spring_force > mu_s * m * G else 0.0
    names = pick_queries(rng, ["F", "a"], low=1)
    word = pick(rng, BODY_WORDS)
    m_text, m_scene = mass(m, rng)
    amp_text, amp_scene = distance(amp, rng)
    friction_block: dict[str, Any] = {"static": mu_s, "kinetic": mu_k}
    scene: dict[str, Any] = {
        "version": 1.1,
        "bodies": [{"id": "block", "mass": m_scene, "placement": {"on": "floor", "offset": 0}}],
        "surfaces": [{"id": "floor", "kind": "plane", "friction": friction_block}],
        "contacts": [{"body": "block", "surface": "floor"}],
        "forces": [
            {
                "id": "spring",
                "kind": "spring",
                "body": "block",
                "anchor": {"fixed": True, "stretch": amp_scene},
                "k": f"{fmt(k)} N/m",
                "restLength": 0,
            }
        ],
        "queries": [],
    }
    if not rough:
        scene["surfaces"] = [{"id": "floor", "kind": "plane"}]
    for n in names:
        if n == "F":
            scene["queries"].append(
                {"id": "F", "ask": "force", "force": "net", "body": "block", "at": 0}
            )
        else:
            scene["queries"].append(query("a", "acceleration", "block", at=0))
    expected = {"F": [net, 0, 0], "a": [net / m, 0, 0]}
    expected = {n: expected[n] for n in names}
    compare = {"F": "norm", "a": "norm"}
    ask_words = {
        "F": [
            "the net force on the {w} at the instant of release",
            "the initial net force on the {w}",
            "the force that acts on it right after it is released (the net force)",
            "the initial restoring force",
            "the force the spring exerts at the moment of release",
        ],
        "a": [
            "the initial acceleration of the {w}",
            "its acceleration at the instant of release",
            "the acceleration of the {w} just after it is let go",
        ],
    }
    asks = [pick(rng, ask_words[n]).format(w=word) for n in names]
    surf = "a rough horizontal surface" if rough else "a frictionless horizontal surface"
    givens = {
        "textbook": [
            f"A {m_text} {word} is attached to a spring of spring constant {fmt(k)} N/m and rests "
            f"on {surf}.",
            *([mu_phrase(rng, mu_s, mu_k, "textbook", mode)] if rough else []),
            f"The spring is stretched by {amp_text} and the {word} is released from rest.",
        ],
        "casual": [
            f"A {m_text} {word} sits on {surf}, hooked to a wall by a {fmt(k)} N/m spring.",
            *([mu_phrase(rng, mu_s, mu_k, "casual", mode)] if rough else []),
            f"I pull it so the spring is stretched {amp_text} and let go.",
        ],
    }
    fric = f", {mu_terse(mu_s, mu_k, mode)}" if rough else ", frictionless"
    terse = (
        f"{m_text} {word}{fric}, spring k = {fmt(k)} N/m, stretched {amp_text}, released from rest."
    )
    return Problem(
        "spring-release",
        finish(rng, word, givens, terse, asks, None, None),
        scene,
        expected,
        compare,
    )


# --- constant acceleration (no mass, no force) ---------------------------------------------------

VEHICLES = ["car", "train", "cyclist", "bus", "motorcycle", "sled", "boat", "scooter"]


def kinematics(rng: random.Random) -> Problem:
    kind = pick(rng, ["speed_up", "speed_up", "rest", "brake"])
    u = 0 if kind == "rest" else pick(rng, [5, 10, 12, 15, 20, 25, 30])
    a = pick(rng, [1, 1.5, 2, 2.5, 3, 4, 5])
    t = pick(rng, [2, 3, 4, 5, 6, 8, 10])
    if kind == "brake":
        a = -a
        t = min(t, math.floor(u / -a))  # stay before the stop, so displacement = distance
        if t < 1:
            kind, a = "speed_up", -a
            t = pick(rng, [2, 4, 5])
    v_end = u + a * t
    disp = u * t + 0.5 * a * t * t
    names = pick_queries(rng, ["v", "x", "d"])
    word = pick(rng, VEHICLES)
    u_text, u_scene = speed(u, rng)
    body: dict[str, Any] = {"id": "body", "constantAcceleration": f"{fmt(a)} m/s^2"}
    if u:
        body["velocity"] = {"speed": u_scene, "angle": "0 deg"}
    scene: dict[str, Any] = {"version": 1.1, "bodies": [body], "queries": []}
    for n in names:
        if n == "v":
            scene["queries"].append(query("v", "velocity", "body", at=t))
        elif n == "x":
            scene["queries"].append(query("x", "position", "body", at=t))
        else:
            scene["queries"].append(query("d", "distance", "body", **{"from": 0, "to": f"{t} s"}))
    expected = {"v": [v_end, 0, 0], "x": [disp, 0, 0], "d": disp}
    expected = {n: expected[n] for n in names}
    compare = {"v": "x", "x": "x", "d": "value"}
    ask_words = {
        "v": [
            "its final velocity",
            "its velocity at the end",
            "how fast it is going at the end",
            "its final speed",
        ],
        "x": [
            "its displacement",
            "its position at the end, measured from the start",
            "its displacement during this interval",
        ],
        "d": ["the distance it covers", "how far it travels", "the distance travelled"],
    }
    asks = [pick(rng, ask_words[n]) for n in names]
    rate = f"{fmt(abs(a))} m/s^2"
    if kind == "rest":
        textbook = f"A {word} starts from rest and accelerates uniformly at {rate} for {t} s."
        casual = (
            f"A {word} sets off from standstill and speeds up steadily at {rate} for {t} seconds."
        )
        terse = f"{word} from rest, a = {rate}, {t} s."
    elif kind == "speed_up":
        textbook = f"A {word} moving at {u_text} accelerates uniformly at {rate} for {t} s."
        casual = f"A {word} is going {u_text} and speeds up at {rate} for {t} seconds."
        terse = f"{word} at {u_text}, speeding up at {rate} for {t} s."
    else:
        textbook = f"A {word} moving at {u_text} brakes uniformly at {rate} for {t} s."
        casual = f"A {word} doing {u_text} slows down at {rate} for {t} seconds."
        terse = f"{word} at {u_text}, braking at {rate} for {t} s."
    givens = {"textbook": [textbook], "casual": [casual]}
    questions = finish(rng, word, givens, terse, asks, None, None)
    return Problem("kinematics", questions, scene, expected, compare)


# --- two bodies meeting ---------------------------------------------------------------------------

LEADERS = ["car", "truck", "motorcycle", "cyclist", "train"]
CHASERS = ["police car", "patrol car", "bus", "second car", "scooter"]


def _slug(word: str) -> str:
    return word.replace(" ", "_")


def chase(rng: random.Random) -> Problem:
    kind = pick(rng, ["pursuit", "pursuit", "head_on", "vertical"])
    if kind == "pursuit":
        while True:  # the meeting must happen inside the 60 s default window
            v1 = pick(rng, [10, 15, 20, 25, 30])
            a = pick(rng, [1, 2, 3, 4, 5])
            d = pick(rng, [0, 2, 3, 4, 5])
            tau = (v1 + math.sqrt(v1 * v1 + 2 * a * v1 * d)) / a
            t_meet = d + tau
            if t_meet < 50:
                break
        lead, chaser = pick(rng, LEADERS), pick(rng, CHASERS)
        v_text, v_scene = speed(v1, rng)
        scene: dict[str, Any] = {
            "version": 1.1,
            "bodies": [
                {
                    "id": _slug(lead),
                    "velocity": {"speed": v_scene, "angle": "0 deg"},
                    "constantAcceleration": "0 m/s^2",
                },
                {"id": _slug(chaser), "constantAcceleration": f"{fmt(a)} m/s^2"},
            ],
            "queries": [],
        }
        if d:
            scene["events"] = [
                {"id": "go", "at": f"{d} s", "kind": "release", "target": _slug(chaser)}
            ]
        names = pick_queries(rng, ["T", "X", "V"])
        for n in names:
            if n == "T":
                scene["queries"].append({"id": "T", "ask": "time", "until": {"event": "meet"}})
            elif n == "X":
                scene["queries"].append(query("X", "position", _slug(chaser), at={"event": "meet"}))
            else:
                scene["queries"].append(query("V", "velocity", _slug(chaser), at={"event": "meet"}))
        values = {"T": t_meet, "X": v1 * t_meet, "V": [a * tau, 0, 0]}
        expected = {n: ([v1 * t_meet, 0, 0] if n == "X" else values[n]) for n in names}
        compare = {"T": "value", "X": "x", "V": "x"}
        ask_words = {
            "T": [
                "how long after the {a} passes the {b} start that they meet",
                "when the {b} catches up with the {a}",
                "the time at which the {b} overtakes the {a}",
            ],
            "X": [
                "how far from the starting point they meet",
                "where the {b} catches the {a} (its position)",
                "the distance from the start at which the {b} catches up",
            ],
            "V": [
                "the speed of the {b} when it catches the {a}",
                "how fast the {b} is going at that moment (its velocity)",
            ],
        }
        asks = [pick(rng, ask_words[n]).format(a=lead, b=chaser) for n in names]
        delay = f" {d} seconds later" if d else " at the same moment"
        base_t = (
            f"A {lead} passes a {chaser} that is standing still, at a constant {v_text}. The {chaser} "
            f"sets off from rest{delay}, accelerating uniformly at {fmt(a)} m/s^2."
        )
        base_c = (
            f"A {lead} goes past a parked {chaser} at {v_text} and keeps that speed. The {chaser} "
            f"starts{delay} and speeds up at {fmt(a)} m/s^2."
        )
        terse = (
            f"{lead} at {v_text} constant passes a {chaser} at rest; the {chaser} starts{delay}, "
            f"a = {fmt(a)} m/s^2."
        )
        givens = {"textbook": [base_t], "casual": [base_c]}
        word = lead
    elif kind == "head_on":
        v1, v2 = pick(rng, [10, 15, 20, 25]), pick(rng, [8, 12, 16, 20])
        dist = pick(rng, [100, 200, 300, 500, 1000])
        t_meet = dist / (v1 + v2)
        lead, chaser = pick(rng, LEADERS), pick(rng, CHASERS)
        v1_text, v1_scene = speed(v1, rng)
        v2_text, v2_scene = speed(v2, rng)
        d_text, d_scene = distance(dist, rng, cm_ok=False)
        scene = {
            "version": 1.1,
            "bodies": [
                {
                    "id": _slug(lead),
                    "velocity": {"speed": v1_scene, "angle": "0 deg"},
                    "constantAcceleration": "0 m/s^2",
                },
                {
                    "id": _slug(chaser),
                    "position": [dist, 0, 0],
                    "velocity": {"speed": v2_scene, "angle": "180 deg"},
                    "constantAcceleration": "0 m/s^2",
                },
            ],
            "queries": [],
        }
        names = pick_queries(rng, ["T", "X"])
        for n in names:
            if n == "T":
                scene["queries"].append({"id": "T", "ask": "time", "until": {"event": "meet"}})
            else:
                scene["queries"].append(query("X", "position", _slug(lead), at={"event": "meet"}))
        values = {"T": t_meet, "X": [v1 * t_meet, 0, 0]}
        expected = {n: values[n] for n in names}
        compare = {"T": "value", "X": "x"}
        ask_words = {
            "T": [
                "how long until they meet",
                "the time at which they meet",
                "when they pass each other",
            ],
            "X": [
                "how far from the {a}'s starting point they meet",
                "where they meet, measured from the {a}'s start",
            ],
        }
        asks = [pick(rng, ask_words[n]).format(a=lead) for n in names]
        base_t = (
            f"A {lead} and a {chaser} start {d_text} apart and drive toward each other along a straight "
            f"road, the {lead} at {v1_text} and the {chaser} at {v2_text}, both at constant speed."
        )
        base_c = (
            f"A {lead} and a {chaser} are {d_text} apart on a straight road, driving toward each other: "
            f"the {lead} at {v1_text}, the {chaser} at {v2_text}."
        )
        terse = (
            f"{lead} {v1_text} and {chaser} {v2_text}, {d_text} apart, head-on, constant speeds."
        )
        givens = {"textbook": [base_t], "casual": [base_c]}
        word = lead
    else:  # vertical: one ball thrown up from the ground, one dropped from a height
        u = pick(rng, [15, 20, 25, 30])
        h = pick(rng, [30, 40, 50, 60, 80])
        t_meet = h / u
        t_flight = 2 * u / G
        if t_meet >= t_flight:  # they must meet before the first ball is back down
            h = round(u * t_flight * 0.5 / 5) * 5 or 5
            t_meet = h / u
        y = u * t_meet - 0.5 * G * t_meet**2
        scene = {
            "version": 1.1,
            "bodies": [
                {"id": "thrown", "velocity": {"speed": f"{u} m/s", "angle": "90 deg"}},
                {"id": "dropped", "position": [0, h, 0]},
            ],
            "queries": [],
        }
        names = pick_queries(rng, ["T", "Y"])
        for n in names:
            if n == "T":
                scene["queries"].append({"id": "T", "ask": "time", "until": {"event": "meet"}})
            else:
                scene["queries"].append(query("Y", "position", "thrown", at={"event": "meet"}))
        values = {"T": t_meet, "Y": [0, y, 0]}
        expected = {n: values[n] for n in names}
        compare = {"T": "value", "Y": "xy"}
        ask_words = {
            "T": ["how long until the balls meet", "the time at which they meet", "when they pass"],
            "Y": [
                "the height at which they meet",
                "how high above the ground they meet (their position)",
            ],
        }
        asks = [pick(rng, ask_words[n]) for n in names]
        base_t = (
            f"One ball is thrown straight up from the ground at {u} m/s. At the same moment a second ball is "
            f"dropped from rest from a height of {h} m directly above the first. Neglect air resistance."
        )
        base_c = (
            f"I toss a ball straight up at {u} m/s from the ground and, at that same instant, let another "
            f"one fall from {h} m right above it. No air resistance."
        )
        terse = f"Ball 1 up at {u} m/s from ground, ball 2 dropped from {h} m at the same time, no drag."
        givens = {"textbook": [base_t], "casual": [base_c]}
        word = "ball"
    when = None
    return Problem(
        "chase", finish(rng, word, givens, terse, asks, when, None), scene, expected, compare
    )


def unsupported_problem(rng: random.Random) -> Problem:
    """A question outside the solver's scope; the target output is a refusal, not a scene."""
    category, questions = unsupported.make(rng)
    return Problem("unsupported", questions, {"unsupported": category}, {}, {})


PARTIAL_EXTRAS = [
    ("the kinetic energy it has at the end", "energy"),
    ("its momentum at the end", "momentum"),
    ("the power needed", "power"),
    ("the speed it has when it gets back to its starting point", "motion after a return"),
    ("the total mechanical energy", "energy"),
    ("the angular velocity", "rotation"),
]


def partial_problem(rng: random.Random) -> Problem:
    """An in-scope problem that also asks for something the solver cannot compute: refuse."""
    base_family = pick(rng, [f for f in FAMILIES if f not in ("unsupported", "partial")])
    base = FAMILIES[base_family](rng)
    extra, reason = pick(rng, PARTIAL_EXTRAS)
    sentence = {
        "textbook": pick(rng, [f" Also find {extra}.", f" In addition, determine {extra}."]),
        "casual": pick(rng, [f" And what is {extra}?", f" Also, I need {extra}."]),
        "terse": pick(rng, [f" Also: {extra}.", f" And {extra}."]),
    }
    questions = {k: base.questions[k].rstrip() + sentence[k] for k in base.questions}
    return Problem("partial", questions, {"unsupported": reason}, {}, {})


FAMILIES: dict[str, Callable[[random.Random], Problem]] = {
    "floor-push": floor_push,
    "incline": incline,
    "sliding-stop": sliding_stop,
    "projectile": projectile,
    "free-fall": free_fall,
    "spring-block": spring_block,
    "lift": lift,
    "ramp": ramp,
    "flight": flight,
    "spring-release": spring_release,
    "kinematics": kinematics,
    "chase": chase,
    "unsupported": unsupported_problem,
    "partial": partial_problem,
}
WEIGHTS = {
    "floor-push": 3,
    "incline": 4,
    "sliding-stop": 2,
    "projectile": 3,
    "free-fall": 2,
    "spring-block": 2,
    "lift": 2,
    "ramp": 3,
    "flight": 5,
    "spring-release": 2,
    "kinematics": 4,
    "chase": 4,
    "unsupported": 4,
    "partial": 2,
}


# --- verification and dataset -------------------------------------------------------------------


def _component(kind: str, value: Any) -> Any:
    if kind == "norm":
        return math.hypot(*value)
    if kind == "norm_scalar":
        return math.hypot(*value) if isinstance(value, list) else value
    if kind == "x":
        return value[0]
    if kind == "xy":
        return value[:2]
    return value


def verify(problem: Problem, rel: float = 1e-3) -> list[str]:
    """Problems where the real solver disagrees with the closed-form answer (empty = fine)."""
    if "unsupported" in problem.scene:
        return []
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


def make_problems(
    n: int, seed: int, prefix: str = "syn", families: list[str] | None = None
) -> list[tuple[str, Problem]]:
    rng = random.Random(seed)
    names = [f for f, w in WEIGHTS.items() for _ in range(w) if families is None or f in families]
    seen: set[str] = set()
    out = []
    counters: dict[str, int] = {}
    while len(out) < n:
        family = pick(rng, names)
        problem = FAMILIES[family](rng)
        if "unsupported" not in problem.scene:
            problem.scene = with_title(problem.scene)
        key = json.dumps(problem.scene, sort_keys=True) + problem.questions["textbook"]
        if key in seen:
            continue
        seen.add(key)
        counters[family] = counters.get(family, 0) + 1
        out.append((f"{prefix}-{family}-{counters[family]:04d}", problem))
    return out


def build(
    n: int,
    seed: int,
    out_path: Path,
    workers: int = 4,
    prefix: str = "syn",
    families: list[str] | None = None,
) -> dict[str, Any]:
    problems = make_problems(n, seed, prefix, families)
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
                    **({"expect": "unsupported"} if "unsupported" in problem.scene else {}),
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
    prefix = args[3] if len(args) > 3 else "syn"
    families = args[4].split(",") if len(args) > 4 else None
    report = build(n, seed, out, prefix=prefix, families=families)
    print(f"kept {report['kept']}/{report['requested']} problems -> {out}")
    for pid, why in report["dropped"][:20]:
        print(f"  dropped {pid}: {why[:150]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
