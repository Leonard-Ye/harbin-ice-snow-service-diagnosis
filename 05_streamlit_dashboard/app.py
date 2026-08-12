# -*- coding: utf-8 -*-
"""哈尔滨冰雪旅游服务设施供需诊断 Dashboard（Streamlit 单页应用）。

运行: streamlit run 05_streamlit_dashboard/app.py
数据: 02_多源融合数据及核心脚本/V30_Multi_Source_Fusion_R2/*.csv（聚合结果，不含原始评论/笔记）
"""
import io
import json
import os

import numpy as np
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
    get_scale_profile,
    get_weight_sets,
    load_scale,
    resolve_selected_anchor,
    strategy_for,
)
from src.detectors.anomaly_detector import AnomalyDetector
from src.engines.metrics_engine import PAIN_RATE_COLS, SUPPLY_COLS
import ui_theme
from pdf_report import build_visual_pdf_bytes

st.set_page_config(page_title="哈尔滨冰雪旅游服务设施供需诊断", layout="wide")


# ---------------------------------------------------------------- 数据
@st.cache_data(show_spinner="加载 V30 多源融合聚合结果 ...")
def get_data(method: str) -> pd.DataFrame:
    return add_diagnosis(full_table(method=method))


with st.sidebar:
    st.header("分析配置")
    st.caption("右上角 **设置菜单 → Theme** 可切换深/浅主题")
    st.divider()
    method = st.radio(
        "指标权重方案",
        ["equal", "entropy"],
        index=1,
        format_func=lambda m: "等权（报告基线口径）" if m == "equal" else "熵权法（数据驱动，默认）",
        help="默认熵权法：按 20 锚点样本离散度客观赋权（数据驱动）；等权为结题报告口径，可切换对照。",
    )
    st.caption(
        "熵权法：min-max 归一化 → 信息熵 → 差异系数 → 权重。"
        "离散度大（信息量大）的维度获得更高权重；常数列权重为 0。"
    )


theme = ui_theme.get_theme()
ui_theme.apply_theme(theme)
df = get_data(method)

# ---------------------------------------------------------------- 颜色
_PAL = ui_theme.palette(theme)
_TYPE_C = ui_theme.type_colors(theme)
_TPL = ui_theme.plotly_template(theme)


def smi_color(smi: float):
    """SMI 高(错配严重)→红, SMI 低→蓝。输入 z-score，输出 RGB 列表。"""
    t = max(-2.5, min(2.5, smi)) / 5.0 + 0.5  # 归一化到 0..1
    if t < 0.5:
        k = t * 2
        return [int(235 * k), int(60 * k), int(60 + 175 * k)]
    k = (t - 0.5) * 2
    return [int(235 - 25 * k), int(60 * (1 - k)), int(235 - 175 * k)]


df["type_color"] = (
    df["diagnosis"].map(_TYPE_C).apply(ui_theme.hex_to_rgb)
)
# 初始透明度层次：alpha 按 DHI 归一化（120~240），高热度锚点更实、低热度更透
_dhi_min, _dhi_max = float(df["DHI"].min()), float(df["DHI"].max())


def _bubble_color(hex_color: str, dhi: float):
    rgb = ui_theme.hex_to_rgb(hex_color)
    t = (dhi - _dhi_min) / (_dhi_max - _dhi_min + 1e-9)
    rgb[3] = int(120 + t * 120)  # alpha 范围 [120, 240]
    return rgb


df["type_color"] = df.apply(
    lambda r: _bubble_color(_TYPE_C[r["diagnosis"]], r["DHI"]), axis=1
)
_rad = (df["DHI"] - df["DHI"].min()) / (df["DHI"].max() - df["DHI"].min() + 1e-9)
df["radius_m"] = (_rad * 2800 + 400).round(0)


