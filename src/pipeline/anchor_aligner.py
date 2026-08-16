# -*- coding: utf-8 -*-
"""AnchorAligner —— POI 锚点对齐模块。

从 30_multi_source_fusion_v22_04R2.py 原样抽取：
- 人工白名单（WHITELIST_ANCHORS）
- 别名映射（ALIAS_MAP）
- 大众点评商圈映射（DP_ANCHOR_MAP）
- 人工坐标修正（MANUAL_COORDS）
- 非地理词汇剔除原因规则（determine_exclusion_reason）

为保证与 V30 基线逐值一致，常量与判定顺序不得随意修改。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

import pandas as pd

# 人工白名单与别名映射（与 30 脚本逐字一致）
WHITELIST_ANCHORS = [
    "中央大街", "圣索菲亚教堂", "冰雪大世界", "松花江", "太阳岛", "中华巴洛克风情街",
    "红专街早市", "防洪纪念塔", "哈药六厂", "极地公园", "东北虎林园", "哈尔滨站",
    "伏尔加庄园", "中东铁路桥", "果戈里大街", "哈西站", "师大夜市", "群力", "龙塔",
    "哈尔滨工业大学", "黑龙江大学", "融创茂", "秋林公司", "音乐公园",
]

ALIAS_MAP = {
    "大世界": "冰雪大世界",
    "冰雪世界": "冰雪大世界",
    "哈尔滨冰雪大世界": "冰雪大世界",
    "索菲亚": "圣索菲亚教堂",
    "索菲亚教堂": "圣索菲亚教堂",
    "圣索菲亚": "圣索菲亚教堂",
    "索菲亚广场": "圣索菲亚教堂",
    "中央街": "中央大街",
    "中央大街步行街": "中央大街",
    "哈站": "哈尔滨站",
    "火车站": "哈尔滨站",
    "哈尔滨西站": "哈西站",
    "哈西": "哈西站",
    "松花江铁路桥": "中东铁路桥",
    "滨州铁路桥": "中东铁路桥",
    "中华巴洛克/老道外": "中华巴洛克风情街",
    "中华巴洛克": "中华巴洛克风情街",
    "老道外": "中华巴洛克风情街",
    "哈工大": "哈尔滨工业大学",
    "雪博会": "太阳岛",
}

DP_ANCHOR_MAP = {
    "中央大街商圈": "中央大街",
    "索菲亚商圈": "圣索菲亚教堂",
    "冰雪大世界/太阳岛周边": "冰雪大世界",
    "哈站商圈": "哈尔滨站",
    "哈西商圈": "哈西站",
    "防洪纪念塔商圈": "防洪纪念塔",
    "红专街早市": "红专街早市",
    "师大夜市": "师大夜市",
    "中华巴洛克": "中华巴洛克风情街",
    "秋林/果戈里商圈": "秋林公司",
    "秋林商圈": "秋林公司",
    "果戈里商圈": "果戈里大街",
    "黑大/服装城商圈": "黑龙江大学",
    "融创茂/王府井商圈": "融创茂",
    "顾乡/群力商圈": "群力",
    "道外区": "中华巴洛克风情街",
}

# 手工修正异常坐标库（与 30 脚本一致）
MANUAL_COORDS = {
    "哈药六厂": (126.685324, 45.771216),
    "中东铁路桥": (126.626354, 45.787358),
    "松花江": (126.560000, 45.780000),
}


@dataclass
class AlignmentResult:
    """对齐结果：有效记录、被剔除记录、剔除词报告、锚点主表。"""

    valid: pd.DataFrame
    excluded: pd.DataFrame
    excluded_terms: pd.DataFrame
    master: pd.DataFrame


class AnchorAligner:
    """执行白名单筛选、别名映射与锚点主表构建。"""

    def determine_exclusion_reason(self, term: str) -> str:
        """与 30 脚本相同的剔除原因规则。"""
        term_str = str(term)
        goods_words = ["冰箱贴", "伴手礼", "文创", "好物", "墨镜"]
        topic_words = [
            "东北", "浪漫", "穿搭", "亲子游", "研学", "攻略", "推荐", "爱吃",
            "好吃", "一点就透", "波波夫", "住宿",
        ]
        outer_cities = ["雪乡", "亚布力", "长白山", "延吉"]
        if any(w in term_str for w in goods_words):
            return "商品词"
        if any(w in term_str for w in topic_words):
            return "主题词/情绪词"
        if any(w in term_str for w in outer_cities):
            return "城市外延地点"
        if "太平机场" in term_str or "机场" in term_str:
            return "偏远交通枢纽(剔除主模型)"
        return "未命中白名单/非核心地理锚点"

    def align(self, df: pd.DataFrame, clean_col: str = "clean_loc") -> AlignmentResult:
        """对清洗后的地点文本做别名映射 + 白名单筛选。"""
        out = df.copy()
        out["standard_anchor"] = out[clean_col].apply(lambda x: ALIAS_MAP.get(x, x))

        valid_mask = out["standard_anchor"].isin(WHITELIST_ANCHORS)
        valid = out[valid_mask]
        excluded = out[~valid_mask]

        ex_counts = excluded[clean_col].value_counts().reset_index()
        ex_counts.columns = ["term", "mentions"]
        ex_counts["reason"] = ex_counts["term"].apply(self.determine_exclusion_reason)

        master = self.build_anchor_master(valid)
        return AlignmentResult(
            valid=valid,
            excluded=excluded,
            excluded_terms=ex_counts,
            master=master,
        )

    @staticmethod
    def build_anchor_master(valid_df: pd.DataFrame) -> pd.DataFrame:
        """按 30 脚本口径构建锚点主表（中位数坐标 + 人工坐标修正）。"""
        anchor_counts = valid_df["standard_anchor"].value_counts()
        master_rows = []

        for i, anchor in enumerate(anchor_counts.index):
            if anchor in MANUAL_COORDS:
                lon, lat = MANUAL_COORDS[anchor]
            else:
                pts = valid_df[valid_df["standard_anchor"] == anchor]
                lon = pts["lon"].median()
                lat = pts["lat"].median()

            if pd.isna(lon) or pd.isna(lat):
                continue

            master_rows.append(
                {
                    "anchor_id": f"A{i + 1:03d}",
                    "anchor_name": anchor,
                    "source": "XHS",
                    "anchor_type": "POI",
                    "lng": lon,
                    "lat": lat,
                    "merge_rule": "manual_whitelist",
                    "confidence": "A",
                    "review_status": "reviewed",
                }
            )

        return pd.DataFrame(master_rows)

    @staticmethod
    def find_dp_areas(anchor_name: str) -> List[str]:
        """返回映射到指定锚点的所有大众点评商圈名。"""
        return [dp_a for dp_a, mapped_a in DP_ANCHOR_MAP.items() if mapped_a == anchor_name]
