# -*- coding: utf-8 -*-
"""UI 主题系统：深/浅两套主题（CSS + Plotly 模板 + 诊断类型配色）。

用法：
    theme = ui_theme.get_theme()          # "dark" | "light"（session_state）
    ui_theme.apply_theme(theme)           # 注入 CSS
    fig.update_layout(template=ui_theme.plotly_template(theme))
    colors = ui_theme.type_colors(theme)  # 诊断类型 → 颜色
"""
import streamlit as st
import plotly.graph_objects as go

# ---------------------------------------------------------------- 主题色板
DARK = {
    "name": "dark",
    "bg": "#0E1117",
    "panel": "#161B22",
    "panel2": "#1C2330",
    "text": "#E6E8EB",
    "muted": "#9AA5B1",
    "accent": "#4FC3F7",     # 冰蓝
    "accent2": "#B388FF",    # 紫
    "grid": "rgba(255,255,255,0.08)",
    "metric_bg": "linear-gradient(135deg, rgba(79,195,247,0.14), rgba(179,136,255,0.10))",
    "metric_border": "1px solid rgba(79,195,247,0.35)",
    "card_bg": "rgba(28,35,48,0.85)",
    "card_border": "1px solid rgba(255,255,255,0.10)",
}

LIGHT = {
    "name": "light",
    "bg": "#F7F9FC",
    "panel": "#FFFFFF",
    "panel2": "#F0F4F8",
    "text": "#1F2937",
    "muted": "#6B7280",
    "accent": "#1565C0",     # 蓝
    "accent2": "#7B1FA2",    # 紫
    "grid": "rgba(0,0,0,0.08)",
    "metric_bg": "linear-gradient(135deg, rgba(21,101,192,0.08), rgba(123,31,162,0.06))",
    "metric_border": "1px solid rgba(21,101,192,0.25)",
    "card_bg": "rgba(255,255,255,0.95)",
    "card_border": "1px solid rgba(0,0,0,0.08)",
}

THEMES = {"dark": DARK, "light": LIGHT}

# ---------------------------------------------------------------- 诊断类型配色
# 六类诊断类型的语义色（深色/浅色各一套，保持色相一致、明度适配）
TYPE_COLORS = {
    "dark": {
        "高需求—低供给型": "#EF5350",       # 红：设施不足
        "高需求—高供给—高风险型": "#FFA726", # 橙：高峰承载
        "低需求—高风险型": "#AB47BC",        # 紫：定点整改
        "低需求—高供给型": "#66BB6A",        # 绿：分流承接
        "高需求—高供给型": "#42A5F5",        # 蓝：均衡
        "低需求—低供给型": "#90A4AE",        # 灰：一般监测
    },
    "light": {
        "高需求—低供给型": "#D32F2F",
        "高需求—高供给—高风险型": "#EF6C00",
        "低需求—高风险型": "#8E24AA",
        "低需求—高供给型": "#388E3C",
        "高需求—高供给型": "#1976D2",
        "低需求—低供给型": "#78909C",
    },
}


def get_theme() -> str:
    """读取当前主题（session_state 持久化，默认 dark）。"""
    if "ui_theme" not in st.session_state:
        st.session_state["ui_theme"] = "dark"
    return st.session_state["ui_theme"]


def set_theme(theme: str) -> None:
    st.session_state["ui_theme"] = theme


def type_colors(theme: str) -> dict:
    return TYPE_COLORS[theme]


def palette(theme: str) -> dict:
    return THEMES[theme]


def plotly_template(theme: str) -> go.layout.Template:
    """基于 Plotly 内置模板定制：透明背景 + 统一字体/网格，适配深/浅主题。"""
    t = THEMES[theme]
    template = go.layout.Template()
    template.layout = go.Layout(
        font=dict(family="'Segoe UI','Microsoft YaHei',sans-serif", color=t["text"], size=13),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        colorway=[t["accent"], t["accent2"], "#66BB6A", "#FFA726", "#EF5350", "#AB47BC"],
        xaxis=dict(gridcolor=t["grid"], zerolinecolor=t["grid"], linecolor=t["grid"]),
        yaxis=dict(gridcolor=t["grid"], zerolinecolor=t["grid"], linecolor=t["grid"]),
        legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor="rgba(0,0,0,0)"),
        hoverlabel=dict(
            bgcolor=t["panel2"], bordercolor=t["grid"], font=dict(color=t["text"])
        ),
        coloraxis_colorbar=dict(outlinewidth=0),
    )
    return template


def apply_theme(theme: str) -> None:
    """注入主题 CSS（覆盖 Streamlit 默认样式）。"""
    t = THEMES[theme]
    if theme == "dark":
        extra = f"""
        [data-testid="stSidebar"] {{ background: {t['panel']}; }}
        .stTabs [data-baseweb="tab-list"] {{ gap: 4px; }}
        .stTabs [data-baseweb="tab"] {{
            background: {t['panel']}; border-radius: 8px 8px 0 0;
            padding: 8px 18px; }}
        """
    else:
        extra = """
        .stTabs [data-baseweb="tab"] { background: #fff; border-radius: 8px 8px 0 0; }
        """
    css = f"""
    <style>
    .stApp {{ background: {t['bg']}; color: {t['text']}; }}
    [data-testid="stHeader"] {{ background: transparent; }}
    h1, h2, h3, h4 {{ color: {t['text']}; }}
    [data-testid="stMetric"] {{
        background: {t['metric_bg']}; border: {t['metric_border']};
        border-radius: 12px; padding: 14px 18px;
    }}
    [data-testid="stMetricLabel"] {{ color: {t['muted']}; }}
    [data-testid="stMetricValue"] {{ color: {t['text']}; }}
    div[data-testid="stExpander"] {{ background: {t['card_bg']}; border: {t['card_border']};
        border-radius: 10px; }}
    .insight-card {{
        background: {t['card_bg']}; border: {t['card_border']};
        border-radius: 12px; padding: 14px 16px; height: 100%;
    }}
    .insight-card .tag {{ font-size: 12px; color: {t['muted']}; }}
    .insight-card .title {{ font-size: 15px; font-weight: 600; margin: 4px 0; }}
    .insight-card .body {{ font-size: 13px; color: {t['text']}; line-height: 1.6; }}
    .hero-sub {{ color: {t['muted']}; font-size: 14px; margin-top: -6px; }}
    .kpi-note {{ color: {t['muted']}; font-size: 12px; margin-top: 2px; }}
    {extra}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)