# ---------------------------------------------------------------- 地图
def build_map(data: pd.DataFrame) -> pdk.Deck:
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=data,
        id="anchors",
        get_position=["lng", "lat"],
        get_fill_color="type_color",
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
        "style": {
            "backgroundColor": "#1C2330" if theme == "dark" else "#FFFFFF",
            "color": "#E6E8EB" if theme == "dark" else "#1F2937",
        },
    }
    view = pdk.ViewState(latitude=45.755, longitude=126.615, zoom=10.0)
    return pdk.Deck(
        layers=[layer],
        initial_view_state=view,
        tooltip=tooltip,
        map_style=None,  # 跟随 Streamlit 当前主题自动选底图（官方推荐）
    )


def smi_rank_chart(data: pd.DataFrame) -> go.Figure:
    d = data.sort_values("SMI")
    colors = [smi_color(v) for v in d["SMI"]]
    fig = go.Figure(
        go.Bar(
            x=d["SMI"],
            y=d["anchor_name"],
            orientation="h",
            marker=dict(
                color=[f"rgb({c[0]},{c[1]},{c[2]})" for c in colors],
                line=dict(width=0),
                cornerradius=4,
            ),
            text=[f"{v:.2f}" for v in d["SMI"]],
            textposition="outside",
            textfont=dict(size=11),
        )
    )
    fig.update_layout(
        title=dict(text="SMI 服务错配排名 Top 10", font=dict(size=14, weight=700)),
        xaxis_title="SMI 错配指数",
        yaxis_title="",
        height=540,
        margin=dict(l=5, r=35, t=45, b=10),
        template=_TPL,
    )
    return fig


def quadrant_chart(data: pd.DataFrame) -> go.Figure:
    """DHI vs SSI 供需象限（对应报告图 3-18，四象限软色底板区）。"""
    d = data.copy()
    fig = px.scatter(
        d,
        x="SSI",
        y="DHI",
        color="diagnosis",
        size=[60] * len(d),
        hover_name="anchor_name",
        hover_data={"SSI": ":.2f", "DHI": ":.2f", "ERI": ":.2f", "SMI": ":.2f"},
        color_discrete_map=_TYPE_C,
    )
    
    # 4 象限软背景区渲染
    _min_x, _max_x = d["SSI"].min() - 0.5, d["SSI"].max() + 0.5
    _min_y, _max_y = d["DHI"].min() - 0.5, d["DHI"].max() + 0.5
    
    # 左上：高需求低供给（设施不足区-红淡色）
    fig.add_shape(type="rect", x0=_min_x, x1=0, y0=0, y1=_max_y, fillcolor="rgba(248, 113, 113, 0.05)", line_width=0, layer="below")
    # 右上：高需求高供给（高峰承载区-橙淡色）
    fig.add_shape(type="rect", x0=0, x1=_max_x, y0=0, y1=_max_y, fillcolor="rgba(251, 146, 60, 0.05)", line_width=0, layer="below")
    # 左下：低需求低供给（一般监测区-灰淡色）
    fig.add_shape(type="rect", x0=_min_x, x1=0, y0=_min_y, y1=0, fillcolor="rgba(148, 163, 184, 0.04)", line_width=0, layer="below")
    # 右下：低需求高供给（分流承接区-绿淡色）
    fig.add_shape(type="rect", x0=0, x1=_max_x, y0=_min_y, y1=0, fillcolor="rgba(52, 211, 153, 0.05)", line_width=0, layer="below")

    fig.add_vline(x=0, line_dash="dash", line_color="rgba(148, 163, 184, 0.3)")
    fig.add_hline(y=0, line_dash="dash", line_color="rgba(148, 163, 184, 0.3)")
    fig.update_layout(
        title=dict(text="需求热度 DHI × 服务供给 SSI 象限（虚线=样本均值 0）", font=dict(size=14, weight=700)),
        xaxis_title="服务供给指数 SSI（→ 供给越强）",
        yaxis_title="需求热度指数 DHI（↑ 需求越高）",
        height=520,
        margin=dict(l=10, r=10, t=45, b=10),
        legend_title=dict(text="诊断类型", font=dict(weight=600)),
        template=_TPL,
    )
    return fig


