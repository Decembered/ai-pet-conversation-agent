"""Safe local artifact generation for the pet's writing and drawing skills."""

from dataclasses import dataclass
from html import escape
from pathlib import Path
import re
import sqlite3
import time
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class Artifact:
    """Describe one generated file stored on the local machine."""

    artifact_id: str
    pet_id: str
    kind: str
    title: str
    path: Path
    created_at: float


class ArtifactService:
    """Create local Markdown letters and deterministic SVG drawings safely."""

    def __init__(
        self,
        db_path: str | Path = Path("data/pet.sqlite3"),
        artifact_root: str | Path = Path("data/artifacts"),
    ) -> None:
        self.db_path = Path(db_path)
        self.root = Path(artifact_root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS pet_artifacts (
                    artifact_id TEXT PRIMARY KEY,
                    pet_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    title TEXT NOT NULL,
                    path TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )

    def write_letter(
        self, pet_id: str, recipient: str, content: str, title: str = "给主人的信"
    ) -> Artifact:
        """Write a UTF-8 Markdown letter and index it in SQLite."""
        safe_title = self._safe_component(title, "给主人的信")
        artifact_id = uuid4().hex
        path = self.root / f"{artifact_id}_{safe_title}.md"
        body = f"# {safe_title}\n\n写给：{recipient.strip() or '主人'}\n\n{content.strip()}\n"
        path.write_text(body, encoding="utf-8")
        return self._record(artifact_id, pet_id, "letter", safe_title, path)

    def create_drawing(
        self, pet_id: str, caption: str, title: str = "宠物画作"
    ) -> Artifact:
        """Write a small self-contained SVG so drawing works offline."""
        safe_title = self._safe_component(title, "宠物画作")
        safe_caption = escape(caption.strip() or "和主人一起发光")
        artifact_id = uuid4().hex
        path = self.root / f"{artifact_id}_{safe_title}.svg"
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="420" viewBox="0 0 640 420">'
            '<defs><linearGradient id="sky" x1="0" x2="1"><stop stop-color="#ffd6e7"/><stop offset="1" stop-color="#d9f2ff"/></linearGradient></defs>'
            '<rect width="640" height="420" rx="32" fill="url(#sky)"/>'
            '<circle cx="320" cy="180" r="90" fill="#ffcc66"/>'
            '<circle cx="285" cy="165" r="12" fill="#392d3d"/><circle cx="355" cy="165" r="12" fill="#392d3d"/>'
            '<path d="M285 210 Q320 240 355 210" fill="none" stroke="#392d3d" stroke-width="8" stroke-linecap="round"/>'
            f'<text x="320" y="340" text-anchor="middle" font-size="28" fill="#392d3d">{safe_caption}</text>'
            "</svg>"
        )
        path.write_text(svg, encoding="utf-8")
        return self._record(artifact_id, pet_id, "drawing", safe_title, path)

    def list_artifacts(self, pet_id: str, limit: int = 20) -> list[Artifact]:
        """List the newest generated files for one pet."""
        with sqlite3.connect(self.db_path) as connection:
            rows = connection.execute(
                "SELECT artifact_id, pet_id, kind, title, path, created_at FROM pet_artifacts "
                "WHERE pet_id=? ORDER BY created_at DESC LIMIT ?",
                (pet_id, max(1, limit)),
            ).fetchall()
        return [self._row_to_artifact(row) for row in rows]

    def _record(
        self, artifact_id: str, pet_id: str, kind: str, title: str, path: Path
    ) -> Artifact:
        created_at = time.time()
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                "INSERT INTO pet_artifacts VALUES (?, ?, ?, ?, ?, ?)",
                (artifact_id, pet_id, kind, title, str(path), created_at),
            )
        return Artifact(artifact_id, pet_id, kind, title, path, created_at)

    @staticmethod
    def _row_to_artifact(row: tuple[object, ...]) -> Artifact:
        return Artifact(
            str(row[0]),
            str(row[1]),
            str(row[2]),
            str(row[3]),
            Path(str(row[4])),
            float(row[5]),
        )

    @staticmethod
    def _safe_component(value: str, fallback: str) -> str:
        cleaned = re.sub(r"[^\w\u4e00-\u9fff -]+", "", value.strip())[:80]
        return cleaned or fallback
