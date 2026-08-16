# -*- coding: utf-8 -*-
"""通用单表质量体检服务：API 与 Streamlit 共用同一实现。

范围：缺失/类型画像、经纬度合法性、IQR/Z-score 离群审计。
不执行文旅锚点对齐与 DHI/SSI/SMI 领域指标计算。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4

import pandas as pd

from src.cleaning.data_cleaner import DataCleaner
from src.detectors.anomaly_detector import AnomalyDetector

ALLOWED_SUFFIXES = {".csv", ".xlsx"}


class TableAuditError(Exception):
    """表格体检业务异常。"""


def _read_tabular(path: Path, filename: str) -> pd.DataFrame:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise TableAuditError("UNSUPPORTED_FILE_TYPE: 仅支持 .csv 或 .xlsx")
    try:
        if suffix == ".xlsx":
            return pd.read_excel(path)
        try:
            return pd.read_csv(path, encoding="utf-8-sig")
        except UnicodeDecodeError:
            try:
                return pd.read_csv(path, encoding="gbk")
            except UnicodeDecodeError:
                return pd.read_csv(path, encoding="utf-8", errors="replace")
    except TableAuditError:
        raise
    except Exception as exc:
        raise TableAuditError(f"PARSE_ERROR: {exc}") from exc


def audit_dataframe(df: pd.DataFrame) -> Dict[str, Any]:
    """对已读取的 DataFrame 执行画像 + 离群 + 坐标审计。"""
    numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    if not numeric_cols:
        audit = pd.DataFrame(
            columns=["column", "n", "missing", "missing_rate", "iqr_outliers",
                     "zscore_outliers", "iqr_lower", "iqr_upper", "flag", "n_outliers"]
        )
    else:
        id_col = next((c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c])), "")
        if not id_col:
            df = df.copy()
            df["__row_id__"] = range(len(df))
            id_col = "__row_id__"
        audit = AnomalyDetector().quality_report(df, numeric_cols, id_col=id_col)

    profile = DataCleaner.profile(df)

    coordinate_issues = 0
    if {"lng", "lat"}.issubset(set(df.columns)):
        try:
            coordinate_issues = int(
                AnomalyDetector.check_coordinates(
                    df,
                    lng_range=(-180.0, 180.0),
                    lat_range=(-90.0, 90.0),
                ).sum()
            )
        except Exception:
            coordinate_issues = 0

    audit_rows: List[Dict[str, Any]] = []
    for row in audit.itertuples(index=False):
        audit_rows.append(
            {
                "column": row.column,
                "n": int(row.n),
                "missing": int(row.missing),
                "missing_rate": float(row.missing_rate),
                "iqr_outliers": list(row.iqr_outliers),
                "zscore_outliers": list(row.zscore_outliers),
                "iqr_lower": float(row.iqr_lower) if pd.notna(row.iqr_lower) else None,
                "iqr_upper": float(row.iqr_upper) if pd.notna(row.iqr_upper) else None,
                "flag": bool(row.flag),
                "n_outliers": int(row.n_outliers),
            }
        )

    profile_rows: List[Dict[str, Any]] = []
    for row in profile.itertuples(index=False):
        profile_rows.append(
            {
                "column": row.column,
                "dtype": row.dtype,
                "missing": int(row.missing),
                "missing_rate": float(row.missing_rate),
                "n_unique": int(row.n_unique),
                "min": float(row.min) if pd.notna(row.min) else None,
                "max": float(row.max) if pd.notna(row.max) else None,
            }
        )

    return {
        "rows": int(len(df)),
        "columns": int(df.shape[1]),
        "profile": profile_rows,
        "audit": audit_rows,
        "coordinate_issues": coordinate_issues,
        "message": "通用质量体检完成：仅做缺失/类型/坐标/IQR-Z-score 审计，不计算领域指标 DHI/SSI/SMI。",
    }


def audit_tabular_bytes(filename: str, content: bytes, upload_dir: Path) -> Dict[str, Any]:
    """保存上传字节并执行通用体检，返回结构化结果。"""
    if not content:
        raise TableAuditError("EMPTY_FILE: 上传文件为空")
    file_id = uuid4().hex
    suffix = Path(filename).suffix.lower() or ".csv"
    upload_dir.mkdir(parents=True, exist_ok=True)
    saved_path = upload_dir / f"{file_id}{suffix}"
    saved_path.write_bytes(content)
    try:
        df = _read_tabular(saved_path, filename)
        result = audit_dataframe(df)
    except Exception:
        saved_path.unlink(missing_ok=True)
        raise
    result["file_id"] = file_id
    result["filename"] = Path(filename).name
    return result