def pain_radar(data: pd.DataFrame, anchor: str) -> go.Figure:
    row = data[data["anchor_name"] == anchor].iloc[0]
    labels = [PAIN_CN[c] for c in PAIN_COLS] + ["负面情绪"]
    vals = [row[c] for c in PAIN_COLS] + [row["xhs_negative_rate"]]
    rmax = max(max(vals) * 1.25, 0.1)
    fig = go.Figure(
        go.Scatterpolar(
            r=vals,
            theta=labels,
            fill="toself",
            name=anchor,
            line=dict(color="#F87171", width=2),
            fillcolor="rgba(248, 113, 113, 0.20)",
            marker=dict(size=6, color="#F87171"),
        )
    )
    fig.update_layout(
        title=dict(text=f"{anchor} — 体验风险触发率（相对比例）", font=dict(size=14, weight=700)),
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, rmax],
                gridcolor=_PAL["grid"],
                linecolor=_PAL["grid"],
                tickfont=dict(size=10, color=_PAL["muted"]),
            ),
            angularaxis=dict(
                gridcolor=_PAL["grid"],
                linecolor=_PAL["grid"],
                tickfont=dict(size=11, color=_PAL["text"]),
            ),
            bgcolor="rgba(0,0,0,0)",
        ),
        height=380,
        margin=dict(l=30, r=30, t=45, b=15),
        template=_TPL,
    )
    return fig


def dp_pressure_chart(data: pd.DataFrame, anchor: str) -> go.Figure:
    row = data[data["anchor_name"] == anchor].iloc[0]
    labels = ["价格压力", "排队压力", "服务负向压力"]
    vals = [row["dp_price_pressure"], row["dp_queue_pressure"], row["dp_service_pressure"]]
    fig = go.Figure(
        go.Bar(
            x=labels,
            y=vals,
            marker=dict(
                color=["#FB923C", "#F87171", "#38BDF8"],
                line=dict(width=0),
                cornerradius=4,
            ),
            text=[f"{v:.3f}" for v in vals],
            textposition="outside",
        )
    )
    fig.update_layout(
        title=dict(text=f"{anchor} — 大众点评餐饮压力（ERI_plus 输入）", font=dict(size=14, weight=700)),
        yaxis_title="触发率",
        height=320,
        margin=dict(l=10, r=10, t=45, b=10),
        template=_TPL,
    )
    return fig


def diagnosis_badge(diagnosis: str) -> str:
    """诊断类型彩色徽章（HTML 胶囊，高质感发光样式）。"""
    color = _TYPE_C.get(diagnosis, _TYPE_C.get("低需求—低供给型", "#94A3B8"))
    return (
        f'<span style="background:{color}18; color:{color}; '
        f'border:1px solid {color}44; padding:3px 14px; border-radius:999px; '
        f'font-size:12px; font-weight:600; display:inline-flex; align-items:center; gap:6px; '
        f'box-shadow: 0 0 10px {color}22;">'
        f'<span style="width:6px; height:6px; border-radius:50%; background:{color}; box-shadow:0 0 6px {color};"></span>'
        f'{diagnosis}</span>'
    )


# ---------------------------------------------------------------- 页面
with st.container(key="hero"):
    st.title("哈尔滨冰雪旅游服务设施供需诊断", anchor=False)
    st.markdown(
        '<p class="hero-sub">融合 4 类平台数据（高德 / 携程 / 大众点评 / 小红书）精确定位'
        "<b>服务短板与高峰拥堵</b>，为 20 个核心文旅锚点提供数据驱动的分区优化策略</p>",
        unsafe_allow_html=True,
    )

    kpi_cols = st.columns(4)
    kpi_cols[0].metric("数据源", "4 类异构", "高德·携程·点评·小红书")
    kpi_cols[1].metric("记录规模", "8 万+ 条", "POI 5.8万 + 文本 3.3万")
    kpi_cols[2].metric("核心锚点", "20 个", "人工白名单复核")
    kpi_cols[3].metric("自研指标", "5 项", "DHI/SSI/ERI/ERI_plus/SMI")

