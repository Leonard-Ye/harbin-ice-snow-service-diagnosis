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
    strategy_for,
)
from src.detectors.anomaly_detector import AnomalyDetector
from src.engines.metrics_engine import PAIN_RATE_COLS, SUPPLY_COLS
import ui_theme

st.set_page_config(page_title="哈尔滨冰雪旅游服务设施供需诊断", page_icon="❄️", layout="wide")


# ---------------------------------------------------------------- 数据
@st.cache_data(show_spinner="加载 V30 多源融合聚合结果 ...")
def get_data(method: str) -> pd.DataFrame:
    return add_diagnosis(full_table(method=method))


with st.sidebar:
    st.header("分析配置")
    theme_sel = st.radio(
        "界面主题",
        ["dark", "light"],
        index=0,
        format_func=lambda t: "深色（大屏）" if t == "dark" else "浅色（清爽）",
        help="深色适合投屏演示；浅色适合日常阅读。",
    )
    ui_theme.set_theme(theme_sel)
    theme = ui_theme.get_theme()
    st.divider()
    method = st.radio(
        "指标权重方案",
        ["equal", "entropy"],
        index=0,
        format_func=lambda m: "等权（报告基线口径）" if m == "equal" else "熵权法（数据驱动）",
        help="equal = 等权，与结题报告口径逐值一致；entropy = 熵权法，按 20 锚点样本离散度客观赋权。",
    )
    st.caption(
        "熵权法：min-max 归一化 → 信息熵 → 差异系数 → 权重。"
        "离散度大（信息量大）的维度获得更高权重；常数列权重为 0。"
    )


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


df["type_color"] = df["diagnosis"].map(_TYPE_C)
_rad = (df["DHI"] - df["DHI"].min()) / (df["DHI"].max() - df["DHI"].min() + 1e-9)
df["radius_m"] = (_rad * 2800 + 400).round(0)


# ---------------------------------------------------------------- 地图
def build_map(data: pd.DataFrame) -> pdk.Deck:
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=data,
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
    map_style = "dark" if theme == "dark" else "light"
    return pdk.Deck(
        layers=[layer],
        initial_view_state=view,
        tooltip=tooltip,
        map_style=map_style,
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
        template=_TPL,
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
        color_discrete_map=_TYPE_C,
    )
    fig.add_vline(x=0, line_dash="dash", line_color="gray")
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    fig.update_layout(
        title="需求热度 DHI × 服务供给 SSI 象限（虚线=样本均值 0）",
        xaxis_title="服务供给指数 SSI（→ 供给越强）",
        yaxis_title="需求热度指数 DHI（↑ 需求越高）",
        height=520,
        legend_title="诊断类型",
        template=_TPL,
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
        template=_TPL,
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
        template=_TPL,
    )
    return fig


# ---------------------------------------------------------------- 页面
st.title("❄️ 哈尔滨冰雪旅游服务设施供需诊断")
st.markdown(
    '<p class="hero-sub">多源异构数据融合（高德 / 携程 / 大众点评 / 小红书）· '
    "20 核心文旅锚点 · 5 项自研指标 · 空间供需错配诊断</p>",
    unsafe_allow_html=True,
)

kpi_cols = st.columns(4)
kpi_cols[0].metric("数据源", "4 类异构", "高德·携程·点评·小红书")
kpi_cols[1].metric("记录规模", "8 万+ 条", "POI 5.8万 + 文本 3.3万")
kpi_cols[2].metric("核心锚点", "20 个", "人工白名单复核")
kpi_cols[3].metric("自研指标", "5 项", "DHI/SSI/ERI/ERI_plus/SMI")

with st.expander("📖 研究叙事（30 秒看懂这个系统）"):
    st.markdown(
        "**为什么做**：哈尔滨冰雪旅游火爆，但服务设施存在空间失衡——景区周边"
        "供给不足、老城核心高峰承载压力大。\n\n"
        "**怎么做**：将 4 类异构数据（设施点位/住宿/餐饮评论/舆情文本）通过 **POI 锚点对齐**"
        "统一到 20 个核心锚点，构建 **DHI（需求）· SSI（供给）· ERI（风险）· SMI（错配）**"
        "四类诊断指标。\n\n"
        "**发现了什么**：问题分三类——**设施不足型**（松花江/冰雪大世界/太阳岛，近场服务薄弱）、"
        "**高峰承载型**（中央大街，设施不缺但拥挤排队）、**局部风险型**（果戈里大街排队压力）。"
    )

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


tab_overview, tab_explore, tab_anchor, tab_quality = st.tabs(
    ["总览地图", "指标筛选与象限", "单锚点诊断", "数据质量"]
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

    col_map, col_side = st.columns([7, 3])
    with col_map:
        st.subheader("核心锚点空间格局")
        st.caption("气泡大小 = DHI 需求热度；颜色 = 诊断类型；点击气泡联动「单锚点诊断」")
        evt = st.pydeck_chart(
            build_map(sub),
            on_select="rerun",
            selection_mode="single-object",
            height=520,
        )
        if evt and evt.selection and evt.selection.get("objects"):
            obj = evt.selection["objects"][0]
            clicked = obj.get("anchor_name") or obj.get("name") or ""
            if clicked:
                st.session_state["selected_anchor"] = clicked
    with col_side:
        st.subheader("SMI 错配 Top 10")
        st.plotly_chart(smi_rank_chart(sub.head(10)), width="stretch")

    # 核心发现
    st.subheader("核心发现")
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

    # 一键导出
    dl1, dl2 = st.columns(2)
    with dl1:
        st.download_button(
            "📥 导出指标明细 Excel",
            data=build_excel_bytes(df, weights_comparison_df()),
            file_name=f"harbin_diagnosis_{method}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="dl_excel",
        )
    with dl2:
        st.download_button(
            "📄 导出诊断报告 HTML",
            data=build_html_summary(df),
            file_name=f"harbin_diagnosis_{method}.html",
            mime="text/html",
            key="dl_html",
        )
    st.caption("Excel 含指标明细/数据质量审计/指标权重三个 sheet；HTML 为 Top 10 错配锚点摘要报告。")

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

    st.divider()
    st.subheader("指标分布（20 锚点样本内相对比较）")
    dist_col = st.selectbox("选择指标", INDEX_COLS, index=0)
    fig_hist = px.histogram(
        df,
        x=dist_col,
        nbins=12,
        marginal="box",
        color="diagnosis",
        color_discrete_map=_TYPE_C,
        hover_name="anchor_name",
        hover_data={"anchor_name": True},
    )
    fig_hist.update_layout(
        title=f"{dist_col} 分布（0=样本均值，正值高于平均水平）",
        xaxis_title=dist_col,
        yaxis_title="锚点数",
        height=380,
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
    with st.expander("⚖️ 指标权重方案对比（等权 vs 熵权）", expanded=False):
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

    st.divider()
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

    st.divider()
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
