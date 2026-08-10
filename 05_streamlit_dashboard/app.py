# -*- coding: utf-8 -*-
"""哈尔滨冰雪旅游服务设施供需诊断 Dashboard（Streamlit 单页应用）。

运行: streamlit run 05_streamlit_dashboard/app.py
数据: 02_多源融合数据及核心脚本/V30_Multi_Source_Fusion_R2/*.csv（聚合结果，不含原始评论/笔记）
"""
import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import pydeck as pdk
import streamlit as st

from dashboard_data import (
    DIAGNOSIS_ORDER,
    INDEX_COLS,
    PAIN_CN,
    PAIN_COLS,
    add_diagnosis,
    full_table,
    strategy_for,
)

st.set_page_config(page_title="哈尔滨冰雪旅游服务设施供需诊断", page_icon="❄️", layout="wide")


# ---------------------------------------------------------------- 数据
@st.cache_data(show_spinner="加载 V30 多源融合聚合结果 ...")
def get_data() -> pd.DataFrame:
    return add_diagnosis(full_table())


df = get_data()

st.markdown(
    """
    <style>
    .block-container {padding-top: 2.2rem;}
    [data-testid="stMetric"] {background:#f5f7fa; border-radius:8px; padding:8px 12px;}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------- 颜色
def smi_color(smi: float):
    """SMI 高(错配严重)→红, SMI 低→蓝。输入 z-score，输出 RGB 列表。"""
    t = max(-2.5, min(2.5, smi)) / 5.0 + 0.5  # 归一化到 0..1
    if t < 0.5:
        k = t * 2
        return [int(235 * k), int(60 * k), int(60 + 175 * k)]
    k = (t - 0.5) * 2
    return [int(235 - 25 * k), int(60 * (1 - k)), int(235 - 175 * k)]


df["color"] = df["SMI"].apply(smi_color)
_rad = (df["DHI"] - df["DHI"].min()) / (df["DHI"].max() - df["DHI"].min() + 1e-9)
df["radius_m"] = (_rad * 2800 + 400).round(0)


# ---------------------------------------------------------------- 地图
def build_map(data: pd.DataFrame) -> pdk.Deck:
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=data,
        get_position=["lng", "lat"],
        get_fill_color="color",
        get_radius="radius_m",
        radius_min_pixels=8,
        radius_max_pixels=90,
        pickable=True,
        stroked=True,
        get_line_color=[30, 30, 30],
        line_width_min_pixels=1,
    )
    tooltip = {
        "html": (
            "<b>{anchor_name}</b><br/>"
            "SMI 错配: {SMI:.2f} (排名 {mismatch_rank})<br/>"
            "DHI 需求: {DHI:.2f} ｜ SSI 供给: {SSI:.2f} ｜ ERI 风险: {ERI:.2f}<br/>"
            "类型: {diagnosis}"
        ),
        "style": {"backgroundColor": "#111827", "color": "white"},
    }
    view = pdk.ViewState(latitude=45.755, longitude=126.615, zoom=10.0)
    return pdk.Deck(
        layers=[layer],
        initial_view_state=view,
        tooltip=tooltip,
        map_style="light",
    )


def smi_rank_chart(data: pd.DataFrame) -> go.Figure:
    d = data.sort_values("SMI")
    colors = [smi_color(v) for v in d["SMI"]]
    fig = go.Figure(
        go.Bar(
            x=d["SMI"],
            y=d["anchor_name"],
            orientation="h",
            marker_color=[f"rgb({c[0]},{c[1]},{c[2]})" for c in colors],
            text=[f"{v:.2f}" for v in d["SMI"]],
            textposition="outside",
        )
    )
    fig.update_layout(
        title="SMI 服务错配指数排名（高=相对错配更突出）",
        xaxis_title="SMI",
        yaxis_title="",
        height=560,
        margin=dict(l=10, r=30, t=45, b=10),
    )
    return fig


def quadrant_chart(data: pd.DataFrame) -> go.Figure:
    """DHI vs SSI 供需象限（对应报告图 3-18，中线为样本均值 0）。"""
    d = data.copy()
    d["type_cn"] = d["diagnosis"].replace("高需求—高供给—高风险型", "高需求—高供给—高风险型")
    fig = px.scatter(
        d,
        x="SSI",
        y="DHI",
        color="diagnosis",
        size=[40] * len(d),
        hover_name="anchor_name",
        hover_data={"SSI": ":.2f", "DHI": ":.2f", "ERI": ":.2f", "SMI": ":.2f"},
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig.add_vline(x=0, line_dash="dash", line_color="gray")
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    fig.update_layout(
        title="需求热度 DHI × 服务供给 SSI 象限（虚线=样本均值 0）",
        xaxis_title="服务供给指数 SSI（→ 供给越强）",
        yaxis_title="需求热度指数 DHI（↑ 需求越高）",
        height=520,
        legend_title="诊断类型",
    )
    return fig


def pain_radar(data: pd.DataFrame, anchor: str) -> go.Figure:
    row = data[data["anchor_name"] == anchor].iloc[0]
    labels = [PAIN_CN[c] for c in PAIN_COLS] + ["负面情绪"]
    vals = [row[c] for c in PAIN_COLS] + [row["xhs_negative_rate"]]
    fig = go.Figure(
        go.Scatterpolar(
            r=vals,
            theta=labels,
            fill="toself",
            name=anchor,
            line_color="#d62728",
            fillcolor="rgba(214,39,40,0.25)",
        )
    )
    fig.update_layout(
        title=f"{anchor} — 体验风险触发率（小红书文本，相对比例）",
        polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
        height=380,
        margin=dict(l=40, r=40, t=45, b=20),
    )
    return fig


def dp_pressure_chart(data: pd.DataFrame, anchor: str) -> go.Figure:
    row = data[data["anchor_name"] == anchor].iloc[0]
    labels = ["价格压力", "排队压力", "服务负向压力"]
    vals = [row["dp_price_pressure"], row["dp_queue_pressure"], row["dp_service_pressure"]]
    fig = go.Figure(
        go.Bar(x=labels, y=vals, marker_color=["#e6550d", "#fd8d3c", "#a1a1a1"])
    )
    fig.update_layout(
        title=f"{anchor} — 大众点评餐饮压力（ERI_plus 输入）",
        yaxis_title="触发率",
        height=320,
        margin=dict(l=10, r=10, t=45, b=10),
    )
    return fig


# ---------------------------------------------------------------- 页面
st.title("❄️ 哈尔滨冰雪旅游服务设施供需诊断")
st.caption(
    "基于 4 类异构数据源（高德 POI / 携程住宿 / 大众点评 / 小红书舆情，8 万+ 条记录）"
    "构建 DHI/SSI/ERI/ERI_plus/SMI 五指标，对 20 个核心文旅锚点做空间供需错配诊断。"
    "数据口径与结论详见结题报告，所有指标均为样本内相对比较。"
)

kpi_cols = st.columns(4)
kpi_cols[0].metric("数据源", "4 类异构")
kpi_cols[1].metric("记录规模", "8 万+ 条")
kpi_cols[2].metric("核心锚点", "20 个")
kpi_cols[3].metric("自研指标", "5 项")

tab_overview, tab_explore, tab_anchor = st.tabs(["总览地图", "指标筛选与象限", "单锚点诊断"])

# ---- Tab 1 总览 ----
with tab_overview:
    col_map, col_rank = st.columns([3, 2])
    with col_map:
        st.subheader("核心锚点供需错配地图")
        st.caption("气泡大小 = DHI 需求热度；颜色 = SMI 错配度（红=错配突出，蓝=相对均衡）")
        st.pydeck_chart(build_map(df))
    with col_rank:
        st.plotly_chart(smi_rank_chart(df), width="stretch")

    st.subheader("诊断类型分布")
    dist = df["diagnosis"].value_counts().reindex(DIAGNOSIS_ORDER).dropna()
    fig_dist = go.Figure(
        go.Bar(
            x=dist.values,
            y=dist.index,
            orientation="h",
            marker_color=px.colors.qualitative.Set2[: len(dist)],
            text=dist.values,
            textposition="outside",
        )
    )
    fig_dist.update_layout(
        xaxis_title="锚点数量",
        yaxis_title="",
        height=300,
        margin=dict(l=10, r=30, t=10, b=10),
    )
    st.plotly_chart(fig_dist, width="stretch")
    st.caption(
        "分类口径：DHI>0 为高需求，SSI>0 为高供给，ERI>0 为高风险（相对 20 锚点均值 0）。"
        "高需求—低供给=设施不足型；高需求—高供给—高风险=高峰承载型。详见报告 3.2.6。"
    )

# ---- Tab 2 指标筛选与象限 ----
with tab_explore:
    st.subheader("指标筛选")
    c1, c2, c3 = st.columns(3)
    dhi_min = c1.slider("DHI 需求热度 ≥", -2.0, 2.0, -2.0, 0.05, format="%.2f")
    ssi_min = c2.slider("SSI 服务供给 ≥", -2.0, 2.0, -2.0, 0.05, format="%.2f")
    eri_min = c3.slider("ERI 体验风险 ≥", -2.0, 2.0, -2.0, 0.05, format="%.2f")
    show_cols = st.multiselect(
        "表格展示列",
        INDEX_COLS + ["mismatch_rank", "diagnosis", "xhs_mentions", "dp_review_count"],
        default=INDEX_COLS + ["mismatch_rank", "diagnosis"],
    )

    mask = (df["DHI"] >= dhi_min) & (df["SSI"] >= ssi_min) & (df["ERI"] >= eri_min)
    sub = df[mask]
    st.write(f"满足条件 **{len(sub)}** / 20 个锚点")

    col_q, col_t = st.columns([3, 2])
    with col_q:
        st.plotly_chart(quadrant_chart(sub), width="stretch")
    with col_t:
        st.plotly_chart(
            smi_rank_chart(sub),
            width="stretch",
        )

    if len(sub) > 0:
        st.subheader("筛选结果明细")
        show = [
            c
            for c in ["anchor_name", "mismatch_rank", "diagnosis"]
            + INDEX_COLS
            if c in sub.columns
        ]
        show = show + [c for c in show_cols if c not in show]
        st.dataframe(
            sub[show].sort_values("SMI", ascending=False).round(3),
            width="stretch",
            hide_index=True,
        )

# ---- Tab 3 单锚点诊断 ----
with tab_anchor:
    anchor = st.selectbox("选择核心锚点", df.sort_values("mismatch_rank")["anchor_name"].tolist())
    row = df[df["anchor_name"] == anchor].iloc[0]

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("SMI 错配", f"{row['SMI']:.2f}", f"排名 {int(row['mismatch_rank'])}/20")
    m2.metric("DHI 需求", f"{row['DHI']:.2f}")
    m3.metric("SSI 供给", f"{row['SSI']:.2f}")
    m4.metric("ERI 风险", f"{row['ERI']:.2f}")
    m5.metric("ERI_plus 餐饮", f"{row['ERI_plus']:.2f}")

    st.info(f"**诊断类型：{row['diagnosis']}**")
    st.write(strategy_for(row["diagnosis"]))

    col_r, col_d = st.columns(2)
    with col_r:
        st.plotly_chart(pain_radar(df, anchor), width="stretch")
    with col_d:
        st.plotly_chart(dp_pressure_chart(df, anchor), width="stretch")

    st.caption(
        "注：DHI/SSI/ERI/SMI 为 20 锚点样本内 Z-score 相对值（0=样本均值）；"
        "痛点触发率 = 该类痛点提及次数 / 该锚点总提及次数；负面情绪占比为平滑后比例。"
        "本页指标为聚合统计，不含任何原始评论文本。"
    )
