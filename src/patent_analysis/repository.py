from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import json
import sqlite3

from .database import get_connection


class PatentRepository:
    def __init__(self, database_path: Path):
        self.database_path = database_path

    @contextmanager
    def connection(self):
        conn = get_connection(self.database_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # ── Patents ──────────────────────────────────────────────

    def create_patent(self, title: str, patent_number: str = "", source: str = "") -> int:
        with self.connection() as conn:
            cursor = conn.execute(
                "INSERT INTO patents (title, patent_number, source) VALUES (?, ?, ?)",
                (title.strip(), patent_number.strip(), source.strip()),
            )
        return int(cursor.lastrowid)

    def update_patent(self, patent_id: int, **fields: str) -> None:
        allowed = {"title", "patent_number", "source", "pdf_path"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        with self.connection() as conn:
            conn.execute(
                f"UPDATE patents SET {set_clause} WHERE id = ?",
                (*updates.values(), patent_id),
            )

    def list_patents(self, limit: int | None = None) -> list[dict]:
        sql = "SELECT * FROM patents ORDER BY created_at DESC, id DESC"
        params: list[object] = []
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        with self.connection() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def get_patent(self, patent_id: int) -> dict | None:
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM patents WHERE id = ?", (patent_id,)).fetchone()
        return dict(row) if row else None

    def delete_patent(self, patent_id: int) -> str | None:
        """Returns the pdf_path so the caller can clean up the file."""
        with self.connection() as conn:
            row = conn.execute("SELECT pdf_path FROM patents WHERE id = ?", (patent_id,)).fetchone()
            conn.execute("DELETE FROM patents WHERE id = ?", (patent_id,))
        return str(row["pdf_path"]) if row and row["pdf_path"] else None

    # ── Agent results ─────────────────────────────────────────

    def save_agent_result(self, patent_id: int, agent: str, result: dict) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO agent_results (patent_id, agent, result_json)
                VALUES (?, ?, ?)
                ON CONFLICT(patent_id, agent) DO UPDATE SET
                    result_json = excluded.result_json,
                    created_at  = CURRENT_TIMESTAMP
                """,
                (patent_id, agent, json.dumps(result)),
            )

    def get_agent_result(self, patent_id: int, agent: str) -> dict | None:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT result_json, created_at FROM agent_results WHERE patent_id = ? AND agent = ?",
                (patent_id, agent),
            ).fetchone()
        if row is None:
            return None
        try:
            return {"result": json.loads(row["result_json"]), "created_at": row["created_at"]}
        except json.JSONDecodeError:
            return None

    def list_patents_with_agent_results(self, exclude_id: int | None = None) -> list[dict]:
        patents = self.list_patents()
        result = []
        for p in patents:
            pid = int(p["id"])
            if exclude_id is not None and pid == exclude_id:
                continue
            entry = dict(p)
            cached = self.get_agent_result(pid, "extraction")
            if cached and "result" in cached:
                details = cached["result"].get("details", {})
                entry["key_technical_features"] = details.get("key_technical_features") or []
            else:
                entry["key_technical_features"] = []
            result.append(entry)
        return result
