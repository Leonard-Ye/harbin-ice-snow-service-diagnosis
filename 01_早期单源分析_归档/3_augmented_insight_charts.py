# -*- coding: utf-8 -*-
"""
阶段二脚本 3：高阶增强洞察图表
功能：
1. 时序舆情趋势分析：全量清洗数据
2. 南北方客源地痛点差异分析：核心体验子集
3. 明确游客画像痛点偏好雷达图：核心体验子集

输入：
D:/舆情分析/analysis_outputs/tables/cleaned_structured_sentiment.csv
D:/舆情分析/analysis_outputs/tables/core_experience_subset.csv

输出：
D:/舆情分析/analysis_outputs/tables/
    temporal_sentiment_trend.csv
    ip_location_summary.csv
    regional_painpoint_comparison.csv
    persona_painpoint_summary.csv

D:/舆情分析/analysis_outputs/figures/
    temporal_sentiment_trend.png
    regional_painpoint_comparison.png
    persona_painpoint_radar.png
"""

from pathlib import Path
import math
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


# =========================
# 1. 路径配置
# =========================

PROJECT_DIR = Path(r"D:\舆情分析")
TABLE_DIR = PROJECT_DIR / "analysis_outputs" / "tables"
FIGURE_DIR = PROJECT_DIR / "analysis_outputs" / "figures"

FULL_INPUT_FILE = TABLE_DIR / "cleaned_structured_sentiment_timefixed.csv"
CORE_INPUT_FILE = TABLE_DIR / "core_experience_subset_recoded.csv"

TABLE_DIR.mkdir(parents=True, exist_ok=True)
FIGURE_DIR.mkdir(parents=True, exist_ok=True)


# =========================
# 2. 全局配置
# =========================

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 120

SAVE_DPI = 300

PAINPOINT_ORDER = [
    "交通拥堵", "停车困难", "接驳不便", "排队时间长", "人流拥挤", "卫生条件差",
    "价格虚高", "商业欺诈", "服务态度差", "管理混乱", "设施老旧", "气候严寒",
    "防寒不足", "路面湿滑", "安全隐患", "复合/未细分痛点"
]

TARGET_PERSONAS = ["亲子家庭", "情侣伴侣", "朋友结伴"]


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


