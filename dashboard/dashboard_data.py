# -*- coding: utf-8 -*-
"""数据层：加载 V30 多源融合聚合结果，输出 Dashboard 所需的 DataFrame 与诊断分类。

本模块只依赖 pandas，不依赖 Streamlit，可独立测试。
数据来源：analysis/V30_Multi_Source_Fusion_R2/*.csv
"""
import os
import sys

import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.engines.metrics_engine import MetricsEngine  # noqa: E402

DATA_DIR = os.path.join(PROJECT_ROOT, "analysis", "V30_Multi_Source_Fusion_R2")

INDEX_FILE = os.path.join(DATA_DIR, "anchor_index_v22_04R2.csv")
MASTER_FILE = os.path.join(DATA_DIR, "anchor_master_v22_04R2.csv")
XHS_FILE = os.path.join(DATA_DIR, "xhs_demand_risk_statistics_v22_04R2.csv")
DP_FILE = os.path.join(DATA_DIR, "dianping_pressure_statistics_v22_04R2.csv")
SCALE_FILE = os.path.join(DATA_DIR, "scale_sensitivity_1_3_5km_v22_04R2.csv")

INDEX_COLS = ["DHI", "SSI", "ERI", "ERI_plus", "SMI"]
PAIN_COLS = ["traffic_pain_rate", "queue_pain_rate", "cold_pain_rate", "price_pain_rate"]
PAIN_CN = {
    "traffic_pain_rate": "交通",
    "queue_pain_rate": "排队",
    "cold_pain_rate": "防寒",
    "price_pain_rate": "价格",
}


def load_index() -> pd.DataFrame:
    return pd.read_csv(INDEX_FILE, encoding="utf-8-sig")


def load_master() -> pd.DataFrame:
    return pd.read_csv(MASTER_FILE, encoding="utf-8-sig")


def load_xhs_risk() -> pd.DataFrame:
    return pd.read_csv(XHS_FILE, encoding="utf-8-sig")


def load_dp() -> pd.DataFrame:
    return pd.read_csv(DP_FILE, encoding="utf-8-sig")


def load_scale() -> pd.DataFrame:
    return pd.read_csv(SCALE_FILE, encoding="utf-8-sig")


def full_table(method: str = "equal") -> pd.DataFrame:
    """合并锚点主表 + 五指标 + 小红书需求风险 + 大众点评压力，返回单表。

    五指标由 MetricsEngine 计算（method="equal" 与 30 脚本口径逐值一致；
    method="entropy" 为熵权法客观赋权），对外列结构与早期版本完全一致。
    """
    engine = MetricsEngine(method=method)
    idx = engine.compute_metrics(load_scale(), scale_km=engine.main_scale)
    master = load_master()[["anchor_name", "anchor_id", "confidence"]]
    xhs = load_xhs_risk()
    dp = load_dp()
    df = idx.merge(master, on="anchor_name", how="left")
    df = df.merge(xhs, on="anchor_name", how="left")
    df = df.merge(dp, on="anchor_name", how="left")
    return df


def get_weight_sets(method: str = "equal") -> dict:
    """返回指定权重方案的三组指标权重（供 Dashboard 对比展示）。"""
    return MetricsEngine(method=method).get_weights(load_scale())


def get_scale_profile() -> pd.DataFrame:
    """多尺度（1/3/5km）供给概览，供数据质量页签使用。"""
    return MetricsEngine().compute_scale_profile(load_scale())


def resolve_selected_anchor(selection) -> str:
    """从 st.pydeck_chart 的 selection 事件解析被点击的锚点名。

    PydeckSelectionState.selection 结构：{"objects": {layer_id: [对象字典]}, ...}，
    对象字典含数据行属性（如 anchor_name）。
    """
    if not selection:
        return ""
    objects = selection.get("objects")
    if not isinstance(objects, dict):
        return ""
    for objs in objects.values():
        if objs:
            name = objs[0].get("anchor_name") or ""
            if name:
                return name
    return ""


def classify_anchor(dhi: float, ssi: float, eri: float) -> str:
    """按四类诊断信号对锚点分类。

    Z-score 以 0 为样本内相对分界（指标 >0 表示高于 20 锚点平均水平）。
    判定顺序：先看需求侧（DHI），再叠加供给（SSI）与风险（ERI）。
    """
    if dhi > 0:
        if ssi < 0:
            return "高需求—低供给型"
        return "高需求—高供给—高风险型" if eri > 0 else "高需求—高供给型"
    if eri > 0:
        return "低需求—高风险型"
    return "低需求—高供给型" if ssi > 0 else "低需求—低供给型"


def add_diagnosis(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["diagnosis"] = df.apply(
        lambda r: classify_anchor(r["DHI"], r["SSI"], r["ERI"]), axis=1
    )
    return df


STRATEGY_MAP = {
    "高需求—低供给型": (
        "设施不足型问题：优先补充短途接驳、临时游客服务点、公共卫生设施、"
        "防寒休憩空间和夜间交通保障；旺季可设临时暖棚、移动厕所、应急医疗点和分时段接驳车。"
    ),
    "高需求—高供给—高风险型": (
        "高峰承载型问题：设施数量并非主矛盾，重点做高峰管理——游客分流、排队组织、"
        "餐饮预约、价格监管、步行空间组织与实时客流提示。"
    ),
    "低需求—高风险型": (
        "非主要流量核心但局部体验问题突出：适合定点整改、信息提示与服务质量提升。"
    ),
    "低需求—高供给型": (
        "具备承接游客分流与线路组织的潜力，结合交通可达性、吸引力与线路组织评估后，"
        "可作为核心景区/商圈的外溢承接空间。"
    ),
    "高需求—高供给型": "供需相对均衡，维持常规监测与动态跟踪。",
    "低需求—低供给型": "当前口径下既非主要关注区也非设施集聚区，短期作为一般监测对象。",
}

DIAGNOSIS_ORDER = [
    "高需求—低供给型",
    "高需求—高供给—高风险型",
    "低需求—高风险型",
    "低需求—高供给型",
    "高需求—高供给型",
    "低需求—低供给型",
]


def strategy_for(diagnosis: str) -> str:
    return STRATEGY_MAP.get(diagnosis, "")
