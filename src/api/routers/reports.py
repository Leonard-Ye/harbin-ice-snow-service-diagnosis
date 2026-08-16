# -*- coding: utf-8 -*-
"""报表下载路由（Excel / PDF / HTML）。"""
from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse, Response

from src.api import services

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.get("/excel")
def report_excel(method: str = Query("equal", pattern="^(equal|entropy)$")) -> Response:
    data = services.report_excel(method)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="harbin_diagnosis_{method}.xlsx"'},
    )


@router.get("/pdf")
def report_pdf(method: str = Query("equal", pattern="^(equal|entropy)$")) -> Response:
    data = services.report_pdf(method)
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="harbin_diagnosis_{method}.pdf"'},
    )


@router.get("/html")
def report_html(method: str = Query("equal", pattern="^(equal|entropy)$")) -> HTMLResponse:
    return HTMLResponse(content=services.report_html(method))
