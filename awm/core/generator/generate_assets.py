"""
Asset library
1. Try to look up an asset in the catalog.json file
2. (disabled) If not found, generate a new asset using the Claude model
"""
from __future__ import annotations

import json
# import re
from pathlib import Path

# from PIL import Image

# from . import prompts


class AssetLibrary:
    def __init__(self, assets_dir: str | Path, generated_dir: str | Path,
                 sprite_model: str | None = None, *,
                 sprite_res: int = 64, sprite_grid: int = 16,
                 sprite_max_tokens: int = 4000, sprite_retries: int = 2) -> None:
        # File paths
        self.assets_dir = Path(assets_dir)
        self.generated_dir = Path(generated_dir)
        self.generated_dir.mkdir(parents=True, exist_ok=True)

        # # Sprite generation parameters (LLM off — catalog only)
        # self.sprite_model = sprite_model
        # self.sprite_res = sprite_res
        # self.sprite_grid = sprite_grid
        # self.sprite_max_tokens = sprite_max_tokens
        # self.sprite_retries = sprite_retries
        # self.compiler = None  # lazily built on first generation

        # Load catalog of existing sprites
        cat = json.loads((self.assets_dir / "catalog.json").read_text())
        self.objects = dict(cat.get("objects", {}))
        self.terrain = dict(cat.get("terrain", {}))
        for sub, table in (("objects", self.objects), ("terrain", self.terrain)):
            for png in sorted((self.assets_dir / sub).glob("*.png")):
                table.setdefault(png.stem, f"{sub}/{png.stem}.png")
        self.object_labels = sorted(self.objects)
        self.terrain_labels = sorted(self.terrain)

    # Resolve a catalog asset by exact name (LLM picks from the allowed list)
    def catalog_sprite(self, name: str, *, kind: str) -> str:
        path = self.from_catalog(name, kind=kind)
        if not path:
            raise ValueError(f"{name!r} not in {kind} catalog")
        return path

    # Search for a sprite in the catalog (LLM generation disabled)
    def init_sprite(self, name: str, *, kind: str = "entity", fallback: str | None = None) -> str | None:
        path = self.from_catalog(name, kind=kind)
        if path:
            return path
        if fallback and fallback != name:
            return self.from_catalog(fallback, kind=kind)
        return None

    @staticmethod
    def sprite_source(path: str | None) -> str:
        if not path:
            return "missing"
        return "generated" if Path(path).name.startswith("gen_") else "catalog"

    @staticmethod
    def sprite_label(path: str | None) -> str | None:
        """Frontend-safe label: objects/rock, terrain/dirt, or gen_entity_foo."""
        if not path:
            return None
        p = Path(path)
        if p.name.startswith("gen_"):
            return p.stem
        for sub in ("objects", "terrain"):
            if sub in p.parts:
                return f"{sub}/{p.stem}"
        return p.stem

    @staticmethod
    def sprite_url(path: str | None) -> str:
        if not path:
            return ""
        p = Path(path)
        if p.name.startswith("gen_"):
            return f"/generated/{p.name}"
        for sub in ("objects", "terrain"):
            if sub in p.parts:
                return f"/assets/{sub}/{p.name}"
        return ""

    # Direct catalog lookup by exact asset name from the spec
    def from_catalog(self, name: str, *, kind: str) -> str | None:
        table = self.terrain if kind == "terrain" else self.objects
        if name in table:
            return str(self.assets_dir / table[name])
        return None

    # # 2. Claude pixel-art generation (disabled — catalog only)
    # def generate(self, name: str, *, kind: str = "entity") -> str | None:
    #     if not self.sprite_model:
    #         return None
    #     slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "obj"
    #     out = self.generated_dir / f"gen_{kind}_{slug}.png"
    #     if out.exists() and out.stat().st_size > 300:
    #         return str(out)
    #     try:
    #         from ..utils import Compiler
    #         if self.compiler is None:
    #             self.compiler = Compiler(
    #                 self.sprite_model, self.sprite_max_tokens, self.sprite_retries)
    #         n = self.sprite_grid
    #         shape = prompts.SPRITE_ENTITY_SHAPE if kind == "entity" else prompts.SPRITE_TERRAIN_SHAPE
    #
    #         # Generate pixel values
    #         data = self.compiler.json(
    #             prompts.SPRITE_GEN_SYSTEM.format(n=n),
    #             prompts.SPRITE_GEN_USER.format(n=n, name=name, shape=shape))
    #         img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    #         px = img.load()
    #         painted = 0
    #
    #         # Iterate over pixel values and gen final png
    #         for y, row in enumerate((data.get("grid") or [])[:n]):
    #             for x, cell in enumerate((row or [])[:n]):
    #                 s = cell.lstrip("#") if isinstance(cell, str) else ""
    #                 s = "".join(c * 2 for c in s) if len(s) == 3 else s
    #                 if len(s) >= 6:
    #                     px[x, y] = (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), 255)
    #                     painted += 1
    #         if painted == 0:
    #             if out.exists():
    #                 out.unlink()
    #             return None
    #         img.resize((self.sprite_res, self.sprite_res), Image.NEAREST).save(out)
    #         return str(out)
    #     except Exception:
    #         if out.exists() and out.stat().st_size <= 300:
    #             out.unlink()
    #         return None
