# -*- coding: utf-8 -*-
"""
阶段四 Alpha 脚本 1：行前信息服务缺口挖掘 (7_consultation_mining.py)
"""
import pandas as pd
import numpy as np
import re
from pathlib import Path
import matplotlib.pyplot as plt

plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

PROJECT_DIR = Path(r"D:\舆情分析")
INPUT_FILE = PROJECT_DIR / "analysis_outputs" / "tables" / "cleaned_structured_sentiment_timefixed.csv"
OUT_TABLE_DIR = PROJECT_DIR / "analysis_outputs_phase4" / "tables"
OUT_FIG_DIR = PROJECT_DIR / "analysis_outputs_phase4" / "figures"

CONSULTATION_RULES = {
    "寻伴结伴咨询": [r"搭子", r"结伴", r"一起", r"求组队", r"有没有人", r"找人", r"拼房", r"组团", r"同游"],
    "行程路线咨询": [r"几天", r"路线", r"攻略", r"安排", r"怎么玩", r"计划", r"行程", r"推荐", r"求推荐", r"去哪", r"帮忙看", r"建议", r"第一天", r"第二天"],
    "交通接驳咨询": [r"机场", r"地铁", r"公交", r"打车", r"接驳", r"怎么去", r"包车", r"拼车", r"大巴", r"高铁", r"火车站", r"哈站", r"哈西"],
    "票务预约咨询": [r"门票", r"预约", r"几点", r"开放", r"闭馆", r"怎么买", r"早鸟票", r"免票", r"退票", r"抢票"],
    "极寒穿搭咨询": [r"冷", r"穿搭", r"羽绒服", r"雪地靴", r"保暖", r"衣服", r"多穿", r"鞋", r"冻", r"手套", r"帽子", r"秋裤", r"厚", r"防寒"],
    "住宿位置咨询": [r"住哪", r"酒店", r"民宿", r"离景区", r"方便", r"洗浴", r"中心", r"道里", r"道外", r"青旅"],
    "餐饮推荐咨询": [r"吃什么", r"去哪吃", r"美食", r"锅包肉", r"铁锅炖", r"俄餐", r"早市", r"饭店", r"好吃", r"特色餐"],
    "特产伴手礼咨询": [r"特产", r"买什么", r"带回去", r"伴手礼", r"红肠", r"大列巴", r"送人", r"纪念品"],
    "预算价格咨询": [r"预算", r"花费", r"价格", r"贵", r"多少钱", r"消费", r"门票多少"],
    "亲子老人适配咨询": [r"带娃", r"孩子", r"老人", r"爸妈", r"亲子", r"推车", r"宝宝"],
    "拍照打卡咨询": [r"打卡", r"拍照", r"出片", r"机位", r"摄影", r"无人机"],
    "避坑安全咨询": [r"避坑", r"坑", r"宰客", r"安全吗", r"被骗", r"防坑", r"防宰", r"导游", r"强制", r"黑车", r"注意"],
    "天气时段咨询": [r"几月", r"什么时候", r"雪", r"天气", r"最佳", r"下雪", r"几号", r"冰雕", r"化了"]
}

def extract_labels(text):
    labels = []
    text = str(text)
    for category, keywords in CONSULTATION_RULES.items():
        for kw in keywords:
            if re.search(kw, text):
                labels.append(category)
                break
    if not labels:
        labels.append("其他咨询")
    return labels

