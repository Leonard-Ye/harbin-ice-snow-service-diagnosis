# -*- coding: utf-8 -*-
"""Pipeline Job Manager：单 Worker 顺序执行，避免并发写同一批产物。"""
from __future__ import annotations

import threading
from collections import deque
from typing import Any, Deque, Dict, Optional
from uuid import uuid4

from src.api.config import settings
from src.pipeline.config import PipelineConfig
from src.pipeline.orchestrator import PipelineRunner


class PipelineJobManager:
    """进程内单飞任务队列。

    - submit() 立即返回 run_id；
    - Worker 串行执行，天然避免同一输出目录并发写；
    - 结果同时写入 SQLite RunStore，可从 /pipeline/runs 查询。
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._queue: Deque[Dict[str, Any]] = deque()
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._worker: Optional[threading.Thread] = None
        self._active_run_id: Optional[str] = None

    def active_run_id(self) -> Optional[str]:
        with self._lock:
            return self._active_run_id

    def submit(self, method: str = "equal", force: bool = False) -> Dict[str, Any]:
        run_id = uuid4().hex
        job = {"run_id": run_id, "method": method, "status": "queued", "error": None}
        with self._lock:
            if self._active_run_id is not None and not force:
                return {
                    "run_id": run_id,
                    "status": "queued",
                    "message": f"已有任务 {self._active_run_id[:12]} 正在执行",
                    "queued": True,
                }
            self._jobs[run_id] = job
            self._queue.append(job)
            if self._worker is None or not self._worker.is_alive():
                self._worker = threading.Thread(target=self._run_worker, name="pipeline-worker", daemon=True)
                self._worker.start()
        return {
            "run_id": run_id,
            "status": "queued",
            "message": "任务已提交，请轮询 GET /api/v1/pipeline/runs/{run_id}",
            "queued": bool(self._active_run_id),
        }

    def _run_worker(self) -> None:
        while True:
            job = None
            with self._lock:
                if not self._queue:
                    self._active_run_id = None
                    return
                job = self._queue.popleft()
                self._active_run_id = job["run_id"]
                job["status"] = "running"

            try:
                cfg = PipelineConfig.from_toml(settings.pipeline_config_path)
                cfg.method = job["method"]
                result = PipelineRunner(cfg).run()
                job.update(
                    {
                        "status": result.status,
                        "error": result.error or result.store_error,
                        "result": result.to_dict(),
                    }
                )
            except Exception as exc:
                job["status"] = "failed"
                job["error"] = str(exc)

    def get(self, run_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return dict(self._jobs.get(run_id) or {})


job_manager = PipelineJobManager()
