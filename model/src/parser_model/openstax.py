"""Extract exercises from OpenStax University Physics (CC BY 4.0, https://openstax.org).

Reads the CNXML sources of the book (``modules/<id>/index.cnxml``) and writes one record per
``<exercise>``: its problem text, its solution text when the book has one, and where it came from.
Attribution: "University Physics Volume 1", OpenStax, licensed CC BY 4.0.

    python -m parser_model.openstax private/openstax out.jsonl
"""

from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

CNX = "{http://cnx.rice.edu/cnxml}"
MML = "{http://www.w3.org/1998/Math/MathML}"

# Volume 1 chapters of interest: first module id, last module id (inclusive), in book order.
CHAPTERS = {
    "ch2-vectors": (58276, 58280),
    "ch3-straight-line": (58281, 58287),
    "ch4-two-three-d": (58288, 58293),
    "ch5-newtons-laws": (58294, 58301),
    "ch6-applications": (58302, 58306),
}


def _math(node: ET.Element) -> str:
    tag = node.tag.removeprefix(MML)
    kids = [_math(c) for c in node]
    if tag == "msub":
        return f"{kids[0]}_{kids[1]}"
    if tag == "msup":
        return f"{kids[0]}^{kids[1]}"
    if tag == "mfrac":
        return f"({kids[0]})/({kids[1]})"
    if tag == "msqrt":
        return f"sqrt({''.join(kids)})"
    if tag == "mspace":
        return " "
    if kids:
        return "".join(kids)
    return node.text or ""


def flatten(node: ET.Element) -> str:
    """Plain text of a CNXML fragment: MathML flattened, sub/sup as ``_``/``^``."""
    parts: list[str] = []

    def walk(el: ET.Element) -> None:
        if el.tag == f"{MML}math":
            parts.append(_math(el))
        elif el.tag == f"{CNX}sup":
            parts.append("^" + "".join(el.itertext()))
        elif el.tag == f"{CNX}sub":
            parts.append("_" + "".join(el.itertext()))
        elif el.tag == f"{CNX}newline":
            parts.append("\n")
        else:
            if el.text:
                parts.append(re.sub(r"\s+", " ", el.text))
            for child in el:
                walk(child)
        if el.tail and el.tag != f"{CNX}problem":
            parts.append(re.sub(r"\s+", " ", el.tail))

    walk(node)
    text = "".join(parts)
    text = re.sub(r"[ \t   ]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    return re.sub(r"\n+", "\n", text).strip()


def _fix_tail(node: ET.Element) -> str:
    # ``flatten`` appends the tail of the node itself; drop it for the top-level call.
    saved, node.tail = node.tail, None
    try:
        return flatten(node)
    finally:
        node.tail = saved


def extract_module(path: Path, chapter: str) -> list[dict[str, Any]]:
    root = ET.parse(path).getroot()
    module = path.parent.name
    title = root.findtext(f"{CNX}title") or ""
    out = []
    for i, ex in enumerate(root.iter(f"{CNX}exercise")):
        problem = ex.find(f"{CNX}problem")
        if problem is None:
            continue
        solution = ex.find(f"{CNX}solution")
        out.append(
            {
                "id": f"openstax-v1/{module}/{ex.get('id') or i}",
                "source": "openstax-university-physics-v1",
                "license": "CC BY 4.0",
                "chapter": chapter,
                "module": module,
                "section": title,
                "question": _fix_tail(problem),
                "solution": _fix_tail(solution) if solution is not None else None,
            }
        )
    return out


def extract_all(book_dir: Path) -> list[dict[str, Any]]:
    records = []
    for chapter, (first, last) in CHAPTERS.items():
        for number in range(first, last + 1):
            path = book_dir / "modules" / f"m{number}" / "index.cnxml"
            if path.exists():
                records.extend(extract_module(path, chapter))
    return records


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print(__doc__)
        return 64
    records = extract_all(Path(args[0]))
    Path(args[1]).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records))
    with_solution = sum(1 for r in records if r["solution"])
    print(f"{len(records)} exercises ({with_solution} with a solution) -> {args[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
