# -*- coding: utf-8 -*-
"""Pydantic V2 数据契约：API 请求/响应与领域模型。

领域实体（锚点、指标）只有这一套定义，API 路由直接复用。
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class WeightScheme(str, Enum):
    equal = "equal"
    entropy = "entropy"


class ComputeParamsRequest(BaseModel):
    scale_km: Literal[1, 3, 5] = 3
    method: WeightScheme = WeightScheme.equal
    smi_coef: Optional[Dict[str, float]] = Field(default=None, description="DHI/ERI/SSI 合成系数")


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


class ComputeResultResponse(BaseModel):
    method: str
    scale_km: int
    generated_at: str
    items: List[AnchorMetricItem]


class AnchorMeta(BaseModel):
    anchor_id: Optional[str] = None
    anchor_name: str
    anchor_type: Optional[str] = None
    lng: Optional[float] = None
    lat: Optional[float] = None
    confidence: Optional[str] = None


class AnchorListResponse(BaseModel):
    method: str
    count: int
    items: List[AnchorMetricItem]


class PainProfile(BaseModel):
    xhs_mentions: int
    xhs_negative_rate: float
    traffic_pain_rate: float
    queue_pain_rate: float
    cold_pain_rate: float
    price_pain_rate: float


class AnchorDetailResponse(BaseModel):
    anchor_name: str
    diagnosis: str
    strategy: str
    metrics: AnchorMetricItem
    pain_profile: Optional[PainProfile] = None
    dp_pressure: Optional[Dict[str, Any]] = None


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


class QualityAuditResponse(BaseModel):
    generated_at: str
    rows: List[AuditRow]


class PipelineRunRequest(BaseModel):
    method: WeightScheme = WeightScheme.equal
    force: bool = Field(default=False, description="已有任务运行时是否强制排队")


class PipelineRunAccepted(BaseModel):
    run_id: str
    status: str
    message: str
    queued: bool = False


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


class IngestProfileColumn(BaseModel):
    column: str
    dtype: str
    missing: int
    missing_rate: float
    n_unique: int
    min: Optional[float] = None
    max: Optional[float] = None


class IngestResponse(BaseModel):
    file_id: str
    filename: str
    rows: int
    columns: int
    profile: List[IngestProfileColumn]
    audit: List[AuditRow]
    coordinate_issues: int = 0
    message: str


class HealthResponse(BaseModel):
    status: str
    version: str
    components: Dict[str, Any]


class ErrorResponse(BaseModel):
    code: str
    message: str
    detail: Optional[Any] = None
