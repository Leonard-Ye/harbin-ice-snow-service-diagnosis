# -*- coding: utf-8 -*-
"""数据质量审计路由。"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter

from src.api import services
from src.api.schemas import QualityAuditResponse

router = APIRouter(prefix="/api/v1/quality", tags=["quality"])


@router.get("/audit", response_model=QualityAuditResponse)
def quality_audit() -> QualityAuditResponse:
    rows = services.quality_audit_rows()
    return QualityAuditResponse(
        generated_at=datetime.now().isoformat(timespec="seconds"),
        rows=rows,
    )
