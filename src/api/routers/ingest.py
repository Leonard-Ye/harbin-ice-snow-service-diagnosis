# -*- coding: utf-8 -*-
"""通用单表数据质量体检路由。

明确范围：仅做缺失/重复/类型/经纬度合法性与 IQR/Z-score 离群审计，
不执行文旅锚点对齐与 DHI/SSI/SMI 领域指标计算。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, List
from uuid import uuid4

import pandas as pd
from fastapi import APIRouter, HTTPException, UploadFile

from src.api.config import settings
from src.api.schemas import AuditRow, IngestProfileColumn, IngestResponse
from src.cleaning.data_cleaner import DataCleaner
from src.detectors.anomaly_detector import AnomalyDetector

router = APIRouter(prefix="/api/v1/ingest", tags=["ingest"])

ALLOWED_SUFFIXES = {".csv", ".xlsx"}


def _read_bytes(upload: UploadFile) -> bytes:
    chunks: List[bytes] = []
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
    return b"".join(chunks)


def _read_tabular(path: Path, filename: str) -> pd.DataFrame:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=415,
            detail={"code": "UNSUPPORTED_FILE_TYPE", "message": "仅支持 .csv 或 .xlsx"},
        )
    if suffix == ".xlsx":
        return pd.read_excel(path)
    try:
        return pd.read_csv(path, encoding="utf-8-sig")
    except UnicodeDecodeError:
        try:
            return pd.read_csv(path, encoding="gbk")
        except UnicodeDecodeError:
            return pd.read_csv(path, encoding="utf-8", errors="replace")


def _audit_df(df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    """构造通用审计输入，返回审计表和 id_col。"""
    numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    if not numeric_cols:
        return pd.DataFrame(), ""
    id_col = next((c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c])), "")
    if not id_col:
        df = df.copy()
        df["__row_id__"] = range(len(df))
        id_col = "__row_id__"
    audit = AnomalyDetector().quality_report(df, numeric_cols, id_col=id_col)
    return audit, id_col


@router.post("", response_model=IngestResponse, status_code=200)
def ingest_quality_audit(upload: UploadFile) -> IngestResponse:
    if not settings.enable_write_endpoints:
        raise HTTPException(status_code=403, detail={"code": "WRITE_DISABLED", "message": "写接口已在服务端关闭"})

    filename = Path(upload.filename or "upload.csv").name
    settings.ensure_upload_dir()
    file_id = uuid4().hex
    saved_path = settings.upload_dir / f"{file_id}{Path(filename).suffix.lower() or '.csv'}"

    try:
        content = _read_bytes(upload)
        if not content:
            raise HTTPException(status_code=400, detail={"code": "EMPTY_FILE", "message": "上传文件为空"})
        saved_path.write_bytes(content)
        df = _read_tabular(saved_path, filename)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"code": "PARSE_ERROR", "message": f"文件解析失败: {exc}"})

    audit, _ = _audit_df(df)
    profile = DataCleaner.profile(df)

    coordinate_issues = 0
    if {"lng", "lat"}.issubset(set(df.columns)):
        try:
            coordinate_issues = int(
                AnomalyDetector.check_coordinates(df, lng_range=(-180.0, 180.0), lat_range=(-90.0, 90.0)).sum()
            )
        except Exception:
            coordinate_issues = 0

    audit_rows = []
    for row in audit.itertuples(index=False):
        audit_rows.append(
            AuditRow(
                column=row.column,
                n=int(row.n),
                missing=int(row.missing),
                missing_rate=float(row.missing_rate),
                iqr_outliers=list(row.iqr_outliers),
                zscore_outliers=list(row.zscore_outliers),
                iqr_lower=float(row.iqr_lower) if pd.notna(row.iqr_lower) else None,
                iqr_upper=float(row.iqr_upper) if pd.notna(row.iqr_upper) else None,
                flag=bool(row.flag),
                n_outliers=int(row.n_outliers),
            )
        )

    profile_rows = []
    for row in profile.itertuples(index=False):
        profile_rows.append(
            IngestProfileColumn(
                column=row.column,
                dtype=row.dtype,
                missing=int(row.missing),
                missing_rate=float(row.missing_rate),
                n_unique=int(row.n_unique),
                min=float(row.min) if pd.notna(row.min) else None,
                max=float(row.max) if pd.notna(row.max) else None,
            )
        )

    return IngestResponse(
        file_id=file_id,
        filename=filename,
        rows=int(len(df)),
        columns=int(df.shape[1]),
        profile=profile_rows,
        audit=audit_rows,
        coordinate_issues=coordinate_issues,
        message="通用质量体检完成：仅做缺失/类型/坐标/IQR-Z-score 审计，不计算领域指标 DHI/SSI/SMI。",
    )
