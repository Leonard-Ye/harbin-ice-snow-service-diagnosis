# -*- coding: utf-8 -*-
"""锚点清单与详情路由。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from src.api import services
from src.api.schemas import (
    AnchorDetailResponse,
    AnchorListResponse,
    AnchorMeta,
)

router = APIRouter(prefix="/api/v1", tags=["anchors"])


@router.get("/meta/anchors", response_model=list[AnchorMeta])
def list_anchor_meta() -> list[AnchorMeta]:
    return [AnchorMeta(**item) for item in services.list_anchor_meta()]


@router.get("/anchors", response_model=AnchorListResponse)
def list_anchors(
    method: str = Query("equal", pattern="^(equal|entropy)$"),
    sort: str = Query("mismatch_rank", description="mismatch_rank | SMI | DHI"),
    limit: int = Query(20, ge=1, le=20),
) -> AnchorListResponse:
    df = services.get_table(method).sort_values("SMI", ascending=False)
    if sort in df.columns:
        df = df.sort_values(sort, ascending=sort not in ("SMI", "DHI", "ERI", "ERI_plus", "SSI"))
    items = services.metric_items(df.head(limit))
    return AnchorListResponse(method=method, count=len(items), items=items)


@router.get("/anchors/{anchor_name}", response_model=AnchorDetailResponse)
def get_anchor(anchor_name: str, method: str = Query("equal", pattern="^(equal|entropy)$")) -> AnchorDetailResponse:
    try:
        item = services.anchor_detail(anchor_name, method)
    except KeyError:
        raise HTTPException(status_code=404, detail={"code": "ANCHOR_NOT_FOUND", "message": f"锚点不存在: {anchor_name}"})
    return AnchorDetailResponse(**item)
