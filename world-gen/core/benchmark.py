"""Session artifacts: database dumps and benchmark.json for each run."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


def dump_database(db_path: str | Path, out_dir: str | Path) -> None:
    """Export every SQLite table to database/<table>.txt (tab-separated rows)."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        for (name,) in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ):
            cols = [r[1] for r in conn.execute(f"PRAGMA table_info({name})")]
            rows = conn.execute(f"SELECT * FROM {name}").fetchall()
            with (out / f"{name}.txt").open("w") as fh:
                fh.write("\t".join(cols) + "\n")
                for row in rows:
                    fh.write("\t".join("" if c is None else str(c) for c in row) + "\n")
    finally:
        conn.close()


def write_benchmark(session_dir: str | Path, **patch: Any) -> dict[str, Any]:
    """Merge patch into session benchmark.json; append verify ticks when tick= is passed."""
    session_dir = Path(session_dir)
    path = session_dir / "benchmark.json"
    data: dict[str, Any] = json.loads(path.read_text()) if path.exists() else {}

    tick = patch.pop("tick", None)
    if tick is not None:
        ver = data.setdefault("verification", {})
        states = ver.setdefault("states", [])
        states.append(tick)
        passed = sum(1 for s in states if s.get("verify_passed"))
        ver["states_collected"] = len(states)
        ver["percentage_passed"] = round(100 * passed / len(states), 1) if states else 0.0

    for key, val in patch.items():
        if isinstance(val, dict) and isinstance(data.get(key), dict):
            data[key].update(val)
        else:
            data[key] = val

    path.write_text(json.dumps(data, indent=2) + "\n")
    return data
