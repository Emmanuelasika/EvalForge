"""SQLite run history and comparison storage for EvalForge."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


class RunStore:
    def __init__(self, database: Path) -> None:
        self.database = database
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode = WAL;
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, candidate TEXT NOT NULL,
                    mode TEXT NOT NULL, model TEXT NOT NULL, created_at TEXT NOT NULL,
                    metrics_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
                    case_id TEXT NOT NULL, passed INTEGER NOT NULL, score REAL NOT NULL,
                    severity TEXT NOT NULL, latency_ms REAL NOT NULL,
                    failures_json TEXT NOT NULL, output_json TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES runs(id)
                );
                CREATE INDEX IF NOT EXISTS idx_results_run ON results(run_id, id);
                CREATE INDEX IF NOT EXISTS idx_runs_created ON runs(created_at DESC);
                """
            )

    def save(self, run: dict[str, Any], results: list[dict[str, Any]]) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    run["id"],
                    run["name"],
                    run["candidate"],
                    run["mode"],
                    run["model"],
                    run["created_at"],
                    json.dumps(run["metrics"], sort_keys=True),
                ),
            )
            connection.executemany(
                """INSERT INTO results
                (run_id, case_id, passed, score, severity, latency_ms, failures_json, output_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        run["id"],
                        result["case_id"],
                        result["passed"],
                        result["score"],
                        result["severity"],
                        result["latency_ms"],
                        json.dumps(result["failures"]),
                        json.dumps(result["output"], sort_keys=True),
                    )
                    for result in results
                ],
            )

    def list_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [self._run(row) for row in rows]

    def get(self, run_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            run = connection.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
            results = connection.execute("SELECT * FROM results WHERE run_id = ? ORDER BY id", (run_id,)).fetchall()
        if not run:
            return None
        return {
            **self._run(run),
            "results": [
                {
                    "case_id": row["case_id"],
                    "passed": bool(row["passed"]),
                    "score": row["score"],
                    "severity": row["severity"],
                    "latency_ms": row["latency_ms"],
                    "failures": json.loads(row["failures_json"]),
                    "output": json.loads(row["output_json"]),
                }
                for row in results
            ],
        }

    @staticmethod
    def _run(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "name": row["name"],
            "candidate": row["candidate"],
            "mode": row["mode"],
            "model": row["model"],
            "created_at": row["created_at"],
            "metrics": json.loads(row["metrics_json"]),
        }
