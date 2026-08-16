# -*- coding: utf-8 -*-
"""私有全量数值回归：将新 Pipeline 输出与 V30 基线逐文件比对。

依赖本地原始数据（00_原始基座数据 / V25 / V27，均未入库）。
公开 CI 不应运行本脚本，请运行 tests/test_pipeline.py 的合成样本冒烟测试。

用法：
    python scripts/verify_v30_regression.py [--out-dir data/regression_out] [--tolerance 1e-9]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.pipeline.config import PipelineConfig  # noqa: E402
from src.pipeline.orchestrator import PipelineRunner  # noqa: E402

BASELINE = ROOT / "analysis" / "V30_Multi_Source_Fusion_R2"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=ROOT / "data" / "regression_out")
    parser.add_argument("--tolerance", type=float, default=1e-9)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cfg = PipelineConfig.from_toml(ROOT / "configs" / "pipeline.toml")
    cfg.out_dir = args.out_dir.resolve()
    result = PipelineRunner(cfg).run()
    if result.status != "succeeded":
        print(f"Pipeline 失败: {result.error}")
        return 2

    ok = True
    audit_cols = ["column", "n", "missing", "missing_rate", "iqr_lower", "iqr_upper", "flag", "n_outliers"]
    for name, filename in PipelineRunner.OUTPUT_NAMES.items():
        baseline_path = BASELINE / filename
        new_path = args.out_dir / filename
        if not baseline_path.exists() or not new_path.exists():
            print(f"缺少输出: baseline={baseline_path.exists()} new={new_path.exists()} -> {name}")
            ok = False
            continue
        b = pd.read_csv(baseline_path, encoding="utf-8-sig")
        n = pd.read_csv(new_path, encoding="utf-8-sig")

        if name == "quality_audit":
            same = b[audit_cols].equals(n[audit_cols])
            print(f"{name:24s} audit-core-equal={same}")
            ok = ok and same
            continue

        if b.shape != n.shape or b.columns.tolist() != n.columns.tolist():
            print(f"{name:24s} SHAPE/COLUMN DIFF")
            ok = False
            continue

        if b.equals(n):
            print(f"{name:24s} EXACT-EQUAL")
            continue

        numeric_cols = b.select_dtypes(include="number").columns.tolist()
        if numeric_cols:
            max_diff = (b[numeric_cols].astype(float) - n[numeric_cols].astype(float)).abs().max().max()
            passed = max_diff < args.tolerance
            print(f"{name:24s} numeric-max-diff={max_diff:.3e} pass={passed}")
            ok = ok and passed
        else:
            print(f"{name:24s} NOT-EQUAL (non-numeric)")
            ok = False

    print("REGRESSION", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
