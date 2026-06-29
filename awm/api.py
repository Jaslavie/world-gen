"""
WebSocket backend for the Studio frontend.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import hydra
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from hydra import compose, initialize_config_dir
from omegaconf import DictConfig

from awm.core.agent import log_tick
from awm.core.generator import Generator
from awm.core.generator.generate_assets import AssetLibrary
from awm.core.runtime import Engine
from awm.core.utils import Compiler

log = logging.getLogger(__name__)
repo = Path(__file__).resolve().parents[1]
conf_dir = str(repo / "awm" / "conf")
stage_names = ["Prompt", "Extract objects", "Build task list", "Ground DB objects",
               "Build MCP tool list", "Verifier", "World-state check"]

app = FastAPI()
studio_cfg: DictConfig | None = None
engine: Engine | None = None
generator: Generator | None = None
db_path: Path | None = None
actions_log: Path | None = None
assets_mounted = False
lock = threading.Lock()

# set default values for each data panel
panel_defaults: dict[str, Any] = {
    "world": None, "checks": [], "assets": [], "positions": {}, "holding": None,
    "clauses": [], "toolCalls": [], "success": False, "goalPct": 0,
}

# state payload
payload: dict[str, Any] = {
    "phase": "idle", "error": None,
    "stages": [{"id": i + 1, "name": n, "status": "idle", "summary": ""} for i, n in enumerate(stage_names)],
    **{k: (v.copy() if isinstance(v, (list, dict)) else v) for k, v in panel_defaults.items()},
}


def setup(cfg: DictConfig) -> None:
    global studio_cfg, engine, generator, db_path, actions_log, assets_mounted
    studio_cfg = cfg
    Path(cfg.paths.logs).mkdir(parents=True, exist_ok=True)
    db_path = Path(cfg.paths.runtime_db)
    actions_log = db_path.with_name("actions.log")
    engine = Engine(db_path, cfg)
    generator = Generator(
        Compiler(cfg.models.compile, cfg.llm.compile_max_tokens, cfg.llm.retries),
        engine.verifier, engine.world, cfg.generation.task_attempts, cfg.generation.env_attempts,
    )
    if not assets_mounted:
        app.mount("/assets", StaticFiles(directory=str(cfg.paths.assets)), name="assets")
        app.mount("/generated", StaticFiles(directory=str(cfg.paths.generated_assets)), name="generated")
        assets_mounted = True


def bind_session(session: Path) -> None:
    """Point the engine at a session directory (world.db + actions.log live here)."""
    global engine, generator, db_path, actions_log
    assert studio_cfg is not None
    session.mkdir(parents=True, exist_ok=True)
    db_path = session / "world.db"
    actions_log = session / "actions.log"
    engine = Engine(db_path, studio_cfg)
    generator = Generator(
        Compiler(studio_cfg.models.compile, studio_cfg.llm.compile_max_tokens, studio_cfg.llm.retries),
        engine.verifier, engine.world, studio_cfg.generation.task_attempts, studio_cfg.generation.env_attempts,
    )


def session_dir_for(prompt: str) -> Path:
    assert studio_cfg is not None
    slug = re.sub(r"[^a-z0-9]+", "_", prompt.lower()).strip("_")[:40] or "run"
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return Path(studio_cfg.paths.logs) / f"{ts}_{slug}"


def ensure_setup() -> None:
    if engine is None:
        with initialize_config_dir(config_dir=conf_dir, version_base=None):
            setup(compose(config_name="config"))


def clear_panels() -> None:
    """Wipe every panel back to empty so each generation starts from a clean slate."""
    payload.update({k: (v.copy() if isinstance(v, (list, dict)) else v) for k, v in panel_defaults.items()})
    if actions_log and actions_log.exists():
        actions_log.write_text("")


def set_stage(sid: int, status: str, summary: str = "") -> None:
    s = payload["stages"][sid - 1]
    s["status"], s["summary"] = status, summary or s["summary"]


# Read the current state of the world from the database
def read_payload() -> dict[str, Any]:
    ensure_setup()
    assert engine is not None and db_path is not None and actions_log is not None
    snap = engine.world.load_snapshot()
    conn = engine.world.connect(read_only=True)

    # static layout: grid size, terrain tiles, entities
    w = int(engine.world.get_meta("grid_w", 0, conn=conn))
    h = int(engine.world.get_meta("grid_h", 0, conn=conn))
    tiles = [[None] * w for _ in range(h)]
    for r in conn.execute("SELECT x, y, sprite FROM map_tiles"):
        tiles[r["y"]][r["x"]] = AssetLibrary.sprite_label(r["sprite"])
    entities = [{"id": r["entity_id"], "type": r["entity_type"], "pos": [r["x"], r["y"]],
                 "components": json.loads(r["components"]),
                 "sprite": AssetLibrary.sprite_label(r["sprite"])}
                for r in conn.execute("SELECT entity_id, entity_type, x, y, components, sprite FROM entities")]
    prompt = engine.world.get_meta("prompt", "", conn=conn)
    conn.close()

    clauses = engine.verifier.clauses(snap)
    calls = [{"n": i, "tool": (p := ln.partition(" "))[0], "arg": p[2] or None}
             for i, ln in enumerate(actions_log.read_text().splitlines())] if actions_log.exists() else []
    return {
        "world": {"gridW": w, "gridH": h, "tiles": tiles, "entities": entities, "prompt": prompt,
                  "objective": engine.verifier.describe(snap.rules)},
        "positions": {eid: list(p) for eid, p in snap.pos.items()},
        "holding": snap.holding.get("agent"),
        "clauses": clauses,
        "success": engine.verifier.verify(snap),
        "toolCalls": calls,
        "goalPct": round(sum(c["satisfied"] for c in clauses) / len(clauses) * 100) if clauses else 0,
    }


def run_generate(prompt: str) -> None:
    ensure_setup()
    assert studio_cfg is not None
    if not lock.acquire(blocking=False):
        return
    try:
        clear_panels()
        payload.update(phase="generating", error=None)
        for s in payload["stages"]:
            s["status"], s["summary"] = "idle", ""
        set_stage(1, "done", f"“{prompt}”")
        session = session_dir_for(prompt)
        bind_session(session)
        log_path = session / "run.log"
        assert generator is not None and engine is not None and db_path is not None

        t0 = time.time()
        task = generator.synthesize_task(prompt)
        t1 = time.time()
        spec, checks = generator.compile_world(prompt, task, studio_cfg.generation.seed)
        t2 = time.time()
        engine.world.instantiate(spec)
        env_attempts = spec["seed"] - studio_cfg.generation.seed + 1
        os.environ["SESSION_META"] = json.dumps({
            "prompt": prompt, "mode": "frontend", "steps_budget": studio_cfg.agent.steps,
            "task_latency_s": round(t1 - t0, 1),
            "gen_latency_s": round(t2 - t1, 1),
            "env_attempts": env_attempts,
            "env_retries": env_attempts - 1,
            "compile_valid_first_try": env_attempts == 1,
            "initial_checks": [{"name": n, "passed": ok, "message": m} for n, ok, m in checks],
        })

        set_stage(2, "done", " · ".join(task.get("required_entities", [])) or "objects extracted")
        set_stage(3, "done", checks[0][2])
        set_stage(4, "done", f"{len(spec['entities'])} entities written to SQLite")
        conn = engine.world.connect(read_only=True)
        payload["assets"] = [
            {"word": t, "label": AssetLibrary.sprite_label(s) or t,
             "source": AssetLibrary.sprite_source(s),
             "png": AssetLibrary.sprite_url(s)}
            for t, s in conn.execute("SELECT entity_type, sprite FROM entities")]
        conn.close()
        set_stage(5, "done", "move · pick · place · toggle · observe")
        set_stage(6, "done", f"{sum(ok for _n, ok, _m in checks)}/{len(checks)} grounding checks · solvable")
        payload["checks"] = [{"name": n, "passed": ok, "message": m} for n, ok, m in checks]

        log_path.write_text("")
        if actions_log:
            actions_log.write_text("")
        log_tick(log_path, engine, "(world generated)", studio_cfg)
        payload.update(read_payload(), phase="ready")
    except Exception as err:
        log.exception("generation failed")
        payload.update(phase="error", error=f"generation failed: {type(err).__name__}: {err}")
    finally:
        lock.release()


def run_agent() -> None:
    ensure_setup()
    if not payload.get("world") or not lock.acquire(blocking=False):
        return
    assert db_path is not None and actions_log is not None and engine is not None and studio_cfg is not None
    log_path = db_path.parent / "run.log"
    try:
        actions_log.write_text("")
        payload["phase"] = "running"
        set_stage(7, "running")
        os.environ["AGENT_START"] = str(time.time())
        agent_env = {**os.environ, "PYTHONPATH": str(repo), "AWM_AGENT_ONLY": "1",
                     "WORLD_DB": str(db_path), "ACTIONS_LOG": str(actions_log),
                     "AWM_STEPS": str(studio_cfg.agent.steps)}
        agent_log = open(db_path.with_name("agent.log"), "w")
        proc = subprocess.Popen([sys.executable, "-m", "awm.core.agent"], cwd=str(repo),
                                env=agent_env, stdout=agent_log, stderr=agent_log)
        seen = 0
        while proc.poll() is None:
            payload.update(read_payload())
            if actions_log.exists():
                lines = actions_log.read_text().splitlines()
                while seen < len(lines):
                    log_tick(log_path, engine, lines[seen], studio_cfg)
                    seen += 1
            if payload["success"]:
                proc.terminate()
                break
            time.sleep(0.2)
        for line in actions_log.read_text().splitlines()[seen:]:
            log_tick(log_path, engine, line, studio_cfg)
        proc.wait()
        log_tick(log_path, engine, "(agent finished)", studio_cfg)
        payload.update(read_payload())
        set_stage(7, "done")
        payload["phase"] = "solved" if payload["success"] else "ready"
    finally:
        lock.release()


# Establish persistent connection with the frontend to stream the current payload
@app.websocket("/ws")
async def studio(ws: WebSocket) -> None:
    await ws.accept()
    last = None
    try:
        while True:
            wire = json.dumps(payload)
            if wire != last:
                await ws.send_text(wire)
                last = wire
            try:
                msg = await asyncio.wait_for(ws.receive_json(), timeout=0.1)
            except asyncio.TimeoutError:
                continue
            if msg.get("cmd") == "generate":
                asyncio.create_task(asyncio.to_thread(run_generate, msg.get("prompt", "")))
            elif msg.get("cmd") == "run":
                asyncio.create_task(asyncio.to_thread(run_agent))
    except WebSocketDisconnect:
        pass


@hydra.main(version_base=None, config_path="conf", config_name="config")
def main(cfg: DictConfig) -> None:
    setup(cfg)
    uvicorn.run(app, host=cfg.server.host, port=cfg.server.port)


if __name__ == "__main__":
    main()
