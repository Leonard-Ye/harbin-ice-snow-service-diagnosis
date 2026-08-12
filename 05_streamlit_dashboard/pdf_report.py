# -*- coding: utf-8 -*-
"""可视化 PDF 报告生成器：渲染高精度图表 (SMI Top10 + 供需象限图) + 排版级 PDF 报告。"""
import io
import os
import matplotlib
matplotlib.use("Agg")  # 后台无 GUI 渲染模式
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

# ---------------------------------------------------------------- 中文字体注册
def _init_font():
    font_path = "C:\\Windows\\Fonts\\simhei.ttf"
    if os.path.exists(font_path):
        try:
            pdfmetrics.registerFont(TTFont("SimHei", font_path))
            return "SimHei"
        except Exception:
            pass
    return "Helvetica"


FONT_NAME = _init_font()

# Matplotlib 中文字体设置
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


# ---------------------------------------------------------------- 图表渲染引擎
def generate_smi_chart_png(df: pd.DataFrame) -> io.BytesIO:
    """渲染 SMI 错配 Top 10 水平渐变柱状图。"""
    sub = df.sort_values("SMI", ascending=True).tail(10)
    fig, ax = plt.subplots(figsize=(7.5, 3.8), dpi=200)
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#F8FAFC")

    # 渐变配色：SMI 高（错配重）→ 珊瑚红，SMI 低 → 冰蓝
    smi_vals = sub["SMI"].values
    norm_vals = (smi_vals - smi_vals.min()) / (smi_vals.max() - smi_vals.min() + 1e-9)
    bar_colors = [plt.cm.coolwarm(0.3 + 0.6 * v) for v in norm_vals]

    bars = ax.barh(sub["anchor_name"], sub["SMI"], color=bar_colors, height=0.6, edgecolor="none")
    
    # 标签数值
    for bar in bars:
        w = bar.get_width()
        ax.text(w + 0.05, bar.get_y() + bar.get_height() / 2, f"{w:.2f}",
                va="center", ha="left", fontsize=9, fontweight="bold", color="#334155")

    ax.set_title("SMI 服务错配排名 Top 10 锚点", fontsize=12, fontweight="bold", pad=12, color="#0F172A")
    ax.set_xlabel("SMI 错配指数（正值说明需求/风险远大于供给）", fontsize=9, color="#64748B")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#E2E8F0")
    ax.spines["bottom"].set_color("#E2E8F0")
    ax.grid(axis="x", linestyle="--", alpha=0.5, color="#CBD5E1")
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def generate_quadrant_chart_png(df: pd.DataFrame) -> io.BytesIO:
    """渲染 DHI × SSI 供需四象限散点图（包含 4 象限软底色区）。"""
    fig, ax = plt.subplots(figsize=(7.5, 4.2), dpi=200)
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#FFFFFF")

    min_x, max_x = df["SSI"].min() - 0.4, df["SSI"].max() + 0.4
    min_y, max_y = df["DHI"].min() - 0.4, df["DHI"].max() + 0.4

    # 绘制 4 象限淡色底板
    ax.fill_between([min_x, 0], 0, max_y, color="#FEE2E2", alpha=0.45, label="高需求低供给（设施不足区）")
    ax.fill_between([0, max_x], 0, max_y, color="#FFEDD5", alpha=0.45, label="高需求高供给（高峰承载区）")
    ax.fill_between([min_x, 0], min_y, 0, color="#F1F5F9", alpha=0.45, label="低需求低供给（一般监测区）")
    ax.fill_between([0, max_x], min_y, 0, color="#D1FAE5", alpha=0.45, label="低需求高供给（分流承接区）")

    # 象限参考线
    ax.axhline(0, color="#94A3B8", linestyle="--", linewidth=1.0)
    ax.axvline(0, color="#94A3B8", linestyle="--", linewidth=1.0)

    # 散点渲染
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
        ax.scatter(group["SSI"], group["DHI"], label=diag_type, color=c, s=70, edgecolors="white", linewidth=1, zorder=5)
        for _, row in group.iterrows():
            ax.annotate(row["anchor_name"], (row["SSI"], row["DHI"]), fontsize=7.5, xytext=(4, 4), textcoords="offset points", color="#1E293B")

    ax.set_title("需求热度 DHI × 服务供给 SSI 供需诊断象限", fontsize=12, fontweight="bold", pad=12, color="#0F172A")
    ax.set_xlabel("SSI 服务供给指数 (0=样本均值)", fontsize=9, color="#64748B")
    ax.set_ylabel("DHI 需求热度指数 (0=样本均值)", fontsize=9, color="#64748B")
    ax.set_xlim(min_x, max_x)
    ax.set_ylim(min_y, max_y)
    ax.legend(loc="upper left", fontsize=7.5, framealpha=0.95, facecolor="#FFFFFF")
    ax.grid(True, linestyle=":", alpha=0.3, color="#94A3B8")
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


