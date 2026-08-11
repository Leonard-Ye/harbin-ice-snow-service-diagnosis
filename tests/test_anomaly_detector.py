# -*- coding: utf-8 -*-
"""AnomalyDetector 单元测试：IQR/Z-score 离群、边界与数据质量审计。"""
import numpy as np
import pandas as pd
import pytest

from src.detectors.anomaly_detector import AnomalyDetector


@pytest.fixture
def detector() -> AnomalyDetector:
    return AnomalyDetector()


def test_iqr_detects_high_and_low(detector):
    df = pd.DataFrame({"anchor_name": list("abcdefg"), "v": [1, 2, 2, 3, 3, 4, 100]})
    mask = detector.detect_outliers_iqr(df, "v")
    assert mask.iloc[-1], "高值 100 应为离群"
    assert not mask.iloc[:-1].any(), "其余点不应离群"


def test_zscore_detects_extreme(detector):
    # 小样本中单个极端值会被均值/标准差拉高，需足够极端才触发 z>3
    df = pd.DataFrame(
        {"anchor_name": [f"a{i}" for i in range(20)], "v": [0] * 19 + [100]}
    )
    mask = detector.detect_outliers_zscore(df, "v")
    assert mask.iloc[-1], "Z-score 应检出极端高值"


def test_constant_column_no_outlier(detector):
    df = pd.DataFrame({"anchor_name": ["a", "b", "c"], "v": [1, 1, 1]})
    assert not detector.detect_outliers_iqr(df, "v").any()
    assert not detector.detect_outliers_zscore(df, "v").any()


def test_missing_counted_in_report(detector):
    df = pd.DataFrame({"anchor_name": ["a", "b", "c"], "v": [1, None, 3]})
    rep = detector.quality_report(df, ["v"])
    assert rep.iloc[0]["missing"] == 1
    # quality_report 将缺失率 round 到 4 位
    assert rep.iloc[0]["missing_rate"] == pytest.approx(1 / 3, abs=1e-3)


def test_coordinate_out_of_range(detector):
    df = pd.DataFrame({"anchor_name": ["ok", "bad"], "lng": [126.6, 115.0], "lat": [45.75, 30.0]})
    assert detector.check_coordinates(df).tolist() == [False, True]


def test_log_transform_catches_right_skewed_low(detector):
    """右偏分布下 IQR 下界为负漏检，log1p 变换后应检出极端低值。"""
    rng = np.random.default_rng(42)
    vals = rng.lognormal(mean=6.0, sigma=0.6, size=20)
    vals[0] = 2.0  # 极端低值（如伏尔加庄园住宿）
    df = pd.DataFrame(
        {"anchor_name": [f"a{i}" for i in range(20)], "v": vals}
    )
    plain = detector.quality_report(df, ["v"])
    assert plain.iloc[0]["n_outliers"] == 0, "原始尺度 IQR 应漏检右偏低值"
    rep = detector.quality_report(df, ["v"], log_transform=["v"])
    assert "a0" in rep.iloc[0]["iqr_outliers"], "log1p 后应检出极端低值"


def test_report_sorted_by_flag(detector):
    df = pd.DataFrame(
        {
            "anchor_name": list("abcd"),
            "clean": [1, 2, 3, 4],
            "dirty": [1, 2, 3, 100],
        }
    )
    rep = detector.quality_report(df, ["clean", "dirty"])
    assert rep.iloc[0]["column"] == "dirty", "有离群的列应排前"
