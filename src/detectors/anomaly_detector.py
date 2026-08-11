# -*- coding: utf-8 -*-
"""AnomalyDetector —— 数据质量与异常监控模块。

将 30 脚本中硬编码的 Z-score/IQR 校验逻辑独立为可复用类：
- IQR（四分位距）离群检测
- Z-score 离群检测
- 经纬度极值校验
- 一键生成数据质量审计表（quality_report）

定位：本项目为历史快照数据，"监控"以**可复用审计工具**形式提供——
输入任意锚点指标表，输出离群清单与质量报告，供 Dashboard「数据质量」页签使用。
"""
from __future__ import annotations

from typing import List, Optional

import numpy as np
import pandas as pd

# 哈尔滨市区及近郊经纬度合理范围（含松花江/哈西/伏尔加庄园等）
HARBIN_LNG_RANGE = (126.20, 127.20)
HARBIN_LAT_RANGE = (45.50, 46.10)


class AnomalyDetector:
    """数据质量与异常检测器。

    Parameters
    ----------
    iqr_multiplier : float
        IQR 离群阈值系数（Tukey 法则默认 1.5，1.5~3 为温和离群，>3 为极端离群）。
    z_threshold : float
        Z-score 离群阈值（默认 3.0）。
    """

    def __init__(self, iqr_multiplier: float = 1.5, z_threshold: float = 3.0) -> None:
        self.iqr_multiplier = iqr_multiplier
        self.z_threshold = z_threshold

    # ------------------------------------------------------------ 单列检测
    def detect_outliers_iqr(self, df: pd.DataFrame, col: str) -> pd.Series:
        """IQR 法离群掩码（True=离群）。数据右偏时效果优于 Z-score。"""
        s = pd.to_numeric(df[col], errors="coerce")
        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        iqr = q3 - q1
        if pd.isna(iqr) or iqr == 0:
            return pd.Series(False, index=df.index)
        lo, hi = q1 - self.iqr_multiplier * iqr, q3 + self.iqr_multiplier * iqr
        return s.lt(lo) | s.gt(hi)

    def detect_outliers_zscore(self, df: pd.DataFrame, col: str) -> pd.Series:
        """Z-score 法离群掩码（True=离群）。"""
        s = pd.to_numeric(df[col], errors="coerce")
        sd = s.std()
        if pd.isna(sd) or sd == 0:
            return pd.Series(False, index=df.index)
        z = (s - s.mean()).abs() / sd
        return z > self.z_threshold

    @staticmethod
    def check_coordinates(
        df: pd.DataFrame,
        lng_range: tuple = HARBIN_LNG_RANGE,
        lat_range: tuple = HARBIN_LAT_RANGE,
    ) -> pd.Series:
        """经纬度合理范围校验（True=异常/越界）。"""
        ok = (
            df["lng"].between(lng_range[0], lng_range[1])
            & df["lat"].between(lat_range[0], lat_range[1])
        )
        return ~ok

    # ------------------------------------------------------------ 质量审计
    def quality_report(
        self,
        df: pd.DataFrame,
        cols: Optional[List[str]] = None,
        id_col: str = "anchor_name",
        log_transform: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """生成数据质量审计表（每列一行）。

        Parameters
        ----------
        log_transform : list of str, optional
            高度右偏的列名列表（如设施数量、评论量）：先 log1p 变换再检测，
            避免 IQR 下界为负导致低端离群漏检。

        Returns
        -------
        pd.DataFrame
            列：column / n / missing_rate / iqr_outliers / zscore_outliers /
                iqr_lower / iqr_upper / flag。
            其中 iqr_outliers 为离群锚点名列表，flag 标记存在离群或缺失的列。
        """
        cols = cols or [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        log_transform = log_transform or []
        rows = []
        for c in cols:
            s = pd.to_numeric(df[c], errors="coerce")
            n = len(s)
            missing = int(s.isna().sum())
            if c in log_transform:
                s_log = np.log1p(s.clip(lower=0))
                mask_iqr = self.detect_outliers_iqr(
                    df.assign(**{c: s_log}), c
                )
                mask_z = self.detect_outliers_zscore(
                    df.assign(**{c: s_log}), c
                )
            else:
                mask_iqr = self.detect_outliers_iqr(df, c)
                mask_z = self.detect_outliers_zscore(df, c)
            iqr_names = df.loc[mask_iqr, id_col].tolist()
            z_names = df.loc[mask_z, id_col].tolist()
            q1, q3 = s.quantile(0.25), s.quantile(0.75)
            iqr = (q3 - q1) if not pd.isna(q3 - q1) else 0.0
            rows.append(
                {
                    "column": c,
                    "n": n,
                    "missing": missing,
                    "missing_rate": round(missing / n, 4) if n else 0.0,
                    "iqr_outliers": iqr_names,
                    "zscore_outliers": z_names,
                    "iqr_lower": round(q1 - self.iqr_multiplier * iqr, 4),
                    "iqr_upper": round(q3 + self.iqr_multiplier * iqr, 4),
                    "flag": bool(missing or iqr_names or z_names),
                }
            )
        report = pd.DataFrame(rows)
        report["n_outliers"] = report["iqr_outliers"].apply(len)
        report = report.sort_values(
            ["flag", "n_outliers"], ascending=[False, False]
        ).reset_index(drop=True)
        return report

    def outlier_anchors(self, df: pd.DataFrame, col: str) -> List[str]:
        """返回某列 IQR 离群锚点名单（用于 Dashboard 高亮展示）。"""
        return df.loc[self.detect_outliers_iqr(df, col), "anchor_name"].tolist()
