from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .config import cfg
from .engine import Engine

# All actions taken by the agent are recorded in a file
DB = os.environ.get("WORLD_DB", cfg.paths.runtime_db)
ACTIONS_LOG = os.environ.get("ACTIONS_LOG") or str(Path(DB).with_name("actions.log"))

engine = Engine(DB, cfg)
mcp = FastMCP("worldgen")


def record(line: str) -> None:
    with open(ACTIONS_LOG, "a") as fh:
        fh.write(line + "\n")


@mcp.tool()
def observe() -> dict[str, Any]:
    """Read the scene graph: every entity's position, components and flags, the walls,
    the objective, per-clause satisfaction, and whether you have won. Call this first."""
    record("observe")
    return engine.observe()


@mcp.tool()
def move(direction: str) -> dict[str, Any]:
    """Move the agent one cell: up, down, left or right. Walls and blocking entities
    stop you (the move is then a no-op). Any item you carry moves with you."""
    record(f"move {direction}")
    return engine.step({"op": "move", "dir": direction})


@mcp.tool()
def pick(entity_id: str) -> dict[str, Any]:
    """Pick up an adjacent pickable entity. You must be next to it and not already
    carrying something."""
    record(f"pick {entity_id}")
    return engine.step({"op": "pick", "id": entity_id})


@mcp.tool()
def place(target: str | None = None) -> dict[str, Any]:
    """Drop the item you carry. Pass target to place it onto an adjacent entity such as
    a table; omit it to drop on your own cell."""
    record("place" + (f" {target}" if target else ""))
    return engine.step({"op": "place", "target": target})


@mcp.tool()
def toggle(entity_id: str) -> dict[str, Any]:
    """Toggle an adjacent openable or toggleable entity, such as opening a door or
    flipping a lever."""
    record(f"toggle {entity_id}")
    return engine.step({"op": "toggle", "id": entity_id})


@mcp.tool()
def get_objective() -> str:
    """Return the human-readable success condition for this world."""
    record("get_objective")
    return engine.objective()


@mcp.tool()
def get_success() -> bool:
    """Return True if the objective is currently satisfied. This is the same
    deterministic check the harness uses to score you."""
    record("get_success")
    return engine.success()


if __name__ == "__main__":
    mcp.run()
