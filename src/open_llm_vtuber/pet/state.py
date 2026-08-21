"""Persistent pet world state, actions and deterministic growth rules."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import sqlite3
import threading
import time


class PetAction(str, Enum):
    """Actions that can change the pet's world state."""

    FEED = "feed"
    PLAY = "play"
    BATHE = "bathe"
    REST = "rest"
    STUDY = "study"
    WORK = "work"
    ADVENTURE = "adventure"


@dataclass(frozen=True, slots=True)
class PetState:
    """A validated snapshot of the pet's current needs and growth."""

    pet_id: str
    hunger: float
    energy: float
    health: float
    mood: float
    intimacy: float
    experience: int
    level: int
    maturity: float
    last_updated_at: float


@dataclass(frozen=True, slots=True)
class ActionResult:
    """Return the action that happened and the resulting state."""

    action: PetAction
    message: str
    state: PetState
    experience_gained: int


class _PetStateStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS pet_state (
                    pet_id TEXT PRIMARY KEY,
                    hunger REAL NOT NULL,
                    energy REAL NOT NULL,
                    health REAL NOT NULL,
                    mood REAL NOT NULL,
                    intimacy REAL NOT NULL,
                    experience INTEGER NOT NULL,
                    level INTEGER NOT NULL,
                    maturity REAL NOT NULL,
                    last_updated_at REAL NOT NULL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, timeout=10)

    def ensure(self, pet_id: str) -> PetState:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM pet_state WHERE pet_id = ?", (pet_id,)
            ).fetchone()
            if row is None:
                now = time.time()
                connection.execute(
                    "INSERT INTO pet_state VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (pet_id, 20.0, 80.0, 100.0, 75.0, 10.0, 0, 1, 0.0, now),
                )
                row = connection.execute(
                    "SELECT * FROM pet_state WHERE pet_id = ?", (pet_id,)
                ).fetchone()
            return self._row_to_state(row)

    def update(self, state: PetState) -> PetState:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE pet_state SET hunger=?, energy=?, health=?, mood=?, intimacy=?,
                experience=?, level=?, maturity=?, last_updated_at=? WHERE pet_id=?
                """,
                (
                    state.hunger,
                    state.energy,
                    state.health,
                    state.mood,
                    state.intimacy,
                    state.experience,
                    state.level,
                    state.maturity,
                    state.last_updated_at,
                    state.pet_id,
                ),
            )
        return state

    def update_timestamp(self, pet_id: str, timestamp: float) -> None:
        self.ensure(pet_id)
        with self._lock, self._connect() as connection:
            connection.execute(
                "UPDATE pet_state SET last_updated_at=? WHERE pet_id=?",
                (timestamp, pet_id),
            )

    @staticmethod
    def _row_to_state(row: tuple[object, ...] | None) -> PetState:
        if row is None or len(row) != 10:
            raise RuntimeError("Pet state row is missing or malformed")
        return PetState(
            pet_id=str(row[0]),
            hunger=float(row[1]),
            energy=float(row[2]),
            health=float(row[3]),
            mood=float(row[4]),
            intimacy=float(row[5]),
            experience=int(row[6]),
            level=int(row[7]),
            maturity=float(row[8]),
            last_updated_at=float(row[9]),
        )


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, value))


class PetWorldService:
    """Provide the single source of truth for state and growth."""

    def __init__(self, db_path: str | Path = Path("data/pet.sqlite3")) -> None:
        self.store = _PetStateStore(Path(db_path))

    def get_state(self, pet_id: str) -> PetState:
        """Refresh time-based decay and return the persisted state snapshot."""
        state = self.store.ensure(pet_id)
        elapsed_hours = max(0.0, (time.time() - state.last_updated_at) / 3600)
        if elapsed_hours < 0.001:
            return state
        refreshed = PetState(
            pet_id=state.pet_id,
            hunger=_clamp(state.hunger + elapsed_hours * 0.6),
            energy=_clamp(state.energy - elapsed_hours * 0.4),
            health=_clamp(
                state.health - max(0.0, state.hunger - 85.0) * elapsed_hours * 0.02
            ),
            mood=_clamp(state.mood - elapsed_hours * 0.15),
            intimacy=state.intimacy,
            experience=state.experience,
            level=state.level,
            maturity=state.maturity,
            last_updated_at=time.time(),
        )
        return self.store.update(refreshed)

    def perform_action(self, pet_id: str, action: PetAction) -> ActionResult:
        """Apply one validated action and persist its growth reward."""
        state = self.get_state(pet_id)
        changes: dict[PetAction, tuple[float, float, float, float, float, int, str]] = {
            PetAction.FEED: (-25.0, 0.0, 0.0, 5.0, 1.0, 10, "吃饱啦，肚子暖暖的！"),
            PetAction.PLAY: (0.0, -5.0, 0.0, 10.0, 3.0, 10, "被你摸摸啦，尾巴都要摇起来了！"),
            PetAction.BATHE: (0.0, 0.0, 8.0, 3.0, 0.0, 8, "洗得香喷喷，心情变好了！"),
            PetAction.REST: (0.0, 30.0, 0.0, 4.0, 0.0, 5, "休息完成，电量回来啦！"),
            PetAction.STUDY: (
                4.0,
                -12.0,
                0.0,
                2.0,
                0.0,
                25,
                "学到新东西啦，变聪明一点点！",
            ),
            PetAction.WORK: (
                8.0,
                -20.0,
                0.0,
                1.0,
                1.0,
                30,
                "工作完成，今天也有小小收获！",
            ),
            PetAction.ADVENTURE: (
                10.0,
                -25.0,
                0.0,
                8.0,
                2.0,
                35,
                "冒险回来啦，发现了闪闪发光的经验！",
            ),
        }
        hunger, energy, health, mood, intimacy, reward, message = changes[action]
        experience = state.experience + reward
        level = experience // 100 + 1
        updated = PetState(
            pet_id=state.pet_id,
            hunger=_clamp(state.hunger + hunger),
            energy=_clamp(state.energy + energy),
            health=_clamp(state.health + health),
            mood=_clamp(state.mood + mood),
            intimacy=_clamp(state.intimacy + intimacy),
            experience=experience,
            level=level,
            maturity=_clamp(level * 12.5),
            last_updated_at=time.time(),
        )
        self.store.update(updated)
        return ActionResult(action, message, updated, reward)

    def infer_action(self, text: str) -> PetAction | None:
        """Map a small set of Chinese user intents to safe local actions."""
        if any(word in text for word in ("喂", "吃饭", "鱼", "食物")):
            return PetAction.FEED
        if any(word in text for word in ("摸摸", "玩耍", "陪我玩", "抱抱", "摸一摸")):
            return PetAction.PLAY
        if any(word in text for word in ("洗澡", "洗一洗")):
            return PetAction.BATHE
        if any(word in text for word in ("睡觉", "休息")):
            return PetAction.REST
        if any(word in text for word in ("学习", "读书")):
            return PetAction.STUDY
        if "打工" in text:
            return PetAction.WORK
        if any(word in text for word in ("冒险", "出去玩")):
            return PetAction.ADVENTURE
        return None

    def is_state_question(self, text: str) -> bool:
        """Detect common state questions so the agent can fetch real values first."""
        return any(
            word in text for word in ("怎么样", "状态", "饿不饿", "累不累", "在干嘛")
        )
