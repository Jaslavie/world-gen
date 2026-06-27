"""Sprite resolution: catalog first, Claude-generated fallback.

  sprite(name, kind, override)  ->  catalog match, else a generated pixel-art sprite
"""
from __future__ import annotations

import re
from pathlib import Path

from PIL import Image


class AssetLibrary:
    ENTITY_ALIASES = {
        "agent": "adventurer", "player": "adventurer", "hero": "adventurer",
        "character": "adventurer", "person": "adventurer", "explorer": "adventurer",
        "ship": "spaceship", "rocket": "spaceship",
        "exit": "exit_sign", "goal": "exit_sign", "finish": "exit_sign", "gate": "door",
        "jewel": "gem", "crystal": "gem", "diamond": "gem", "money": "coin",
        "lamp": "torch", "light": "torch", "candle": "torch", "toggle": "switch",
        "trap": "spikes", "shrub": "bush", "flower": "plant",
        "boulder": "rock", "stone": "rock", "treasure": "gold",
    }
    TILE_ALIASES = {
        "ground": "floor", "room": "floor", "path": "floor", "corridor": "floor",
        "passage": "floor", "hall": "floor", "tile": "floor", "rock": "stone",
    }
    SPRITE_RES = 64   # final sprite size (px), matching the catalog art
    SPRITE_GRID = 16  # resolution the model designs at; nearest-neighbour upscaled

    def __init__(self, assets_dir: str | Path, generated_dir: str | Path,
                 sprite_model: str | None = None) -> None:
        self.assets_dir = Path(assets_dir)
        self.generated_dir = Path(generated_dir)
        self.generated_dir.mkdir(parents=True, exist_ok=True)
        self.sprite_model = sprite_model   # None -> generation off
        self._compiler = None              # lazily built on first generation
        import json
        cat = self.assets_dir / "catalog.json"
        cat = json.loads(cat.read_text()) if cat.exists() else {"objects": {}, "terrain": {}}
        self.objects = dict(cat.get("objects", {}))
        self.terrain = dict(cat.get("terrain", {}))
        for sub, table in (("objects", self.objects), ("terrain", self.terrain)):
            for png in sorted((self.assets_dir / sub).glob("*.png")):
                table.setdefault(png.stem, f"{sub}/{png.stem}.png")
        self.object_labels = sorted(self.objects)
        self.terrain_labels = sorted(self.terrain)

    # main entry: catalog (model's label first, then the noun), else generate
    def sprite(self, name: str, kind: str, override: str | None = None) -> str | None:
        return (self.from_catalog(override, kind) if override else None) \
            or self.from_catalog(name, kind) \
            or self.generate(name, kind)

    # 1. catalog lookup based on aliases
    def from_catalog(self, name: str | None, kind: str) -> str | None:
        if not name:
            return None
        table = self.objects if kind == "entity" else self.terrain
        aliases = self.ENTITY_ALIASES if kind == "entity" else self.TILE_ALIASES
        for n in (name, aliases.get(name.lower()), name.lower()):
            if n and n in table:
                return str(self.assets_dir / table[n])
        return None

    # 2. Claude pixel-art generation
    def generate(self, name: str, kind: str) -> str | None:
        if not self.sprite_model:
            return None
        slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "obj"
        out = self.generated_dir / f"gen_{kind}_{slug}.png"
        if out.exists():
            return str(out)
        try:
            from .llm import Compiler
            if self._compiler is None:
                self._compiler = Compiler(self.sprite_model, max_tokens=4000, retries=2)
            n = self.SPRITE_GRID
            shape = ("a single object centered on a transparent background" if kind == "entity"
                     else "a seamless terrain texture filling the whole grid")
            
            # Generate pixel values
            data = self._compiler.json(
                f"You are a pixel-art sprite generator for a top-down 2D game. You design "
                f"tiny, iconic, low-detail sprites on a {n}x{n} grid — no text, no fine detail.",
                f"Design a {n}x{n} pixel-art sprite of '{name}' as {shape}. Keep it simple and "
                f"instantly readable at small size, with a small flat color palette. Return JSON "
                f'{{"grid": [[...]]}} of exactly {n} rows of {n} cells; each cell is a hex color '
                f'like "#3a7d44", or null for a transparent pixel.')
            img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
            px = img.load()
            
            # Iterate over pixel values and gen final png
            for y, row in enumerate((data.get("grid") or [])[:n]):
                for x, cell in enumerate((row or [])[:n]):
                    s = cell.lstrip("#") if isinstance(cell, str) else ""
                    s = "".join(c * 2 for c in s) if len(s) == 3 else s
                    if len(s) >= 6:
                        px[x, y] = (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), 255)
            img.resize((self.SPRITE_RES, self.SPRITE_RES), Image.NEAREST).save(out)
            return str(out)
        except Exception:
            return None
