# -*- coding: utf-8 -*-
"""PipelineRunner —— 多源数据自动化 Pipeline 编排器。

完整链路：
加载四源数据 → DataCleaner 清洗 → AnchorAligner 对齐
→ BufferAggregator 多尺度缓冲统计 → RiskCalculator 需求/痛点/餐饮压力
→ 合并 V30 底表 → AnomalyDetector 质量审计 → MetricsEngine 指标计算
→ 写出标准 CSV 产物 → SQLite RunStore 记录运行元数据与 SHA256。

equal 模式输出与 analysis/30_multi_source_fusion_v22_04R2.py 基线逐值一致。
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

import pandas as pd

from src.cleaning.data_cleaner import DataCleaner, CleaningConfig
from src.detectors.anomaly_detector import AnomalyDetector
from src.engines.metrics_engine import (
    METRIC_COLS,
    PAIN_RATE_COLS,
    SUPPLY_COLS,
    MetricsEngine,
)
from src.pipeline.anchor_aligner import AlignmentResult, AnchorAligner
from src.pipeline.buffer_aggregator import BufferAggregator
from src.pipeline.config import PipelineConfig, RawDataUnavailableError
from src.pipeline.risk import RiskCalculator
from src.storage.run_store import RunStore

# 与 dashboard 数据质量页签保持同一口径
AUDIT_COLS = SUPPLY_COLS + ["xhs_mentions", "dp_review_count"] + PAIN_RATE_COLS
LOG_COLS = SUPPLY_COLS + ["xhs_mentions", "dp_review_count"]


@dataclass
class PipelineRunResult:
    """一次 Pipeline 运行的可序列化结果。"""

    run_id: str
    status: str
    method: str
    main_scale: int
    started_at: str
    finished_at: str = ""
    duration_ms: int = 0
    out_dir: str = ""
    input_sha256: str = ""
    output_sha256: str = ""
    artifacts: List[Dict[str, str]] = field(default_factory=list)
    metrics_rows: int = 0
    error: Optional[str] = None
    store_error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "method": self.method,
            "main_scale": self.main_scale,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": self.duration_ms,
            "out_dir": self.out_dir,
            "input_sha256": self.input_sha256,
            "output_sha256": self.output_sha256,
            "artifacts": self.artifacts,
            "metrics_rows": self.metrics_rows,
            "error": self.error,
            "store_error": self.store_error,
        }


class PipelineRunner:
    """按配置执行完整自动化 Pipeline，并落盘 + 入库。"""

    OUTPUT_NAMES = {
        "excluded_terms": "excluded_terms_v22_04R2.csv",
        "anchor_master": "anchor_master_v22_04R2.csv",
        "supply_buffer": "supply_buffer_statistics_v22_04R2.csv",
        "xhs_risk": "xhs_demand_risk_statistics_v22_04R2.csv",
        "dp_risk": "dianping_pressure_statistics_v22_04R2.csv",
        "scale_base": "scale_sensitivity_1_3_5km_v22_04R2.csv",
        "base_3km": "anchor_supply_demand_base_v22_04R2.csv",
        "quality_audit": "data_quality_audit_v22_04R2.csv",
        "anchor_index": "anchor_index_v22_04R2.csv",
    }

    def __init__(self, config: PipelineConfig) -> None:
        self.config = config
        self.cleaner = DataCleaner(CleaningConfig(parity_mode=config.parity_mode))
        self.aligner = AnchorAligner()
        self.aggregator = BufferAggregator(scales=config.scales)
        self.risk = RiskCalculator()
        self.store = RunStore(config.db_path)
        self.store.initialize()

    # ---------------------------------------------------------------- 工具
    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    @staticmethod
    def _sha256_file(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()

    def _sha256_dict(self, paths: List[Path]) -> str:
        h = hashlib.sha256()
        for p in sorted(paths):
            h.update(p.name.encode("utf-8"))
            h.update(self._sha256_file(p).encode("utf-8"))
        return h.hexdigest()

    def _write_csv(self, df: pd.DataFrame, path: Path) -> str:
        df.to_csv(path, index=False, encoding="utf-8-sig")
        return self._sha256_file(path)

    # ---------------------------------------------------------------- 加载
    def load_inputs(self) -> Dict[str, pd.DataFrame]:
        missing = self.config.missing_inputs()
        if missing:
            names = ", ".join(str(p) for p in missing)
            raise RawDataUnavailableError(
                f"原始数据缺失，无法执行全量 Pipeline: {names}"
            )
        return {
            "xhs": pd.read_csv(self.config.xhs_path),
            "dp": pd.read_csv(self.config.dp_path),
            "amap": pd.read_csv(self.config.amap_path),
            "ctrip": pd.read_csv(self.config.ctrip_path),
        }


    def _persist_failure(self, run_id: str, started_ts: float, error: str) -> None:
        """失败任务也必须落库，保证 /pipeline/runs/{id} 可查询。"""
        try:
            self.store.finish_run(
                run_id=run_id,
                status="failed",
                finished_at=self._now(),
                duration_ms=int((time.monotonic() - started_ts) * 1000),
                input_sha256="",
                output_sha256="",
                error=error,
            )
        except Exception:
            pass

    # ---------------------------------------------------------------- 主流程
    def run(self, run_id: str | None = None) -> PipelineRunResult:
        """执行 Pipeline。``run_id`` 允许由外部 Job 队列指定，保证 API 契约一致。"""
        run_id = run_id or uuid4().hex
        started_at = self._now()
        result = PipelineRunResult(
            run_id=run_id,
            status="running",
            method=self.config.method,
            main_scale=self.config.main_scale,
            started_at=started_at,
        )
        started_ts = time.monotonic()

        try:
            self.store.start_run(
                run_id=run_id,
                method=self.config.method,
                main_scale=self.config.main_scale,
                config_dict=self._config_dict(),
                started_at=started_at,
            )
        except Exception as exc:  # DB 异常不应阻断 Pipeline
            result.store_error = str(exc)

        missing = self.config.missing_inputs()
        if missing:
            names = ", ".join(str(p) for p in missing)
            error = f"原始数据缺失，无法执行全量 Pipeline: {names}"
            self._persist_failure(run_id, started_ts, error)
            self.store.close()
            raise RawDataUnavailableError(error)

        input_paths = [
            self.config.xhs_path,
            self.config.dp_path,
            self.config.amap_path,
            self.config.ctrip_path,
        ]
        try:
            result.input_sha256 = self._sha256_dict(input_paths)
            data = self.load_inputs()
            outputs = self._execute(data, run_id)
            result.out_dir = str(self.config.out_dir)
            result.output_sha256 = self._sha256_dict(outputs)
            result.metrics_rows = int(
                pd.read_csv(outputs[-1], encoding="utf-8-sig").shape[0]
            )
            result.status = "succeeded"
            result.artifacts = [
                {
                    "kind": p.name.split("_v")[0],
                    "path": str(p),
                    "sha256": self._sha256_file(p),
                }
                for p in outputs
            ]
        except Exception as exc:
            result.status = "failed"
            result.error = str(exc)
            try:
                self.store.finish_run(
                    run_id=run_id,
                    status=result.status,
                    finished_at=self._now(),
                    duration_ms=int((time.monotonic() - started_ts) * 1000),
                    input_sha256=result.input_sha256,
                    output_sha256="",
                    error=result.error,
                )
            except Exception as store_exc:
                result.store_error = str(store_exc)
            self.store.close()
            return result

        result.finished_at = self._now()
        result.duration_ms = int((time.monotonic() - started_ts) * 1000)
        try:
            self.store.finish_run(
                run_id=run_id,
                status=result.status,
                finished_at=result.finished_at,
                duration_ms=result.duration_ms,
                input_sha256=result.input_sha256,
                output_sha256=result.output_sha256,
                error=None,
            )
            for artifact in result.artifacts:
                self.store.record_artifact(
                    run_id=run_id,
                    kind=artifact["kind"],
                    path=artifact["path"],
                    sha256=artifact["sha256"],
                    created_at=result.finished_at,
                )
        except Exception as exc:
            result.store_error = str(exc)
        self.store.close()
        return result

    def _config_dict(self) -> Dict[str, Any]:
        cfg = self.config
        return {
            "xhs_path": str(cfg.xhs_path),
            "dp_path": str(cfg.dp_path),
            "amap_path": str(cfg.amap_path),
            "ctrip_path": str(cfg.ctrip_path),
            "out_dir": str(cfg.out_dir),
            "db_path": str(cfg.db_path),
            "scales": cfg.scales,
            "main_scale": cfg.main_scale,
            "method": cfg.method,
            "parity_mode": cfg.parity_mode,
        }

    # ---------------------------------------------------------------- 步骤
    def _execute(self, data: Dict[str, pd.DataFrame], run_id: str) -> List[Path]:
        cfg = self.config
        cfg.out_dir.mkdir(parents=True, exist_ok=True)

        # 1) 清洗小红书地点列（parity 口径）
        xhs = self.cleaner.clean_location_text(data["xhs"], col="normalized_location")

        # 2) 锚点对齐
        alignment: AlignmentResult = self.aligner.align(xhs)

        # 3) 多尺度缓冲供给统计
        supply = self.aggregator.compute(alignment.master, data["amap"], data["ctrip"])

        # 4) 需求 / 痛点 / 餐饮压力
        anchor_names = alignment.master["anchor_name"].tolist()
        xhs_risk = self.risk.compute_xhs_risk(alignment.valid, anchor_names)
        dp_risk = self.risk.compute_dp_risk(data["dp"], anchor_names)

        # 5) 合并 V30 多尺度底表
        merged = []
        for scale in cfg.scales:
            sup_scale = supply[supply["scale_km"] == scale]
            m1 = pd.merge(alignment.master, sup_scale, on="anchor_name")
            m2 = pd.merge(m1, xhs_risk, on="anchor_name")
            merged.append(pd.merge(m2, dp_risk, on="anchor_name"))
        scale_base = pd.concat(merged)
        base_3km = scale_base[scale_base["scale_km"] == cfg.main_scale].copy()

        # 6) 写中间产物
        outputs: List[Path] = []
        for key, df, fmt in [
            ("excluded_terms", alignment.excluded_terms, None),
            ("anchor_master", alignment.master, None),
            ("supply_buffer", supply, None),
            ("xhs_risk", xhs_risk, None),
            ("dp_risk", dp_risk, None),
            ("scale_base", scale_base, None),
            ("base_3km", base_3km, None),
        ]:
            path = cfg.out_dir / self.OUTPUT_NAMES[key]
            self._write_csv(df, path)
            outputs.append(path)

        # 7) 数据质量审计
        audit = AnomalyDetector().quality_report(
            scale_base[scale_base["scale_km"] == cfg.main_scale],
            cols=AUDIT_COLS,
            log_transform=LOG_COLS,
        )
        audit_for_csv = audit.copy()
        audit_for_csv["iqr_outliers"] = audit_for_csv["iqr_outliers"].apply(
            lambda x: json.dumps(x, ensure_ascii=False)
        )
        audit_for_csv["zscore_outliers"] = audit_for_csv["zscore_outliers"].apply(
            lambda x: json.dumps(x, ensure_ascii=False)
        )
        audit_path = cfg.out_dir / self.OUTPUT_NAMES["quality_audit"]
        self._write_csv(audit_for_csv, audit_path)
        outputs.append(audit_path)

        # 8) 指标计算
        engine = MetricsEngine(method=cfg.method, main_scale=cfg.main_scale)
        metrics = engine.compute_metrics(scale_base, scale_km=cfg.main_scale)
        index_path = cfg.out_dir / self.OUTPUT_NAMES["anchor_index"]
        self._write_csv(metrics, index_path)
        outputs.append(index_path)

        # 9) 入库快照
        try:
            self.store.record_metric_snapshots(run_id, metrics, cfg.main_scale)
            self.store.record_anomaly_events(run_id, audit, scale_base, cfg.method)
        except Exception:
            # 入库失败不阻断产物生成；由 run() 的 store_error 语义覆盖主表
            pass
        return outputs
