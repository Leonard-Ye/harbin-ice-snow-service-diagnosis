# -*- coding: utf-8 -*-
"""Pydantic V2 数据契约：API 请求/响应与领域模型。

领域实体（锚点、指标）只有这一套定义，API 路由直接复用。
每个对外模型均配置 json_schema_extra 示例，Swagger UI 可直接展示。
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class WeightScheme(str, Enum):
    equal = "equal"
    entropy = "entropy"


class ComputeParamsRequest(BaseModel):
    scale_km: Literal[1, 3, 5] = 3
    method: WeightScheme = WeightScheme.equal
    smi_coef: Optional[Dict[str, float]] = Field(default=None, description="DHI/ERI/SSI 合成系数")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "scale_km": 3,
                "method": "equal",
                "smi_coef": {"DHI": 1.0, "ERI": 1.0, "SSI": -1.0},
            }
        }
    )


class AnchorMetricItem(BaseModel):
    anchor_name: str
    lng: Optional[float] = None
    lat: Optional[float] = None
    DHI: float
    SSI: float
    ERI: float
    ERI_plus: float
    SMI: float
    mismatch_rank: int

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "anchor_name": "中央大街",
                "lng": 126.618916,
                "lat": 45.774014,
                "DHI": 1.095,
                "SSI": -1.858,
                "ERI": -0.355,
                "ERI_plus": -0.563,
                "SMI": 2.552,
                "mismatch_rank": 1,
            }
        }
    )


class ComputeResultResponse(BaseModel):
    method: str
    scale_km: int
    generated_at: str
    items: List[AnchorMetricItem]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "method": "equal",
                "scale_km": 3,
                "generated_at": "2026-08-16T22:00:00+08:00",
                "items": [
                    {
                        "anchor_name": "中央大街",
                        "lng": 126.618916,
                        "lat": 45.774014,
                        "DHI": 1.095,
                        "SSI": -1.858,
                        "ERI": -0.355,
                        "ERI_plus": -0.563,
                        "SMI": 2.552,
                        "mismatch_rank": 1,
                    }
                ],
            }
        }
    )


class AnchorMeta(BaseModel):
    anchor_id: Optional[str] = None
    anchor_name: str
    anchor_type: Optional[str] = None
    lng: Optional[float] = None
    lat: Optional[float] = None
    confidence: Optional[str] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "anchor_id": "A001",
                "anchor_name": "中央大街",
                "anchor_type": "POI",
                "lng": 126.618916,
                "lat": 45.774014,
                "confidence": "A",
            }
        }
    )


class AnchorListResponse(BaseModel):
    method: str
    count: int
    items: List[AnchorMetricItem]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "method": "equal",
                "count": 20,
                "items": [
                    {
                        "anchor_name": "中央大街",
                        "lng": 126.618916,
                        "lat": 45.774014,
                        "DHI": 1.095,
                        "SSI": -1.858,
                        "ERI": -0.355,
                        "ERI_plus": -0.563,
                        "SMI": 2.552,
                        "mismatch_rank": 1,
                    }
                ],
            }
        }
    )


class PainProfile(BaseModel):
    xhs_mentions: int
    xhs_negative_rate: float
    traffic_pain_rate: float
    queue_pain_rate: float
    cold_pain_rate: float
    price_pain_rate: float

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "xhs_mentions": 501,
                "xhs_negative_rate": 0.0209,
                "traffic_pain_rate": 0.0010,
                "queue_pain_rate": 0.0050,
                "cold_pain_rate": 0.0110,
                "price_pain_rate": 0.0010,
            }
        }
    )


class AnchorDetailResponse(BaseModel):
    anchor_name: str
    diagnosis: str
    strategy: str
    metrics: AnchorMetricItem
    pain_profile: Optional[PainProfile] = None
    dp_pressure: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "anchor_name": "中央大街",
                "diagnosis": "高需求—低供给型",
                "strategy": "优先补充短途接驳、临时游客服务点与防寒休憩空间。",
                "metrics": {
                    "anchor_name": "中央大街",
                    "lng": 126.618916,
                    "lat": 45.774014,
                    "DHI": 1.095,
                    "SSI": -1.858,
                    "ERI": -0.355,
                    "ERI_plus": -0.563,
                    "SMI": 2.552,
                    "mismatch_rank": 1,
                },
                "pain_profile": {
                    "xhs_mentions": 501,
                    "xhs_negative_rate": 0.0209,
                    "traffic_pain_rate": 0.0010,
                    "queue_pain_rate": 0.0050,
                    "cold_pain_rate": 0.0110,
                    "price_pain_rate": 0.0010,
                },
                "dp_pressure": {
                    "dp_review_count": 2094,
                    "dp_price_pressure": 0.429,
                    "dp_queue_pressure": 0.403,
                    "dp_service_pressure": 0.000,
                },
            }
        }
    )


class AuditRow(BaseModel):
    column: str
    n: int
    missing: int
    missing_rate: float
    iqr_outliers: List[str] = Field(default_factory=list)
    zscore_outliers: List[str] = Field(default_factory=list)
    iqr_lower: Optional[float] = None
    iqr_upper: Optional[float] = None
    flag: bool
    n_outliers: int

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "column": "ctrip_lodging_count",
                "n": 20,
                "missing": 0,
                "missing_rate": 0.0,
                "iqr_outliers": ["伏尔加庄园"],
                "zscore_outliers": [],
                "iqr_lower": -1596.25,
                "iqr_upper": 5147.75,
                "flag": True,
                "n_outliers": 1,
            }
        }
    )


class QualityAuditResponse(BaseModel):
    generated_at: str
    rows: List[AuditRow]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "generated_at": "2026-08-16T22:00:00+08:00",
                "rows": [
                    {
                        "column": "ctrip_lodging_count",
                        "n": 20,
                        "missing": 0,
                        "missing_rate": 0.0,
                        "iqr_outliers": ["伏尔加庄园"],
                        "zscore_outliers": [],
                        "iqr_lower": -1596.25,
                        "iqr_upper": 5147.75,
                        "flag": True,
                        "n_outliers": 1,
                    }
                ],
            }
        }
    )


class PipelineRunRequest(BaseModel):
    method: WeightScheme = WeightScheme.equal
    force: bool = Field(default=False, description="已有任务运行时是否强制排队")

    model_config = ConfigDict(
        json_schema_extra={"example": {"method": "equal", "force": False}}
    )


class PipelineRunAccepted(BaseModel):
    run_id: str
    status: str
    message: str
    queued: bool = False

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "run_id": "74d91ba050264527892eb0c9e8080c03",
                "status": "queued",
                "message": "任务已提交，请轮询 GET /api/v1/pipeline/runs/{run_id}",
                "queued": False,
            }
        }
    )


class PipelineRunStatus(BaseModel):
    run_id: str
    status: str
    method: str
    main_scale: int
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    duration_ms: Optional[int] = None
    error: Optional[str] = None
    artifacts: List[Dict[str, str]] = Field(default_factory=list)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "run_id": "74d91ba050264527892eb0c9e8080c03",
                "status": "succeeded",
                "method": "equal",
                "main_scale": 3,
                "started_at": "2026-08-16T22:00:00+08:00",
                "finished_at": "2026-08-16T22:00:01+08:00",
                "duration_ms": 820,
                "error": None,
                "artifacts": [
                    {"kind": "anchor_index", "path": "analysis/V30_Multi_Source_Fusion_R2/anchor_index_v22_04R2.csv", "sha256": "..."}
                ],
            }
        }
    )


class IngestProfileColumn(BaseModel):
    column: str
    dtype: str
    missing: int
    missing_rate: float
    n_unique: int
    min: Optional[float] = None
    max: Optional[float] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "column": "value",
                "dtype": "int64",
                "missing": 0,
                "missing_rate": 0.0,
                "n_unique": 8,
                "min": 1.0,
                "max": 100.0,
            }
        }
    )


class IngestResponse(BaseModel):
    file_id: str
    filename: str
    rows: int
    columns: int
    profile: List[IngestProfileColumn]
    audit: List[AuditRow]
    coordinate_issues: int = 0
    message: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "file_id": "5c19a5adb543420c80caf4f3bd07555f",
                "filename": "sample.csv",
                "rows": 8,
                "columns": 4,
                "profile": [
                    {
                        "column": "value",
                        "dtype": "int64",
                        "missing": 0,
                        "missing_rate": 0.0,
                        "n_unique": 8,
                        "min": 1.0,
                        "max": 100.0,
                    }
                ],
                "audit": [
                    {
                        "column": "value",
                        "n": 8,
                        "missing": 0,
                        "missing_rate": 0.0,
                        "iqr_outliers": ["g"],
                        "zscore_outliers": [],
                        "iqr_lower": -2.125,
                        "iqr_upper": 7.125,
                        "flag": True,
                        "n_outliers": 1,
                    }
                ],
                "coordinate_issues": 1,
                "message": "通用质量体检完成：仅做缺失/类型/坐标/IQR-Z-score 审计，不计算领域指标 DHI/SSI/SMI。",
            }
        }
    )


class HealthResponse(BaseModel):
    status: str
    version: str
    components: Dict[str, Any]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "ok",
                "version": "1.0.0",
                "components": {
                    "data": "ok",
                    "database": "ok",
                    "raw_data": "available",
                    "write_endpoints": True,
                },
            }
        }
    )


class ErrorResponse(BaseModel):
    code: str
    message: str
    detail: Optional[Any] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "code": "ANCHOR_NOT_FOUND",
                "message": "锚点不存在: 不存在的锚点",
                "detail": None,
            }
        }
    )
