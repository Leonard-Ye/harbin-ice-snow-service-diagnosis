# -*- coding: utf-8 -*-
"""可视化 PDF 报告生成器：渲染高精度图表 (SMI Top10 + 供需象限图) + 排版级 PDF 报告。"""
import io
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

def _init_font():
    """跨平台中文字体查找：Windows / Linux(Noto/WQY) / macOS(PingFang)。

    Streamlit Cloud 为 Linux 环境，Windows 硬编码路径部署后中文会变方框。
    找不到中文字体时回退 Helvetica（PDF 不崩溃，中文字形受限）。
    """
    candidates = [
        ("C:\\Windows\\Fonts\\simhei.ttf", "SimHei", None),
        ("C:\\Windows\\Fonts\\msyh.ttc", "MicrosoftYaHei", 0),
        ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "NotoSansCJK", 0),
        ("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", "NotoSansCJK", 0),
        ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", "WenQuanYiZenHei", 0),
        ("/System/Library/Fonts/PingFang.ttc", "PingFang", 0),
    ]
    for path, name, subfont in candidates:
        if os.path.exists(path):
            try:
                if subfont is not None:
                    pdfmetrics.registerFont(TTFont(name, path, subfontIndex=subfont))
                else:
                    pdfmetrics.registerFont(TTFont(name, path))
                return name
            except Exception:
                continue
    return "Helvetica"

FONT_NAME = _init_font()

plt.rcParams["font.sans-serif"] = [
    "Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "WenQuanYi Zen Hei",
    "PingFang SC", "DejaVu Sans",
]
plt.rcParams["axes.unicode_minus"] = False

def generate_smi_chart_png(df: pd.DataFrame) -> io.BytesIO:
    sub = df.sort_values("SMI", ascending=True).tail(10)
    fig, ax = plt.subplots(figsize=(7.2, 3.4), dpi=200)
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#F8FAFC")

    smi_vals = sub["SMI"].values
    norm_vals = (smi_vals - smi_vals.min()) / (smi_vals.max() - smi_vals.min() + 1e-9)
    bar_colors = [plt.cm.coolwarm(0.25 + 0.65 * v) for v in norm_vals]

    bars = ax.barh(sub["anchor_name"], sub["SMI"], color=bar_colors, height=0.6, edgecolor="none")
    
    for bar in bars:
        w = bar.get_width()
        ax.text(w + 0.05, bar.get_y() + bar.get_height() / 2, f"{w:.2f}",
                va="center", ha="left", fontsize=8.5, fontweight="bold", color="#334155")

    ax.set_title("SMI 服务错配排名 Top 10 锚点", fontsize=11, fontweight="bold", pad=10, color="#0F172A")
    ax.set_xlabel("SMI 错配指数（正值说明需求/风险远大于供给）", fontsize=8.5, color="#64748B")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#E2E8F0")
    ax.spines["bottom"].set_color("#E2E8F0")
    ax.grid(axis="x", linestyle="--", alpha=0.4, color="#CBD5E1")
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf

