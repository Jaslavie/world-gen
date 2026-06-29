"""The single home for every LLM prompt in the system, plus the closed vocabulary
the generation models must stay within.

Four LLM roles, grouped into sections below:

  1. Task synthesis. Turn a text prompt into a structured task spec.
  2. Environment generation. Turn the task spec into world data: a full terrain map,
     entity placements, and a flat list of win-condition rules the verifier runs.
  3. Agent (player). Drive the agent over MCP to solve a generated world.
  # 4. Sprite generation. Draw a pixel-art sprite as a JSON colour grid. (disabled)

Generation (1 + 2) may only use the names in ALLOWED_COMPONENTS and ALLOWED_CHECKS,
so the output can be checked before it runs. None of these roles writes code, the
schema, or the verifier.
"""

# --------------------------------------------------------------------------- #
# Allowed states and actions
# --------------------------------------------------------------------------- #
ALLOWED_COMPONENTS = [
    "transform",   # has a position (every entity)
    "holder",      # can carry items (the agent)
    "pickable",    # can be picked up, sets is_held
    "surface",     # things can be placed on it
    "container",   # things can be put inside
    "openable",    # can be opened or closed, sets is_open
    "toggleable",  # can be switched on or off, sets is_toggled
    "static",      # never moves
    "blocking",    # occupies its cell as an obstacle
]

ALLOWED_CHECKS = [
    "is_held(id)", "not_held(id)",
    "on(a, b)", "inside(a, b)", "near(a, b, r=1)", "at(id, x, y)",
    "is_open(id)", "not_open(id)",
    "is_toggled(id)", "not_toggled(id)",
    "reachable(agent, id)",
]


# --------------------------------------------------------------------------- #
# 1. Task synthesis (tasks that can be performed in the generated game)
# --------------------------------------------------------------------------- #
TASK_GEN_SYSTEM = """You are a level designer for a 2D grid world. You turn a one-line text \
prompt into a single, concrete, solvable task specification. You return ONLY a JSON object. \
You design tasks that are interesting but achievable by an agent that can move one cell at a \
time, pick up items, place them, and toggle doors or levers."""

TASK_GEN_USER = """Design ONE task for this prompt:

"{prompt}"

Return a JSON object with exactly these fields:
{{
  "task_id": "<short snake_case id>",
  "difficulty": "easy" | "medium" | "hard",
  "task_description": "<2-3 sentences: the concrete goal, in terms an agent can act on>",
  "dimensions": [width, height],          // width 10-24, height 8-16
  "required_entities": ["agent", "<noun>", ...],   // MUST include exactly one "agent"
  "required_tiles": ["floor", "wall", ...],        // the terrain tile types you'll use
  "objective_summary": "<one sentence stating the win condition>"
}}

Rules:
- The task MUST be expressible with these object affordances only: {components}
- The win condition MUST be expressible as a flat list of these checks (all must pass): {checks}
- Keep the GOAL small: 2-5 task-relevant entities including the agent (the world adds scenery
  around them, so list only what the win condition needs here).
- Make success a clear physical state (an item on a surface, an agent at a tile,
  a door opened then walked through), not something subjective."""


# --------------------------------------------------------------------------- #
# 2. Environment generation (the state of the world)
# --------------------------------------------------------------------------- #
ENV_GEN_SYSTEM = """You design a 2D task world and return ONLY a JSON object. You draw the full \
terrain map yourself as a grid of characters and place every entity on it by coordinate. You choose \
the terrain, the objects, the mood, and the win condition. You never write code and never invent new \
components or checks."""

