"""
The generator runs a text prompt through an LLM and verifier:

1. Generate/Get assets: Get or generate the assets for the world
2. Generate task spec: a structured list of tasks that must be accomplishable in the world
3. Generate world spec: Use 1 (assets) and 2 (task spec) as priors to generate the world spec
4. Verify world spec
"""
from __future__ import annotations

import copy
import json
import logging
from typing import Any

from . import generate_layout as layout
from . import prompts

log = logging.getLogger(__name__)
Check = tuple[str, bool, str]


class Generator:
    def __init__(self, compiler, verifier, world, task_attempts: int = 2,
                env_attempts: int = 6) -> None:
        self.compiler = compiler
        self.verifier = verifier
        self.world = world
        self.task_attempts = task_attempts
        self.env_attempts = env_attempts

    def synthesize_task(self, prompt: str) -> dict[str, Any]:
        user = prompts.TASK_GEN_USER.format(
            prompt=prompt, components=", ".join(prompts.ALLOWED_COMPONENTS),
            checks=", ".join(prompts.ALLOWED_CHECKS))
        task: dict[str, Any] = {}
        for _ in range(self.task_attempts):
            task = self.compiler.json(prompts.TASK_GEN_SYSTEM, user)
            try:
                self.validate_task(task)
                return task
            except ValueError as err:
                log.warning("task spec rejected: %s", err)
                user += f"\n\nFix this and return corrected JSON: {err}"
        if isinstance(task, dict) and (task.get("task_description") or task.get("objective_summary")):
            task.setdefault("task_description", task.get("objective_summary", prompt))
            return task
        raise ValueError("could not synthesize a usable task spec")

    @staticmethod
    def validate_task(task: dict[str, Any]) -> None:
        if not isinstance(task, dict):
            raise ValueError("task spec is not a JSON object")
        if not (task.get("task_description") or task.get("objective_summary")):
            raise ValueError("task spec needs a 'task_description' or 'objective_summary'")
        if "required_entities" in task and "agent" not in task["required_entities"]:
            raise ValueError("required_entities must include 'agent'")

    def compile_world(self, prompt: str, task: dict[str, Any], seed: int = 0
                      ) -> tuple[dict[str, Any], list[Check]]:
        base = prompts.ENV_GEN_USER.format(
            task_json=json.dumps(task, indent=2), prompt=prompt,
            components=", ".join(prompts.ALLOWED_COMPONENTS), checks=", ".join(prompts.ALLOWED_CHECKS),
            object_sprites=", ".join(self.world.assets.object_labels),
            terrain_sprites=", ".join(self.world.assets.terrain_labels))

        last_failure = ""
        for attempt in range(self.env_attempts):
            user = base if not last_failure else (
                f"{base}\n\n--- REJECTED (attempt {attempt}) ---\n"
                f"{last_failure}\n"
                f"Return a full corrected JSON object that fixes only this problem."
            )
            sem = self.compiler.json(prompts.ENV_GEN_SYSTEM, user)
            sem["prompt"] = prompt
            spec = layout.generate(copy.deepcopy(sem), seed + attempt)
            try:
                self.validate_schema(spec)
                snap = self.world.build_snapshot(spec)
            except (ValueError, KeyError) as err:
                log.warning("invalid spec (attempt %d): %s", attempt + 1, err)
                last_failure = f"invalid spec ({err})"
                continue
            checks = self.verifier.verify_world(snap)
            if all(ok for _n, ok, _m in checks):
                spec["seed"] = seed + attempt
                return spec, checks
            failed = [(n, m) for n, ok, m in checks if not ok]
            last_failure = ", ".join(f"{n} ({m})" for n, m in failed)
            log.warning("world failed checks (attempt %d): %s", attempt + 1, last_failure)
        raise RuntimeError(
            f"no grounded world after {self.env_attempts} attempts: {last_failure or 'unknown'}"
        )

    def validate_schema(self, spec: dict[str, Any]) -> None:
        objects = self.world.assets.object_labels
        terrain = self.world.assets.terrain_labels
        # 1. the three top-level pieces exist
        for key in ("terrain", "entities", "rules"):
            if key not in spec:
                raise ValueError(f"missing '{key}'")
        if not isinstance(spec["rules"], list) or not spec["rules"]:
            raise ValueError("rules must be a non-empty list")

        # 2. the map is a real rectangle and every char is a defined tile
        legend = spec["terrain"].get("legend", {})
        rows = spec["terrain"].get("map", [])
        if not rows:
            raise ValueError("terrain.map is empty")
        width = len(rows[0])
        bad_rows = [i for i, r in enumerate(rows) if len(r) != width]
        if bad_rows:
            lens = [len(rows[i]) for i in bad_rows[:5]]
            raise ValueError(
                f"terrain.map must be a rectangle: {len(rows)} rows, expected width {width}, "
                f"but row(s) {bad_rows[:5]} have length(s) {lens}"
            )
        for code in {c for row in rows for c in row}:
            if code not in legend:
                raise ValueError(f"map char {code!r} missing from terrain.legend")
            if {"tile", "walkable"} - legend[code].keys():
                raise ValueError(f"legend[{code!r}] needs 'tile' and 'walkable'")
            tspr = legend[code].get("sprite") or legend[code]["tile"]
            if tspr not in terrain:
                raise ValueError(f"legend[{code!r}] sprite {tspr!r} not in catalog ({terrain})")

        # 3. exactly one agent, unique ids
        ids = [e.get("id") for e in spec["entities"]]
        if ids.count("agent") != 1:
            raise ValueError("spec must contain exactly one entity with id 'agent'")
        if len(set(ids)) != len(ids):
            raise ValueError("entity ids must be unique")

        # 4. every entity is well-formed, on a walkable cell, with a catalog asset
        h, w = len(rows), len(rows[0])
        walkable = {(x, y) for y, row in enumerate(rows)
                    for x, c in enumerate(row) if legend[c]["walkable"]}
        for e in spec["entities"]:
            if {"id", "type", "asset", "x", "y"} - e.keys():
                raise ValueError(f"entity {e.get('id')!r} needs id/type/asset/x/y")
            if e["asset"] not in objects:
                raise ValueError(
                    f"entity {e['id']} asset {e['asset']!r} not in catalog; pick from: {objects}")
            unknown = set(e.get("components", [])) - set(prompts.ALLOWED_COMPONENTS)
            if unknown:
                raise ValueError(f"unknown components {sorted(unknown)} on {e['id']}")
            if not (0 <= e["x"] < w and 0 <= e["y"] < h):
                raise ValueError(f"entity {e['id']} out of bounds")
            if (e["x"], e["y"]) not in walkable:
                raise ValueError(
                    f"entity {e['id']} at ({e['x']}, {e['y']}) is not on a walkable cell"
                )
