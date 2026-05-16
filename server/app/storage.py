from __future__ import annotations

import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


def _data_dir() -> Path:
    return Path(os.environ.get("BIRB_DATA_DIR", "data")).resolve()


class FrameStore:
    """File-system store for captured JPEGs with a SQLite index.

    Layout on disk:

        <data_dir>/
            index.sqlite
            2026/05/16/153012_482.jpg
            2026/05/16/153013_511.jpg
            ...
    """

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or _data_dir()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = self.base_dir / "index.sqlite"
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS frames (
                    filename     TEXT PRIMARY KEY,
                    ts_iso       TEXT NOT NULL,
                    ts_epoch_ms  INTEGER NOT NULL,
                    date         TEXT NOT NULL,
                    diff_score   REAL,
                    is_highlight INTEGER NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_frames_date ON frames(date);
                CREATE INDEX IF NOT EXISTS idx_frames_ts ON frames(ts_epoch_ms);
                """
            )

    def save_frame(self, jpeg_bytes: bytes, ts: datetime | None = None) -> dict:
        """Persist a JPEG and index it. Returns the new row as a dict."""
        ts = ts or datetime.now(timezone.utc)
        date_str = ts.strftime("%Y-%m-%d")
        sub = self.base_dir / ts.strftime("%Y") / ts.strftime("%m") / ts.strftime("%d")
        sub.mkdir(parents=True, exist_ok=True)
        ms = int(ts.microsecond / 1000)
        fname = f"{ts.strftime('%H%M%S')}_{ms:03d}.jpg"
        rel = f"{ts.strftime('%Y/%m/%d')}/{fname}"
        path = sub / fname
        path.write_bytes(jpeg_bytes)

        epoch_ms = int(ts.timestamp() * 1000)
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO frames(filename, ts_iso, ts_epoch_ms, date)"
                " VALUES (?, ?, ?, ?)",
                (rel, ts.isoformat(), epoch_ms, date_str),
            )
        return {
            "filename": rel,
            "ts_iso": ts.isoformat(),
            "ts_epoch_ms": epoch_ms,
            "date": date_str,
            "bytes": len(jpeg_bytes),
        }

    def latest(self) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT filename, ts_iso, ts_epoch_ms, date, diff_score, is_highlight"
                " FROM frames ORDER BY ts_epoch_ms DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None

    def previous_frame_path(self) -> Path | None:
        row = self.latest()
        return self.base_dir / row["filename"] if row else None

    def absolute(self, relative_filename: str) -> Path:
        return self.base_dir / relative_filename

    def list_by_date(self, date_str: str, highlights_only: bool = False) -> list[dict]:
        sql = (
            "SELECT filename, ts_iso, ts_epoch_ms, date, diff_score, is_highlight"
            " FROM frames WHERE date = ?"
        )
        if highlights_only:
            sql += " AND is_highlight = 1"
        sql += " ORDER BY ts_epoch_ms DESC"
        with self._connect() as conn:
            return [dict(r) for r in conn.execute(sql, (date_str,)).fetchall()]

    def dates_with_frames(self) -> list[str]:
        with self._connect() as conn:
            return [
                r["date"]
                for r in conn.execute(
                    "SELECT DISTINCT date FROM frames ORDER BY date DESC"
                ).fetchall()
            ]

    def mark_highlight(self, filename: str, diff_score: float, is_highlight: bool) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE frames SET diff_score = ?, is_highlight = ? WHERE filename = ?",
                (diff_score, 1 if is_highlight else 0, filename),
            )

    def recent(self, limit: int = 12, highlights_only: bool = False) -> list[dict]:
        sql = (
            "SELECT filename, ts_iso, ts_epoch_ms, date, diff_score, is_highlight"
            " FROM frames"
        )
        if highlights_only:
            sql += " WHERE is_highlight = 1"
        sql += " ORDER BY ts_epoch_ms DESC LIMIT ?"
        with self._connect() as conn:
            return [dict(r) for r in conn.execute(sql, (limit,)).fetchall()]


_store: FrameStore | None = None


def get_store() -> FrameStore:
    global _store
    if _store is None:
        _store = FrameStore()
    return _store
