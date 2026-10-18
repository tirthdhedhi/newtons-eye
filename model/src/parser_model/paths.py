"""Repo layout helpers: where the examples, schema and seed set live."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


@lru_cache(maxsize=1)
def repo_root() -> Path:
    """The monorepo root: the nearest parent holding pnpm-workspace.yaml."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "pnpm-workspace.yaml").exists():
            return parent
    raise RuntimeError("cannot find the repo root (no pnpm-workspace.yaml above parser_model)")


def examples_dir() -> Path:
    return repo_root() / "examples"


def model_dir() -> Path:
    return repo_root() / "model"


def schema_path() -> Path:
    """schema/model.schema.json if it exists, else schema/authoring.schema.json."""
    schema_dir = repo_root() / "schema"
    preferred = schema_dir / "model.schema.json"
    return preferred if preferred.exists() else schema_dir / "authoring.schema.json"


def load_schema() -> dict[str, Any]:
    return json.loads(schema_path().read_text())


def gold_scene_path(example: str) -> Path:
    return examples_dir() / f"{example}.scene.json"


def authoring_path(example: str) -> Path:
    return examples_dir() / f"{example}.authoring.json"


def load_seed(path: str | Path) -> list[dict[str, Any]]:
    items = []
    for line in Path(path).read_text().splitlines():
        if line.strip():
            items.append(json.loads(line))
    return items


REFUSAL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"unsupported": {"type": "string", "minLength": 1}},
    "required": ["unsupported"],
    "additionalProperties": False,
}


def constrained_schema() -> dict[str, Any]:
    """Schema for constrained decoding: a valid scene OR a refusal ``{"unsupported": reason}``."""
    scene = {k: v for k, v in load_schema().items() if k != "$schema"}
    return {"anyOf": [scene, REFUSAL_SCHEMA]}
