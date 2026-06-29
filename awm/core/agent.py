"""The agent: an LLM player that solves a generated world over MCP.

Connects to the MCP server, observes the world, and calls action tools until it wins.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import hydra
from mcp_agent.agents.agent import Agent as MCPAgent
from mcp_agent.app import MCPApp
from mcp_agent.config import (AnthropicSettings, MCPServerSettings, MCPSettings,
                            Settings)
from mcp_agent.workflows.llm.augmented_llm import RequestParams
from mcp_agent.workflows.llm.augmented_llm_anthropic import AnthropicAugmentedLLM
from omegaconf import DictConfig

from .generator import Generator
from .generator.prompts import AGENT_SYSTEM, AGENT_USER
from .runtime import Engine
from .utils import Compiler

log = logging.getLogger(__name__)
repo = Path(__file__).resolve().parent.parent.parent


def log_tick(log_path: Path, engine: Engine, action: str, cfg: DictConfig | None = None) -> None:
    obs = dict(engine.observe())
    obs["walls"] = " ".join(f"({x},{y})" for x, y in obs["walls"])
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    snap = engine.world.load_snapshot()
    verify_passed = engine.verifier.verify(snap)
    clauses = engine.verifier.clauses(snap)
    state = json.dumps(
        {"observe": obs, "get_objective": engine.objective(), "get_success": verify_passed},
        indent=2,
    )
    block = f"{ts}\n- agent action: {action}\n- world state:\n{state}\n\n"
    with log_path.open("a") as fh:
        fh.write(block)
        fh.flush()
    print(block, end="", flush=True)

    session_dir = log_path.parent
    from .benchmark import dump_database, write_benchmark

    if action == "(world generated)":
        meta = json.loads(os.environ.get("SESSION_META", "{}"))
        dump_database(engine.world.db_path, session_dir / "database")
        if cfg is not None:
            from .render import Renderer
            Renderer(str(engine.world.db_path), cfg.render.cell, cfg).save_png(
                session_dir / "environment.png")
        initial_checks = meta.get("initial_checks", [])
        write_benchmark(
            session_dir,
            prompt=meta.get("prompt", ""),
            session=session_dir.name,
            mode=meta.get("mode", "terminal"),
            generation={
                "latency_s": meta.get("gen_latency_s"),
                "task_latency_s": meta.get("task_latency_s"),
                "env_attempts": meta.get("env_attempts"),
                "env_retries": meta.get("env_retries", 0),
                "compile_valid_first_try": meta.get("compile_valid_first_try"),
                "initial_verification_passed": all(c.get("passed") for c in initial_checks)
                if initial_checks else verify_passed,
                "initial_checks": initial_checks,
            },
            agent={"actions": 0, "success": False, "latency_s": None, "steps_budget": meta.get("steps_budget")},
            verification={"states": [], "states_collected": 0, "percentage_passed": 0.0},
        )
        write_benchmark(
            session_dir,
            tick={"action": action, "verify_passed": verify_passed,
                  "clauses_passed": sum(c["satisfied"] for c in clauses), "clauses_total": len(clauses)},
        )
    elif action == "(agent finished)":
        actions_log = session_dir / "actions.log"
        n_actions = len(actions_log.read_text().splitlines()) if actions_log.exists() else 0
        agent_start = float(os.environ.get("AGENT_START", "0"))
        agent_latency = round(time.time() - agent_start, 1) if agent_start else None
        write_benchmark(
            session_dir,
            tick={"action": action, "verify_passed": verify_passed,
                  "clauses_passed": sum(c["satisfied"] for c in clauses), "clauses_total": len(clauses)},
            agent={"actions": n_actions, "success": verify_passed, "latency_s": agent_latency},
        )
    else:
        write_benchmark(
            session_dir,
            tick={"action": action, "verify_passed": verify_passed,
                  "clauses_passed": sum(c["satisfied"] for c in clauses), "clauses_total": len(clauses)},
        )


# The LLM policy, driven by the mcp-agent library. It only calls the deterministic tools,
# so every state change is grounded and the verifier scores the result.
class Agent:
    def __init__(self, model: str, max_tokens: int = 1500) -> None:
        self.model = model
        self.max_tokens = max_tokens

    def run(self, db_path: str | os.PathLike, steps: int, objective: str | None = None) -> bool:
        return asyncio.run(self.drive(str(db_path), steps, objective))

    async def drive(self, db_path: str, steps: int, objective: str | None) -> bool:
        if objective is None:
            objective = self.read_meta(db_path, "success_when", "the objective")
        server_env = {**os.environ, "WORLD_DB": db_path, "PYTHONPATH": str(repo)}
        
        # Log state of the world live
        if actions_log := os.environ.get("ACTIONS_LOG"):
            server_env["ACTIONS_LOG"] = actions_log
        
        settings = Settings(
            execution_engine="asyncio",
            anthropic=AnthropicSettings(api_key=os.environ.get("ANTHROPIC_API_KEY"),
                                        default_model=self.model),
            mcp=MCPSettings(servers={"worldgen": MCPServerSettings(
                transport="stdio", command=sys.executable,
                args=["-m", "awm.core.server"], cwd=str(repo), env=server_env)}),
        )
        app = MCPApp(name="worldgen_agent", settings=settings)
        async with app.run():
            agent = MCPAgent(name="explorer", instruction=AGENT_SYSTEM, server_names=["worldgen"])
            async with agent:
                policy = await agent.attach_llm(AnthropicAugmentedLLM)
                await policy.generate_str(
                    message=AGENT_USER.format(objective=objective),
                    request_params=RequestParams(model=self.model, maxTokens=self.max_tokens,
                                                 max_iterations=steps, use_history=True))
        return bool(self.read_meta(db_path, "success", False))

    # Execute sql command
    @staticmethod
    def read_meta(db_path: str, key: str, default):
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
            return json.loads(row["value"]) if row else default
        finally:
            conn.close()


def run_terminal(cfg: DictConfig) -> None:
    args = argparse.ArgumentParser(add_help=False)
    args.add_argument("prompt", nargs="?", default=None)
    args.add_argument("--name", default=None)
    args.add_argument("--steps", type=int, default=None)
    args = args.parse_known_args()[0]

    prompt = args.prompt or input("Prompt: ").strip()
    if not prompt:
        raise SystemExit("no prompt given")
    steps = args.steps or cfg.agent.steps

    slug = re.sub(r"[^a-z0-9]+", "_", prompt.lower()).strip("_")[:40] or "run"
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_dir = (Path(cfg.paths.logs) / args.name if args.name
               else Path(cfg.paths.logs) / f"{ts}_{slug}")
    run_dir.mkdir(parents=True, exist_ok=True)
    db_path = run_dir / "world.db"
    log_path = run_dir / "run.log"
    actions_log = run_dir / "actions.log"

    engine = Engine(db_path, cfg)
    generator = Generator(
        Compiler(cfg.models.compile, cfg.llm.compile_max_tokens, cfg.llm.retries),
        engine.verifier, engine.world, cfg.generation.task_attempts, cfg.generation.env_attempts,
    )

    t0 = time.time()
    task = generator.synthesize_task(prompt)
    t1 = time.time()
    spec, checks = generator.compile_world(prompt, task, cfg.generation.seed)
    t2 = time.time()
    engine.world.instantiate(spec)
    env_attempts = spec["seed"] - cfg.generation.seed + 1
    os.environ["SESSION_META"] = json.dumps({
        "prompt": prompt, "mode": "terminal", "steps_budget": steps,
        "task_latency_s": round(t1 - t0, 1),
        "gen_latency_s": round(t2 - t1, 1),
        "env_attempts": env_attempts,
        "env_retries": env_attempts - 1,
        "compile_valid_first_try": env_attempts == 1,
        "initial_checks": [{"name": n, "passed": ok, "message": m} for n, ok, m in checks],
    })

    log_path.write_text("")
    log_tick(log_path, engine, "(world generated)", cfg)
    actions_log.write_text("")

    render_cmd = f"cd {repo} && export WORLD_DB={db_path} PYTHONPATH={repo} && {sys.executable} -m awm.core.render"
    render_env = {**os.environ, "WORLD_DB": str(db_path), "PYTHONPATH": str(repo)}
    if sys.platform == "darwin":
        subprocess.Popen(["osascript", "-e", f'tell application "Terminal" to do script "{render_cmd}"'])
    else:
        subprocess.Popen([sys.executable, "-m", "awm.core.render"], cwd=str(repo), env=render_env,
                         start_new_session=True)

    os.environ["AGENT_START"] = str(time.time())
    agent_env = {**os.environ, "WORLD_DB": str(db_path), "ACTIONS_LOG": str(actions_log),
                 "AWM_AGENT_ONLY": "1", "AWM_STEPS": str(steps), "PYTHONPATH": str(repo)}
    proc = subprocess.Popen([sys.executable, "-m", "awm.core.agent"], cwd=str(repo), env=agent_env)

    seen = 0
    while proc.poll() is None:
        time.sleep(0.2)
        if actions_log.exists():
            lines = actions_log.read_text().splitlines()
            while seen < len(lines):
                log_tick(log_path, engine, lines[seen], cfg)
                seen += 1
        if engine.success():
            proc.terminate()
            break

    for line in actions_log.read_text().splitlines()[seen:]:
        log_tick(log_path, engine, line, cfg)
    proc.wait()
    log_tick(log_path, engine, "(agent finished)", cfg)


@hydra.main(version_base=None, config_path="../conf", config_name="config")
def main(cfg: DictConfig) -> None:
    if os.environ.get("AWM_AGENT_ONLY"):
        db = os.environ["WORLD_DB"]
        steps = int(os.environ.get("AWM_STEPS", cfg.agent.steps))
        engine = Engine(db, cfg)
        Agent(cfg.models.agent, cfg.agent.max_tokens).run(db, steps, engine.objective())
        return
    if cfg.mode == "terminal":
        run_terminal(cfg)
        return
    db = cfg.paths.runtime_db
    engine = Engine(db, cfg)
    Agent(cfg.models.agent, cfg.agent.max_tokens).run(db, cfg.agent.steps, engine.objective())


if __name__ == "__main__":
    main()
