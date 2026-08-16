# -*- coding: utf-8 -*-
"""健康检查路由。"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from src.api.config import settings
from src.api.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    index_file = settings.project_root / "analysis" / "V30_Multi_Source_Fusion_R2" / "anchor_index_v22_04R2.csv"
    db_file = settings.project_root / "data" / "platform.db"
    raw_ready = bool((settings.project_root / "00_原始基座数据" / "携程经纬度.csv").exists())
    components = {
        "data": "ok" if index_file.exists() else "missing",
        "database": "ok" if Path(str(db_file)).exists() else "not_initialized",
        "raw_data": "available" if raw_ready else "unavailable",
        "write_endpoints": settings.enable_write_endpoints,
    }
    return HealthResponse(
        status="ok",
        version=settings.version,
        components=components,
    )