# ---------------------------------------------------------------- Visual PDF 文档排版
def build_visual_pdf_bytes(df: pd.DataFrame, method: str) -> bytes:
    """生成包含高精图表与精美排版的 Visual PDF 报告字节流。"""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()

    # 极光冰雪主题 Style 族
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontName=FONT_NAME,
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=6,
    )
    meta_style = ParagraphStyle(
        "DocMeta",
        parent=styles["Normal"],
        fontName=FONT_NAME,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#64748B"),
        spaceAfter=14,
    )
    h2_style = ParagraphStyle(
        "SectionH2",
        parent=styles["Heading2"],
        fontName=FONT_NAME,
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#0284C7"),
        spaceBefore=12,
        spaceAfter=8,
    )
    body_style = ParagraphStyle(
        "BodyDark",
        parent=styles["Normal"],
        fontName=FONT_NAME,
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor("#334155"),
        spaceAfter=6,
    )

    story = []

    # 1. 顶部 Header & 标题
    story.append(Paragraph("哈尔滨冰雪旅游服务设施供需诊断简报", title_style))
    method_name = "熵权法（数据驱动）" if method == "entropy" else "等权（报告基线口径）"
    now_str = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
    story.append(
        Paragraph(
            f"<b>数据源：</b>高德·携程·大众点评·小红书 | <b>赋权方案：</b>{method_name} | <b>导出时间：</b>{now_str}",
            meta_style,
        )
    )
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#38BDF8"), spaceAfter=12))

    # 2. 核心 KPI 汇总卡片
    kpi_data = [
        [
            Paragraph("<b>数据记录规模</b><br/><font size=11 color='#0284C7'><b>8 万+ 条</b></font>", body_style),
            Paragraph("<b>核心文旅锚点</b><br/><font size=11 color='#0284C7'><b>20 个核心区</b></font>", body_style),
            Paragraph("<b>自研诊断指标</b><br/><font size=11 color='#0284C7'><b>5 项 (SMI/DHI/SSI)</b></font>", body_style),
            Paragraph("<b>主要错配类型</b><br/><font size=11 color='#EF4444'><b>设施不足/高峰承载</b></font>", body_style),
        ]
    ]
    t_kpi = Table(kpi_data, colWidths=[130, 130, 130, 130])
    t_kpi.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#E2E8F0")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    story.append(t_kpi)
    story.append(Spacer(1, 14))

    # 3. 核心结论与分类策略
    story.append(Paragraph("一、 核心诊断结论与优化策略", h2_style))
    conclusions = [
        "<b>1. 设施不足型（松花江 · 冰雪大世界 · 太阳岛）：</b>高需求但近场服务薄弱（住宿/餐饮/交通供给离群低值），建议优先补短途接驳与防寒休憩设施。",
        "<b>2. 高峰承载型（中央大街 · 圣索菲亚教堂）：</b>设施供给充足但高峰期排队与价格压力突出，应侧重客流分流与排队组织而非盲目增建设施。",
        "<b>3. 局部风险与分流潜力型（果戈里大街 · 中东铁路桥）：</b>果戈里大街排队痛点显著需定点整改；低需求高供给锚点具备承接核心区外溢客流的潜力。",
    ]
    for c in conclusions:
        story.append(Paragraph(c, body_style))

    story.append(Spacer(1, 10))

    # 4. 可视化图表 1：SMI Top 10 柱状图
    story.append(Paragraph("二、 服务错配 Top 10 锚点可视化", h2_style))
    chart1_buf = generate_smi_chart_png(df)
    story.append(Image(chart1_buf, width=520, height=260))

    story.append(Spacer(1, 12))

    # 5. 可视化图表 2：DHI × SSI 四象限散点图
    story.append(Paragraph("三、 需求热度 DHI × 服务供给 SSI 四象限矩阵", h2_style))
    chart2_buf = generate_quadrant_chart_png(df)
    story.append(Image(chart2_buf, width=520, height=290))

    story.append(Spacer(1, 14))

    # 6. Top 10 锚点诊断明细表
    story.append(Paragraph("四、 Top 10 服务错配锚点详细指标", h2_style))
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

    t_detail = Table(table_data, colWidths=[36, 110, 55, 55, 55, 55, 154])
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
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(t_detail)

    doc.build(story)
    return buf.getvalue()
