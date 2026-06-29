"""The viewer: a pygame window that watches the world and shows it to a human.

Polls the SQLite world read-only and draws the board plus the live objective state.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import hydra
import pygame
from omegaconf import DictConfig

from .runtime import Engine


# Live pygame viewer: polls the SQLite world read-only and draws the board + objective state.
class Renderer:
    tiles = {"floor": (38, 40, 48), "wall": (90, 96, 110), "water": (40, 70, 130), "door": (120, 86, 50)}
    palette = [(230, 180, 70), (200, 110, 200), (110, 200, 120), (230, 120, 120), (160, 160, 230)]

    def __init__(self, db_path, cell, cfg) -> None:
        self.engine = Engine(db_path, cfg)
        self.cell = cell
        self.sprites: dict = {}

    def sprite(self, path):
        if path and path not in self.sprites:
            p = Path(path)
            self.sprites[path] = (pygame.transform.scale(
                pygame.image.load(str(p)).convert_alpha(), (self.cell, self.cell)) if p.exists() else None)
        return self.sprites.get(path)

    # one frame from the db, or None if no world yet
    def read_frame(self):
        try:
            snap = self.engine.world.load_snapshot()
            conn = self.engine.world.connect(read_only=True)
            tiles = {(r["x"], r["y"]): (r["tile_type"], r["sprite"])
                     for r in conn.execute("SELECT x, y, tile_type, sprite FROM map_tiles")}
            entity_sprites = {r["entity_id"]: r["sprite"]
                              for r in conn.execute("SELECT entity_id, sprite FROM entities")}
            conn.close()
        except (sqlite3.Error, KeyError, TypeError):
            return None
        if not tiles:
            return None
        entities = [(eid, snap.pos[eid], entity_sprites.get(eid)) for eid in snap.pos]
        return snap.grid.w, snap.grid.h, tiles, entities

    def draw(self, screen, tiles, entities) -> None:
        screen.fill((20, 21, 26))
        # board: terrain tiles, then entities (sprite if present, else a coloured cell)
        for (x, y), (ttype, sprite) in tiles.items():
            rect = pygame.Rect(x * self.cell, y * self.cell, self.cell, self.cell)
            spr = self.sprite(sprite)
            screen.blit(spr, rect) if spr else pygame.draw.rect(screen, self.tiles.get(ttype, (70, 70, 70)), rect)
        for i, (eid, (x, y), sprite) in enumerate(entities):
            rect = pygame.Rect(x * self.cell, y * self.cell, self.cell, self.cell)
            spr = self.sprite(sprite)
            screen.blit(spr, rect) if spr else pygame.draw.rect(
                screen, self.palette[i % len(self.palette)], rect.inflate(-6, -6), border_radius=6)

    def run(self) -> None:
        pygame.init()
        pygame.display.set_caption("Agent World Model")
        screen = pygame.display.set_mode((480, 360))
        clock = pygame.time.Clock()
        while True:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT or (ev.type == pygame.KEYDOWN and ev.key in (pygame.K_q, pygame.K_ESCAPE)):
                    pygame.quit()
                    return
            frame = self.read_frame()
            if frame:
                w, h, tiles, entities = frame
                size = (w * self.cell, h * self.cell)
                if screen.get_size() != size:
                    screen = pygame.display.set_mode(size)
                self.draw(screen, tiles, entities)
                pygame.display.flip()
            clock.tick(8)

    def save_png(self, out_path: str | Path) -> None:
        frame = self.read_frame()
        if not frame:
            return
        w, h, tiles, entities = frame
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        pygame.init()
        pygame.display.set_mode((1, 1))
        surf = pygame.Surface((w * self.cell, h * self.cell))
        self.draw(surf, tiles, entities)
        pygame.image.save(surf, str(out_path))
        pygame.quit()


@hydra.main(version_base=None, config_path="../conf", config_name="config")
def main(cfg: DictConfig) -> None:
    db = os.environ.get("WORLD_DB", cfg.paths.runtime_db)
    Renderer(db, cfg.render.cell, cfg).run()


if __name__ == "__main__":
    main()
