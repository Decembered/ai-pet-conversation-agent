"""SQLite persistence for SLAI Pet's initial state vertical slice."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .models import PetState

SCHEMA_SQL = """
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
"""


class PetStateRepository:
    """Small repository with explicit transactions and no framework coupling."""

    def __init__(self, database_path: str | Path = "data/pet.db") -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """Commit or roll back a transaction and always release the file handle."""

        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(SCHEMA_SQL)

    def get_state(self, user_id: str) -> PetState | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM pet_state WHERE user_id = ?", (user_id,)
            ).fetchone()
        return PetState.from_row(row) if row else None

    def save_state(self, state: PetState) -> None:
        state.normalize()
        values = self._state_values(state)
        with self._connection() as connection:
            self._upsert_state(connection, values)

    def get_event_by_request(self, request_id: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM pet_events WHERE request_id = ?", (request_id,)
            ).fetchone()
        if not row:
            return None
        return {
            "event_id": row["event_id"],
            "request_id": row["request_id"],
            "user_id": row["user_id"],
            "event_type": row["event_type"],
            "payload": json.loads(row["payload_json"]),
            "created_at": row["created_at"],
        }

    def save_state_with_event(
        self,
        state: PetState,
        *,
        event_id: str,
        request_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        """Atomically persist state and its corresponding audit event."""

        state.normalize()
        values = self._state_values(state)
        with self._connection() as connection:
            self._upsert_state(connection, values)
            connection.execute(
                """
                INSERT INTO pet_events (
                    event_id, request_id, user_id, event_type,
                    payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    request_id,
                    state.user_id,
                    event_type,
                    json.dumps(payload, ensure_ascii=False),
                    state.last_updated_at.isoformat(),
                ),
            )

    @staticmethod
    def _state_values(state: PetState) -> tuple[Any, ...]:
        return (
            state.user_id,
            state.hunger,
            state.energy,
            state.health,
            state.mood,
            state.cleanliness,
            state.intimacy,
            state.location,
            state.activity,
            state.level,
            state.experience,
            state.maturity,
            state.last_updated_at.isoformat(),
        )

    @staticmethod
    def _upsert_state(connection: sqlite3.Connection, values: tuple[Any, ...]) -> None:
        connection.execute(
            """
            INSERT INTO pet_state (
                user_id, hunger, energy, health, mood, cleanliness,
                intimacy, location, activity, level, experience,
                maturity, last_updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                hunger = excluded.hunger,
                energy = excluded.energy,
                health = excluded.health,
                mood = excluded.mood,
                cleanliness = excluded.cleanliness,
                intimacy = excluded.intimacy,
                location = excluded.location,
                activity = excluded.activity,
                level = excluded.level,
                experience = excluded.experience,
                maturity = excluded.maturity,
                last_updated_at = excluded.last_updated_at
            """,
            values,
        )