def generate_quadrant_chart_png(df: pd.DataFrame) -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(7.2, 3.8), dpi=200)
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#FFFFFF")

    min_x, max_x = df["SSI"].min() - 0.4, df["SSI"].max() + 0.4
    min_y, max_y = df["DHI"].min() - 0.4, df["DHI"].max() + 0.4

    ax.fill_between([min_x, 0], 0, max_y, color="#FEE2E2", alpha=0.45, label="高需求低供给（设施不足区）")
    ax.fill_between([0, max_x], 0, max_y, color="#FFEDD5", alpha=0.45, label="高需求高供给（高峰承载区）")
    ax.fill_between([min_x, 0], min_y, 0, color="#F1F5F9", alpha=0.45, label="低需求低供给（一般监测区）")
    ax.fill_between([0, max_x], min_y, 0, color="#D1FAE5", alpha=0.45, label="低需求高供给（分流承接区）")

    ax.axhline(0, color="#94A3B8", linestyle="--", linewidth=0.9)
    ax.axvline(0, color="#94A3B8", linestyle="--", linewidth=0.9)

    type_color_map = {
        "高需求—低供给型": "#EF4444",
        "高需求—高供给—高风险型": "#F97316",
        "低需求—高风险型": "#A855F7",
        "低需求—高供给型": "#10B981",
        "高需求—高供给型": "#0284C7",
        "低需求—低供给型": "#64748B",
    }

    for diag_type, group in df.groupby("diagnosis"):
        c = type_color_map.get(diag_type, "#64748B")
        ax.scatter(group["SSI"], group["DHI"], label=diag_type, color=c, s=65, edgecolors="white", linewidth=0.8, zorder=5)
        for _, row in group.iterrows():
            ax.annotate(row["anchor_name"], (row["SSI"], row["DHI"]), fontsize=7, xytext=(3, 3), textcoords="offset points", color="#1E293B")

    ax.set_title("需求热度 DHI x 服务供给 SSI 供需诊断象限", fontsize=11, fontweight="bold", pad=10, color="#0F172A")
    ax.set_xlabel("SSI 服务供给指数 (0=样本均值)", fontsize=8.5, color="#64748B")
    ax.set_ylabel("DHI 需求热度指数 (0=样本均值)", fontsize=8.5, color="#64748B")
    ax.set_xlim(min_x, max_x)
    ax.set_ylim(min_y, max_y)
    ax.legend(loc="upper left", fontsize=7, framealpha=0.95, facecolor="#FFFFFF")
    ax.grid(True, linestyle=":", alpha=0.3, color="#94A3B8")
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf

