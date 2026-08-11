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
    """读取当前主题（Streamlit 原生，跟随设置菜单/系统偏好）。

    全局颜色由 .streamlit/config.toml 的 [theme.light]/[theme.dark] 接管，
    这里只读取值以驱动 Plotly 模板与图表语义配色。
    """
    try:
        theme = st.context.theme.type  # "light" | "dark"
        return theme if theme in ("dark", "light") else "light"
    except Exception:
        return "light"


def set_theme(theme: str) -> None:
    """原生主题由设置菜单控制，不可程序化设置；保留占位以防误用。"""
    raise NotImplementedError(
        "Streamlit 原生主题不可程序化切换，请在右上角 ⚙ 设置 → Theme 中切换。"
    )


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
    """注入组件级 CSS（内容卡片/KPI 视觉增强）。

    遵循官方最佳实践：全局背景/文字/控件颜色由 .streamlit/config.toml 原生主题
    接管，此处**只**负责自定义组件（insight-card、KPI 渐变卡）的视觉效果。
    """
    t = THEMES[theme]
    css = f"""
    <style>
    [data-testid="stMetric"] {{
        background: {t['metric_bg']}; border: {t['metric_border']};
        border-radius: 12px; padding: 14px 18px;
    }}
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
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)
