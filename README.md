# World Gen: Verifiable 2D world generation with queryable game states

We turn text prompts into code-grounded 2D games where the world state and objects are stored in a deterministic database. All agent actions and success checks are executed as "tool calls" (i.e. queries) to this database.

The primary goal of this project is to demonstrate that **AI generation can be grounded into tangible, stateful objects that code can verify**. We demonstrate that a fully grounded, verifiable world can be generated in **tens of seconds**, meaning we can meaningfully scale to "infinite" worlds that generate in real time.

See [Architecture Overview](#architecture-overview) to understand how it works.


|                                                                               |                                                                       |                                                              |
| ----------------------------------------------------------------------------- | --------------------------------------------------------------------- | ------------------------------------------------------------ |
| *"a wizard arrives at the dungeon and locks the golden key inside the chest"* | *"an astronaut docks the ship and sets the green gem on the console"* | *"an explorer unlocks the ancient door with the red key"*    |
| *"a scientist pulls the lever to power up the reactor"*                       | *"a pirate digs the gold coin out of the sand"*                       | *"a gardener carries the watering can to the wilting plant"* |
| *"a frog hops over to drop the star onto the mossy rock"*                     | *"a knight seals the red gem inside the treasure crate"*              | *"a witch tosses the mushroom into the bubbling cauldron"*   |


---



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

---



# Getting Started

1. Install once

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-...
```

1. Pick one of the two options below

**Option A: Terminal**

```bash
# Run generation
python -m awm.core.agent

# or pass the prompt directly to the command line
python -m awm.core.agent "get the can onto the table"
```

**Option B: frontend interface** (Recommended)

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

1. Open `run.log` to inspect the world state over time

```text
2026-06-27T19:54:34+00:00
- agent action: move up
- world state:
  { "observe": { ... }, "get_objective": "...", "get_success": false }
```

---



# Architecture Overview

![Architecture](artifacts/architecture-diagram.png)

World Gen turns text prompts into playable 2D games where the entire world state is tracked in a database. This allows code to mathematically prove the game is solvable before an agent ever takes an action.

WorldGen consists of three parts:

**Stochastic World Generation**: This module turns natural language prompts into a complete world specification (objects, ). It excels at what LLMs do best: formulating the semantics, creative themes, and aesthetic layout of the world based on user intent.

**World state stored in queryable database**: This module takes the generator's output and writes it into a local SQLite database. It serves as the single, absolute source of truth where all entities, rules, and world primitives are stored as rigid relational rows.

**Deterministic Verifier**: This module runs a traditional graph-search algorithm (BFS) directly over the database rows. By checking the layout against the objective predicates, it mathematically proves with 100% certainty whether the generated level is beatable before the runtime engine even starts.

---

# Building Blocks

A world is made of 3 primitives that are built on top of each other like legos. This grounds each generation process into checkable steps.

## Stateful objects

Instead of generating everything from scratch, we explicitly ground generation into explicit **object** and **action** primitives, outlined below.

**Object primitives** are entities in the game: rocks, placeable keys, agents. We have an existing catalog of 2D object assets that is searched first. If not found, the 2D assets will be generated by calude.


|                                          |                                   |                                             |                                          |                                                                      |
| ---------------------------------------- | --------------------------------- | ------------------------------------------- | ---------------------------------------- | -------------------------------------------------------------------- |
|                                          |                                   |                                             |                                          |                                                                      |
| `holder`: an object that can carry items | walkable tile terrain to stand on | `pickable`: an object that can be picked up | `openable`: an object that can be opened | `container`: a container object which other objects can be placed in |


Each object has a state. That is, a key can have the `pickable` state and a wall has a `blocking` state (becuase the agent cannot walk through a wall). The 

**Action primitives** are 

## World state represented as a Database

The world state is stored in an **SQLite** Database. An example is below.

The current state can be queried through SQL queries. 

```python
{
  "grid": {"w": 14, "h": 10},
  "walls": {(0, 0), (0, 1), (1, 0), ...},          # non-walkable cells
  "entities": {
    "agent":      {"type": "agent", "components": ["transform", "holder"],
                   "sprite": "awm/assets/objects/adventurer.png"},
    "golden_key": {"type": "key",   "components": ["transform", "pickable"],
                   "sprite": "awm/assets/objects/key.png"},
    "chest":      {"type": "chest", "components": ["transform", "container", "openable", "blocking"],
                   "sprite": "awm/runtime/sprites/gen_entity_chest.png"},
  },
  "pos":     {"agent": (2, 5), "golden_key": (3, 2), "chest": (10, 5)},
  "flags":   {"agent": {}, "golden_key": {"is_held": False}, "chest": {"is_open": False}},
  "holding": {"agent": None},
  "rules": [
    {"check": "inside",   "args": ["golden_key", "chest"]},
    {"check": "not_open", "args": ["chest"]},
  ],
}
```



## Tool-based interaction with world

The agent interacts with the world through a fixed set of queries the database only:

1. `move`
2. `pick`
3. `place`
4. `toggle`



## Deterministic Verifier

### Verifying world validity

We can check if the world is solvable via test cases. If the world passes all test cases, then its valid. The test cases are as follows:

1. **Is the objective reachable?**: Can the agent navigate to the target destination and is the goal state possible?
2. **Are all entities legally placed?** Every entity sits inside the grid bounds, not on a wall tile, and no two entities occupy the same cell.
3. **Is the world non-trivial?** The win condition must be false at the start. A world where the rules are already satisfied at spawn is rejected — there has to be something left to solve.
4. **Is the rule set well-formed?** The rules generated by the LLM must already exist in the fixed set of rules. If it fails, then the output was hallucinated.

### Checking for game success

We can check if the agent reached a success state with a tool call

```python
# Example: The key must be in the chest AND the chest must be closed
state = State(snap, verifier)
state.inside("golden_key", "chest") and state.not_open("chest")
```

---



# Architecture Deep Dive

```text
awm/
├── api.py                  # talks to the frontend
├── conf/config.yaml             
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



### World State Generator

The LLM's role is to design the task. 

**Stage 1: Generate the task list** 
The ordered sub-goals the world must support.

```json
{
    "task_id": "seal_gem_in_chest",
    "difficulty": "medium",
    "task_description": "A gem rests in the dungeon vault. Pick it up, carry it to the treasure chest, place it inside, and close the lid so it is sealed away.",
    "required_entities": ["agent", "goal", "container"],
    "required_tiles": ["floor", "lava"],
    "objective_summary": "the gem is inside the chest and the chest is closed"
  }
```

**Stage 2: Compile the world specification**
The procedural generator will consume this to diversify the world chunk-by-chunk.

```json
{
    "chunk_size": 6,
    "grid": [["entrance", "corridor"],
             ["vault",    "lava_moat"]],
    "chunks": {
      "entrance": {
        "tile": "stone", "walkable": true,
        "entities": [
          {"id": "agent", "type": "agent", "components": ["transform", "holder"], "sprite": "wizard"}
        ]
      },
      ...
    },
    "rules": [
      {"check": "inside",   "args": ["gem", "chest"]},
      {"check": "not_open", "args": ["chest"]}
    ]
  }
```

### Database design
The SQLite database is formed from the output of the World generator.

### Tool Layer

FastMCP exposes tool calls like `observe`, `move`, `pick`, `place`, `toggle` that read/write the SQLite database. The agent can only change the world through these tools.

### Verifier

Plain Python rule functions over world state. Every rule must pass — `verifier.verify(snap)` returns true or false.

---



# Results

**TLDR: 100% of generated worlds are verified solvable before use, by code**
Measured with the 9 prompt benchmarks with Opus-4.8 for compiling the world spec and Sonnet-4.6 for mcp tool calls.


| metric                    | value                                                                                              |
| ------------------------- | -------------------------------------------------------------------------------------------------- |
| worlds compiled           | 5 of 5 grounded and solvable                                                                       |
| solvability               | guaranteed, proven by BFS before use, not estimated                                                |
| check coverage            | all rule checks exercised across the prompts                                                       |
| generation latency        | about 10 to 18 s per world (2 LLM calls)                                                           |
| agent success (our suite) | 1.0 on simple and compositional worlds (apple onto counter in 12 tool calls, can onto table in 10) |
| sprite grounding          | 21 of 21 entities used a real labeled asset the model chose                                        |




## Baseline comparison


| System                                                              | Domain    | Success check | Solvable   | Gen cost  |
| ------------------------------------------------------------------- | --------- | ------------- | ---------- | --------- |
| World-Gen (this work)                                               | 2D grid   | fixed code    | guaranteed | ~14 s     |
| Agent World Model / EnvScaler [↗](https://arxiv.org/abs/2601.05808) | web       | LLM judge     | no         | n/r       |
| OMNI-EPIC [↗](https://arxiv.org/abs/2405.15568)                     | code sim  | LLM code      | partial    | minutes   |
| GenSim [↗](https://arxiv.org/abs/2310.01361)                        | robotics  | LLM code      | partial    | minutes   |
| ProcTHOR [↗](https://arxiv.org/abs/2206.06994)                      | 3D scenes | engine        | n/a        | seconds   |
| Genie 3                                                             | pixels    | VLM           | no         | real-time |
| DIAMOND [↗](https://arxiv.org/abs/2405.12399)                       | neural WM | none          | no         | GPU       |


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

