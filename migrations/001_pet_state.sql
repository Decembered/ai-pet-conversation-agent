CREATE TABLE IF NOT EXISTS pet_state (
    user_id TEXT PRIMARY KEY,
    hunger REAL NOT NULL,
    energy REAL NOT NULL,
    health REAL NOT NULL,
    mood REAL NOT NULL,
    cleanliness REAL NOT NULL,
    intimacy REAL NOT NULL,
    location TEXT NOT NULL,
    activity TEXT NOT NULL,
    level INTEGER NOT NULL,
    experience INTEGER NOT NULL,
    maturity REAL NOT NULL,
    last_updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pet_events (
    event_id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL UNIQUE,
    user_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pet_events_user_created
ON pet_events(user_id, created_at);
