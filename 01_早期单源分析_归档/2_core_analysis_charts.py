# -*- coding: utf-8 -*-
"""
阶段二脚本 2：主线核心体验图表渲染
输入：
D:/舆情分析/analysis_outputs/tables/core_experience_subset.csv

输出：
D:/舆情分析/analysis_outputs/tables/
    aspect_sentiment_crosstab.csv
    aspect_negative_ratio.csv
    painpoint_frequency.csv
    aspect_painpoint_matrix.csv
    aspect_painpoint_matrix_ratio.csv

D:/舆情分析/analysis_outputs/figures/
    aspect_sentiment_stacked_bar.png
    aspect_negative_ratio_bar.png
    painpoint_pareto.png
    aspect_painpoint_heatmap_count.png
    aspect_painpoint_heatmap_ratio.png
"""

from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns


# =========================
# 1. 路径配置
# =========================

PROJECT_DIR = Path(r"D:\舆情分析")
TABLE_DIR = PROJECT_DIR / "analysis_outputs" / "tables"
FIGURE_DIR = PROJECT_DIR / "analysis_outputs" / "figures"

INPUT_FILE = TABLE_DIR / "core_experience_subset_recoded.csv"

TABLE_DIR.mkdir(parents=True, exist_ok=True)
FIGURE_DIR.mkdir(parents=True, exist_ok=True)


# =========================
# 2. 全局配置
# =========================

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 120

SAVE_DPI = 300

SENTIMENT_LABELS = {
    -1: "负面",
    0: "中立",
    1: "正面"
}

SENTIMENT_ORDER = [-1, 0, 1]

ASPECT_ORDER = [
    "交通出行", "行程规划", "景区游玩", "景观打卡", "休闲娱乐", "餐饮消费",
    "住宿体验", "购物特产", "城市人文", "服务管理", "气候环境", "安全保障"
]

PAINPOINT_ORDER = [
    "交通拥堵", "停车困难", "接驳不便", "排队时间长", "人流拥挤", "卫生条件差",
    "价格虚高", "商业欺诈", "服务态度差", "管理混乱", "设施老旧", "气候严寒",
    "防寒不足", "路面湿滑", "安全隐患", "复合/未细分痛点"
]


# =========================
# 3. 工具函数
# =========================

def read_csv_safely(path: Path) -> pd.DataFrame:
    encodings = ["utf-8-sig", "utf-8", "gbk"]
    last_error = None

    for enc in encodings:
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception as e:
            last_error = e

    raise RuntimeError(f"CSV 读取失败，请检查编码。最后错误：{last_error}")


def save_fig(path: Path):
    plt.savefig(path, dpi=SAVE_DPI, bbox_inches="tight")
    plt.close()


def split_painpoints(value):
    if pd.isna(value):
        return []

    text = str(value).strip()
    if not text:
        return []

    return [x.strip() for x in text.split("、") if x.strip()]


def add_bar_labels(ax, fmt="{:.1%}", padding=0.01):
    for patch in ax.patches:
        width = patch.get_width()
        if width <= 0:
            continue

        x = patch.get_x() + width + padding
        y = patch.get_y() + patch.get_height() / 2
        ax.text(x, y, fmt.format(width), va="center", fontsize=9)


