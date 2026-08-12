# -*- coding: utf-8 -*-
"""UI 主题系统：深/浅两套主题（CSS + Plotly 模板 + 诊断类型配色）。

用法：
    theme = ui_theme.get_theme()          # "dark" | "light"（session_state）
    ui_theme.apply_theme(theme)           # 注入 CSS
    fig.update_layout(template=ui_theme.plotly_template(theme))
    colors = ui_theme.type_colors(theme)  # 诊断类型 → 颜色
"""
import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------- 主题色板 (Design Tokens)
DARK = {
    "name": "dark",
    "bg": "#0B0F17",
    "panel": "#131B2A",
    "panel2": "#1A2436",
    "text": "#F8FAFC",
    "muted": "#94A3B8",
    "accent": "#38BDF8",     # 冰晶蓝
    "accent2": "#C084FC",    # 极光紫
    "grid": "rgba(255, 255, 255, 0.05)",
    "metric_bg": "linear-gradient(135deg, rgba(56, 189, 248, 0.06) 0%, rgba(192, 132, 252, 0.03) 100%)",
    "metric_border": "1px solid rgba(56, 189, 248, 0.20)",
    "card_bg": "rgba(19, 27, 42, 0.75)",
    "card_border": "1px solid rgba(255, 255, 255, 0.08)",
    "surface": "rgba(19, 27, 42, 0.85)",
    "shadow": "0 8px 32px rgba(0, 0, 0, 0.40)",
    "glow": "0 0 20px rgba(56, 189, 248, 0.20)",
}

LIGHT = {
    "name": "light",
    "bg": "#F8FAFC",
    "panel": "#FFFFFF",
    "panel2": "#F1F5F9",
    "text": "#0F172A",
    "muted": "#64748B",
    "accent": "#0284C7",     # 冰川蓝
    "accent2": "#9333EA",    # 极光紫
    "grid": "rgba(0, 0, 0, 0.05)",
    "metric_bg": "linear-gradient(135deg, rgba(2, 132, 199, 0.05) 0%, rgba(147, 51, 234, 0.02) 100%)",
    "metric_border": "1px solid rgba(2, 132, 199, 0.16)",
    "card_bg": "rgba(255, 255, 255, 0.90)",
    "card_border": "1px solid rgba(0, 0, 0, 0.06)",
    "surface": "#FFFFFF",
    "shadow": "0 4px 20px rgba(15, 23, 42, 0.06)",
    "glow": "0 0 15px rgba(2, 132, 199, 0.15)",
}

THEMES = {"dark": DARK, "light": LIGHT}

# ---------------------------------------------------------------- 诊断类型配色
TYPE_COLORS = {
    "dark": {
        "高需求—低供给型": "#F87171",       # 珊红：设施不足
        "高需求—高供给—高风险型": "#FB923C", # 暖橙：高峰承载
        "低需求—高风险型": "#C084FC",        # 罗兰紫：局部风险
        "低需求—高供给型": "#34D399",        # 翡翠绿：分流承接
        "高需求—高供给型": "#38BDF8",        # 冰蓝：均衡
        "低需求—低供给型": "#94A3B8",        # 板岩灰：一般监测
    },
    "light": {
        "高需求—低供给型": "#DC2626",
        "高需求—高供给—高风险型": "#EA580C",
        "低需求—高风险型": "#9333EA",
        "低需求—高供给型": "#16A34A",
        "高需求—高供给型": "#0284C7",
        "低需求—低供给型": "#64748B",
    },
}


def get_theme() -> str:
    """读取当前主题（Streamlit 原生，跟随设置菜单/系统偏好）。"""
    try:
        theme = st.context.theme.type
        return theme if theme in ("dark", "light") else "light"
    except Exception:
        return "light"


def set_theme(theme: str) -> None:
    raise NotImplementedError(
        "Streamlit 原生主题不可程序化切换，请在右上角 ⚙ 设置 → Theme 中切换。"
    )


