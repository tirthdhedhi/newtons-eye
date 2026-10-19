"""The "find:" line: the model lists what is asked before it encodes it as queries.

A small model sometimes drops the second or third ask. Writing the list first makes that much rarer
(the list is short and easy), and it gives a check that needs no physics: a scene whose title
declares three things but holds two queries is incomplete.

    {"version": 1.1, "title": "find: velocity, position", "bodies": [...], "queries": [...]}
"""

from __future__ import annotations

import re
from typing import Any

PREFIX = "find:"


def ask_label(q: dict[str, Any]) -> str:
    """A short canonical name for what a query asks."""
    ask = q.get("ask")
    at = q.get("at")
    landing = isinstance(at, dict) and at.get("event") == "land"
    if ask == "force":
        return {
            "normal": "normal force",
            "friction": "friction force",
            "tension": "tension",
            "net": "net force",
        }.get(q.get("force"), "force")
    if ask == "time":
        event = (q.get("until") or {}).get("event")
        return {
            "land": "time of flight",
            "stop": "time to stop",
            "edge": "time to reach the edge",
            "slack": "time until the string goes slack",
            "slide_start": "time until it starts to slide",
        }.get(event, "time")
    if ask == "velocity":
        return "impact velocity" if landing else "velocity"
    if ask == "max_height":
        return "maximum height"
    if ask == "min_mu_s":
        return "minimum static friction coefficient"
    return {
        "acceleration": "acceleration",
        "position": "position",
        "distance": "distance",
        "work": "work",
        "range": "range",
        "relative_velocity": "relative velocity",
    }.get(str(ask), str(ask))


def title_for(scene: dict[str, Any]) -> str:
    return f"{PREFIX} " + ", ".join(ask_label(q) for q in scene.get("queries", []))


def with_title(scene: dict[str, Any]) -> dict[str, Any]:
    """A copy of ``scene`` whose ``title`` is the find line, placed right after ``version``."""
    out: dict[str, Any] = {}
    for key, value in scene.items():
        out[key] = value
        if key == "version":
            out["title"] = title_for(scene)
    if "version" not in scene:
        out = {"title": title_for(scene), **scene}
    return out


def declared_asks(scene: dict[str, Any]) -> list[str] | None:
    """The items of a ``find:`` title, or ``None`` if the scene has no such title."""
    title = scene.get("title")
    if not isinstance(title, str) or not title.lower().startswith(PREFIX):
        return None
    body = title[len(PREFIX) :].strip()
    return [item.strip() for item in re.split(r",", body) if item.strip()]


def asks_complete(scene: dict[str, Any]) -> bool:
    """False when the model declared more things than it wrote queries for.

    A scene without a ``find:`` title cannot be checked and counts as complete.
    """
    declared = declared_asks(scene)
    if declared is None:
        return True
    return len(scene.get("queries", [])) >= len(declared)