# ---- 数据质量审计（供数据质量页签与导出复用）----
AUDIT_COLS = SUPPLY_COLS + ["xhs_mentions", "dp_review_count"] + PAIN_RATE_COLS
LOG_COLS = SUPPLY_COLS + ["xhs_mentions", "dp_review_count"]  # 右偏数量列


def weights_comparison_df() -> pd.DataFrame:
    w_eq = get_weight_sets("equal")
    w_cur = get_weight_sets(method)
    grp_cn = {"supply": "SSI 服务供给", "eri": "ERI 体验风险", "dp": "ERI_plus 餐饮压力"}
    rows = []
    for grp in ["supply", "eri", "dp"]:
        for k in w_eq[grp]:
            rows.append(
                {
                    "指标组": grp_cn[grp],
                    "维度": k,
                    "等权": w_eq[grp][k],
                    "当前方案": w_cur[grp][k],
                }
            )
    dfw = pd.DataFrame(rows)
    dfw["差异"] = (dfw["当前方案"] - dfw["等权"]).round(4)
    return dfw


def build_audit_df() -> pd.DataFrame:
    scale3 = load_scale()
    scale3 = scale3[scale3["scale_km"] == 3].copy()
    audit = AnomalyDetector().quality_report(scale3, AUDIT_COLS, log_transform=LOG_COLS)
    audit["iqr_outliers"] = audit["iqr_outliers"].apply(
        lambda x: "、".join(x) if x else "—"
    )
    audit["zscore_outliers"] = audit["zscore_outliers"].apply(
        lambda x: "、".join(x) if x else "—"
    )
    return audit


def build_excel_bytes(df: pd.DataFrame, wdf: pd.DataFrame) -> bytes:
    """打包指标明细/数据质量审计/指标权重 为多 sheet Excel。"""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df[["anchor_name", "mismatch_rank", "diagnosis"] + INDEX_COLS].to_excel(
            writer, sheet_name="指标明细", index=False
        )
        build_audit_df().to_excel(writer, sheet_name="数据质量审计", index=False)
        wdf.to_excel(writer, sheet_name="指标权重", index=False)
    return buf.getvalue()


def build_html_summary(df: pd.DataFrame) -> str:
    """生成诊断报告 HTML 摘要（锚点排名 + 诊断分布 + 口径说明）。"""
    rows = "".join(
        f"<tr><td>{i}</td><td>{r.anchor_name}</td><td>{r.SMI:.2f}</td>"
        f"<td>{r.DHI:.2f}</td><td>{r.SSI:.2f}</td><td>{r.ERI:.2f}</td>"
        f"<td>{r.diagnosis}</td></tr>"
        for i, r in df.head(10).iterrows()
    )
    dist = df["diagnosis"].value_counts().to_dict()
    dist_html = "".join(f"<li>{k}: {v} 个锚点</li>" for k, v in dist.items())
    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>哈尔滨冰雪旅游服务设施供需诊断报告</title>