def ensure_sentiment_int(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Sentiment"] = pd.to_numeric(df["Sentiment"], errors="coerce").fillna(0).astype(int)
    df.loc[~df["Sentiment"].isin([-1, 0, 1]), "Sentiment"] = 0
    return df


def split_painpoints(value):
    if pd.isna(value):
        return []

    text = str(value).strip()
    if not text:
        return []

    return [x.strip() for x in text.split("、") if x.strip()]


def prepare_negative_painpoint_long(df: pd.DataFrame) -> pd.DataFrame:
    """
    将核心体验负面样本中的 PainPoints 拆成长表。
    """
    neg_df = df[df["Sentiment"] == -1].copy()
    neg_df["PainPoint"] = neg_df["PainPoints"].apply(split_painpoints)

    long_df = neg_df.explode("PainPoint")
    long_df = long_df.dropna(subset=["PainPoint"])
    long_df = long_df[long_df["PainPoint"].astype(str).str.strip() != ""]

    return long_df


def parse_publish_date(df: pd.DataFrame) -> pd.DataFrame:
    """
    优先使用 publish_date；
    若不可用，则回退到 publish_time。
    """
    df = df.copy()

    if "publish_date" in df.columns:
        df["publish_date_parsed"] = pd.to_datetime(df["publish_date"], errors="coerce")
    else:
        df["publish_date_parsed"] = pd.NaT

    if df["publish_date_parsed"].isna().all() and "publish_time" in df.columns:
        df["publish_date_parsed"] = pd.to_datetime(df["publish_time"], errors="coerce")

    df["publish_date_parsed"] = df["publish_date_parsed"].dt.normalize()

    return df


# =========================
# 4. 模块 E：时序舆情趋势
# =========================

def build_temporal_trend_table(full_df: pd.DataFrame) -> pd.DataFrame:
    df = parse_publish_date(full_df)
    df = df.dropna(subset=["publish_date_parsed"]).copy()

    if df.empty:
        return pd.DataFrame()

    daily_total = df.groupby("publish_date_parsed").size().rename("daily_total_posts")
    daily_negative = (
        df[df["Sentiment"] == -1]
        .groupby("publish_date_parsed")
        .size()
        .rename("daily_negative_posts")
    )

    date_index = pd.date_range(
        start=df["publish_date_parsed"].min(),
        end=df["publish_date_parsed"].max(),
        freq="D"
    )

    trend = pd.concat([daily_total, daily_negative], axis=1).reindex(date_index).fillna(0)
    trend.index.name = "publish_date"
    trend = trend.reset_index()

    trend["daily_total_posts"] = trend["daily_total_posts"].astype(int)
    trend["daily_negative_posts"] = trend["daily_negative_posts"].astype(int)

    trend["negative_ratio"] = trend["daily_negative_posts"] / trend["daily_total_posts"].replace(0, np.nan)
    trend["negative_ratio"] = trend["negative_ratio"].fillna(0)

    trend["total_posts_7d_ma"] = trend["daily_total_posts"].rolling(window=7, min_periods=1).mean()
    trend["negative_posts_7d_ma"] = trend["daily_negative_posts"].rolling(window=7, min_periods=1).mean()
    trend["negative_ratio_7d_ma"] = trend["negative_ratio"].rolling(window=7, min_periods=1).mean()

    output_path = TABLE_DIR / "temporal_sentiment_trend.csv"
    trend.to_csv(output_path, index=False, encoding="utf-8-sig")

    return trend


def plot_temporal_trend(trend: pd.DataFrame):
    if trend.empty:
        print("时序数据为空，跳过 temporal_sentiment_trend.png。")
        return

    fig, ax1 = plt.subplots(figsize=(13, 6))

    x = trend["publish_date"]

    ax1.fill_between(
        x,
        trend["total_posts_7d_ma"],
        alpha=0.35,
        label="发帖量 7日均值"
    )
    ax1.plot(
        x,
        trend["total_posts_7d_ma"],
        linewidth=1.8,
        label="发帖量 7日均值"
    )
    ax1.set_xlabel("发布日期")
    ax1.set_ylabel("每日发帖量（7日均值）")
    ax1.grid(axis="y", linestyle="--", alpha=0.3)

    ax2 = ax1.twinx()
    ax2.plot(
        x,
        trend["negative_posts_7d_ma"],
        linewidth=2.2,
        label="负面量 7日均值"
    )
    ax2.set_ylabel("每日负面帖子数（7日均值）")

    ax1.set_title("哈尔滨旅游舆情时序波动趋势：发帖量与负面量")

    # 合并图例
    lines_1, labels_1 = ax1.get_legend_handles_labels()
    lines_2, labels_2 = ax2.get_legend_handles_labels()
    ax1.legend(lines_1 + lines_2, labels_1 + labels_2, loc="upper left")

    fig.autofmt_xdate(rotation=30)

    save_fig(FIGURE_DIR / "temporal_sentiment_trend.png")


# =========================
# 5. 模块 F：南北方客源地痛点差异
# =========================

def build_regional_painpoint_table(core_df: pd.DataFrame):
    long_df = prepare_negative_painpoint_long(core_df)

    if long_df.empty or "Region" not in long_df.columns:
        summary = pd.DataFrame()
        comparison = pd.DataFrame()
        return summary, comparison

    # 只比较南方与北方
    long_df = long_df[long_df["Region"].isin(["南方", "北方"])].copy()

    if long_df.empty:
        summary = pd.DataFrame()
        comparison = pd.DataFrame()
        return summary, comparison

    # 每个区域的负面样本数，注意这里是负面帖子数，不是痛点提及数
    neg_posts_by_region = (
        core_df[(core_df["Sentiment"] == -1) & (core_df["Region"].isin(["南方", "北方"]))]
        .groupby("Region")
        .size()
        .rename("negative_post_count")
    )

    count_table = pd.crosstab(long_df["PainPoint"], long_df["Region"])
    count_table = count_table.reindex(PAINPOINT_ORDER).fillna(0).astype(int)

    # 出现率：某痛点在该区域负面样本中的出现次数 / 该区域负面帖子数
    rate_table = count_table.copy().astype(float)
    for region in ["南方", "北方"]:
        base = neg_posts_by_region.get(region, 0)
        if base > 0 and region in rate_table.columns:
            rate_table[region] = rate_table[region] / base
        elif region in rate_table.columns:
            rate_table[region] = 0

    # 导出长表 summary
    rows = []
    for pp in count_table.index:
        for region in ["南方", "北方"]:
            rows.append({
                "PainPoint": pp,
                "Region": region,
                "频次": int(count_table.loc[pp, region]) if region in count_table.columns else 0,
                "负面样本基数": int(neg_posts_by_region.get(region, 0)),
                "出现率": float(rate_table.loc[pp, region]) if region in rate_table.columns else 0,
                "千分比": float(rate_table.loc[pp, region] * 1000) if region in rate_table.columns else 0
            })

    summary = pd.DataFrame(rows)

    # 对比表，便于画图
    comparison = pd.DataFrame({
        "PainPoint": count_table.index,
        "南方频次": count_table["南方"].values if "南方" in count_table.columns else 0,
        "北方频次": count_table["北方"].values if "北方" in count_table.columns else 0,
        "南方出现率": rate_table["南方"].values if "南方" in rate_table.columns else 0,
        "北方出现率": rate_table["北方"].values if "北方" in rate_table.columns else 0
    })

    comparison["差值_南方减北方"] = comparison["南方出现率"] - comparison["北方出现率"]
    comparison["总频次"] = comparison["南方频次"] + comparison["北方频次"]

    # 去掉两边都为 0 的痛点
    comparison = comparison[comparison["总频次"] > 0].copy()

    summary.to_csv(TABLE_DIR / "ip_location_summary.csv", index=False, encoding="utf-8-sig")
    comparison.to_csv(TABLE_DIR / "regional_painpoint_comparison.csv", index=False, encoding="utf-8-sig")

    return summary, comparison


def plot_regional_painpoint_comparison(comparison: pd.DataFrame, top_n: int = 10):
    if comparison.empty:
        print("南北方痛点数据为空，跳过 regional_painpoint_comparison.png。")
        return

    plot_df = comparison.sort_values("总频次", ascending=False).head(top_n).copy()
    plot_df = plot_df.sort_values("总频次", ascending=True)

    y = np.arange(len(plot_df))
    height = 0.36

    fig, ax = plt.subplots(figsize=(11, max(6, 0.55 * len(plot_df))))

    ax.barh(
        y - height / 2,
        plot_df["南方出现率"],
        height=height,
        label="南方"
    )
    ax.barh(
        y + height / 2,
        plot_df["北方出现率"],
        height=height,
        label="北方"
    )

    ax.set_yticks(y)
    ax.set_yticklabels(plot_df["PainPoint"])
    ax.set_xlabel("痛点出现率：痛点提及次数 / 区域负面样本数")
    ax.set_title("南北方客源地核心痛点感知差异")
    ax.legend(loc="lower right")

    max_x = max(plot_df["南方出现率"].max(), plot_df["北方出现率"].max())
    ax.set_xlim(0, max(max_x * 1.25, 0.05))
    ax.set_xticks(np.linspace(0, ax.get_xlim()[1], 6))
    ax.set_xticklabels([f"{x:.0%}" for x in np.linspace(0, ax.get_xlim()[1], 6)])

    ax.grid(axis="x", linestyle="--", alpha=0.3)

    for i, row in enumerate(plot_df.itertuples()):
        ax.text(
            row.南方出现率 + 0.003,
            i - height / 2,
            f"{row.南方出现率:.1%}",
            va="center",
            fontsize=8
        )
        ax.text(
            row.北方出现率 + 0.003,
            i + height / 2,
            f"{row.北方出现率:.1%}",
            va="center",
            fontsize=8
        )

    save_fig(FIGURE_DIR / "regional_painpoint_comparison.png")


# =========================
# 6. 模块 G：游客画像痛点雷达图
# =========================

def build_persona_painpoint_table(core_df: pd.DataFrame, top_k: int = 5):
    long_df = prepare_negative_painpoint_long(core_df)

    if long_df.empty:
        summary = pd.DataFrame()
        radar_table = pd.DataFrame()
        return summary, radar_table

    long_df = long_df[long_df["TouristPersona"].isin(TARGET_PERSONAS)].copy()

    if long_df.empty:
        summary = pd.DataFrame()
        radar_table = pd.DataFrame()
        return summary, radar_table

    # 全部明确画像样本中，筛选 Top K 痛点作为雷达维度
    top_painpoints = (
        long_df["PainPoint"]
        .value_counts()
        .head(top_k)
        .index
        .tolist()
    )

    long_df = long_df[long_df["PainPoint"].isin(top_painpoints)].copy()

    count_table = pd.crosstab(long_df["TouristPersona"], long_df["PainPoint"])
    count_table = count_table.reindex(index=TARGET_PERSONAS, columns=top_painpoints, fill_value=0)

    # 画像负面样本基数
    neg_persona_base = (
        core_df[(core_df["Sentiment"] == -1) & (core_df["TouristPersona"].isin(TARGET_PERSONAS))]
        .groupby("TouristPersona")
        .size()
        .rename("negative_post_count")
    )

    # 归一化：每类画像内痛点占比
    ratio_table = count_table.div(count_table.sum(axis=1).replace(0, np.nan), axis=0).fillna(0)

    rows = []
    for persona in count_table.index:
        for pp in count_table.columns:
            rows.append({
                "TouristPersona": persona,
                "PainPoint": pp,
                "频次": int(count_table.loc[persona, pp]),
                "画像负面样本基数": int(neg_persona_base.get(persona, 0)),
                "画像内痛点占比": float(ratio_table.loc[persona, pp])
            })

    summary = pd.DataFrame(rows)

    summary.to_csv(TABLE_DIR / "persona_painpoint_summary.csv", index=False, encoding="utf-8-sig")
    ratio_table.to_csv(TABLE_DIR / "persona_painpoint_radar_matrix.csv", encoding="utf-8-sig")

    return summary, ratio_table


def plot_persona_radar(radar_table: pd.DataFrame):
    if radar_table.empty:
        print("画像痛点数据为空，跳过 persona_painpoint_radar.png。")
        return

    labels = radar_table.columns.tolist()
    n = len(labels)

    if n < 3:
        print("雷达图维度少于 3，跳过 persona_painpoint_radar.png。")
        return

    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    angles += angles[:1]

    fig = plt.figure(figsize=(8, 8))
    ax = plt.subplot(111, polar=True)

    for persona in radar_table.index:
        values = radar_table.loc[persona].values.astype(float).tolist()
        values += values[:1]

        ax.plot(angles, values, linewidth=2, label=persona)
        ax.fill(angles, values, alpha=0.12)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels)

    max_val = radar_table.values.max()
    max_val = max(max_val, 0.1)

    ticks = np.linspace(0, max_val, 5)
    ax.set_yticks(ticks)
    ax.set_yticklabels([f"{x:.0%}" for x in ticks])
    ax.set_ylim(0, max_val * 1.15)

    ax.set_title("不同游客画像的核心痛点偏好雷达图", pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.25, 1.1))

    save_fig(FIGURE_DIR / "persona_painpoint_radar.png")


