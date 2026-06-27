# World Gen: Verifiable 2d world generation with queryable game states

We turn text prompts into code-grounded 2D games where the world state and objects are stored in a database and the agent interacts with the world via deterministic queries ("tool calls") to the database.

The primary goal of this project is to demonstrate that **AI generation can be grounded into tangible, stateful objects that code can verify**.

We demonstrate that a fully grounded, verifiable world can be generated in **tens of seconds**, meaning we can meaningfully scale to "infinite" worlds that generate in real time.


|                                                                               |                                                                       |                                                              |
| ----------------------------------------------------------------------------- | --------------------------------------------------------------------- | ------------------------------------------------------------ |
| *"a wizard arrives at the dungeon and locks the golden key inside the chest"* | *"an astronaut docks the ship and sets the green gem on the console"* | *"an explorer unlocks the ancient door with the red key"*    |
| *"a scientist pulls the lever to power up the reactor"*                       | *"a pirate digs the gold coin out of the sand"*                       | *"a gardener carries the watering can to the wilting plant"* |
| *"a frog hops over to drop the star onto the mossy rock"*                     | *"a knight seals the red gem inside the treasure crate"*              | *"a witch tosses the mushroom into the bubbling cauldron"*   |


![Architecture](/artifacts/architecture-diagram.png)

# Table of Contents