def main():
    print("读取全量数据...")
    df = pd.read_csv(INPUT_FILE, encoding='utf-8-sig')
    
    # 筛选咨询求助
    c_df = df[df["Aspect"] == "咨询求助"].copy()
    print(f"提取咨询求助样本数: {len(c_df)}")
    
    # 多标签分类
    c_df["consultation_labels"] = c_df["OriginalText"].apply(extract_labels)
    c_df["consultation_labels_str"] = c_df["consultation_labels"].apply(lambda x: "、".join(x))
    
    # 保存 Subset
    c_df.to_csv(OUT_TABLE_DIR / "consultation_subset.csv", index=False, encoding="utf-8-sig")
    
    # 展开为长表
    long_records = []
    for _, row in c_df.iterrows():
        for lbl in row["consultation_labels"]:
            long_records.append({
                "source_id": row["source_id"],
                "OriginalText": row["OriginalText"],
                "consultation_label": lbl,
                "Region": row.get("Region", "未知"),
                "publish_month": pd.to_datetime(row["publish_time_parsed"]).strftime('%Y-%m') if pd.notna(row["publish_time_parsed"]) else "未知"
            })
            
    long_df = pd.DataFrame(long_records)
    long_df.to_csv(OUT_TABLE_DIR / "consultation_gap_long.csv", index=False, encoding="utf-8-sig")
    
    # 频次统计
    summary = long_df["consultation_label"].value_counts().reset_index()
    summary.columns = ["咨询类别", "频次"]
    summary["咨询类别"] = summary["咨询类别"].replace("其他咨询", "综合性/未细分咨询")
    summary["占比(基于标签总数)"] = summary["频次"] / summary["频次"].sum()
    summary.to_csv(OUT_TABLE_DIR / "consultation_gap_summary.csv", index=False, encoding="utf-8-sig")
    
    print("\n========= 检查 Alpha 判断标准 (脚本 7) =========")
    other_ratio = summary[summary["咨询类别"] == "综合性/未细分咨询"]["占比(基于标签总数)"].sum()
    print(f"‘综合性/未细分咨询’占比: {other_ratio:.2%}")
    if other_ratio > 0.25:
        print("【预警】‘综合性/未细分咨询’占比超过 25%，请补充规则词典！")
    else:
        print("【达标】‘综合性/未细分咨询’占比合理。")
    print(f"前五大咨询诉求覆盖率: {summary['占比(基于标签总数)'].head(5).sum():.2%}")
    print("=================================================\n")
    
    # 关键词保存（简化版直接输出高频规则词典）
    keys_df = pd.DataFrame(list(CONSULTATION_RULES.items()), columns=["咨询类别", "匹配规则库"])
    keys_df.to_csv(OUT_TABLE_DIR / "consultation_gap_keywords.csv", index=False, encoding="utf-8-sig")

    # 代表性 Case
    cases = []
    for label in summary["咨询类别"].head(8).tolist():
        # Revert back to match the original label if needed for the subset extraction, 
        # but since '其他咨询' might not be in top 8, we can use the original logic if we match on the extracted labels
        search_label = "其他咨询" if label == "综合性/未细分咨询" else label
        samples = c_df[c_df["consultation_labels"].apply(lambda x: search_label in x)]["OriginalText"].head(5).tolist()
        for i, text in enumerate(samples):
            cases.append({"咨询类别": label, "代表性原文": text})
    pd.DataFrame(cases).to_csv(OUT_TABLE_DIR / "consultation_representative_cases.csv", index=False, encoding="utf-8-sig")
    
    # 图 1：排行榜 Bar
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.barh(summary["咨询类别"][::-1], summary["频次"][::-1], color="#3498db")
    ax.set_title("行前信息服务缺口排行榜 (Top 需求)", fontsize=14, pad=15)
    ax.set_xlabel("咨询求助频次")
    # Add values
    for bar in bars:
        width = bar.get_width()
        ax.text(width + 10, bar.get_y() + bar.get_height()/2, f'{int(width)}', ha='left', va='center')
    plt.tight_layout()
    plt.savefig(OUT_FIG_DIR / "consultation_gap_bar.png", dpi=300, bbox_inches='tight')
    plt.close()
    
    # 图 2：时间/地域热力图 (使用 Pandas 交叉表)
    # 取 Top 6 类别
    top_categories = summary[summary["咨询类别"] != "综合性/未细分咨询"]["咨询类别"].head(6).tolist()
    # Map back to original labels to subset long_df
    top_orig = ["其他咨询" if cat == "综合性/未细分咨询" else cat for cat in top_categories]
    heat_df = long_df[long_df["consultation_label"].isin(top_orig)].copy()
    heat_df["consultation_label"] = heat_df["consultation_label"].replace("其他咨询", "综合性/未细分咨询")
    
    # Region x Category
    heat_region = pd.crosstab(heat_df["Region"], heat_df["consultation_label"])
    # 过滤极小众 Region，只看主流南方北方
    main_regions = [x for x in ["南方省份", "北方省份", "本省"] if x in heat_region.index]
    if main_regions:
        heat_region = heat_region.reindex(main_regions).fillna(0)
    
    fig, ax = plt.subplots(figsize=(10, 5))
    import seaborn as sns
    import matplotlib.colors as mcolors
    cmap_base = plt.get_cmap("Blues")
    cmap_custom = mcolors.LinearSegmentedColormap.from_list("custom", cmap_base(np.linspace(0.15, 1.0, 100)))
    sns.heatmap(heat_region, cmap=cmap_custom, annot=True, fmt="d", ax=ax, robust=True, cbar_kws={'label': "频次"})
    ax.set_yticklabels(ax.get_yticklabels(), rotation=0)
    ax.set_title("行前信息服务缺口分布图：客源地 × 咨询类别 (频次)", fontsize=14)
    ax.set_xlabel("")
    ax.set_ylabel("")
    plt.tight_layout()
    plt.savefig(OUT_FIG_DIR / "consultation_gap_heatmap.png", dpi=300, bbox_inches='tight')
    plt.close()
    
    # 图 3：比例版 (行归一化)
    heat_norm = heat_region.div(heat_region.sum(axis=1), axis=0).fillna(0)
    fig, ax = plt.subplots(figsize=(10, 5))
    import matplotlib.colors as mcolors
    cmap_base = plt.get_cmap("Oranges")
    cmap_custom = mcolors.LinearSegmentedColormap.from_list("custom", cmap_base(np.linspace(0.15, 1.0, 100)))
    sns.heatmap(heat_norm, cmap=cmap_custom, annot=True, fmt=".1%", ax=ax, robust=True, cbar_kws={'label': "行内占比"})
    ax.set_yticklabels(ax.get_yticklabels(), rotation=0)
    ax.set_title("行前信息服务缺口分布图：客源地 × 咨询类别 (比例)", fontsize=14)
    ax.set_xlabel("")
    ax.set_ylabel("")
    plt.tight_layout()
    plt.savefig(OUT_FIG_DIR / "consultation_gap_heatmap_normalized.png", dpi=300, bbox_inches='tight')
    plt.close()

    print("=== 脚本 7 执行完毕 ===")

if __name__ == "__main__":
    main()
