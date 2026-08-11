# -*- coding: utf-8 -*-
"""MetricsEngine 单元测试：基线回归 / 熵权法 / 权重与半径可配置。"""
import os

import numpy as np
import pandas as pd
import pytest

from src.engines.metrics_engine import MetricsEngine, SUPPLY_COLS

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "02_多源融合数据及核心脚本",
    "V30_Multi_Source_Fusion_R2",
)
SCALE_FILE = os.path.join(DATA_DIR, "scale_sensitivity_1_3_5km_v22_04R2.csv")
BASELINE_FILE = os.path.join(DATA_DIR, "anchor_index_v22_04R2.csv")


@pytest.fixture(scope="module")
def scale_df() -> pd.DataFrame:
    return pd.read_csv(SCALE_FILE, encoding="utf-8-sig")


@pytest.fixture(scope="module")
def baseline() -> pd.DataFrame:
    return pd.read_csv(BASELINE_FILE, encoding="utf-8-sig")


METRIC_COLS = ["DHI", "SSI", "ERI", "ERI_plus", "SMI"]


def test_equal_matches_baseline(scale_df, baseline):
    """等权模式必须与 30 脚本基线（anchor_index_v22_04R2.csv）逐值一致。"""
    out = MetricsEngine(method="equal").compute_metrics(scale_df, scale_km=3)
    merged = out.merge(baseline, on="anchor_name", suffixes=("_n", "_b"))
    assert len(merged) == 20
    for col in METRIC_COLS:
        diff = (merged[f"{col}_n"] - merged[f"{col}_b"]).abs().max()
        assert diff < 1e-9, f"{col} 与基线不一致: {diff}"
    assert (merged["mismatch_rank_n"] == merged["mismatch_rank_b"]).all()


def test_entropy_weights_are_normalized(scale_df):
    w = MetricsEngine(method="entropy").get_weights(scale_df, 3)
    for grp, d in w.items():
        assert abs(sum(d.values()) - 1.0) < 1e-4, f"{grp} 权重和不为 1"


def test_entropy_constant_column_zero_weight():
    df = pd.DataFrame({"a": [1, 2, 3, 4], "b": [1, 1, 1, 1], "c": [10, 10, 10, 20]})
    w = MetricsEngine.entropy_weights(df, ["a", "b", "c"])
    assert w["b"] == 0.0, "常数列权重应为 0"
    assert w["c"] > w["a"], "离散度大的列权重应更高"


def test_supply_weights_configurable(scale_df):
    """自定义权重应改变 SSI 结果（与等权不同）。"""
    custom = {c: 1.0 for c in SUPPLY_COLS}
    custom["ctrip_lodging_count"] = 0.8  # 强化住宿
    custom["amap_medical_count"] = 0.2
    engine = MetricsEngine(supply_weights=custom)
    out = engine.compute_metrics(scale_df, 3)
    eq = MetricsEngine(method="equal").compute_metrics(scale_df, 3)
    diff = (out["SSI"] - eq["SSI"]).abs().max()
    assert diff > 0.01, "自定义权重未生效"


def test_main_scale_configurable(scale_df):
    """不同缓冲半径应产生不同的供给统计（进而 SSI 不同）。"""
    out3 = MetricsEngine().compute_metrics(scale_df, 3)
    out5 = MetricsEngine().compute_metrics(scale_df, 5)
    assert not out3["SSI"].equals(out5["SSI"]), "不同半径结果不应相同"


def test_invalid_method_raises():
    with pytest.raises(ValueError):
        MetricsEngine(method="unknown")


def test_missing_scale_raises(scale_df):
    with pytest.raises(ValueError):
        MetricsEngine().compute_metrics(scale_df, scale_km=99)


def test_smi_coef_configurable(scale_df):
    """SMI 系数可配置（默认 1/1/-1）。"""
    out_default = MetricsEngine().compute_metrics(scale_df, 3)
    out_custom = MetricsEngine(smi_coef={"DHI": 2.0, "ERI": 1.0, "SSI": -1.0}).compute_metrics(
        scale_df, 3
    )
    assert not out_default["SMI"].equals(out_custom["SMI"]), "SMI 系数未生效"
