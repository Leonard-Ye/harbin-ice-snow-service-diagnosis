# -*- coding: utf-8 -*-
"""API 服务层：把领域模块组合为可返回的 JSON 安全数据。"""
from __future__ import annotations

import math
from typing import Any, Dict, List

import pandas as pd

from dashboard.report_builders import build_audit_df, build_excel_bytes, build_html_summary
from dashboard.pdf_report import build_visual_pdf_bytes
from dashboard.dashboard_data import (
    PAIN_CN,
    add_diagnosis,
    full_table,
    get_weight_sets,
    load_master,
    load_scale,
    strategy_for,
)
from src.detectors.anomaly_detector import AnomalyDetector
from src.engines.metrics_engine import PAIN_RATE_COLS, SUPPLY_COLS, MetricsEngine
from src.pipeline.orchestrator import AUDIT_COLS, LOG_COLS


def _clean(v: Any) -> Any:
    """把 numpy/pandas 类型转换为 JSON 安全的 Python 类型。"""
    if isinstance(v, (int, float)) and math.isfinite(float(v)):
        return int(v) if isinstance(v, (int,)) else float(v)
    if isinstance(v, list):
        return [_clean(x) for x in v]
    if isinstance(v, dict):
        return {k: _clean(x) for k, x in v.items()}
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v


def get_table(method: str) -> pd.DataFrame:
    return add_diagnosis(full_table(method=method))


def metric_items(df: pd.DataFrame) -> List[Dict[str, Any]]:
    cols = ["anchor_name", "lng", "lat", "DHI", "SSI", "ERI", "ERI_plus", "SMI", "mismatch_rank"]
    records = df[cols].to_dict(orient="records")
    return [_clean(r) for r in records]


def calculate_metrics(
    scale_km: int = 3,
    method: str = "equal",
    smi_coef: Dict[str, float] | None = None,
) -> List[Dict[str, Any]]:
    engine = MetricsEngine(method=method, smi_coef=smi_coef)
    out = engine.compute_metrics(load_scale(), scale_km=scale_km)
    return metric_items(out)


def list_anchor_meta() -> List[Dict[str, Any]]:
    master = load_master()
    records = master[
        ["anchor_id", "anchor_name", "anchor_type", "lng", "lat", "confidence"]
    ].to_dict(orient="records")
    return [_clean(r) for r in records]


def anchor_detail(anchor_name: str, method: str) -> Dict[str, Any]:
    df = get_table(method)
    sub = df[df["anchor_name"] == anchor_name]
    if sub.empty:
        raise KeyError(anchor_name)
    row = sub.iloc[0]
    pain = {
        "xhs_mentions": int(row["xhs_mentions"]),
        "xhs_negative_rate": float(row["xhs_negative_rate"]),
    }
    for col in PAIN_RATE_COLS:
        pain[col] = float(row[col])
    dp = {
        "dp_review_count": int(row["dp_review_count"]),
        "dp_price_pressure": float(row["dp_price_pressure"]),
        "dp_queue_pressure": float(row["dp_queue_pressure"]),
        "dp_service_pressure": float(row["dp_service_pressure"]),
    }
    return {
        "anchor_name": anchor_name,
        "diagnosis": row["diagnosis"],
        "strategy": strategy_for(row["diagnosis"]),
        "metrics": {
            "anchor_name": anchor_name,
            "lng": _clean(row.get("lng")),
            "lat": _clean(row.get("lat")),
            "DHI": float(row["DHI"]),
            "SSI": float(row["SSI"]),
            "ERI": float(row["ERI"]),
            "ERI_plus": float(row["ERI_plus"]),
            "SMI": float(row["SMI"]),
            "mismatch_rank": int(row["mismatch_rank"]),
        },
        "pain_profile": pain,
        "dp_pressure": dp,
    }


def quality_audit_rows() -> List[Dict[str, Any]]:
    """结构化质量审计（保留离群名单为 list）。"""
    scale3 = load_scale()
    scale3 = scale3[scale3["scale_km"] == 3].copy()
    audit = AnomalyDetector().quality_report(scale3, AUDIT_COLS, log_transform=LOG_COLS)
    records = []
    for row in audit.itertuples(index=False):
        records.append(
            {
                "column": row.column,
                "n": int(row.n),
                "missing": int(row.missing),
                "missing_rate": float(row.missing_rate),
                "iqr_outliers": list(row.iqr_outliers),
                "zscore_outliers": list(row.zscore_outliers),
                "iqr_lower": _clean(row.iqr_lower),
                "iqr_upper": _clean(row.iqr_upper),
                "flag": bool(row.flag),
                "n_outliers": int(row.n_outliers),
            }
        )
    return records


def weight_sets(method: str) -> Dict[str, Dict[str, float]]:
    return get_weight_sets(method)


def report_excel(method: str) -> bytes:
    df = get_table(method)
    return build_excel_bytes(df, method)


def report_pdf(method: str) -> bytes:
    df = get_table(method)
    return build_visual_pdf_bytes(df, method)


def report_html(method: str) -> str:
    df = get_table(method)
    return build_html_summary(df, method)
