# -*- coding: utf-8 -*-
"""RunStore —— 轻量 SQLite 运行元数据存储。

设计约定：
- 原生 sqlite3，不引入 ORM；
- WAL + busy_timeout 降低并发写锁概率；
- 每个线程独立连接（FastAPI 线程池安全）。
"""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

SCHEMA = """
CREATE TABLE IF NOT EXISTS pipeline_run (
    run_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    method TEXT NOT NULL,
    main_scale INTEGER NOT NULL,
    config_json TEXT NOT NULL,
    input_sha256 TEXT,
    output_sha256 TEXT,
    started_at TEXT,
    finished_at TEXT,
    duration_ms INTEGER,
    error TEXT
);

CREATE TABLE IF NOT EXISTS artifact (
    run_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    path TEXT NOT NULL,
    sha256 TEXT,
    created_at TEXT,
    PRIMARY KEY (run_id, kind, path)
);

CREATE TABLE IF NOT EXISTS metric_snapshot (
    run_id TEXT NOT NULL,
    anchor_name TEXT NOT NULL,
    scale_km INTEGER NOT NULL,
    DHI REAL,
    SSI REAL,
    ERI REAL,
    ERI_plus REAL,
    SMI REAL,
    mismatch_rank INTEGER,
    PRIMARY KEY (run_id, anchor_name, scale_km)
);

CREATE TABLE IF NOT EXISTS anomaly_event (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    column_name TEXT NOT NULL,
    anchor_name TEXT NOT NULL,
    method TEXT NOT NULL,
    value REAL,
    lower_bound REAL,
    upper_bound REAL
);

CREATE INDEX IF NOT EXISTS idx_run_status ON pipeline_run(status);
CREATE INDEX IF NOT EXISTS idx_artifact_run ON artifact(run_id);
CREATE INDEX IF NOT EXISTS idx_anomaly_run ON anomaly_event(run_id);
"""


class RunStore:
    """Pipeline 运行记录、产物、指标快照与异常事件的持久化。"""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        self._local = threading.local()
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _connection(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = self._connect()
            self._local.conn = conn
        return conn

    def initialize(self) -> None:
        conn = self._connect()
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=30000;")
            conn.executescript(SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None

    # ---------------------------------------------------------------- 写
    def start_run(
        self,
        run_id: str,
        method: str,
        main_scale: int,
        config_dict: Dict[str, Any],
        started_at: str,
    ) -> None:
        conn = self._connection()
        conn.execute(
            "INSERT OR REPLACE INTO pipeline_run "
            "(run_id, status, method, main_scale, config_json, started_at) "
            "VALUES (?, 'running', ?, ?, ?, ?)",
            (run_id, method, main_scale, json.dumps(config_dict, ensure_ascii=False, default=str), started_at),
        )
        conn.commit()

    def finish_run(
        self,
        run_id: str,
        status: str,
        finished_at: str,
        duration_ms: int,
        input_sha256: str,
        output_sha256: str,
        error: Optional[str] = None,
    ) -> None:
        conn = self._connection()
        conn.execute(
            "UPDATE pipeline_run SET status=?, finished_at=?, duration_ms=?, "
            "input_sha256=?, output_sha256=?, error=? WHERE run_id=?",
            (status, finished_at, duration_ms, input_sha256, output_sha256, error, run_id),
        )
        conn.commit()

    def record_artifact(self, run_id: str, kind: str, path: str, sha256: str, created_at: str) -> None:
        conn = self._connection()
        conn.execute(
            "INSERT OR REPLACE INTO artifact (run_id, kind, path, sha256, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (run_id, kind, path, sha256, created_at),
        )
        conn.commit()

    def record_metric_snapshots(self, run_id: str, metrics_df: pd.DataFrame, scale_km: int) -> None:
        conn = self._connection()
        rows = [
            (
                run_id,
                str(row.anchor_name),
                scale_km,
                float(row.DHI),
                float(row.SSI),
                float(row.ERI),
                float(row.ERI_plus),
                float(row.SMI),
                int(row.mismatch_rank),
            )
            for row in metrics_df.itertuples(index=False)
        ]
        conn.executemany(
            "INSERT OR REPLACE INTO metric_snapshot "
            "(run_id, anchor_name, scale_km, DHI, SSI, ERI, ERI_plus, SMI, mismatch_rank) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()

    def record_anomaly_events(
        self,
        run_id: str,
        audit_df: pd.DataFrame,
        scale_df: pd.DataFrame,
        method: str,
    ) -> None:
        """将质量审计表中的离群锚点写入 anomaly_event。

        audit_df 的 iqr_outliers 需为可迭代对象（锚点名列表）。
        """
        conn = self._connection()
        rows: List[tuple] = []
        for item in audit_df.itertuples(index=False):
            outliers = item.iqr_outliers
            if isinstance(outliers, str):
                try:
                    outliers = json.loads(outliers)
                except (TypeError, json.JSONDecodeError):
                    outliers = []
            if not outliers:
                continue
            for anchor in outliers:
                value = None
                try:
                    sub = scale_df[scale_df["anchor_name"] == anchor]
                    if not sub.empty:
                        value = float(pd.to_numeric(sub.iloc[0][item.column], errors="coerce"))
                except Exception:
                    value = None
                rows.append(
                    (
                        run_id,
                        str(item.column),
                        str(anchor),
                        method,
                        value,
                        float(item.iqr_lower) if pd.notna(item.iqr_lower) else None,
                        float(item.iqr_upper) if pd.notna(item.iqr_upper) else None,
                    )
                )
        if rows:
            conn.executemany(
                "INSERT INTO anomaly_event "
                "(run_id, column_name, anchor_name, method, value, lower_bound, upper_bound) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
            conn.commit()

    # ---------------------------------------------------------------- 读
    def list_runs(self, limit: int = 20) -> List[Dict[str, Any]]:
        conn = self._connection()
        rows = conn.execute(
            "SELECT * FROM pipeline_run ORDER BY COALESCE(started_at, '') DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        conn = self._connection()
        row = conn.execute("SELECT * FROM pipeline_run WHERE run_id=?", (run_id,)).fetchone()
        if row is None:
            return None
        run = dict(row)
        run["artifacts"] = [
            dict(r)
            for r in conn.execute(
                "SELECT kind, path, sha256, created_at FROM artifact WHERE run_id=? ORDER BY kind",
                (run_id,),
            ).fetchall()
        ]
        return run

    def latest_run(self) -> Optional[Dict[str, Any]]:
        runs = self.list_runs(limit=1)
        return runs[0] if runs else None
