"""worldgen.core.runtime — the deterministic half: run a world and judge it.

`SpatialTools` are the action primitives that mutate state; `Verifier` is the only
judge of success (never an LLM); `Engine` bundles them and exposes the single
state-transition step(). The SQLite state layer (`db.World`) and the stochastic
build half both live in `worldgen.core.generator`.
"""
from .engine import Engine
from .tools import SpatialTools
from .types import Check, Grid, Rule, Snapshot, Vec
from .verifier import Verifier

__all__ = [
    "Engine", "SpatialTools", "Verifier",
    "Check", "Snapshot", "Grid", "Rule", "Vec",
]
