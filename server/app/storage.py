from __future__ import annotations

import logging
import os
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo


def _data_dir() -> Path:
    return Path(os.environ.get("BIRB_DATA_DIR", "data")).resolve()


def local_tz() -> ZoneInfo:
    """Return the configured local timezone (BIRB_TZ env, default UTC)."""
    return ZoneInfo(os.environ.get("BIRB_TZ", "UTC"))


log = logging.getLogger("birbesp.storage")


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
                CREATE TABLE IF NOT EXISTS meta (
                    key   TEXT PRIMARY KEY,
                    value TEXT
                );
                """
            )
        self._migrate_dates_to_local_tz()

    def _migrate_dates_to_local_tz(self) -> None:
        """Recompute the date column for every existing row in the configured
        local timezone. One-shot, idempotent (gated on a meta sentinel).
        Files on disk are not moved — only the index column changes."""
        key = "migration_v2_local_dates"
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
            if row is not None:
                return
            tz = local_tz()
            rows = conn.execute("SELECT filename, ts_epoch_ms FROM frames").fetchall()
            for r in rows:
                ts = datetime.fromtimestamp(r["ts_epoch_ms"] / 1000, tz=timezone.utc)
                local_date = ts.astimezone(tz).strftime("%Y-%m-%d")
                conn.execute(
                    "UPDATE frames SET date = ? WHERE filename = ?",
                    (local_date, r["filename"]),
                )
            conn.execute("INSERT INTO meta(key, value) VALUES (?, 'done')", (key,))
            log.info(
                "[storage] migrated %d rows to local-tz date buckets (tz=%s)",
                len(rows), tz.key,
            )

    def save_frame(self, jpeg_bytes: bytes, ts: datetime | None = None) -> dict:
        """Persist a JPEG and index it. Returns the new row as a dict.

        On-disk path and DB `date` are computed in the configured local
        timezone (BIRB_TZ) so that a frame captured at 00:30 local always
        appears under the same date the user is thinking in. The full
        UTC ISO timestamp is preserved in `ts_iso` for unambiguous storage
        and client-side localisation.
        """
        ts = ts or datetime.now(timezone.utc)
        local_ts = ts.astimezone(local_tz())
        date_str = local_ts.strftime("%Y-%m-%d")
        sub = self.base_dir / local_ts.strftime("%Y") / local_ts.strftime("%m") / local_ts.strftime("%d")
        sub.mkdir(parents=True, exist_ok=True)
        ms = int(local_ts.microsecond / 1000)
        fname = f"{local_ts.strftime('%H%M%S')}_{ms:03d}.jpg"
        rel = f"{local_ts.strftime('%Y/%m/%d')}/{fname}"
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

    def prune(
        self,
        now: datetime | None = None,
        retain_days: int = 7,
        retain_highlight_days: int = 30,
    ) -> dict:
        """Delete frames older than the retention windows.

        Non-highlight frames are dropped after ``retain_days``; highlights live
        until ``retain_highlight_days``. A non-positive ``retain_days``
        disables pruning entirely as a safety against accidental wipe.
        """
        if retain_days <= 0:
            return {"deleted_frames": 0, "deleted_bytes": 0, "disabled": True}

        now = now or datetime.now(timezone.utc)
        cutoff_raw_ms = int((now - timedelta(days=retain_days)).timestamp() * 1000)
        cutoff_hl_ms = int((now - timedelta(days=max(retain_highlight_days, retain_days))).timestamp() * 1000)

        deleted = 0
        deleted_bytes = 0
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT filename FROM frames"
                " WHERE (is_highlight = 0 AND ts_epoch_ms < ?)"
                "    OR (is_highlight = 1 AND ts_epoch_ms < ?)",
                (cutoff_raw_ms, cutoff_hl_ms),
            ).fetchall()
            dirs_to_check: set[Path] = set()
            for r in rows:
                fname = r["filename"]
                p = self.base_dir / fname
                try:
                    deleted_bytes += p.stat().st_size
                    p.unlink()
                except FileNotFoundError:
                    pass
                conn.execute("DELETE FROM frames WHERE filename = ?", (fname,))
                dirs_to_check.add(p.parent)
                deleted += 1
            # Walk up each affected directory tree, removing dirs that became empty.
            for d in sorted(dirs_to_check, key=lambda x: -len(x.parts)):
                cur = d
                while cur != self.base_dir and cur.is_relative_to(self.base_dir):
                    try:
                        cur.rmdir()
                    except OSError:
                        break
                    cur = cur.parent
        return {"deleted_frames": deleted, "deleted_bytes": deleted_bytes}

    def list_around(self, filename: str, radius: int = 30) -> list[dict]:
        """Return up to `radius` frames before + the center + up to `radius`
        frames after, in chronological order (oldest first)."""
        center = self.get(filename)
        if center is None:
            return []
        ts_ms = center["ts_epoch_ms"]
        cols = "filename, ts_iso, ts_epoch_ms, date, diff_score, is_highlight"
        with self._connect() as conn:
            older = conn.execute(
                f"SELECT {cols} FROM frames WHERE ts_epoch_ms < ?"
                " ORDER BY ts_epoch_ms DESC LIMIT ?",
                (ts_ms, radius),
            ).fetchall()
            newer = conn.execute(
                f"SELECT {cols} FROM frames WHERE ts_epoch_ms > ?"
                " ORDER BY ts_epoch_ms ASC LIMIT ?",
                (ts_ms, radius),
            ).fetchall()
        return [dict(r) for r in reversed(older)] + [center] + [dict(r) for r in newer]

    def neighbors(self, filename: str) -> dict:
        """Return adjacent frame filenames by capture time: newer and older."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT ts_epoch_ms FROM frames WHERE filename = ?", (filename,)
            ).fetchone()
            if row is None:
                return {"newer": None, "older": None}
            ts = row["ts_epoch_ms"]
            newer = conn.execute(
                "SELECT filename FROM frames WHERE ts_epoch_ms > ? ORDER BY ts_epoch_ms ASC LIMIT 1",
                (ts,),
            ).fetchone()
            older = conn.execute(
                "SELECT filename FROM frames WHERE ts_epoch_ms < ? ORDER BY ts_epoch_ms DESC LIMIT 1",
                (ts,),
            ).fetchone()
        return {
            "newer": newer["filename"] if newer else None,
            "older": older["filename"] if older else None,
        }

    def get(self, filename: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT filename, ts_iso, ts_epoch_ms, date, diff_score, is_highlight"
                " FROM frames WHERE filename = ?",
                (filename,),
            ).fetchone()
        return dict(row) if row else None

    def list_in_range(
        self,
        since_epoch_ms: int,
        until_epoch_ms: int,
        max_count: int = 2400,
    ) -> dict:
        """Frames in [since..until], capped at max_count via even sampling.

        All highlights are always included regardless of sampling — so the
        scrubber never hides moments of motion. Returns a dict with the
        frame list, the unsampled total, and whether sampling kicked in.
        """
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT filename, ts_epoch_ms, is_highlight"
                " FROM frames WHERE ts_epoch_ms BETWEEN ? AND ?"
                " ORDER BY ts_epoch_ms ASC",
                (since_epoch_ms, until_epoch_ms),
            ).fetchall()
        frames = [dict(r) for r in rows]
        total = len(frames)
        if total <= max_count:
            return {"frames": frames, "total": total, "sampled": False}
        highlights = [f for f in frames if f["is_highlight"]]
        budget = max(1, max_count - len(highlights))
        step = max(1, total // budget)
        sampled = frames[::step]
        seen: set[str] = set()
        out: list[dict] = []
        for f in highlights + sampled:
            if f["filename"] not in seen:
                seen.add(f["filename"])
                out.append(f)
        out.sort(key=lambda x: x["ts_epoch_ms"])
        return {"frames": out, "total": total, "sampled": True}


_store: FrameStore | None = None


def get_store() -> FrameStore:
    global _store
    if _store is None:
        _store = FrameStore()
    return _store
