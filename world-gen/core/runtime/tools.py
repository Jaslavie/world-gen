"""
The runtime splits into two responsibilities, kept in two classes:

  * Observer      -- a read-only view of a snapshot plus the success verdict.
                     It never mutates state; it only judges and reports it.
  * SpatialTools  -- the agent's action primitives that mutate the snapshot.
                     Each action fails (returns the snapshot unchanged) if its
                     precondition is not met, so the agent can never reach an
                     illegal state.

Action loop:
1. Get the current state of the agent based on the snapshot
2. Check if the move is valid
3. Update the agent's state based on the move
4. Return the updated snapshot
"""
from __future__ import annotations

from typing import Any

from .types import Snapshot


class Observer:
    """Read-only observation and success judgment over a snapshot (never mutates)."""

    def __init__(self, verifier) -> None:
        self.v = verifier

    # success == every win-condition rule currently holds in this snapshot
    def success(self, snap: Snapshot) -> bool:
        return self.v.verify(snap)

    def observe(self, snap: Snapshot, agent: str = "agent") -> dict[str, Any]:
        entities = [{
            "id": eid, "type": e.type, "pos": list(self.v.pos(snap, eid)),
            "components": e.components, "flags": snap.flags.get(eid, {}),
        } for eid, e in snap.entities.items()]
        return {
            "grid": {"w": snap.grid.w, "h": snap.grid.h},
            "agent": agent,
            "holding": snap.holding.get(agent),
            "walls": [list(w) for w in sorted(snap.walls)],
            "objective": self.v.describe(snap.rules),
            "clauses": self.v.clauses(snap),
            "success": self.success(snap),
            "entities": entities,
        }


class SpatialTools(Observer):
    """The agent's action primitives -- each mutates the snapshot in place."""

    directions = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0),
                  "forward": (0, -1), "backward": (0, 1)}

    def held(self, snap: Snapshot, agent: str) -> str | None:
        return snap.holding.get(agent)

    def move(self, snap: Snapshot, direction: str, agent: str = "agent") -> Snapshot:
        if direction not in self.directions:
            return snap
        dx, dy = self.directions[direction]
        src = self.v.pos(snap, agent)
        dst = (src[0] + dx, src[1] + dy)
        if (not self.v.in_bounds(snap, dst) or dst in snap.walls
                or dst in self.v.blocked_cells(snap, ignore=(agent,))):
            return snap
        snap.pos[agent] = dst
        carried = self.held(snap, agent)
        if carried is not None:
            snap.pos[carried] = dst
        return snap

    def pick(self, snap: Snapshot, eid: str, agent: str = "agent") -> Snapshot:
        if not self.v.has_component(snap, agent, "holder"):
            return snap
        if self.held(snap, agent) is not None or not self.v.has_component(snap, eid, "pickable"):
            return snap
        if not self.v.adjacent(self.v.pos(snap, agent), self.v.pos(snap, eid)):
            return snap
        snap.holding[agent] = eid
        snap.flags.setdefault(eid, {})["is_held"] = True
        snap.pos[eid] = self.v.pos(snap, agent)
        return snap

    def place(self, snap: Snapshot, target: str | None = None, agent: str = "agent") -> Snapshot:
        eid = self.held(snap, agent)
        if eid is None:
            return snap
        if target is not None:
            if target not in snap.entities or not self.v.adjacent(
                    self.v.pos(snap, agent), self.v.pos(snap, target)):
                return snap
            if not (self.v.has_component(snap, target, "container")
                    or self.v.has_component(snap, target, "surface")):
                return snap
            snap.pos[eid] = self.v.pos(snap, target)
        else:
            snap.pos[eid] = self.v.pos(snap, agent)
        snap.holding[agent] = None
        snap.flags.setdefault(eid, {}).update(is_held=False, resting=True)
        return snap

    def toggle(self, snap: Snapshot, eid: str, agent: str = "agent") -> Snapshot:
        if not (self.v.has_component(snap, eid, "openable") or
                self.v.has_component(snap, eid, "toggleable")):
            return snap
        if not self.v.adjacent(self.v.pos(snap, agent), self.v.pos(snap, eid)):
            return snap
        flags = snap.flags.setdefault(eid, {})
        if self.v.has_component(snap, eid, "openable"):
            flags["is_open"] = not flags.get("is_open", False)
        if self.v.has_component(snap, eid, "toggleable"):
            flags["is_toggled"] = not flags.get("is_toggled", False)
        return snap

    def apply(self, snap: Snapshot, action: dict[str, Any], agent: str = "agent") -> Snapshot:
        op = action.get("op", "wait")
        if op == "move":
            self.move(snap, action.get("dir", ""), agent)
        elif op == "pick":
            self.pick(snap, action["id"], agent)
        elif op == "place":
            self.place(snap, action.get("target"), agent)
        elif op == "toggle":
            self.toggle(snap, action["id"], agent)
        return snap