def type_colors(theme: str) -> dict:
    return TYPE_COLORS[theme]


def hex_to_rgb(hex_color: str):
    """hex 颜色 → deck.gl RGB 列表。"""
    if not isinstance(hex_color, str) or not hex_color.startswith("#") or len(hex_color) != 7:
        return [128, 128, 128, 255]
    return [int(hex_color[i : i + 2], 16) for i in (1, 3, 5)] + [255]


def palette(theme: str) -> dict:
    return THEMES[theme]


def plotly_template(theme: str) -> go.layout.Template:
    """大厂级 Plotly 零边距高高密图表模板。"""
    t = THEMES[theme]
    template = go.layout.Template()
    template.layout = go.Layout(
        font=dict(
            family="'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif",
            color=t["text"],
            size=12,
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        colorway=[t["accent"], t["accent2"], "#34D399", "#FB923C", "#F87171", "#C084FC"],
        margin=dict(l=10, r=20, t=35, b=10),
        xaxis=dict(
            gridcolor=t["grid"],
            zerolinecolor=t["grid"],
            linecolor=t["grid"],
            title=dict(font=dict(size=12, color=t["muted"])),
            tickfont=dict(size=11, color=t["muted"]),
        ),
        yaxis=dict(
            gridcolor=t["grid"],
            zerolinecolor=t["grid"],
            linecolor=t["grid"],
            title=dict(font=dict(size=12, color=t["muted"])),
            tickfont=dict(size=11, color=t["muted"]),
        ),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            bordercolor="rgba(0,0,0,0)",
            font=dict(size=11, color=t["text"]),
        ),
        hoverlabel=dict(
            bgcolor=t["panel2"],
            bordercolor=t["grid"],
            font=dict(family="'Inter', 'Microsoft YaHei', sans-serif", color=t["text"], size=12),
        ),
        coloraxis_colorbar=dict(outlinewidth=0),
    )
    return template


