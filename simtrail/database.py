from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from .models import Run


class RunRepository:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self._create_schema()

    def _create_schema(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                project TEXT NOT NULL,
                analyst TEXT NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL,
                solver TEXT NOT NULL,
                source_path TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                inputs_json TEXT NOT NULL,
                results_json TEXT NOT NULL,
                fingerprint TEXT NOT NULL DEFAULT ''
            )
            """
        )
        columns = {row[1] for row in self.connection.execute("PRAGMA table_info(runs)")}
        if "fingerprint" not in columns:
            self.connection.execute("ALTER TABLE runs ADD COLUMN fingerprint TEXT NOT NULL DEFAULT ''")
        self.connection.execute("CREATE INDEX IF NOT EXISTS idx_runs_project ON runs(project)")
        self.connection.execute("CREATE INDEX IF NOT EXISTS idx_runs_created ON runs(created_at DESC)")
        self.connection.execute("CREATE INDEX IF NOT EXISTS idx_runs_fingerprint ON runs(fingerprint)")
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS app_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        self.connection.commit()

    def add(self, run: Run) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO runs(name, project, analyst, created_at, status, solver, source_path,
                             notes, inputs_json, results_json, fingerprint)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run.name, run.project, run.analyst, run.created_at.isoformat(), run.status,
                run.solver, run.source_path, run.notes, json.dumps(run.inputs, ensure_ascii=False),
                json.dumps(run.results, ensure_ascii=False), run.fingerprint(),
            ),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def add_or_update(self, run: Run) -> tuple[int, bool]:
        """Insert a new solver snapshot, or refresh metadata on an exact match."""
        fingerprint = run.fingerprint()
        row = self.connection.execute(
            "SELECT id FROM runs WHERE fingerprint = ? ORDER BY id LIMIT 1", (fingerprint,)
        ).fetchone()
        if not row:
            return self.add(run), True
        run_id = int(row["id"])
        self.connection.execute(
            """
            UPDATE runs SET name = ?, analyst = ?, status = ?, notes = ?, created_at = ?,
                            inputs_json = ?, results_json = ?
            WHERE id = ?
            """,
            (run.name, run.analyst, run.status, run.notes, run.created_at.isoformat(),
             json.dumps(run.inputs, ensure_ascii=False), json.dumps(run.results, ensure_ascii=False),
             run_id),
        )
        self.connection.commit()
        return run_id, False

    def delete(self, run_id: int) -> None:
        self.connection.execute("DELETE FROM runs WHERE id = ?", (run_id,))
        self.connection.commit()

    def all(self) -> list[Run]:
        rows = self.connection.execute("SELECT * FROM runs ORDER BY created_at DESC").fetchall()
        return [self._from_row(row) for row in rows]

    def get(self, run_id: int) -> Run | None:
        row = self.connection.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return self._from_row(row) if row else None

    def count(self) -> int:
        return int(self.connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0])

    def clear(self) -> int:
        count = self.count()
        self.connection.execute("DELETE FROM runs")
        self.connection.commit()
        return count

    def is_initialized(self) -> bool:
        row = self.connection.execute("SELECT value FROM app_meta WHERE key = 'initialized'").fetchone()
        return bool(row and row[0] == "1")

    def mark_initialized(self) -> None:
        self.connection.execute(
            "INSERT OR REPLACE INTO app_meta(key, value) VALUES ('initialized', '1')"
        )
        self.connection.commit()

    @staticmethod
    def _from_row(row: sqlite3.Row) -> Run:
        return Run(
            id=row["id"], name=row["name"], project=row["project"], analyst=row["analyst"],
            created_at=datetime.fromisoformat(row["created_at"]), status=row["status"],
            solver=row["solver"], source_path=row["source_path"], notes=row["notes"],
            inputs=json.loads(row["inputs_json"]), results=json.loads(row["results_json"]),
        )

    def close(self) -> None:
        self.connection.close()
