"""
Layout pass: the LLM draws terrain.map and entity coordinates; this stage only
repairs the grid rectangle (pad short rows / missing rows). It does not move
entities or change tiles the model already placed.
"""
from __future__ import annotations

from typing import Any


def fill_map_gaps(spec: dict[str, Any]) -> None:
    """Pad terrain.map to a rectangle. Never truncate — only fill missing cells."""
    terrain = spec.get("terrain")
    rows = terrain.get("map", []) if terrain else []
    if not rows:
        return
    legend = terrain.get("legend", {})
    fill = "#" if "#" in legend else next(iter(legend), ".")

    w = max(len(r) for r in rows)
    h = len(rows)
    dims = spec.get("dimensions")
    if isinstance(dims, list) and len(dims) >= 2:
        w = max(w, int(dims[0]))
        h = max(h, int(dims[1]))

    padded: list[str] = []
    for i in range(h):
        row = rows[i] if i < len(rows) else ""
        if len(row) < w:
            row += fill * (w - len(row))
        padded.append(row)
    terrain["map"] = padded
    spec["dimensions"] = [w, h]


def generate(spec: dict[str, Any], seed: int = 0) -> dict[str, Any]:
    fill_map_gaps(spec)
    return spec