def apply_theme(theme: str) -> None:
    """注入大厂级 Bento Box 布局、Glassmorphism 玻璃拟态与数字微调 CSS。"""
    t = THEMES[theme]
    css = f"""
    <style>
    /* 全局平滑渲染与数字等宽 */
    html, body, [class*="st-"] {{
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
        font-variant-numeric: tabular-nums;
    }}
    
    /* ---- st.container(border=True) Bento Box 容器美化 ---- */
    div[data-testid="stVerticalBlockBorderWrapper"] > div {{
        background: {t['card_bg']} !important;
        border: {t['card_border']} !important;
        border-radius: 12px !important;
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        box-shadow: {t['shadow']};
        transition: transform 0.2s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    }}
    div[data-testid="stVerticalBlockBorderWrapper"] > div:hover {{
        border-color: {t['accent']}44 !important;
    }}

    /* ---- stMetric KPI 卡片质感升级 ---- */
    [data-testid="stMetric"] {{
        background: {t['metric_bg']} !important;
        border: {t['metric_border']} !important;
        border-radius: 12px !important;
        padding: 14px 16px !important;
        position: relative !important;
        overflow: hidden !important;
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        box-shadow: {t['shadow']};
        transition: transform 0.2s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    }}
    [data-testid="stMetric"]::before {{
        content: "";
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 3px;
        background: linear-gradient(90deg, {t['accent']}, {t['accent2']});
        opacity: 0.8;
    }}
    [data-testid="stMetric"]:hover {{
        transform: translateY(-2px);
        box-shadow: {t['glow']};
    }}
    [data-testid="stMetricLabel"] {{
        color: {t['muted']} !important;
        font-size: 13px !important;
        font-weight: 500 !important;
        letter-spacing: 0.2px;
    }}
    [data-testid="stMetricValue"] {{
        color: {t['text']} !important;
        font-weight: 700 !important;
        font-size: 24px !important;
        letter-spacing: -0.5px;
    }}

    /* ---- stExpander 质感重构 ---- */
    div[data-testid="stExpander"] {{
        background: {t['card_bg']} !important;
        border: {t['card_border']} !important;
        border-radius: 12px !important;
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        box-shadow: {t['shadow']};
    }}

    /* ---- 洞察卡片 (Bento Card) ---- */
    .insight-card {{
        background: {t['card_bg']};
        border: {t['card_border']};
        border-radius: 12px;
        padding: 16px 18px;
        height: 100%;
        position: relative;
        overflow: hidden;
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        box-shadow: {t['shadow']};
        transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
    }}
    .insight-card:hover {{
        transform: translateY(-2px);
        box-shadow: {t['glow']};
        border-color: {t['accent']}55;
    }}
    .insight-card .title {{
        font-size: 15px;
        font-weight: 700;
        color: {t['text']};
        margin: 6px 0 8px;
        letter-spacing: -0.2px;
    }}
    .insight-card .body {{
        font-size: 13px;
        color: {t['muted']};
        line-height: 1.6;
    }}

    /* ---- Hero 头部沉浸式面板 ---- */
    .st-key-hero {{
        background: linear-gradient(135deg, {t['accent']}0A 0%, {t['accent2']}05 50%, transparent 100%) !important;
        border: {t['card_border']} !important;
        border-radius: 14px !important;
        padding: 18px 22px 14px !important;
        margin-bottom: 14px !important;
        backdrop-filter: blur(14px);
        -webkit-backdrop-filter: blur(14px);
        box-shadow: {t['shadow']};
    }}
    .st-key-hero h1 {{
        background: linear-gradient(135deg, {t['text']} 50%, {t['accent']} 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800 !important;
        letter-spacing: -0.8px;
        margin-bottom: 4px !important;
    }}
    .hero-sub {{
        color: {t['muted']};
        font-size: 14px;
        line-height: 1.5;
        margin-top: 0px;
    }}

    /* ---- 导出卡片（与 hero 同风格的分区卡片）---- */
    .st-key-export {{
        background: {t['surface']} !important;
        border: {t['card_border']} !important;
        border-radius: 14px !important;
        padding: 14px 20px !important;
        margin-top: 12px !important;
        box-shadow: {t['shadow']};
    }}

    /* ---- 标题修饰条 ---- */
    .section-title {{
        display: flex;
        align-items: center;
        gap: 10px;
        font-size: 15px;
        font-weight: 700;
        color: {t['text']};
        margin: 16px 0 10px;
        letter-spacing: -0.3px;
    }}
    .section-title::before {{
        content: "";
        width: 4px;
        height: 16px;
        border-radius: 4px;
        background: linear-gradient(180deg, {t['accent']}, {t['accent2']});
        box-shadow: 0 0 8px {t['accent']}66;
    }}

    /* ---- Tabs 页签美化 ---- */
    button[data-baseweb="tab"] {{
        font-weight: 600 !important;
        font-size: 13px !important;
        border-radius: 8px 8px 0 0 !important;
        padding: 8px 16px !important;
        transition: all 0.2s ease !important;
    }}
    button[data-baseweb="tab"]:hover {{
        color: {t['accent']} !important;
        background: {t['accent']}0D !important;
    }}

    /* ---- 按钮与下载控件 ---- */
    div.stButton > button {{
        border-radius: 10px !important;
        font-weight: 600 !important;
        transition: all 0.2s ease !important;
    }}
    div.stDownloadButton > button {{
        border-radius: 10px !important;
        font-weight: 600 !important;
        border: 1px solid {t['accent']}33 !important;
        background: {t['metric_bg']} !important;
        color: {t['text']} !important;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }}
    div.stDownloadButton > button:hover {{
        border-color: {t['accent']} !important;
        box-shadow: {t['glow']} !important;
        transform: translateY(-2px);
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


