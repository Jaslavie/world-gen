"""World snapshot types and strict shape validation.

Reject anything that does not match these structures exactly — no extra keys,
no missing fields, no wrong types.
"""
from __future__ import annotations

from dataclasses import dataclass

Vec = tuple[int, int]
Check = tuple[str, bool, str]


@dataclass
class Grid:
    w: int
    h: int


@dataclass
class Entity:
    type: str
    components: list[str]
    sprite: str


@dataclass
class Rule:
    check: str
    args: list[str | int]


@dataclass
class Snapshot:
    grid: Grid
    walls: set[Vec]
    entities: dict[str, Entity]
    pos: dict[str, Vec]
    flags: dict[str, dict[str, bool]]
    holding: dict[str, str | None]
    rules: list[Rule]