# =========================
# 7. 主流程
# =========================

def main():
    if not FULL_INPUT_FILE.exists():
        raise FileNotFoundError(
            f"找不到输入文件：{FULL_INPUT_FILE}\n"
            f"请先运行 1_data_cleaning_and_subset.py。"
        )

    if not CORE_INPUT_FILE.exists():
        raise FileNotFoundError(
            f"找不到输入文件：{CORE_INPUT_FILE}\n"
            f"请先运行 1_data_cleaning_and_subset.py。"
        )

    print("读取全量清洗数据 ...")
    full_df = read_csv_safely(FULL_INPUT_FILE)
    full_df = ensure_sentiment_int(full_df)

    print("读取核心体验子集 ...")
    core_df = read_csv_safely(CORE_INPUT_FILE)
    core_df["PainPoints"] = core_df["PainPoints"].astype(str).str.replace("其他痛点", "复合/未细分痛点")
    core_df = ensure_sentiment_int(core_df)

    print(f"全量清洗样本量：{len(full_df)}")
    print(f"核心体验样本量：{len(core_df)}")

    # 模块 E：时序趋势
    print("生成时序趋势表与图 ...")
    trend = build_temporal_trend_table(full_df)
    plot_temporal_trend(trend)

    # 模块 F：南北方痛点差异
    print("生成南北方痛点差异表与图 ...")
    regional_summary, regional_comparison = build_regional_painpoint_table(core_df)
    plot_regional_painpoint_comparison(regional_comparison, top_n=10)

    # 模块 G：画像雷达图
    print("生成游客画像痛点雷达图 ...")
    persona_summary, radar_table = build_persona_painpoint_table(core_df, top_k=5)
    plot_persona_radar(radar_table)

    print("\n====== 脚本 3 执行完成 ======")
    print(f"统计表输出目录：{TABLE_DIR}")
    print(f"图表输出目录：{FIGURE_DIR}")

    print("\n已生成或尝试生成表格：")
    print("- temporal_sentiment_trend.csv")
    print("- ip_location_summary.csv")
    print("- regional_painpoint_comparison.csv")
    print("- persona_painpoint_summary.csv")
    print("- persona_painpoint_radar_matrix.csv")

    print("\n已生成或尝试生成图表：")
    print("- temporal_sentiment_trend.png")
    print("- regional_painpoint_comparison.png")
    print("- persona_painpoint_radar.png")


if __name__ == "__main__":
    main()
