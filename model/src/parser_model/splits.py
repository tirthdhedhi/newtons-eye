"""Train/val/test assignment that keeps evaluation honest.

Rules (enforced here, checked by ``check_no_leakage``):

* The split is decided per *problem*, by a hash of ``parent`` (or ``id`` when there is no parent).
  Every rewritten or templated variant of a problem has the same ``parent`` and so lands in the same
  split as the original. A held-out problem can never leak into training through a variant.
* Seed-set questions (``source == "seed"``) and records of a held-out ``family`` are always test.
* Roughly 70/10/20 train/val/test otherwise. The hash makes the assignment stable when records are
  added later, so test items never migrate into training.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from typing import Any

TRAIN_PCT = 70
VAL_PCT = 80  # cumulative: 70-79 is val, 80-99 is test


def _bucket(key: str) -> int:
    return int.from_bytes(hashlib.sha256(key.encode()).digest()[:4], "big") % 100


def split_of(record: dict[str, Any], holdout_families: Iterable[str] = ()) -> str:
    if record.get("source") == "seed" or record.get("family") in set(holdout_families):
        return "test"
    bucket = _bucket(str(record.get("parent") or record["id"]))
    if bucket < TRAIN_PCT:
        return "train"
    return "val" if bucket < VAL_PCT else "test"


def assign(
    records: list[dict[str, Any]], holdout_families: Iterable[str] = ()
) -> dict[str, list[dict[str, Any]]]:
    holdout = tuple(holdout_families)
    out: dict[str, list[dict[str, Any]]] = {"train": [], "val": [], "test": []}
    for record in records:
        out[split_of(record, holdout)].append(record)
    return out


def _normalise(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def check_no_leakage(splits: dict[str, list[dict[str, Any]]]) -> None:
    """Raise ``ValueError`` if a parent or a question appears in training and in val/test."""
    train = splits["train"]
    train_parents = {str(r.get("parent") or r["id"]) for r in train}
    train_questions = {_normalise(r["question"]) for r in train}
    for name in ("val", "test"):
        for r in splits[name]:
            parent = str(r.get("parent") or r["id"])
            if parent in train_parents:
                raise ValueError(f"{r['id']} ({name}) shares parent {parent!r} with training data")
            if _normalise(r["question"]) in train_questions:
                raise ValueError(f"{r['id']} ({name}) has the same question as a training item")