def ensure_sentiment_int(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Sentiment"] = pd.to_numeric(df["Sentiment"], errors="coerce").fillna(0).astype(int)
    df.loc[~df["Sentiment"].isin([-1, 0, 1]), "Sentiment"] = 0
    return df


# =========================
# 4. 模块 A：Aspect × Sentiment
# =========================

def build_aspect_sentiment_tables(df: pd.DataFrame):
    crosstab = pd.crosstab(df["Aspect"], df["Sentiment"])

    for s in SENTIMENT_ORDER:
        if s not in crosstab.columns:
            crosstab[s] = 0

    crosstab = crosstab[SENTIMENT_ORDER]

    # 只保留核心体验中出现过的 Aspect，并按既定顺序排列
    ordered_aspects = [a for a in ASPECT_ORDER if a in crosstab.index]
    crosstab = crosstab.reindex(ordered_aspects)

    crosstab.columns = [SENTIMENT_LABELS[x] for x in crosstab.columns]
    crosstab["总量"] = crosstab.sum(axis=1)
    crosstab["负面率"] = crosstab["负面"] / crosstab["总量"].replace(0, np.nan)
    crosstab["中立率"] = crosstab["中立"] / crosstab["总量"].replace(0, np.nan)
    crosstab["正面率"] = crosstab["正面"] / crosstab["总量"].replace(0, np.nan)

    crosstab = crosstab.fillna(0)

    output_path = TABLE_DIR / "aspect_sentiment_crosstab.csv"
    crosstab.to_csv(output_path, encoding="utf-8-sig")

    return crosstab


def plot_aspect_sentiment_stacked_bar(crosstab: pd.DataFrame):
    ratio_cols = ["负面率", "中立率", "正面率"]
    plot_df = crosstab.sort_values("负面率", ascending=True)

    fig_height = max(6, 0.45 * len(plot_df))
    fig, ax = plt.subplots(figsize=(11, fig_height))

    left = np.zeros(len(plot_df))
    y = np.arange(len(plot_df))

    colors = {
        "负面率": "#D95F5F",
        "中立率": "#BDBDBD",
        "正面率": "#5F9ED1"
    }

    labels = {
        "负面率": "负面",
        "中立率": "中立",
        "正面率": "正面"
    }

    for col in ratio_cols:
        values = plot_df[col].values
        ax.barh(y, values, left=left, label=labels[col], color=colors[col])
        left += values

    ax.set_yticks(y)
    ax.set_yticklabels(plot_df.index)
    ax.set_xlim(0, 1)
    ax.set_xlabel("情绪占比")
    ax.set_title("核心体验维度的情绪结构分布（100%堆叠）")
    ax.legend(loc="lower right")

    ax.set_xticks(np.linspace(0, 1, 6))
    ax.set_xticklabels([f"{int(x * 100)}%" for x in np.linspace(0, 1, 6)])

    ax.grid(axis="x", linestyle="--", alpha=0.3)

    # 标注负面率，突出重点
    for i, (_, row) in enumerate(plot_df.iterrows()):
        if row["负面率"] > 0:
            ax.text(
                row["负面率"] + 0.01,
                i,
                f"负面 {row['负面率']:.1%}",
                va="center",
                fontsize=8
            )

    save_fig(FIGURE_DIR / "aspect_sentiment_stacked_bar.png")


# =========================
# 5. 模块 B：Aspect Negative Ratio
# =========================

def build_negative_ratio_table(crosstab: pd.DataFrame):
    neg_df = crosstab[["负面", "中立", "正面", "总量", "负面率"]].copy()
    neg_df = neg_df.sort_values("负面率", ascending=False)

    output_path = TABLE_DIR / "aspect_negative_ratio.csv"
    neg_df.to_csv(output_path, encoding="utf-8-sig")

    return neg_df


def plot_negative_ratio_bar(neg_df: pd.DataFrame):
    plot_df = neg_df.sort_values("负面率", ascending=True)

    fig_height = max(6, 0.45 * len(plot_df))
    fig, ax = plt.subplots(figsize=(10, fig_height))

    ax.barh(plot_df.index, plot_df["负面率"])
    ax.set_xlabel("负面率")
    ax.set_title("核心体验维度负面率排序")

    ax.set_xlim(0, min(max(plot_df["负面率"].max() * 1.25, 0.1), 1.0))
    ax.set_xticks(np.linspace(0, ax.get_xlim()[1], 6))
    ax.set_xticklabels([f"{x:.0%}" for x in np.linspace(0, ax.get_xlim()[1], 6)])

    ax.grid(axis="x", linestyle="--", alpha=0.3)

    for i, (aspect, row) in enumerate(plot_df.iterrows()):
        ax.text(
            row["负面率"] + 0.005,
            i,
            f"{row['负面率']:.1%}  n={int(row['总量'])}",
            va="center",
            fontsize=9
        )

    save_fig(FIGURE_DIR / "aspect_negative_ratio_bar.png")


# =========================
# 6. 模块 C：PainPoints Pareto
# =========================

def build_painpoint_frequency(df: pd.DataFrame):
    neg_df = df[df["Sentiment"] == -1].copy()
    neg_df["PainPoint"] = neg_df["PainPoints"].apply(split_painpoints)

    pp_long = neg_df.explode("PainPoint")
    pp_long = pp_long.dropna(subset=["PainPoint"])
    pp_long = pp_long[pp_long["PainPoint"].astype(str).str.strip() != ""]

    if len(pp_long) == 0:
        freq_df = pd.DataFrame(columns=["PainPoint", "频次", "占比", "累计占比"])
    else:
        freq = pp_long["PainPoint"].value_counts()

        # 按预设词表补齐未出现痛点，便于横向比较
        freq = freq.reindex([p for p in PAINPOINT_ORDER if p in freq.index])

        freq_df = freq.reset_index()
        freq_df.columns = ["PainPoint", "频次"]

        total = freq_df["频次"].sum()
        freq_df["占比"] = freq_df["频次"] / total
        freq_df["累计占比"] = freq_df["占比"].cumsum()

    output_path = TABLE_DIR / "painpoint_frequency.csv"
    freq_df.to_csv(output_path, index=False, encoding="utf-8-sig")

    return freq_df, pp_long


def plot_painpoint_pareto(freq_df: pd.DataFrame):
    if freq_df.empty:
        print("PainPoints 为空，跳过帕累托图。")
        return

    fig_width = max(11, 0.65 * len(freq_df))
    fig, ax1 = plt.subplots(figsize=(fig_width, 6))

    x = np.arange(len(freq_df))

    ax1.bar(x, freq_df["频次"])
    ax1.set_ylabel("频次")
    ax1.set_xlabel("痛点类型")
    ax1.set_title("核心负面痛点帕累托图")
    ax1.set_xticks(x)
    ax1.set_xticklabels(freq_df["PainPoint"], rotation=45, ha="right")

    for i, v in enumerate(freq_df["频次"]):
        ax1.text(i, v + max(freq_df["频次"]) * 0.01, str(int(v)), ha="center", fontsize=8)

    ax2 = ax1.twinx()
    ax2.plot(x, freq_df["累计占比"], marker="o")
    ax2.set_ylabel("累计占比")
    ax2.set_ylim(0, 1.05)
    ax2.set_yticks(np.linspace(0, 1, 6))
    ax2.set_yticklabels([f"{int(t * 100)}%" for t in np.linspace(0, 1, 6)])

    ax2.axhline(0.8, linestyle="--", linewidth=1)
    ax2.text(
        len(freq_df) - 1,
        0.82,
        "80% 阈值",
        ha="right",
        va="bottom",
        fontsize=9
    )

    for i, v in enumerate(freq_df["累计占比"]):
        ax2.text(i, v + 0.025, f"{v:.0%}", ha="center", fontsize=8)

    ax1.grid(axis="y", linestyle="--", alpha=0.3)

    save_fig(FIGURE_DIR / "painpoint_pareto.png")


# =========================
# 7. 模块 D：Aspect × PainPoints Heatmap
# =========================

def build_aspect_painpoint_matrix(pp_long: pd.DataFrame):
    if pp_long.empty:
        count_matrix = pd.DataFrame(index=[], columns=[])
        ratio_matrix = pd.DataFrame(index=[], columns=[])
    else:
        count_matrix = pd.crosstab(pp_long["Aspect"], pp_long["PainPoint"])

        row_order = [a for a in ASPECT_ORDER if a in count_matrix.index]
        col_order = [p for p in PAINPOINT_ORDER if p in count_matrix.columns]

        count_matrix = count_matrix.reindex(index=row_order, columns=col_order, fill_value=0)

        ratio_matrix = count_matrix.div(
            count_matrix.sum(axis=1).replace(0, np.nan),
            axis=0
        ).fillna(0)

    count_path = TABLE_DIR / "aspect_painpoint_matrix.csv"
    ratio_path = TABLE_DIR / "aspect_painpoint_matrix_ratio.csv"

    count_matrix.to_csv(count_path, encoding="utf-8-sig")
    ratio_matrix.to_csv(ratio_path, encoding="utf-8-sig")

    return count_matrix, ratio_matrix


def plot_heatmap(matrix: pd.DataFrame, output_path: Path, title: str, value_type: str):
    """
    value_type:
    - "count": 绝对频次
    - "ratio": 行归一化百分比
    """
    if matrix.empty:
        print(f"{title} 数据为空，跳过绘图。")
        return

    data = matrix.values.astype(float)
    n_rows, n_cols = data.shape

    fig_width = max(12, 0.75 * n_cols)
    fig_height = max(6, 0.5 * n_rows)

    fig, ax = plt.subplots(figsize=(fig_width, fig_height))

    import matplotlib.colors as mcolors
    cmap_name = "Blues" if value_type == "count" else "Oranges"
    cmap_base = plt.get_cmap(cmap_name)
    cmap = mcolors.LinearSegmentedColormap.from_list("custom", cmap_base(np.linspace(0.15, 1.0, 100)))
    fmt = ".0f" if value_type == "count" else ".1%"
    
    sns.heatmap(
        data, 
        cmap=cmap, 
        annot=True, 
        fmt=fmt, 
        ax=ax, 
        cbar_kws={'label': "频次" if value_type == "count" else "行内占比"},
        xticklabels=matrix.columns,
        yticklabels=matrix.index,
        robust=True
    )

    ax.set_title(title)
    ax.set_xlabel("痛点类型")
    ax.set_ylabel("体验维度")
    ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha="right")
    ax.set_yticklabels(ax.get_yticklabels(), rotation=0)

    save_fig(output_path)


