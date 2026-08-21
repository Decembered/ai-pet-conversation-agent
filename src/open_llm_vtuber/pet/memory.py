"""SQLite-backed long-term facts for cross-session pet memory."""

from dataclasses import dataclass
from pathlib import Path
import re
import sqlite3
import time


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    """A durable fact that can be recalled in a later session."""

    memory_id: int
    pet_id: str
    key: str
    value: str
    importance: float
    created_at: float


class MemoryStore:
    """Persist and retrieve exact facts without requiring an external vector DB."""

    def __init__(self, db_path: str | Path = Path("data/pet.sqlite3")) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS pet_memories (
                    memory_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pet_id TEXT NOT NULL,
                    memory_key TEXT NOT NULL,
                    memory_value TEXT NOT NULL,
                    importance REAL NOT NULL,
                    created_at REAL NOT NULL,
                    UNIQUE(pet_id, memory_key)
                )
                """
            )

    def remember(
        self, pet_id: str, key: str, value: str, importance: float = 0.5
    ) -> MemoryRecord:
        """Upsert one fact and return the persisted record."""
        safe_key = key.strip()
        safe_value = value.strip()
        if not safe_key or not safe_value:
            raise ValueError("Memory key and value cannot be empty")
        now = time.time()
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO pet_memories(pet_id, memory_key, memory_value, importance, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(pet_id, memory_key) DO UPDATE SET
                memory_value=excluded.memory_value, importance=excluded.importance
                """,
                (pet_id, safe_key, safe_value, max(0.0, min(1.0, importance)), now),
            )
            row = connection.execute(
                "SELECT memory_id, pet_id, memory_key, memory_value, importance, created_at "
                "FROM pet_memories WHERE pet_id=? AND memory_key=?",
                (pet_id, safe_key),
            ).fetchone()
        if row is None:
            raise RuntimeError("Memory was not persisted")
        return self._row_to_record(row)

    def recall(self, pet_id: str, query: str, limit: int = 5) -> list[MemoryRecord]:
        """Return facts ranked by simple token overlap and importance."""
        tokens = set(re.findall(r"[\w\u4e00-\u9fff]+", query.lower()))
        aliases = {
            "星座": "zodiac",
            "生日": "birthday",
            "名字": "name",
            "喜欢": "preference",
        }
        tokens.update(alias for token, alias in aliases.items() if token in query)
        with sqlite3.connect(self.db_path) as connection:
            rows = connection.execute(
                "SELECT memory_id, pet_id, memory_key, memory_value, importance, created_at "
                "FROM pet_memories WHERE pet_id=?",
                (pet_id,),
            ).fetchall()
        scored = []
        for row in rows:
            record = self._row_to_record(row)
            haystack = f"{record.key} {record.value}".lower()
            overlap = sum(1 for token in tokens if token in haystack)
            if overlap or not tokens:
                scored.append((overlap, record.importance, record))
        scored.sort(
            key=lambda item: (item[0], item[1], item[2].created_at), reverse=True
        )
        return [item[2] for item in scored[: max(1, limit)]]

    @staticmethod
    def _row_to_record(row: tuple[object, ...]) -> MemoryRecord:
        return MemoryRecord(
            memory_id=int(row[0]),
            pet_id=str(row[1]),
            key=str(row[2]),
            value=str(row[3]),
            importance=float(row[4]),
            created_at=float(row[5]),
        )
