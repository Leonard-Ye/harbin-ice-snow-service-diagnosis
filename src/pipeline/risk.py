# -*- coding: utf-8 -*-
"""RiskCalculator —— 小红书需求/痛点与大众点评餐饮压力统计。

与 30_multi_source_fusion_v22_04R2.py 保持逐值一致：
- 负面率与四类痛点触发率采用平滑公式 (count + 0.5) / (mentions + 1)
- 痛点关键词命中、大众点评列自动识别与阈值口径原样保留
"""
from __future__ import annotations

from typing import Iterable, List

import pandas as pd

PAIN_KEYWORDS = {
    "traffic": ["交通", "车", "路", "堵"],
    "queue": ["排队", "人多", "挤", "等"],
    "cold": ["冷", "寒", "冻", "气温"],
    "price": ["价格", "贵", "坑", "宰客"],
}


class RiskCalculator:
    """计算各锚点的需求风险与餐饮压力指标。"""

    @staticmethod
    def _contains_any(value, keywords: List[str]) -> bool:
        if pd.isna(value):
            return False
        text = str(value)
        return any(k in text for k in keywords)

    def compute_xhs_risk(
        self,
        valid_xhs: pd.DataFrame,
        anchor_names: Iterable[str],
    ) -> pd.DataFrame:
        """按锚点统计小红书提及量、负面占比与四类痛点触发率。"""
        rows = []
        for anchor in anchor_names:
            subset = valid_xhs[valid_xhs["standard_anchor"] == anchor]
            mentions = len(subset)

            neg_count = len(subset[subset["Sentiment"] == -1])
            neg_rate = (neg_count + 0.5) / (mentions + 1)

            traffic = int(
                subset["PainPoints"].apply(
                    lambda x: self._contains_any(x, PAIN_KEYWORDS["traffic"])
                ).sum()
            )
            queue = int(
                subset["PainPoints"].apply(
                    lambda x: self._contains_any(x, PAIN_KEYWORDS["queue"])
                ).sum()
            )
            cold = int(
                subset["PainPoints"].apply(
                    lambda x: self._contains_any(x, PAIN_KEYWORDS["cold"])
                ).sum()
            )
            price = int(
                subset["PainPoints"].apply(
                    lambda x: self._contains_any(x, PAIN_KEYWORDS["price"])
                ).sum()
            )

            rows.append(
                {
                    "anchor_name": anchor,
                    "xhs_mentions": mentions,
                    "xhs_heat_proxy": mentions,
                    "xhs_negative_rate": neg_rate,
                    "traffic_pain_rate": (traffic + 0.5) / (mentions + 1),
                    "queue_pain_rate": (queue + 0.5) / (mentions + 1),
                    "cold_pain_rate": (cold + 0.5) / (mentions + 1),
                    "price_pain_rate": (price + 0.5) / (mentions + 1),
                }
            )
        return pd.DataFrame(rows)

    def compute_dp_risk(
        self,
        dp_df: pd.DataFrame,
        anchor_names: Iterable[str],
        dp_anchor_map=None,
        find_dp_areas=None,
    ) -> pd.DataFrame:
        """按锚点统计大众点评价格/排队/服务压力。

        ``find_dp_areas`` 与 ``dp_anchor_map`` 允许由 AnchorAligner 注入；
        默认直接使用 AnchorAligner 的常量与静态方法，避免重复定义。
        """
        if find_dp_areas is None or dp_anchor_map is None:
            from src.pipeline.anchor_aligner import AnchorAligner

            find_dp_areas = AnchorAligner.find_dp_areas

        dp_cols = dp_df.columns.tolist()
        area_col = [c for c in dp_cols if "商圈" in str(c) or "景区" in str(c)]
        price_col = [c for c in dp_cols if "元" in str(c) or "均" in str(c)]
        queue_col = [c for c in dp_cols if "队" in str(c)]
        service_col = [c for c in dp_cols if "服务" in str(c)]

        area_col = area_col[0] if area_col else dp_cols[3]
        price_col = price_col[0] if price_col else dp_cols[4]
        queue_col = queue_col[0] if queue_col else dp_cols[10]
        service_col = service_col[0] if service_col else dp_cols[11]

        rows = []
        for anchor in anchor_names:
            target_areas = find_dp_areas(anchor)
            subset = (
                dp_df[dp_df[area_col].isin(target_areas)]
                if target_areas
                else pd.DataFrame()
            )

            if len(subset) == 0:
                subset = dp_df[dp_df[area_col].astype(str).str.contains(anchor, na=False)]

            mentions = len(subset)
            if mentions > 0:
                prices = pd.to_numeric(subset[price_col], errors="coerce").fillna(0)
                queues = pd.to_numeric(subset[queue_col], errors="coerce").fillna(0)
                services = pd.to_numeric(subset[service_col], errors="coerce").fillna(5.0)

                rows.append(
                    {
                        "anchor_name": anchor,
                        "dp_review_count": mentions,
                        "dp_price_pressure": (len(prices[prices > 100]) + 0.5) / (mentions + 1),
                        "dp_queue_pressure": (len(queues[queues > 30]) + 0.5) / (mentions + 1),
                        "dp_service_pressure": (len(services[services < 3.5]) + 0.5) / (mentions + 1),
                    }
                )
            else:
                rows.append(
                    {
                        "anchor_name": anchor,
                        "dp_review_count": 0,
                        "dp_price_pressure": 0.0,
                        "dp_queue_pressure": 0.0,
                        "dp_service_pressure": 0.0,
                    }
                )
        return pd.DataFrame(rows)
