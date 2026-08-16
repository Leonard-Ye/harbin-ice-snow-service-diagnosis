# -*- coding: utf-8 -*-
"""指标计算与多尺度趋势路由。"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query

from src.api import services
from src.api.schemas import ComputeParamsRequest, ComputeResultResponse

router = APIRouter(prefix="/api/v1/metrics", tags=["metrics"])


@router.post("/calculate", response_model=ComputeResultResponse)
def calculate_metrics(body: ComputeParamsRequest) -> ComputeResultResponse:
    items = services.calculate_metrics(
        scale_km=body.scale_km,
        method=body.method.value,
        smi_coef=body.smi_coef,
    )
    return ComputeResultResponse(
        method=body.method.value,
        scale_km=body.scale_km,
        generated_at=datetime.now().isoformat(timespec="seconds"),
        items=items,
    )


@router.get("/trend")
def metrics_trend(
    metric: str = Query("supply_total", description="supply_total | ctrip_lodging_count | amap_dining_count ..."),
    scale_km: int = Query(3, ge=1, le=5),
) -> dict:
    from src.engines.metrics_engine import MetricsEngine

    profile = MetricsEngine().compute_scale_profile(services.load_scale())
    profile = profile[profile["scale_km"] == scale_km]
    if metric not in profile.columns:
        return {"metric": metric, "scale_km": scale_km, "items": [], "message": f"指标不存在，可选: {list(profile.columns)}"}
    items = [
        {"anchor_name": str(r.anchor_name), "value": float(r[metric])}
        for r in profile.sort_values(metric, ascending=False).itertuples(index=False)
    ]
    return {"metric": metric, "scale_km": scale_km, "items": items}
