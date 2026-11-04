"""Persistencia SQLite da fila de producao.

Somente a biblioteca padrao do Python e necessaria. Cada operacao abre sua
propria conexao para funcionar com as threads do servidor HTTP.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
import threading
import time
from pathlib import Path
from typing import Any


class JobStore:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    @contextmanager
    def _connect(self):
        con = sqlite3.connect(str(self.db_path), timeout=15)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA busy_timeout=15000")
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def _init_db(self):
        with self._lock, self._connect() as con:
            con.execute("PRAGMA journal_mode=WAL")
            con.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    payload_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            con.execute("CREATE INDEX IF NOT EXISTS idx_jobs_updated ON jobs(updated_at DESC)")
            con.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at REAL NOT NULL
                )
            """)
            con.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(1, ?)",
                (time.time(),),
            )

    def create(self, job: dict[str, Any]) -> int:
        now = time.time()
        payload = dict(job)
        payload.pop("id", None)
        with self._lock, self._connect() as con:
            cur = con.execute(
                "INSERT INTO jobs(payload_json, created_at, updated_at) VALUES(?,?,?)",
                (json.dumps(payload, ensure_ascii=False), now, now),
            )
            job_id = int(cur.lastrowid)
        return job_id

    def save(self, job: dict[str, Any]) -> None:
        job_id = int(job["id"])
        payload = dict(job)
        payload.pop("id", None)
        now = time.time()
        with self._lock, self._connect() as con:
            cur = con.execute(
                "UPDATE jobs SET payload_json=?, updated_at=? WHERE id=?",
                (json.dumps(payload, ensure_ascii=False), now, job_id),
            )
            if cur.rowcount == 0:
                con.execute(
                    "INSERT INTO jobs(id,payload_json,created_at,updated_at) VALUES(?,?,?,?)",
                    (job_id, json.dumps(payload, ensure_ascii=False), now, now),
                )

    def list(self) -> list[dict[str, Any]]:
        with self._lock, self._connect() as con:
            rows = con.execute("SELECT id,payload_json FROM jobs ORDER BY id").fetchall()
        result = []
        for row in rows:
            try:
                payload = json.loads(row["payload_json"])
            except (TypeError, json.JSONDecodeError):
                payload = {"status": "erro", "erro": "Registro de tarefa ilegivel.", "log": []}
            payload["id"] = int(row["id"])
            payload.setdefault("log", [])
            result.append(payload)
        return result

    def remove(self, job_id: int) -> bool:
        with self._lock, self._connect() as con:
            cur = con.execute("DELETE FROM jobs WHERE id=?", (int(job_id),))
            return cur.rowcount > 0

    def get(self, job_id: int) -> dict[str, Any] | None:
        with self._lock, self._connect() as con:
            row = con.execute("SELECT id,payload_json FROM jobs WHERE id=?", (int(job_id),)).fetchone()
        if not row:
            return None
        payload = json.loads(row["payload_json"])
        payload["id"] = int(row["id"])
        return payload

    def mark_interrupted(self) -> list[int]:
        """Marca como interrompidos jobs que estavam rodando no desligamento."""
        changed = []
        for job in self.list():
            if job.get("status") == "rodando":
                job["status"] = "interrompido"
                job["etapa_nome"] = "Interrompido — pronto para retomar"
                job["erro"] = (
                    "O servidor foi encerrado durante esta producao. "
                    "Use Retomar para continuar; arquivos ja produzidos serao reaproveitados quando possivel."
                )
                job.setdefault("log", []).append(
                    "[RECUPERACAO] Servidor reiniciado; tarefa marcada como interrompida, sem repeticao automatica."
                )
                self.save(job)
                changed.append(int(job["id"]))
        return changed