# =========================
# 8. 主流程
# =========================

def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"找不到输入文件：{INPUT_FILE}\n"
            f"请先运行 1_data_cleaning_and_subset.py 生成 core_experience_subset.csv。"
        )

    print("读取核心体验子集 ...")
    df = read_csv_safely(INPUT_FILE)
    df["PainPoints"] = df["PainPoints"].astype(str).str.replace("其他痛点", "复合/未细分痛点")
    df = ensure_sentiment_int(df)

    print(f"核心体验样本量：{len(df)}")

    # 模块 A
    print("生成 Aspect × Sentiment 交叉表与 100% 堆叠图 ...")
    crosstab = build_aspect_sentiment_tables(df)
    plot_aspect_sentiment_stacked_bar(crosstab)

    # 模块 B
    print("生成 Aspect 负面率表与负面率排序图 ...")
    neg_df = build_negative_ratio_table(crosstab)
    plot_negative_ratio_bar(neg_df)

    # 模块 C
    print("生成 PainPoints 频次表与帕累托图 ...")
    freq_df, pp_long = build_painpoint_frequency(df)
    plot_painpoint_pareto(freq_df)

    # 模块 D
    print("生成 Aspect × PainPoints 矩阵与热力图 ...")
    count_matrix, ratio_matrix = build_aspect_painpoint_matrix(pp_long)

    plot_heatmap(
        count_matrix,
        FIGURE_DIR / "aspect_painpoint_heatmap_count.png",
        "体验维度 × 痛点类型绝对频次热力图",
        value_type="count"
    )

    plot_heatmap(
        ratio_matrix,
        FIGURE_DIR / "aspect_painpoint_heatmap_ratio.png",
        "体验维度 × 痛点类型行归一化比例热力图",
        value_type="ratio"
    )

    print("\n====== 脚本 2 执行完成 ======")
    print(f"统计表输出目录：{TABLE_DIR}")
    print(f"图表输出目录：{FIGURE_DIR}")

    print("\n已生成表格：")
    print("- aspect_sentiment_crosstab.csv")
    print("- aspect_negative_ratio.csv")
    print("- painpoint_frequency.csv")
    print("- aspect_painpoint_matrix.csv")
    print("- aspect_painpoint_matrix_ratio.csv")

    print("\n已生成图表：")
    print("- aspect_sentiment_stacked_bar.png")
    print("- aspect_negative_ratio_bar.png")
    print("- painpoint_pareto.png")
    print("- aspect_painpoint_heatmap_count.png")
    print("- aspect_painpoint_heatmap_ratio.png")


if __name__ == "__main__":
    main()
