# Brainstorming and thoughts doc

Goal:

> Create an agent harness (i.e. a system that can accept the text prompt of any llm agent) that can create a stateful 2D world that we can query objects/objectives from. 

You can read in the primary "ReadMe" for more insight here.

The core contribution should include:

- stateful objects: physics grounded objects in the generated environment that we can query from
- autonomous agent: an autonomous agent powered by claude should be able to navigate around this environment
- communication through UI: a lightweight user interface (ex: as a small modal) should communicate what the agent is interacting with and the current states of the game. This is important to expose the reasoning of the agent and to demonstrate the stateful design

Out of scope:

- High fidelity physics (i.e. depth maps, ensemble models to finetune all aspects of physics)

## Logistics

- Model: GPT 5 (~$57 per run baseline from the paper)

## Architecture

As mentioned in the read me, we will implement the Agent World paper. Conceptually, we are using MCP agents to generate POMDP components like state, observations, actions etc. These are all stored inside a structured database (SQLite) and accessed via determinsitic function calls.

The og paper focuses on web apps. The main deviations of our approach are:

- The SQL database will be designed around spatial dynamics instead of web app data (below is a non exhaustive version of this)

```
-- 1. The Static Map Layer
CREATE TABLE map_tiles (
    x INTEGER,
    y INTEGER,
    tile_type TEXT, -- 'wall', 'floor', 'water', 'door', etc.
    is_walkable BOOLEAN,
    svg IMG (or path to image),
    PRIMARY KEY (x, y)
);

-- 2. The Dynamic Entity Layer
CREATE TABLE entities (
    entity_id TEXT PRIMARY KEY,
    entity_type TEXT, -- 'agent', 'enemy', 'item'
    x INTEGER,
    y INTEGER,
    is_blocking BOOLEAN, # i.e. can we walk past this or is it a barrier
    svg IMG (or path to image),
    FOREIGN KEY(x, y) REFERENCES map_tiles(x, y)
);
```

- Deterministic verifier: the og paper uses LLM as a judge, likely due to the very complex and user-orientated design of web apps that it targets. However in video games, there are concrete modes that if broken, breaks the physics and sense of the video game. Thus, we replace the verifier with a deterministic one similar to test cases in code

We make the following assumption, that all games must include:

- current world state
- objective (goal)
- constraints
- termination conditions
- reward/success checks

The main architectural components are. Observe we use terms like "S", "A", "O" which map to the components of POMDP (ex: S = state)

1. **Task synthesis** - This serves as an intermediary layer and bridge btwn the prompt and SQL database generator. Specifically, it generates a list of "functional requirements" on different levels of difficulty and necessary database elements.

```json
// Version 1: more expansive and defines all game states
{
  "task_id": "defeat_boss_after_key",
  "difficulty": "medium",
  "world_seed": 48291,
  "objective": "Obtain the silver key, unlock the dungeon gate, and defeat the dungeon boss.",
  "subgoals": [
    {
      "id": "obtain_key",
      "condition": {
        "inventory_contains": "silver_key"
      }
    },
    {
      "id": "unlock_gate",
      "condition": {
        "object_state": {
          "dungeon_gate": "open"
        }
      }
    },
    {
      "id": "defeat_boss",
      "condition": {
        "enemy_alive": {
          "boss_01": false
        }
      }
    }
  ],

  "allowed_actions": [
    "move_left",
    "move_right",
    "jump",
    "attack",
    "interact",
    "use_item"
  ],

  "success": {
    "all_subgoals_completed": true
  },

  "failure": {
    "player_dead": true,
    "step_limit": 1000
  }
}
// Verion 2: More concise and allows LLM to work its magic based on task description
{
    "task_id": "game_task_002",
    "difficulty": "Medium",
    "task_description": "Locate the 'iron_lever' entity on the grid. Move adjacent to it and execute the interact tool to switch its state to active=True. This action drops the 'bridge_gate' at (4, 8) from impassable to walkable. Navigate across the gate to reach the safe zone at (4, 10).",
    "environment_requirements": {
      "dimensions": [12, 12],
      "required_entities": ["player", "iron_lever"],
      "required_tiles": ["floor", "wall", "bridge_gate"]
    }
  },
```

1. **SQLite database generator (S)** - Prompt tuned LLM generates SQLite schema that represents each element of the env state + small verifier similar to the final verifier that verifies the logical consistency of the state and prompt retries if necessary

- The generation is broken up into two seconds for fast failing: (1) Generate a single object(s) for each database (ex: a single tile object is generated for the tiles db) (2) If step 1 passes the verifier, then genreate the rest of the database

> "The LLM analyzes preconditions for each task and creates records satisfying these constraints, including variation data needed for robust execution."

- Initialize initial state of the environment based on the verified database schema

1. **MCP spatial tools definition** (A)-- execute queries (read/write) in the database to perform actions.

- Importantly, this ensures that the agent can only use deterministic tools to interact with the db and it will never lead to unintended actions that break the entire DB schema as LLMs might

> "MCP (Anthropic, 2024) interface layer that exposes a toolset in Python, which defines the action space AEi as tool calls and the observation space OEi as tool responses"

1. **Python script defining tool exection (T)** -- LLM generates a lightweight python script calls each MCP tool to accomplish a task. This is a python wrapper that communicates with the backend by calling the MCP tools (ex: `move_direction`)
2. **Test suites verifier** -- The verification engine executes an automated script at the end of the agent's turn limit:

```python
def verify_task_success(db_connection):
    # Task requirement: Pick up the key and stand on the exit tile (10, 10)
    agent_pos = db_connection.execute("SELECT x, y FROM entities WHERE entity_type = 'agent'").fetchone()
    has_key = db_connection.execute("SELECT count(*) FROM inventory WHERE item_id = 'blue_key'").fetchone()[0]
    
    # Deterministic evaluation assert rules
    if agent_pos == (10, 10) and has_key == 1:
        return "Completed"
    elif has_key == 1:
        return "Partially Completed"
    else:
        return "Failed"
```

**Flag: the original paper uses a combination of LLM as a judge and code verificaitons. Here, we focus on deterministic code verifications first**

> However, because our environments are fully synthetic, verification can occasionally be affected by environment imperfections, such as incomplete state updates, unexpected execution failures, or infrastructurerelated issues (e.g., timeouts). To improve reward robustness, the ultimate decision is made by an LLM-as-aJudge [along with code verifications]

Importantly, they state a core assumption is

> A natural question arises: why not rely entirely on codedriven verification? While appealing, this approach assumes that **task success is perfectly specifiable and reliably observable from state alone**.

While this is not true in web applicaitons, this is absolutely true in video games and 2D environments! Success is completlely determined from the state of the game. 

Thus, we needn't spend inference on an LLM-as-a-judge, at least for the current scope of our MVP generation. Instead, we can have simple checks on win conditions (ex: `is_agent_at_coordinate_2_4( )`)

