"""
Deterministic state verifier.
"""
from __future__ import annotations

from .types import Check, Rule, Snapshot, Vec


class Verifier:
    def __init__(self) -> None:
        self.checks = {
            "is_held": self.is_held, "not_held": self.not_held,
            "on": self.on, "inside": self.on, "near": self.near, "at": self.at,
            "is_open": self.is_open, "not_open": self.not_open,
            "is_toggled": self.is_toggled, "not_toggled": self.not_toggled,
            "reachable": self.reachable,
        }

    # ============================
    # Check if a condition is true
    # ============================
    def is_held(self, snap: Snapshot, eid: str) -> bool:
        return bool(snap.flags.get(eid, {}).get("is_held"))

    def not_held(self, snap: Snapshot, eid: str) -> bool:
        return not self.is_held(snap, eid)

    def on(self, snap: Snapshot, a: str, b: str) -> bool:
        return self.pos(snap, a) == self.pos(snap, b) and not self.is_held(snap, a)

    def near(self, snap: Snapshot, a: str, b: str, r: int = 1) -> bool:
        return self.manhattan(self.pos(snap, a), self.pos(snap, b)) <= int(r)

    def at(self, snap: Snapshot, eid: str, x: int, y: int) -> bool:
        return self.pos(snap, eid) == (int(x), int(y))

    def is_open(self, snap: Snapshot, eid: str) -> bool:
        return bool(snap.flags.get(eid, {}).get("is_open"))

    def not_open(self, snap: Snapshot, eid: str) -> bool:
        return not self.is_open(snap, eid)

    def is_toggled(self, snap: Snapshot, eid: str) -> bool:
        return bool(snap.flags.get(eid, {}).get("is_toggled"))

    def not_toggled(self, snap: Snapshot, eid: str) -> bool:
        return not self.is_toggled(snap, eid)

    # Use BFS to check if the goal object is reachable
    def reachable(self, snap: Snapshot, agent: str, eid: str) -> bool:
        start, goal = self.pos(snap, agent), self.pos(snap, eid)
        blocked = snap.walls | self.blocked_cells(snap, ignore=(agent, eid))
        seen, frontier = {start}, [start]
        while frontier:
            cell = frontier.pop()
            if self.adjacent(cell, goal):
                return True
            for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                nxt = (cell[0] + dx, cell[1] + dy)
                if nxt not in seen and self.in_bounds(snap, nxt) and nxt not in blocked:
                    seen.add(nxt)
                    frontier.append(nxt)
        return False

    # ==============================
    # Geometry helpers
    # ==============================
    @staticmethod
    def pos(snap: Snapshot, eid: str) -> Vec:
        return snap.pos[eid]

    @staticmethod
    def in_bounds(snap: Snapshot, cell: Vec) -> bool:
        return 0 <= cell[0] < snap.grid.w and 0 <= cell[1] < snap.grid.h

    @staticmethod
    def manhattan(a: Vec, b: Vec) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    @classmethod
    def adjacent(cls, a: Vec, b: Vec) -> bool:
        return cls.manhattan(a, b) <= 1

    @staticmethod
    def has_component(snap: Snapshot, eid: str, component: str) -> bool:
        return component in snap.entities[eid].components

    def blocked_cells(self, snap: Snapshot, ignore: tuple[str, ...] = ()) -> set[Vec]:
        return {self.pos(snap, eid) for eid, e in snap.entities.items()
                if "blocking" in e.components and eid not in ignore
                and not self.is_held(snap, eid)}
    
    # Human readable description of the rules
    def clauses(self, snap: Snapshot) -> list[dict]:
        return [{"clause": f"{r.check}({', '.join(map(str, r.args))})",
                 "satisfied": self.checks[r.check](snap, *r.args)} for r in snap.rules]

    def describe(self, rules: list[Rule]) -> str:
        return " AND ".join(r.check + "(" + ", ".join(map(str, r.args)) + ")" for r in rules)
    
    # Verify that the current state is valid
    def verify(self, snap: Snapshot) -> bool:
        return all(self.checks[r.check](snap, *r.args) for r in snap.rules)

    # Verify the world is valid before the agent takes any actions
    def verify_world(self, snap: Snapshot) -> list[Check]:
        out: list[Check] = []
        # 1. every rule is well-formed, references only defined entities, and uses only defined checks
        ids = set(snap.entities)
        formed, formed_msg = True, self.describe(snap.rules)
        for r in snap.rules:
            if r.check not in self.checks:
                formed, formed_msg = False, f"unknown check {r.check!r}"
                break
            for a in r.args:
                if isinstance(a, str) and a not in ids:
                    formed, formed_msg = False, f"{r.check} references unknown entity {a!r}"
                    break
            if not formed:
                break
        out.append(("snapshot", formed, formed_msg))

        # 2. every entity is in bounds, off walls, and on a distinct cell
        seen: dict[Vec, str] = {}
        placement_ok, placement_msg = True, f"{len(snap.entities)} entities on distinct cells"
        for eid in snap.entities:
            p = self.pos(snap, eid)
            if not self.in_bounds(snap, p) or p in snap.walls:
                placement_ok, placement_msg = False, f"{eid} out of bounds or in a wall"
                break
            if p in seen and not self.is_held(snap, eid):
                placement_ok, placement_msg = False, f"{eid} overlaps {seen[p]}"
                break
            seen.setdefault(p, eid)
        out.append(("placement", placement_ok, placement_msg))

        # 3. the objective is not already satisfied at t0 (room to solve)
        solved = self.verify(snap)
        out.append(("non-trivial", not solved,
                    "already true at t0" if solved else "false at t0 (room to solve)"))

        # 4. the agent can BFS-reach every goal object the rules reference
        solvable, solvable_msg = True, "agent reaches all goal objects (BFS)"
        for rule in snap.rules:
            targets = rule.args[:2] if rule.check in ("on", "inside", "near") else rule.args[:1]
            for t in targets:
                if not isinstance(t, str) or t not in snap.entities or t == "agent":
                    continue
                if not self.reachable(snap, "agent", t):
                    solvable = False
                    solvable_msg = (
                        f"agent at {self.pos(snap, 'agent')} cannot reach {t} "
                        f"at {self.pos(snap, t)} (BFS); keep them in one connected walkable "
                        f"region — no lava/water/walls/blocking entities between them at start"
                    )
                    break
            if not solvable:
                break
        out.append(("solvable", solvable, solvable_msg))

        return out
