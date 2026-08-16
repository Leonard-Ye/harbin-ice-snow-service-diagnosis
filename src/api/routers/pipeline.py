# -*- coding: utf-8 -*-
"""Pipeline 触发与运行历史路由。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from src.api.config import settings
from src.api.jobs import job_manager
from src.api.schemas import PipelineRunAccepted, PipelineRunRequest, PipelineRunStatus
from src.storage.run_store import RunStore

router = APIRouter(prefix="/api/v1/pipeline", tags=["pipeline"])


def _store() -> RunStore:
    store = RunStore(settings.project_root / "data" / "platform.db")
    store.initialize()
    return store


@router.post("/run", response_model=PipelineRunAccepted, status_code=202)
def run_pipeline(body: PipelineRunRequest) -> PipelineRunAccepted:
    if not settings.enable_write_endpoints:
        raise HTTPException(status_code=403, detail={"code": "WRITE_DISABLED", "message": "写接口已在服务端关闭"})
    result = job_manager.submit(method=body.method.value, force=body.force)
    return PipelineRunAccepted(**result)


@router.get("/runs", response_model=list[PipelineRunStatus])
def list_runs(limit: int = Query(20, ge=1, le=100)) -> list[PipelineRunStatus]:
    store = _store()
    try:
        runs = store.list_runs(limit=limit)
    finally:
        store.close()
    out = []
    for run in runs:
        out.append(
            PipelineRunStatus(
                run_id=run["run_id"],
                status=run["status"],
                method=run["method"],
                main_scale=run["main_scale"],
                started_at=run.get("started_at"),
                finished_at=run.get("finished_at"),
                duration_ms=run.get("duration_ms"),
                error=run.get("error"),
            )
        )
    return out


@router.get("/runs/{run_id}", response_model=PipelineRunStatus)
def get_run(run_id: str) -> PipelineRunStatus:
    job = job_manager.get(run_id)
    if job and job.get("result"):
        result = job["result"]
        return PipelineRunStatus(
            run_id=result["run_id"],
            status=result["status"],
            method=result["method"],
            main_scale=result["main_scale"],
            started_at=result["started_at"],
            finished_at=result["finished_at"],
            duration_ms=result["duration_ms"],
            error=result["error"] or result["store_error"],
            artifacts=result.get("artifacts", []),
        )

    store = _store()
    try:
        run = store.get_run(run_id)
    finally:
        store.close()
    if run is None:
        raise HTTPException(status_code=404, detail={"code": "RUN_NOT_FOUND", "message": f"run_id 不存在: {run_id}"})
    return PipelineRunStatus(
        run_id=run["run_id"],
        status=run["status"],
        method=run["method"],
        main_scale=run["main_scale"],
        started_at=run.get("started_at"),
        finished_at=run.get("finished_at"),
        duration_ms=run.get("duration_ms"),
        error=run.get("error"),
        artifacts=run.get("artifacts", []),
    )
