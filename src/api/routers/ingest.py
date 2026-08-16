# -*- coding: utf-8 -*-
"""通用单表数据质量体检路由（委托 src/services/table_audit.py）。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, UploadFile

from src.api.config import settings
from src.api.schemas import IngestResponse
from src.services.table_audit import TableAuditError, audit_tabular_bytes

router = APIRouter(prefix="/api/v1/ingest", tags=["ingest"])


@router.post("", response_model=IngestResponse, status_code=200)
def ingest_quality_audit(upload: UploadFile) -> IngestResponse:
    if not settings.enable_write_endpoints:
        raise HTTPException(status_code=403, detail={"code": "WRITE_DISABLED", "message": "写接口已在服务端关闭"})

    filename = upload.filename or "upload.csv"
    chunks = []
    total = 0
    while True:
        chunk = upload.file.read(1 << 20)
        if not chunk:
            break
        total += len(chunk)
        if total > settings.max_upload_bytes:
            raise HTTPException(
                status_code=413,
                detail={"code": "FILE_TOO_LARGE", "message": f"文件超过 {settings.max_upload_bytes // (1 << 20)}MB 限制"},
            )
        chunks.append(chunk)

    try:
        result = audit_tabular_bytes(filename, b"".join(chunks), settings.upload_dir)
    except TableAuditError as exc:
        code, _, message = str(exc).partition(": ")
        status_code = {
            "UNSUPPORTED_FILE_TYPE": 415,
            "FILE_TOO_LARGE": 413,
            "EMPTY_FILE": 400,
        }.get(code, 400)
        raise HTTPException(status_code=status_code, detail={"code": code, "message": message or str(exc)})

    return IngestResponse(**result)