def build_visual_pdf_bytes(df: pd.DataFrame, method: str) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=32,
        rightMargin=32,
        topMargin=32,
        bottomMargin=32,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontName=FONT_NAME,
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=4,
    )
    meta_style = ParagraphStyle(
        "DocMeta",
        parent=styles["Normal"],
        fontName=FONT_NAME,
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#64748B"),
        spaceAfter=10,
    )
    h2_style = ParagraphStyle(
        "SectionH2",
        parent=styles["Heading2"],
        fontName=FONT_NAME,
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#0284C7"),
        spaceBefore=10,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "BodyDark",
        parent=styles["Normal"],
        fontName=FONT_NAME,
        fontSize=8.5,
        leading=13.5,
        textColor=colors.HexColor("#334155"),
        spaceAfter=4,
    )

    story = []

    story.append(Paragraph("哈尔滨冰雪旅游服务设施供需诊断分析简报", title_style))
    method_name = "熵权法（数据驱动）" if method == "entropy" else "等权重方案"
    now_str = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
    story.append(
        Paragraph(
            f"<b>多源数据：</b>高德 POI (5.8万) | 携程住宿 | 大众点评评论 | 小红书文本 (3.3万) | <b>权重方案：</b>{method_name} | <b>生成时间：</b>{now_str}",
            meta_style,
        )
    )
    story.append(HRFlowable(width="100%", thickness=1.2, color=colors.HexColor("#38BDF8"), spaceAfter=10))

    kpi_data = [
        [
            Paragraph("<b>数据记录规模</b><br/><font size=10 color='#0284C7'><b>8 万+ 条记录</b></font>", body_style),
            Paragraph("<b>核心文旅锚点</b><br/><font size=10 color='#0284C7'><b>20 个核心区</b></font>", body_style),
            Paragraph("<b>自研诊断指标</b><br/><font size=10 color='#0284C7'><b>5 项 (DHI/SSI/SMI)</b></font>", body_style),
            Paragraph("<b>主要错配类型</b><br/><font size=10 color='#EF4444'><b>设施不足/高峰承载</b></font>", body_style),
        ]
    ]
    t_kpi = Table(kpi_data, colWidths=[132, 132, 132, 135])
    t_kpi.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#E2E8F0")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(t_kpi)
    story.append(Spacer(1, 8))

    story.append(Paragraph("一、 多源融合诊断结论与分区优化策略", h2_style))

    strategies = [
        (
            "<b>1. 高需求—低供给重点关注区（近场设施与交通接驳）</b>",
            "松花江冰雪嘉年华、冰雪大世界、太阳岛等锚点呈现极高游客关注度，但周边 3km 住宿、餐饮及交通基础设施供给离群偏低。优化重点在于补充近场短途接驳、设置临时防寒休憩暖棚、移动卫生间与夜间疏散应急交通，避免设施缺口影响游客体验。"
        ),
        (
            "<b>2. 高需求—高供给高承载区（高峰管理与客流分流）</b>",
            "中央大街、圣索菲亚教堂等老城核心锚点设施总量充足，但冰雪旺季高峰期面临巨大的承载与排队压力。优化核心在于推行预约分流、排队时长可视化、价格合规监管与步行空间流线组织，引导客流向周边次级节点疏散，而非盲目增建设施。"
        ),
        (
            "<b>3. 局部体验风险与外溢承接区（定点整改与副中心分流）</b>",
            "果戈里大街等锚点体验风险指数（ERI）较高，需聚焦排队与交通痛点开展定点整改；中东铁路桥、中华巴洛克等低需求高供给锚点，基础设施充裕，具备承接核心商圈外溢客流的良好潜力，可作为精品游览替代线路节点。"
        ),
        (
            "<b>4. 餐饮消费压力区（明码标价与线上取号）</b>",
            "结合大众点评餐饮压力增强验证（ERI_plus），冰雪旅游旺季主要矛盾体现为热门商圈的价格感知与排队等待。建议推动热门餐饮商家推行线上取号预定与明码标价，并引导游客向哈西、群力等副中心商圈分流。"
        ),
        (
            "<b>5. 多源数据动态监测机制（长效保障）</b>",
            "建立面向冰雪季的多源数据动态监测机制，持续跟踪高德 POI 变化、携程住宿价格与空房、大众点评餐饮压力及小红书舆情痛点，动态更新 DHI、SSI、ERI 与 SMI 指标，为节假日高峰保障与应急设施投放提供及时科学依据。"
        ),
    ]

    strategy_table_rows = []
    for title, text in strategies:
        p_title = Paragraph(title, ParagraphStyle("StTitle", parent=body_style, fontSize=9, textColor=colors.HexColor("#0284C7"), leading=12))
        p_text = Paragraph(text, body_style)
        strategy_table_rows.append([p_title])
        strategy_table_rows.append([p_text])

    t_strat = Table(strategy_table_rows, colWidths=[531])
    t_strat.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#E2E8F0")),
                ("LINELEFT", (0, 0), (-1, -1), 3, colors.HexColor("#0284C7")),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(t_strat)
    story.append(Spacer(1, 10))

    story.append(Paragraph("二、 SMI 服务错配 Top 10 锚点可视化", h2_style))
    chart1_buf = generate_smi_chart_png(df)
    story.append(Image(chart1_buf, width=530, height=240))

    story.append(Spacer(1, 10))

    story.append(Paragraph("三、 需求热度 DHI x 服务供给 SSI 供需诊断象限", h2_style))
    chart2_buf = generate_quadrant_chart_png(df)
    story.append(Image(chart2_buf, width=530, height=270))

    story.append(Spacer(1, 10))

    story.append(Paragraph("四、 Top 10 服务错配锚点详细指标明细", h2_style))
    top10_df = df.sort_values("SMI", ascending=False).head(10)
    
    table_data = [["排名", "锚点名称", "SMI错配", "DHI需求", "SSI供给", "ERI风险", "诊断类型"]]
    for i, r in top10_df.reset_index().iterrows():
        table_data.append(
            [
                str(i + 1),
                r["anchor_name"],
                f"{r['SMI']:.2f}",
                f"{r['DHI']:.2f}",
                f"{r['SSI']:.2f}",
                f"{r['ERI']:.2f}",
                r["diagnosis"],
            ]
        )

    t_detail = Table(table_data, colWidths=[35, 110, 55, 55, 55, 55, 166])
    t_detail.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0284C7")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("ALIGN", (2, 0), (5, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("TOPPADDING", (0, 0), (-1, -1), 4.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
            ]
        )
    )
    story.append(t_detail)

    doc.build(story)
    return buf.getvalue()