- [Getting Started](#getting-started)
- [Overview: why verifiable worlds?](#overview-why-verifiable-worlds)
- [Architecture Overview](#architecture-overview)
  - [Building Blocks](#building-blocks)
    - [Primitives: grounding objects](#primitives-grounding-objects)
    - [World state stored in a Database](#world-state-stored-in-a-database)
    - [Tool calls for verification](#tool-calls-for-verification)
  - [Architecture](#architecture)
- [Results](#results)
  - [Baseline comparison](#baseline-comparison)
- [Next steps](#next-steps)
- [Acknowledgements](#acknowledgements)

# Getting Started

1. Install once

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-...
```

1. Pick one of the two options below

**Option A: Claude Code**

```bash
# Terminal 1
python -m awm.main "get the can onto the table"

# add --name to fully populate logs/<name>/ with the world, screenshots and trajectory
python -m awm.main "a maze: grab the key and reach the exit" --name maze --steps 100
```

```bash
# Terminal 2 (optional, live viewer)
python -m awm.core.render
```

**Option B: frontend interface**

```bash
# Terminal 1: backend (holds ANTHROPIC_API_KEY)
pip install fastapi "uvicorn[standard]"
python -m awm.api
```

```bash
# Terminal 2: frontend
cd frontend
pnpm install
pnpm dev
```

Open `http://localhost:5173`. Type a prompt, press Generate, then press Run agent.

---



# Overview: why verifiable worlds?

Neural world models like Genie make worlds that are visually realistic, but are stateless, so success can only be inferred from pixels. This makes it unrealistic for diverse task environment generation at scale.

This matters for training agents. To train one you need a large supply of diverse environments with rewards it can trust. A vision model reading frames is an unreliable reward signal.

Storing the world in a queryable database addresses this. Success is not inferred but verified via a row on the database. There is no gray area. 

Additionally, generation is observable, so a failure can be traced to the stage that produced it.

---



# Architecture Overview

```text
awm/
├── api.py                  # talks to the frontend
├── config.yaml             
├── assets/                 # default 2d sprites
└── core/                   
    ├── server.py               
    ├── render.py               # draws the world with pygame
    ├── agent.py                # agent calls tools to interact with db
    │
    ├── utils/                 
    │   └── llm.py              
    │
    ├── generator/              
    │   ├── generate_world.py   #   generates world state / sqlite db
    │   ├── prompts.py          
    │   ├── generate_layout.py  #   places things on the grid
    │   └── generate_assets.py  #   generates sprites
    │
    └── runtime/                
        ├── engine.py       
        ├── world.py        
        ├── tools.py        #   agent tools to interact with the db
        ├── verifier.py     #   verifies validity of world
        └── schema.sql      #   the shape of the world sate data
```



## Building Blocks

A world is made of 3 primitives that are built on top of each other like legos. This grounds each generation process into checkable steps.

### Stateful objects

Each "object" is mapped to a png and an **object type**, some examples are below.


|                                          |                                   |                                             |                                          |                                                                      |
| ---------------------------------------- | --------------------------------- | ------------------------------------------- | ---------------------------------------- | -------------------------------------------------------------------- |
|                                          |                                   |                                             |                                          |                                                                      |
| `holder`: an object that can carry items | walkable tile terrain to stand on | `pickable`: an object that can be picked up | `openable`: an object that can be opened | `container`: a container object which other objects can be placed in |


The model picks which labeled asset each object uses, so almost any prompt renders; anything off the catalog is generated on the fly as a pixel-art sprite by Claude, then cached.

`components` = `transform` `holder` `pickable` `surface` `container` `openable` `toggleable` `static` `blocking`

### World state stored in a Database

The chosen primitives are placed on a grid and written to SQLite: one queryable source of truth. The objective is a **predicate tree** (AND / OR / NOT over predicate leaves) the verifier reads. A snapshot at one tick:

```python
# Snapshot of world state at a period of time
{
  "grid": {"w": 14, "h": 10},
  "walls": {(0,0),(0,1),(0,2),(0,3),(0,4),(0,5),(0,6),(0,7),(0,8),(0,9),
            (1,0),(1,9),(2,0),(2,9),(3,0),(3,9),(4,0),(4,9),(5,0),(5,9),
            (6,0),(6,9),(7,0),(7,9),(8,0),(8,9),(9,0),(9,9),(10,0),(10,9),
            (11,0),(11,9),(12,0),(12,9),(13,0),(13,1),(13,2),(13,3),(13,4),
            (13,5),(13,6),(13,7),(13,8),(13,9)},
  "entities": {
    "agent":      {"type": "agent", "components": ["transform", "holder"],
                   "sprite": "awm/assets/objects/adventurer.png"},
    "golden_key": {"type": "key",   "components": ["transform", "pickable"],
                   "sprite": "awm/assets/objects/key.png"},
    "chest":      {"type": "chest", "components": ["transform", "container", "openable", "blocking"],
                   "sprite": "awm/runtime/sprites/gen_entity_chest.png"},
  },
  "pos":      {"agent": (2, 5), "golden_key": (3, 2), "chest": (10, 5)},
  "flags":    {"agent": {}, "golden_key": {"is_held": False}, "chest": {"is_open": False}},
  "holding":  {"agent": None},
  "objective": {"all": [{"pred": "inside", "args": ["golden_key", "chest"]},
                        {"not": {"pred": "is_open", "args": ["chest"]}}]},
}
```



### Tool calls for verification

The agent can only change the world through a fixed set of deterministic MCP tools; it can never reach past them or corrupt the schema. Each tool writes to SQLite, so every action is grounded and replayable.

`actions` = `move` `pick` `place` `toggle` (plus `observe` and `get_success` to read state)

---



## Architecture

The system strictly separates stochastic generation (i.e. via LLM) from deterministic generation (via functions):

### **Generator.**

A Claude call turns the prompt into world data.

- Stage 1: Generate the task list — the ordered sub-goals the world must support.
- Stage 2: Compile the spec and check for solvability. The state schema is verified against a predicate tree built from the task list, so all task dependencies hold.
- Stage 3: The SQLite database is formed from the output of stage 2.

1. **Tool layer.** The agent loop runs and uses a deterministic set of tool calls to interact with the environment (i.e. the SQLite schema).

- FastMCP exposes tool calls like `observe`, `move`, `pick`, `place`, `toggle`, and `get_success` that read/write the SQLite database. The agent can only change the world through these tools, so it can never reach past them or corrupt the schema.

1. **Verifier.** Plain Python over the world state. It evaluates the objective predicate tree and returns true or false.

---



# Results

**TLDR: 100% of generated worlds are verified solvable before use, by code**
Measured with the 9 prompt benchmarks with Opus-4.8 for compiling the world spec and Sonnet-4.6 for mcp tool calls.


| metric                    | value                                                                                              |
| ------------------------- | -------------------------------------------------------------------------------------------------- |
| worlds compiled           | 5 of 5 grounded and solvable                                                                       |
| solvability               | guaranteed, proven by BFS before use, not estimated                                                |
| objective coverage        | 6 of 6 predicates exercised across the prompts                                                     |
| generation latency        | about 10 to 18 s per world (2 LLM calls)                                                           |
| agent success (our suite) | 1.0 on simple and compositional worlds (apple onto counter in 12 tool calls, can onto table in 10) |
| sprite grounding          | 21 of 21 entities used a real labeled asset the model chose                                        |




## Baseline comparison


| System                                                              | Domain    | Success check | Solvable   | Gen cost  | Headline      |
| ------------------------------------------------------------------- | --------- | ------------- | ---------- | --------- | ------------- |
| World-Gen (this work)                                               | 2D grid   | fixed code    | guaranteed | ~14 s     | 5/5 solvable  |
| Agent World Model / EnvScaler [↗](https://arxiv.org/abs/2601.05808) | web       | LLM judge     | no         | n/r       | 191 envs      |
| OMNI-EPIC [↗](https://arxiv.org/abs/2405.15568)                     | code sim  | LLM code      | partial    | minutes   | open-ended    |
| GenSim [↗](https://arxiv.org/abs/2310.01361)                        | robotics  | LLM code      | partial    | minutes   | +25% transfer |
| ProcTHOR [↗](https://arxiv.org/abs/2206.06994)                      | 3D scenes | engine        | n/a        | seconds   | SR 65%        |
| Genie 3                                                             | pixels    | VLM           | no         | real-time | 720p/24fps    |
| DIAMOND [↗](https://arxiv.org/abs/2405.12399)                       | neural WM | none          | no         | GPU       | 1.46 HNS      |


---



# Next steps

Things I would do if I had more time

- **Infinite procedural generation**. We have demonstrated that generation can run fast. We can continuously generate new chunks of the world as the agent navigates by using the current world state as a prior.
- **Enhancing environment diversity**: This phase focuses on verifiability. There is room to create more diverse worlds with added procedural generation methods like optimized Perlin noise, etc.
- **3D.** The world spec is engine agnostic, so the same verifier could drive a 3D physics backend.

---



# Acknowledgements

- [Agent World Model](https://arxiv.org/pdf/2602.10090) for baseline architecture which I adapted into 2D games.
- [mcp-agent](https://github.com/lastmile-ai/mcp-agent) for MCP server. 
- Sprites from [Kenney](https://kenney.nl).