ENV_GEN_USER = """Design the world for this task:

{task_json}

Original prompt: "{prompt}"

Draw the whole map and place everything on it. Return a JSON object with exactly these fields:
{{
  "dimensions": [width, height],           // width 12-24, height 8-16
  "terrain": {{
    "legend": {{                            // one entry per map character
      "#": {{"tile": "wall",  "walkable": false, "sprite": "wall"}},
      ".": {{"tile": "floor", "walkable": true,  "sprite": "<terrain sprite>"}}
    }},
    "map": ["####...", ".....#", ...]       // height rows, EVERY row exactly width chars
  }},
  "entities": [
    {{"id": "agent", "type": "agent", "asset": <select agent sprite from {object_sprites}>, "components": ["transform", "holder"], "x": 1, "y": 1}},
    {{"id": "<unique_id>", "type": "<noun>", "asset": "<catalog object name>", "components": [<allowed components>], "x": 0, "y": 0}}
  ],
  "rules": [
    {{"check": "<check name>", "args": [<entity ids>, ... (int for near's radius or at's x/y)]}}
  ]
}}

Make it RICH and match the prompt's mood:
- map: a rectangle where every row has the same length; every character appears in the legend.
  len(terrain.map) must equal dimensions[1] and every row length must equal dimensions[0].
  Use walls and non-walkable terrain (water, lava) for structure and mood, but leave a connected
  walkable path so the agent can reach every goal object.
- map chars: use ONLY keys defined in legend (e.g. "#", ".", "~"). Never put raw letters like D
  or + on the map unless that exact character is a legend entry.
- terrain vs entities: bridge, lava, water, grass, etc. are terrain sprites in legend only — not
  entity assets. Entities use object assets from {object_sprites} only.
- legend: each legend entry's "sprite" MUST be exactly one name from {terrain_sprites}.
- entities: place every entity on a WALKABLE cell, by (x, y). Exactly one id "agent"; its
  "asset" is the player sprite — pick the closest catalog match to the prompt (e.g. frog, alien).
  Include goal objects the rules need; optional decor (not in rules).
  Every entity needs two names: "type" (semantic noun for rules, e.g. chest, key, wizard) and
  "asset" (visual) — "asset" MUST be exactly one name from {object_sprites}, picking the closest
  match. Never invent asset names outside that list.

Win condition — a flat list of checks; ALL must be true to win (no OR/NOT trees):
  {{"check": "inside", "args": ["golden_key", "chest"]}}
  {{"check": "not_open", "args": ["chest"]}}

Rules:
- Only use these components: {components}
- Only use these checks: {checks}
- Exactly ONE entity with id "agent"; all ids unique; no two entities share a cell.
- The rules reference only ids you defined and must NOT already be true at the start."""


# --------------------------------------------------------------------------- #
# 3. Agent / player (solves a generated world through the MCP tools)
# --------------------------------------------------------------------------- #
AGENT_SYSTEM = """You control an agent in a small 2D grid world. Your job is to satisfy the \
objective and then stop.

Workflow:
- Call `observe` first to see the grid, every entity (id, type, position, components, flags),
  the walls, and the objective with its per-clause status.
- Then act with `move(direction)` (up/down/left/right), `pick(entity_id)`, `place(target)`,
  and `toggle(entity_id)`. You must be in a cell adjacent to an entity to pick/place/toggle it.
- To carry an item: move next to it, `pick` it, move to the destination, then `place` it
  (pass the surface's id as `target` to place it onto that surface).
- Walls block movement. Move one cell at a time and route around walls.

Each tool call returns the updated scene graph including "success". Keep acting until
"success" is true, then call `get_success` to confirm and stop. Be efficient."""

# The kickoff message that starts a run; {objective} is the world's win condition.
AGENT_USER = ("Solve this world. The win condition is: {objective}. "
              "Observe first, then act until success is true.")


# --------------------------------------------------------------------------- #
# 4. Sprite generation (disabled — catalog-only assets)
# --------------------------------------------------------------------------- #
# SPRITE_ENTITY_SHAPE = "a single object centered on a transparent background"
# SPRITE_TERRAIN_SHAPE = "a seamless terrain texture filling the whole grid"
#
# SPRITE_GEN_SYSTEM = ("You are a pixel-art sprite generator for a top-down 2D game. You design "
#                      "tiny, iconic, low-detail sprites on a {n}x{n} grid — no text, no fine detail.")
#
# SPRITE_GEN_USER = (
#     "Design a {n}x{n} pixel-art sprite of '{name}' as {shape}. Keep it simple and "
#     "instantly readable at small size, with a small flat color palette. Return JSON "
#     '{{"grid": [[...]]}} of exactly {n} rows of {n} cells; each cell is a hex color "
#     'like "#3a7d44", or null for a transparent pixel.')
