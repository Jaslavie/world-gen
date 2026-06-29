"""
awm.core.generator — the stochastic half: build a world from a prompt.
- `generate_world` runs the two LLM generation stages (prompt -> task spec -> sqlite database)
- `prompts` holds the generation prompts and closed vocabulary
- `generate_layout` pass-through; the LLM already emits the terrain map + placements
- `generate_assets` resolves sprites from the Kenney catalog
- `db` is the SQLite state layer (schema.sql is its determinism contract)
"""
from ..utils import Compiler
from .generate_assets import AssetLibrary
from .generate_world import Check, Generator

__all__ = ["Generator", "Check", "Compiler", "AssetLibrary"]