<style>body{{font-family:'Microsoft YaHei',sans-serif;margin:24px;}}
table{{border-collapse:collapse;width:100%;}} th,td{{border:1px solid #ccc;padding:6px 10px;font-size:13px;}}
th{{background:#f0f4f8;}} h1{{font-size:20px;}} .note{{color:#666;font-size:12px;}}</style>
</head><body>
<h1>哈尔滨冰雪旅游服务设施供需诊断报告（Top 10 错配锚点）</h1>
<p>权重方案：{'等权（报告基线口径）' if method == 'equal' else '熵权法（数据驱动）'}　|　生成时间：{pd.Timestamp.now():%Y-%m-%d %H:%M}</p>
<table><tr><th>排名</th><th>锚点</th><th>SMI</th><th>DHI</th><th>SSI</th><th>ERI</th><th>诊断类型</th></tr>{rows}</table>
<h2>诊断类型分布</h2><ul>{dist_html}</ul>
<p class="note">口径说明：所有指标为 20 个核心锚点样本内 Z-score 相对值（0=样本均值），SMI = z(DHI)+z(ERI)−z(SSI)。数据为聚合统计，不含任何原始评论。</p>
</body></html>"""



# ---- 核心结论（首屏，HR 30 秒看懂）----
st.markdown('<div class="section-title">核心结论</div>', unsafe_allow_html=True)
c1, c2, c3 = st.columns(3)
c1.markdown(
    '<div class="insight-card"><div class="tag">类型 ① 设施不足型</div>'
    '<div class="title">松花江 · 冰雪大世界 · 太阳岛</div>'
    '<div class="body">高需求但近场服务薄弱（住宿/餐饮/交通供给离群低值），'
    "优先补短途接驳与防寒休憩设施。</div></div>",
    unsafe_allow_html=True,
)
c2.markdown(
    '<div class="insight-card"><div class="tag">类型 ② 高峰承载型</div>'
    '<div class="title">中央大街 · 圣索菲亚教堂</div>'
    '<div class="body">设施供给充足但高峰排队/价格压力突出，需客流分流与排队组织'
    "而非增加设施。</div></div>",
    unsafe_allow_html=True,
)
c3.markdown(
    '<div class="insight-card"><div class="tag">类型 ③ 局部风险与分流</div>'
    '<div class="title">果戈里排队压力 · 中东铁路桥承接潜力</div>'
    '<div class="body">局部锚点体验风险高（定点整改）；低需求高供给锚点具备'
    "承接核心区外溢的潜力。</div></div>",
    unsafe_allow_html=True,
)

# ---- 一键导出（首屏显眼位置）----
with st.container(border=True, key="export"):
    dl1, dl2, dl3 = st.columns(3)
    with dl1:
        st.download_button(
            "导出指标明细 Excel",
            icon=":material/download:",
            data=build_excel_bytes(df, weights_comparison_df()),
            file_name=f"harbin_diagnosis_{method}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="dl_excel",
        )
    with dl2:
        st.download_button(
            "导出可视化诊断报告 PDF",
            icon=":material/picture_as_pdf:",
            data=build_visual_pdf_bytes(df, method),
            file_name=f"harbin_diagnosis_{method}.pdf",
            mime="application/pdf",
            key="dl_pdf",
        )
    with dl3:
        st.download_button(
            "导出诊断报告 HTML",
            icon=":material/description:",
            data=build_html_summary(df),
            file_name=f"harbin_diagnosis_{method}.html",
            mime="text/html",
            key="dl_html",
        )
    st.caption(
        "三连导出方案：Excel（含指标明细/质量审计/权重）；PDF（含高精可视化图表、KPI 与策略简报）；HTML（Top 10 错配摘要报告）。"
    )

with st.expander("研究叙事（30 秒看懂这个系统）", icon=":material/menu_book:"):
    st.markdown(
        "#### 为什么做\n"
        "哈尔滨冰雪旅游火爆，但服务设施存在空间失衡：景区周边供给不足、老城核心高峰承载压力大。"
    )
    st.markdown(
        "#### 怎么做\n"
        "将 4 类异构数据（设施点位 / 住宿 / 餐饮评论 / 舆情文本）通过 POI 锚点对齐"
        "统一到 20 个核心锚点，构建 5 项自研诊断指标。"
    )
    st.markdown(
        "#### 5 项自研指标怎么读\n"
        "全部为 20 锚点样本内的相对值（Z-score，0 = 平均水平）：\n\n"
        "| 指标 | 含义 | 数值大于 0 说明 |\n"
        "|---|---|---|\n"
        "| DHI 需求热度 | 小红书提及热度（log1p 压缩极端值） | 关注度高于平均 |\n"
        "| SSI 服务供给 | 3km 内六类设施数量（住宿/餐饮/交通/公共/购物/医疗） | 周边服务更密集 |\n"
        "| ERI 体验风险 | 负面情绪占比 + 交通/排队/防寒/价格痛点触发率 | 吐槽风险高于平均 |\n"
        "| ERI_plus 餐饮压力 | 大众点评价格/排队/服务压力（核心餐饮锚点验证） | 餐饮消费压力更大 |\n"
        "| SMI 服务错配 | z(DHI) + z(ERI) − z(SSI) | 需求与风险叠加、供给相对不足 |\n\n"
        "注意：SMI 排名靠前不等于设施一定不够，需回到 DHI/SSI/ERI 分项判断驱动因素。"
    )
    st.markdown(
        "#### 发现了什么\n"
        "问题分三类：设施不足型（松花江 / 冰雪大世界 / 太阳岛，近场服务薄弱）；"
        "高峰承载型（中央大街，设施不缺但拥挤排队）；局部风险型（果戈里大街排队压力）。"
    )

tab_overview, tab_explore, tab_anchor, tab_quality = st.tabs(
    ["总览地图", "指标筛选与象限", "单锚点诊断", "数据质量"]
)
st.caption(
    "页签导览：总览（人人都能看懂）· 指标筛选（分析师向）· 单锚点诊断（深挖）· "
    "数据质量（技术细节，评审向）。"
)

# ---- Tab 1 总览 ----
with tab_overview:
    st.session_state.setdefault("selected_anchor", None)

    # 诊断类型筛选
    avail_types = [t for t in DIAGNOSIS_ORDER if t in df["diagnosis"].unique()]
    sel_types = st.multiselect(
        "按诊断类型筛选锚点",
        DIAGNOSIS_ORDER,
        default=avail_types,
        help="地图与排名同步过滤。颜色编码：红=设施不足，橙=高峰承载，紫=局部风险，绿=分流承接。",
    )
    sub = df[df["diagnosis"].isin(sel_types)] if sel_types else df

    col_map, col_side = st.columns([3, 2])
    with col_map:
        st.subheader("核心锚点空间格局")
        st.caption("气泡大小 = DHI 需求热度；颜色 = 诊断类型；点击气泡联动「单锚点诊断」")
        evt = st.pydeck_chart(
            build_map(sub),
            on_select="rerun",
            selection_mode="single-object",
            height=520,
            key="anchor_map",
        )
        clicked = resolve_selected_anchor(evt.selection if evt else None)
        if clicked:
            st.session_state["selected_anchor"] = clicked
    with col_side:
        st.subheader("SMI 错配 Top 10")
        st.plotly_chart(smi_rank_chart(sub.head(10)), width="stretch")
        st.caption("SMI = z(DHI) + z(ERI) − z(SSI)，正值越高表示需求与风险叠加、供给相对不足越突出。")

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

    st.subheader("指标分布（20 锚点样本内相对比较）")
    dist_col = st.selectbox("选择指标", INDEX_COLS, index=0)
    fig_hist = px.histogram(
        df,
        x=dist_col,
        nbins=14,
        color="diagnosis",
        color_discrete_map=_TYPE_C,
        hover_name="anchor_name",
        hover_data={"anchor_name": True},
    )
    fig_hist.update_layout(
        title=f"{dist_col} 分布（0=样本均值，正值高于平均水平）",
        xaxis_title=dist_col,
        yaxis_title="锚点数",
        height=460,
        bargap=0.08,
        template=_TPL,
        legend_title="诊断类型",
    )
    st.plotly_chart(fig_hist, width="stretch")

# ---- Tab 3 单锚点诊断 ----
with tab_anchor:
    anchors_sorted = df.sort_values("mismatch_rank")["anchor_name"].tolist()
    _default = st.session_state.get("selected_anchor")
    _default_idx = anchors_sorted.index(_default) if _default in anchors_sorted else 0
    anchor = st.selectbox("选择核心锚点（点击地图气泡可联动到此）", anchors_sorted, index=_default_idx)
    row = df[df["anchor_name"] == anchor].iloc[0]

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("SMI 错配", f"{row['SMI']:.2f}", f"排名 {int(row['mismatch_rank'])}/20")
    m2.metric("DHI 需求", f"{row['DHI']:.2f}")
    m3.metric("SSI 供给", f"{row['SSI']:.2f}")
    m4.metric("ERI 风险", f"{row['ERI']:.2f}")
    m5.metric("ERI_plus 餐饮", f"{row['ERI_plus']:.2f}")

    st.markdown(
        f'<div style="display:flex; align-items:center; gap:10px; margin:6px 0;">'
        f'<span style="color:{_PAL["muted"]}; font-size:14px;">诊断类型</span>'
        f'{diagnosis_badge(row["diagnosis"])}</div>',
        unsafe_allow_html=True,
    )
    st.write(strategy_for(row["diagnosis"]))

    with st.expander("指标速查：五个指标是什么意思？", icon=":material/query_stats:"):
        st.markdown(
            "所有指标均为 **20 个锚点样本内的相对值**（Z-score，0 = 平均水平，"
            "**正值高于平均、负值低于平均**）：\n\n"
            "| 指标 | 含义 | 数值 > 0 说明 |\n"
            "|---|---|---|\n"
            "| **DHI** 需求热度 | 小红书提及热度（log1p 压缩极端值） | 该锚点在社交媒体上关注度高于平均 |\n"
            "| **SSI** 服务供给 | 3km 内六类设施数量（住宿/餐饮/交通/公共/购物/医疗） | 周边实体服务比平均更密集 |\n"
            "| **ERI** 体验风险 | 负面情绪占比 + 交通/排队/防寒/价格四类痛点**触发率** | 游客吐槽风险高于平均（触发率=痛点提及数/总提及数，避免高热度误判） |\n"
            "| **ERI_plus** 餐饮压力 | ERI + 大众点评价格/排队/服务压力 | 餐饮消费压力高于平均（仅核心餐饮锚点验证） |\n"
            "| **SMI** 服务错配 | z(DHI) + z(ERI) − z(SSI) | 需求与风险叠加、供给不足的相对错配更突出 |\n\n"
            "**怎么看**：SMI 排名靠前≠设施一定不够，回到 DHI/SSI/ERI 三个分项看是"
            "「需求热」「风险高」还是「供给缺」哪种驱动。"
        )

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

# ---- Tab 4 数据质量 ----


def outlier_chart(scale3: pd.DataFrame, col: str) -> go.Figure:
    det = AnomalyDetector()
    s = scale3[col]
    if col in LOG_COLS:
        # 右偏列：在 log1p 空间检测离群，参考线映射回原始值
        s_log = np.log1p(s.clip(lower=0))
        mask = det.detect_outliers_iqr(scale3.assign(**{col: s_log}), col)
        q1l, q3l = s_log.quantile(0.25), s_log.quantile(0.75)
        iqrl = q3l - q1l
        lo = float(np.expm1(q1l - 1.5 * iqrl))
        hi = float(np.expm1(q3l + 1.5 * iqrl))
        note = "（log1p 空间检测，参考线已映射回原始值）"
    else:
        mask = det.detect_outliers_iqr(scale3, col)
        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        iqr = q3 - q1
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        note = ""
    d = scale3.copy()
    d["is_outlier"] = mask.map({True: "IQR 离群", False: "正常"})
    fig = px.scatter(
        d,
        x="anchor_name",
        y=col,
        color="is_outlier",
        color_discrete_map={"IQR 离群": "#d62728", "正常": "#1f77b4"},
        hover_name="anchor_name",
    )
    fig.add_hline(y=lo, line_dash="dot", line_color="gray", annotation_text="IQR 下界")
    fig.add_hline(y=hi, line_dash="dot", line_color="gray", annotation_text="IQR 上界")
    fig.update_layout(
        title=f"{col} — 锚点分布与 IQR 离群标注 {note}",
        xaxis_title="",
        yaxis_title="原始值",
        height=420,
        xaxis=dict(tickangle=45),
        legend_title="",
        template=_TPL,
    )
    return fig


with tab_quality:
    with st.expander(
        "指标权重方案对比（等权 vs 熵权）", expanded=False, icon=":material/balance:"
    ):
        st.caption(
            f"当前应用使用 **{'等权（报告基线口径）' if method == 'equal' else '熵权法（数据驱动）'}**。"
            "等权为原报告口径；熵权法按 20 锚点样本离散度客观赋权，避免人为等权带来的主观性。"
        )
        wdf = weights_comparison_df()
        fig_w = px.bar(
            wdf,
            x="维度",
            y=["等权", "当前方案"],
            barmode="group",
            facet_col="指标组",
            facet_col_wrap=3,
            color_discrete_sequence=["#9ecae1", "#d62728"],
        )
        fig_w.update_layout(
            height=320, legend_title="权重方案", template=ui_theme.plotly_template(theme)
        )
        st.plotly_chart(fig_w, width="stretch")
        st.dataframe(
            wdf[wdf["当前方案"] != wdf["等权"]].round(4) if method != "equal" else wdf.round(4),
            width="stretch",
            hide_index=True,
        )

    st.subheader("数据质量审计（IQR / Z-score 离群检测）")
    scale3 = load_scale()
    scale3 = scale3[scale3["scale_km"] == 3].copy()
    audit = build_audit_df()
    st.dataframe(
        audit[
            ["column", "n", "missing_rate", "n_outliers", "iqr_outliers", "zscore_outliers"]
        ],
        width="stretch",
        hide_index=True,
    )
    st.caption(
        "右偏数量列（设施数量/评论量）经 log1p 变换后再检测，避免 IQR 下界为负导致低端离群漏检。"
        "典型发现：伏尔加庄园在住宿/餐饮/交通/公共/购物/医疗六类供给上均为离群低值（远郊设施不足）；"
        "果戈里大街排队痛点触发率为离群高值。"
    )

    col_pick = st.selectbox("离群可视化维度", AUDIT_COLS, index=AUDIT_COLS.index("ctrip_lodging_count"))
    st.plotly_chart(outlier_chart(scale3, col_pick), width="stretch")

    st.subheader("多尺度供给稳定性（1km / 3km / 5km）")
    prof = get_scale_profile()
    pivot = prof.pivot(index="anchor_name", columns="scale_km", values="supply_total").reset_index()
    pivot.columns = ["anchor_name"] + [f"{c}km" for c in pivot.columns[1:]]
    pivot["1→3km 增幅"] = ((pivot["3km"] - pivot["1km"]) / pivot["1km"].replace(0, pd.NA) * 100).round(1)
    st.dataframe(
        pivot.sort_values("1→3km 增幅", ascending=False).round(0),
        width="stretch",
        hide_index=True,
    )
    st.caption(
        "锚点在 1km 近场与 3km 短途服务圈的供给总量变化。增幅大说明服务依赖 3km 圈层（近场供给弱），"
        "是缓冲半径选择敏感性的直接证据。"
    )

# ---- 页脚 ----
st.caption(
    "数据说明：本应用基于 2026 年 6 月结题时的多源数据静态快照"
    "（高德 / 携程 / 大众点评 / 小红书聚合统计，不含原始评论），"
    "指标为 20 个核心锚点样本内相对值；默认熵权法（数据驱动），等权为报告基线口径可切换对照。"
)
