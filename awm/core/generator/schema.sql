-- Fixed world schema. The LLM creates data that fills in these tables

-- world-level configurations/metadata: grid size, seed, tick, success flags
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL            -- JSON-encoded scalar/object
);

-- one row per terrain item
CREATE TABLE IF NOT EXISTS map_tiles (
    x         INTEGER NOT NULL,
    y         INTEGER NOT NULL,
    tile_type TEXT    NOT NULL,    -- 'floor', 'wall', 'water', 'door', ...
    walkable  INTEGER NOT NULL,    -- 0 / 1
    sprite    TEXT,                -- relative image path for this tile (NULL -> colour fallback)
    PRIMARY KEY (x, y)
);

CREATE TABLE IF NOT EXISTS entities (
    entity_id   TEXT PRIMARY KEY,
    entity_type TEXT    NOT NULL,  -- 'agent', 'key', 'table', 'door', ...
    x           INTEGER NOT NULL,
    y           INTEGER NOT NULL,
    components  TEXT    NOT NULL,  -- JSON array, e.g. ["transform","pickable"]
    blocking    INTEGER NOT NULL DEFAULT 0,
    sprite      TEXT               -- relative image path for this entity (the per-entity asset)
);

-- States that each entity can have
CREATE TABLE IF NOT EXISTS entity_state (
    entity_id TEXT    NOT NULL,
    flag      TEXT    NOT NULL,    -- 'is_held', 'is_open', 'is_toggled', 'resting'
    value     INTEGER NOT NULL,    -- 0 / 1
    PRIMARY KEY (entity_id, flag),
    FOREIGN KEY (entity_id) REFERENCES entities(entity_id)
);

-- what each agent is currently carrying (one item at a time)
CREATE TABLE IF NOT EXISTS holding (
    agent_id TEXT PRIMARY KEY,
    item_id  TEXT,                 -- nullable: the carried entity_id, or NULL
    FOREIGN KEY (agent_id) REFERENCES entities(entity_id)
);

-- flat list of win-condition rule checks; verifier runs all (logical AND)
CREATE TABLE IF NOT EXISTS objective (
    id    INTEGER PRIMARY KEY CHECK (id = 1),  -- singleton row
    rules TEXT NOT NULL            -- JSON array: [{"check": "inside", "args": ["key", "chest"]}, ...]
);

-- log of (action, success) each time the agent takes an action
CREATE TABLE IF NOT EXISTS trajectory (
    tick    INTEGER NOT NULL,     
    action  TEXT    NOT NULL,     -- JSON action dict
    success INTEGER NOT NULL      -- 0 / 1 success AFTER this action
);
