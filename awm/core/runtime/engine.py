"""
Main runtime that runs the agent in the world
"""
from __future__ import annotations

import os
from typing import Any

from omegaconf import DictConfig

from ..generator.generate_assets import AssetLibrary
from ..generator.db import World
from .tools import SpatialTools
from .verifier import Verifier


class Engine:
    def __init__(self, db_path: str | os.PathLike, cfg: DictConfig) -> None:
        self.assets = AssetLibrary(
            cfg.paths.assets, cfg.paths.generated_assets,
            # sprite_model=cfg.models.get("sprite"),  # LLM sprite gen disabled
            sprite_model=None,
            sprite_res=cfg.sprites.res, sprite_grid=cfg.sprites.grid,
            sprite_max_tokens=cfg.sprites.max_tokens, sprite_retries=cfg.sprites.retries,
        )
        self.verifier = Verifier()
        self.tools = SpatialTools(self.verifier)
        self.world = World(db_path, self.assets, self.verifier)

    def step(self, action: dict[str, Any]) -> dict[str, Any]:
        snap = self.world.load_snapshot()
        self.tools.apply(snap, action)
        tick = int(self.world.get_meta("tick", 0)) + 1
        success = self.verifier.verify(snap)
        self.world.set_meta("tick", tick)
        self.world.set_meta("done", success)
        self.world.persist_snapshot(snap)
        self.world.append_trajectory(tick, action, success)
        obs = self.tools.observe(snap)
        obs["tick"] = tick
        return obs

    def observe(self) -> dict[str, Any]:
        snap = self.world.load_snapshot()
        obs = self.tools.observe(snap)
        obs["tick"] = int(self.world.get_meta("tick", 0))
        return obs

    def objective(self) -> str:
        return self.verifier.describe(self.world.load_snapshot().rules)

    def success(self) -> bool:
        return self.verifier.verify(self.world.load_snapshot())
