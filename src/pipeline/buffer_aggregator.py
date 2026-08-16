# -*- coding: utf-8 -*-
"""BufferAggregator —— BallTree 多尺度缓冲圈统计模块。

与 30_multi_source_fusion_v22_04R2.py 保持逐值一致，包括：
- 高德/携程坐标列读取口径（携程取第 2、3 列）
- haversine BallTree
- 1/3/5km 缓冲半径
- 六类高德设施 + 携程住宿数量统计
"""
from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

EARTH_RADIUS_KM = 6371.0

AMAP_CATEGORY_TO_COLUMN = {
    "住宿服务": "amap_lodging_count_optional",
    "餐饮服务": "amap_dining_count",
    "交通设施服务": "amap_transport_count",
    "公共设施": "amap_public_count",
    "购物服务": "amap_shopping_count",
    "医疗保健服务": "amap_medical_count",
}


class BufferAggregator:
    """对锚点周边做多尺度设施数量统计。

    Parameters
    ----------
    scales : Iterable[int]
        缓冲半径（km），默认 (1, 3, 5)。
    earth_radius_km : float
        地球半径（km），默认 6371.0。
    """

    def __init__(
        self,
        scales: Iterable[int] = (1, 3, 5),
        earth_radius_km: float = EARTH_RADIUS_KM,
    ) -> None:
        self.scales = list(scales)
        self.earth_radius_km = earth_radius_km

    @staticmethod
    def build_tree(coords: np.ndarray) -> BallTree:
        return BallTree(coords, metric="haversine")

    def compute(
        self,
        anchor_master: pd.DataFrame,
        amap_df: pd.DataFrame,
        ctrip_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """计算每个锚点在各缓冲半径下的设施数量。

        注意：高德坐标先 dropna 再构建树，后续用 df.iloc 回取子集；
        该口径与 30 脚本一致，重构时保持原样以通过数值回归。
        """
        amap_coords = np.radians(amap_df[["lat", "lon"]].dropna().values)
        amap_tree = self.build_tree(amap_coords)

        ctrip_lon_col = ctrip_df.columns[1]
        ctrip_lat_col = ctrip_df.columns[2]
        ctrip_pts = ctrip_df[[ctrip_lat_col, ctrip_lon_col]].dropna()
        ctrip_coords = np.radians(ctrip_pts.values)
        ctrip_tree = self.build_tree(ctrip_coords)

        buffer_rows = []
        for _, row in anchor_master.iterrows():
            center = np.radians([[row["lat"], row["lng"]]])
            for scale in self.scales:
                r = scale / self.earth_radius_km
                idx_amap = amap_tree.query_radius(center, r=r)[0]
                amap_subset = amap_df.iloc[idx_amap]

                counts = {
                    col: int(len(amap_subset[amap_subset["category_group"] == cat]))
                    for cat, col in AMAP_CATEGORY_TO_COLUMN.items()
                }

                idx_ctrip = ctrip_tree.query_radius(center, r=r)[0]
                buffer_rows.append(
                    {
                        "anchor_name": row["anchor_name"],
                        "scale_km": scale,
                        "ctrip_lodging_count": int(len(idx_ctrip)),
                        "amap_dining_count": counts["amap_dining_count"],
                        "amap_transport_count": counts["amap_transport_count"],
                        "amap_public_count": counts["amap_public_count"],
                        "amap_shopping_count": counts["amap_shopping_count"],
                        "amap_medical_count": counts["amap_medical_count"],
                        "amap_lodging_count_optional": counts["amap_lodging_count_optional"],
                    }
                )

        return pd.DataFrame(buffer_rows)
