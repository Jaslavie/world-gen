"""
The SQLite state layer and single source of truth. Bridges the fixed schema to the
verifier and tools.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from ..runtime.types import Entity, Grid, Rule, Snapshot


class World:
    schema_path = Path(__file__).resolve().parent / "schema.sql"
    flag_for_component = {"pickable": "is_held", "openable": "is_open", "toggleable": "is_toggled"}

    def __init__(self, db_path: str | Path, assets, verifier) -> None:
        self.db_path = Path(db_path)
        self.assets = assets
        self.verifier = verifier
    
    # ==============================
    # 1. Connect and populate sqlite
    # ==============================
    # Connect to db
    def connect(self, read_only: bool = False) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if read_only:
            conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True, timeout=5)
        else:
            conn = sqlite3.connect(self.db_path, timeout=5)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

    def reset(self) -> None:
        for suffix in ("", "-wal", "-shm"):
            p = Path(str(self.db_path) + suffix)
            if p.exists():
                p.unlink()
        conn = self.connect()
        conn.executescript(self.schema_path.read_text())
        conn.commit()
        conn.close()
    
    # Turn LLM specification into database schema
    def instantiate(self, spec: dict[str, Any]) -> None:
        self.reset()   # wipe the old db and recreate the schema
        grid, tiles = self.expand_terrain(spec)
        conn = self.connect()

        # Insert all entities into the schema.sql template
        conn.executemany(
            "INSERT INTO map_tiles (x, y, tile_type, walkable, sprite) VALUES (?, ?, ?, ?, ?)",
            [(x, y, tile, int(w), self.assets.catalog_sprite(spr, kind="terrain"))
             for x, y, tile, w, spr in tiles])

        for e in spec["entities"]:
            # the entity itself
            conn.execute(
                "INSERT INTO entities (entity_id, entity_type, x, y, components, blocking, sprite) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (e["id"], e["type"], int(e["x"]), int(e["y"]),
                 json.dumps(e.get("components", [])), int(e.get("blocking", 0)),
                 self.assets.catalog_sprite(e["asset"], kind="entity")))
            # its initial on/off flags (is_held, is_open, ...)
            for flag, val in self.initial_flags(e).items():
                conn.execute("INSERT INTO entity_state (entity_id, flag, value) VALUES (?, ?, ?)",
                             (e["id"], flag, int(bool(val))))
            # the agent starts empty-handed
            if e["id"] == "agent":
                conn.execute("INSERT INTO holding (agent_id, item_id) VALUES (?, NULL)", (e["id"],))

        # the win condition: a flat list of rule checks (all must pass), stored as JSON
        conn.execute("INSERT INTO objective (id, rules) VALUES (1, ?)", (json.dumps(spec["rules"]),))

        # world-level scalars (grid size, seed, prompt, tick, success flags)
        rules = [Rule(r["check"], r["args"]) for r in spec["rules"]]
        meta = {"grid_w": grid["w"], "grid_h": grid["h"], "seed": spec.get("seed", 0),
                "prompt": spec.get("prompt", ""),
                "success_when": self.verifier.describe(rules),
                "goal_objects": sorted({a for r in rules for a in r.args if isinstance(a, str)}),
                "tick": 0, "success": False, "failed": False, "done": False}
        conn.executemany("INSERT INTO meta (key, value) VALUES (?, ?)",
                         [(k, json.dumps(v)) for k, v in meta.items()])
        conn.commit()
        conn.close()

    # 
    @staticmethod
    def expand_terrain(spec: dict[str, Any]):
        legend, rows = spec["terrain"]["legend"], spec["terrain"]["map"]
        grid = {"w": len(rows[0]), "h": len(rows)}
        tiles = [(x, y, legend[c]["tile"], bool(legend[c]["walkable"]),
                  legend[c].get("sprite") or legend[c]["tile"])
                 for y, row in enumerate(rows) for x, c in enumerate(row)]
        return grid, tiles

    @classmethod
    def initial_flags(cls, entity: dict[str, Any]) -> dict[str, bool]:
        flags = {f: False for c, f in cls.flag_for_component.items()
                 if c in entity.get("components", [])}
        flags.update(entity.get("flags", {}))
        return flags

    # ==============================
    # 2. Take snapshots of world states
    # ==============================
    # Build JSON snapshot of the current world state based on the SQL database state
    # Tool calls only interact with the snapshot
    def build_snapshot(self, spec: dict[str, Any]) -> Snapshot:
        grid_dims, tiles = self.expand_terrain(spec)
        walls = {(x, y) for x, y, _t, walkable, _s in tiles if not walkable}
        entities, posn, flags, holding = {}, {}, {}, {}
        for e in spec["entities"]:
            eid = e["id"]
            entities[eid] = Entity(
                type=e["type"],
                components=e.get("components", []),
                sprite=self.assets.catalog_sprite(e["asset"], kind="entity"),
            )
            posn[eid] = (int(e["x"]), int(e["y"]))
            flags[eid] = self.initial_flags(e)
            if eid == "agent":
                holding[eid] = None
        rules = [Rule(r["check"], r["args"]) for r in spec["rules"]]
        return Snapshot(
            grid=Grid(w=grid_dims["w"], h=grid_dims["h"]),
            walls=walls, entities=entities, pos=posn, flags=flags, holding=holding, rules=rules,
        )

    # Read the current state of the world from the database
    def load_snapshot(self, conn: sqlite3.Connection | None = None) -> Snapshot:
        own = conn is None
        conn = conn or self.connect(read_only=True)
        try:
            grid = Grid(w=self.get_meta("grid_w", conn=conn), h=self.get_meta("grid_h", conn=conn))
            walls = {(r["x"], r["y"]) for r in
                     conn.execute("SELECT x, y FROM map_tiles WHERE walkable = 0")}
            entities, posn = {}, {}
            for r in conn.execute("SELECT entity_id, entity_type, x, y, components, sprite FROM entities"):
                entities[r["entity_id"]] = Entity(
                    type=r["entity_type"],
                    components=json.loads(r["components"]),
                    sprite=r["sprite"],
                )
                posn[r["entity_id"]] = (r["x"], r["y"])
            flags: dict[str, dict[str, bool]] = {eid: {} for eid in entities}
            for r in conn.execute("SELECT entity_id, flag, value FROM entity_state"):
                flags.setdefault(r["entity_id"], {})[r["flag"]] = bool(r["value"])
            holding = {r["agent_id"]: r["item_id"]
                       for r in conn.execute("SELECT agent_id, item_id FROM holding")}
            rules = [Rule(r["check"], r["args"])
                     for r in json.loads(conn.execute("SELECT rules FROM objective WHERE id = 1").fetchone()["rules"])]
            return Snapshot(grid=grid, walls=walls, entities=entities, pos=posn,
                            flags=flags, holding=holding, rules=rules)
        finally:
            if own:
                conn.close()

    # ==============================
    # 3. Update the SQL database based on new snapshots
    # ==============================
    # Update the SQL database based on new snapshots
    def persist_snapshot(self, snap: Snapshot) -> None:
        conn = self.connect()
        for eid, (x, y) in snap.pos.items():
            conn.execute("UPDATE entities SET x = ?, y = ? WHERE entity_id = ?", (int(x), int(y), eid))
        conn.execute("DELETE FROM entity_state")
        for eid, fl in snap.flags.items():
            for flag, val in fl.items():
                conn.execute("INSERT INTO entity_state (entity_id, flag, value) VALUES (?, ?, ?)",
                             (eid, flag, int(bool(val))))
        for agent_id, item_id in snap.holding.items():
            conn.execute("UPDATE holding SET item_id = ? WHERE agent_id = ?", (item_id, agent_id))
        self.set_meta("success", self.verifier.verify(snap), conn=conn)
        conn.commit()
        conn.close()

    # Get some metadata value from the database
    def get_meta(self, key: str, default: Any = None, conn: sqlite3.Connection | None = None) -> Any:
        own = conn is None
        conn = conn or self.connect(read_only=True)
        try:
            row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
            return json.loads(row["value"]) if row else default
        finally:
            if own:
                conn.close()

    # Sets metadata values (ex: success state etc)
    def set_meta(self, key: str, value: Any, conn: sqlite3.Connection | None = None) -> None:
        own = conn is None
        conn = conn or self.connect()
        conn.execute("INSERT INTO meta (key, value) VALUES (?, ?) "
                     "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, json.dumps(value)))
        if own:
            conn.commit()
            conn.close()

    # Add the action and success state to the trajectory table
    def append_trajectory(self, tick: int, action: dict[str, Any], success: bool) -> None:
        conn = self.connect()
        conn.execute("INSERT INTO trajectory (tick, action, success) VALUES (?, ?, ?)",
                     (tick, json.dumps(action), int(success)))
        conn.commit()
        conn.close()
