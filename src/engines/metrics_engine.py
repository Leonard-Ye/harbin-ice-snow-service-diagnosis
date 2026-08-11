# -*- coding: utf-8 -*-
"""MetricsEngine —— 供需诊断指标计算引擎。

将原 30_multi_source_fusion_v22_04R2.py 中硬编码的指标计算解耦为可配置类：

- 输入：V30 多尺度聚合表（含各缓冲半径的设施数量、小红书需求/痛点原始率、大众点评压力率）
- 输出：DHI / SSI / ERI / ERI_plus / SMI 五项指标与错配排名
- 可配置：主分析缓冲半径（默认 3km）、各类指标权重（默认等权）

计算口径与 30 脚本逐值一致（log1p 转换 + 稳健 Z-score 标准化 + 平滑触发率），
重构后输出与 V30 基线（anchor_index_v22_04R2.csv）可做数值回归验证。
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

# 六类供给设施（SSI 输入，含购物/医疗两个补充维度）
SUPPLY_COLS = [
    "ctrip_lodging_count",
    "amap_dining_count",
    "amap_transport_count",
    "amap_public_count",
    "amap_shopping_count",
    "amap_medical_count",
]
# 四类小红书痛点触发率（ERI 输入）
PAIN_RATE_COLS = [
    "traffic_pain_rate",
    "queue_pain_rate",
    "cold_pain_rate",
    "price_pain_rate",
]
# 大众点评压力率（ERI_plus 输入）
DP_PRESSURE_COLS = [
    "dp_queue_pressure",
    "dp_price_pressure",
    "dp_service_pressure",
]

METRIC_COLS = ["DHI", "SSI", "ERI", "ERI_plus", "SMI"]


class MetricsEngine:
    """多源供需诊断指标引擎。

    Parameters
    ----------
    supply_weights : dict, optional
        SSI 六类设施权重，键为 SUPPLY_COLS 中的列名，默认 None（等权 1/6）。
    eri_weights : dict, optional
        ERI 五维权重（负面占比 + 四类痛点），键：xhs_negative_rate + PAIN_RATE_COLS，
        默认 None（等权 1/5）。
    dp_weights : dict, optional
        ERI_plus 中大众点评三维权重，键为 DP_PRESSURE_COLS，默认 None（等权）。
    main_scale : int
        主分析缓冲半径（km），默认 3。
    method : {"equal", "entropy"}
        指标内部权重方案。equal = 等权（与 30 脚本基线逐值一致）；
        entropy = 熵权法，基于样本离散度客观赋权（数据驱动，仅适用于同向指标）。
    smi_coef : dict, optional
        SMI 合成系数（结构性：需求/风险为正项、供给为缓解项），
        键 DHI/ERI/SSI，默认 {"DHI": 1.0, "ERI": 1.0, "SSI": -1.0}。
    """

    def __init__(
        self,
        supply_weights: Optional[Dict[str, float]] = None,
        eri_weights: Optional[Dict[str, float]] = None,
        dp_weights: Optional[Dict[str, float]] = None,
        main_scale: int = 3,
        method: str = "equal",
        smi_coef: Optional[Dict[str, float]] = None,
    ) -> None:
        if method not in ("equal", "entropy"):
            raise ValueError("method 仅支持 'equal' 或 'entropy'")
        self.method = method
        self.main_scale = main_scale
        self.smi_coef = {"DHI": 1.0, "ERI": 1.0, "SSI": -1.0}
        if smi_coef:
            self.smi_coef.update(smi_coef)
        # equal 模式下的显式权重（entropy 模式运行时从数据计算，忽略此处）
        self.supply_weights = self._normalize_weights(supply_weights, SUPPLY_COLS)
        self.eri_weights = self._normalize_weights(
            eri_weights, ["xhs_negative_rate"] + PAIN_RATE_COLS
        )
        self.dp_weights = self._normalize_weights(dp_weights, DP_PRESSURE_COLS)

    # ------------------------------------------------------------ 工具方法
    @staticmethod
    def _normalize_weights(
        weights: Optional[Dict[str, float]], cols: List[str]
    ) -> Dict[str, float]:
        """将部分权重补全为对 cols 的归一化权重（缺失列自动取等权）。"""
        if weights is None:
            return {c: 1.0 / len(cols) for c in cols}
        missing = [c for c in cols if c not in weights]
        fill = (1.0 - sum(weights.values())) / len(missing) if missing else 0.0
        return {c: weights.get(c, fill) for c in cols}

    @staticmethod
    def entropy_weights(df: pd.DataFrame, cols: List[str]) -> Dict[str, float]:
        """熵权法客观赋权（仅适用于同向正向指标列）。

        步骤：min-max 归一化 → 信息熵 → 差异系数 → 权重。
        常数列（无信息量）权重自动为 0；全部为常数时回退等权避免除零。
        权重保留 6 位小数，和为 1。
        """
        x = df[cols].apply(pd.to_numeric, errors="coerce").dropna(how="all")
        if x.empty:
            return {c: 1.0 / len(cols) for c in cols}
        xmin, xmax = x.min(), x.max()
        span = (xmax - xmin).replace(0, np.nan)
        norm = (x - xmin) / span
        norm = norm.fillna(0.0)  # 常数/缺失列归一化记 0
        valid = norm.sum() > 0  # 有效列（有信息量）；常数列视为无效
        p = norm / norm.sum().where(valid, np.nan)
        p = p.fillna(0.0)
        # 0*log(0) 约定为 0：log 中 0 替换为 NaN 再回填
        logp = np.log(p.replace(0, np.nan)).fillna(0.0)
        contrib = (p * logp).fillna(0.0)
        n = len(p)
        ent = -(contrib.sum(axis=0)) / np.log(n)
        ent = ent.where(valid, 1.0)  # 常数列熵=1（无信息量）
        diff = (1 - ent).clip(lower=0.0)
        s = diff.sum()
        if s == 0 or pd.isna(s):
            return {c: 1.0 / len(cols) for c in cols}
        w = diff / s
        return w.round(6).to_dict()

    def _resolve_weights(self, d: pd.DataFrame):
        """按 method 解析三组权重（entropy 模式下由数据动态计算）。"""
        if self.method == "entropy":
            return (
                self.entropy_weights(d, SUPPLY_COLS),
                self.entropy_weights(d, ["xhs_negative_rate"] + PAIN_RATE_COLS),
                self.entropy_weights(d, DP_PRESSURE_COLS),
            )
        return self.supply_weights, self.eri_weights, self.dp_weights

    def get_weights(
        self, scale_df: pd.DataFrame, scale_km: Optional[int] = None
    ) -> Dict[str, Dict[str, float]]:
        """返回当前 method 下的三组权重（供 Dashboard 展示与等权/熵权对比）。"""
        scale_km = scale_km or self.main_scale
        d = scale_df[scale_df["scale_km"] == scale_km]
        sw, ew, dw = self._resolve_weights(d)
        return {"supply": sw, "eri": ew, "dp": dw}

    @staticmethod
    def zscore(s: pd.Series) -> pd.Series:
        """稳健 Z-score：标准差为 0 或缺失时返回全 0（与 30 脚本 safe_zscore 一致）。"""
        sd = s.std()
        if pd.isna(sd) or sd == 0:
            return pd.Series(np.zeros(len(s)), index=s.index)
        return (s - s.mean()) / sd

    @staticmethod
    def _log1p_z(col: pd.Series) -> pd.Series:
        return MetricsEngine.zscore(np.log1p(col))

    # ------------------------------------------------------------ 指标计算
    def compute_metrics(self, scale_df: pd.DataFrame, scale_km: Optional[int] = None) -> pd.DataFrame:
        """在指定缓冲半径上计算五指标与错配排名。

        Parameters
        ----------
        scale_df : pd.DataFrame
            V30 多尺度聚合表（scale_sensitivity_1_3_5km_v22_04R2.csv 或等价结构）。
        scale_km : int, optional
            使用的缓冲半径，默认取 self.main_scale。

        Returns
        -------
        pd.DataFrame
            按 SMI 降序排列，含 anchor_name/lng/lat 与 DHI/SSI/ERI/ERI_plus/SMI/mismatch_rank。
        """
        scale_km = scale_km or self.main_scale
        d = scale_df[scale_df["scale_km"] == scale_km].copy()
        if d.empty:
            raise ValueError(f"scale_df 中不存在 scale_km={scale_km} 的记录")

        supply_w, eri_w, dp_w = self._resolve_weights(d)

        # DHI：需求热度（小红书提及频次，log1p + Z-score）
        d["DHI"] = self._log1p_z(d["xhs_mentions"])

        # SSI：六类设施数量 log1p + Z-score，按权重合成
        z_supply = pd.DataFrame(
            {c: self._log1p_z(d[c]) for c in SUPPLY_COLS}, index=d.index
        )
        d["SSI"] = sum(z_supply[c] * w for c, w in supply_w.items())

        # ERI：负面占比 + 四类痛点触发率 Z-score，按权重合成
        z_neg = self.zscore(d["xhs_negative_rate"])
        z_pains = pd.DataFrame(
            {c: self.zscore(d[c]) for c in PAIN_RATE_COLS}, index=d.index
        )
        d["ERI"] = (
            z_neg * eri_w["xhs_negative_rate"]
            + sum(z_pains[c] * eri_w[c] for c in PAIN_RATE_COLS)
        )

        # ERI_plus：30 脚本口径为 (ERI + z_dp_q + z_dp_p + z_dp_s) / 4，
        # 即 ERI 与三个 dp 项共 4 项均分；dp 三者的相对权重由 dp_w 决定。
        n_dp = len(dp_w)  # 3
        s_dp = sum(dp_w.values())
        z_dp = pd.DataFrame(
            {c: self.zscore(d[c]) for c in DP_PRESSURE_COLS}, index=d.index
        )
        d["ERI_plus"] = (
            d["ERI"] * (1.0 / (1 + n_dp))
            + sum(z_dp[c] * (w / s_dp) * (n_dp / (1 + n_dp)) for c, w in dp_w.items())
        )

        # SMI：对 DHI/ERI/SSI 再次标准化，需求与风险为正项、供给为缓解项（系数可配）
        d["SMI"] = (
            self.smi_coef["DHI"] * self.zscore(d["DHI"])
            + self.smi_coef["ERI"] * self.zscore(d["ERI"])
            + self.smi_coef["SSI"] * self.zscore(d["SSI"])
        )
        d = d.sort_values("SMI", ascending=False)
        d["mismatch_rank"] = range(1, len(d) + 1)

        out_cols = [
            "anchor_name",
            "lng",
            "lat",
            "DHI",
            "SSI",
            "ERI",
            "ERI_plus",
            "SMI",
            "mismatch_rank",
        ]
        return d[out_cols].reset_index(drop=True)

    def compute_scale_profile(self, scale_df: pd.DataFrame) -> pd.DataFrame:
        """多尺度（1/3/5km）供给概览：各锚点在不同缓冲半径下的设施数量。

        用于数据质量页签的多尺度稳定性观察（某锚点在 1km 与 3km 间供给
        剧烈变化时，提示缓冲半径选择敏感性）。
        """
        cols = ["anchor_name", "scale_km"] + SUPPLY_COLS
        d = scale_df[cols].copy()
        d["supply_total"] = d[SUPPLY_COLS].sum(axis=1)
        d["lodging_only"] = d["ctrip_lodging_count"]
        return d
