# -*- coding: utf-8 -*-
"""
阶段四 Alpha 脚本 2：隐性风险识别 (8_secondary_aspect_analysis.py)
"""
import pandas as pd
import numpy as np
import json
from pathlib import Path
import matplotlib.pyplot as plt
import ast

plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

PROJECT_DIR = Path(r"D:\舆情分析")
INPUT_FILE = PROJECT_DIR / "analysis_outputs" / "tables" / "cleaned_structured_sentiment_timefixed.csv"
OUT_TABLE_DIR = PROJECT_DIR / "analysis_outputs_phase4" / "tables"
OUT_FIG_DIR = PROJECT_DIR / "analysis_outputs_phase4" / "figures"

def parse_secondary(s):
    if pd.isna(s) or not str(s).strip():
        return {}
    s_str = str(s).strip()
    if s_str == "{}" or s_str == "[]" or s_str.lower() == "none":
        return {}
    try:
        parsed = json.loads(s_str.replace("'", '"'))
        if isinstance(parsed, dict):
            return parsed
        elif isinstance(parsed, list):
            # Convert list of dicts [{"Aspect": "X", "Sentiment": -1}] to {"X": -1}
            res = {}
            for item in parsed:
                if isinstance(item, dict) and "Aspect" in item and "Sentiment" in item:
                    res[item["Aspect"]] = item["Sentiment"]
            return res
        return {}
    except:
        return {}

def main():
    print("读取全量数据...")
    df = pd.read_csv(INPUT_FILE, encoding='utf-8-sig')
    
    # 核心筛选条件: 主评价必须非“咨询求助”“其他”，且为主评价非负面样本 (>=0)
    mask = (~df["Aspect"].isin(["咨询求助", "其他"])) & (pd.to_numeric(df["Sentiment"], errors="coerce") >= 0)
    core_df = df[mask].copy()
    print(f"主评价非负面的核心体验样本数: {len(core_df)}")
    
    long_records = []
    hidden_cases = []
    
    for _, row in core_df.iterrows():
        sec_dict = parse_secondary(row["SecondaryAspect"])
        has_hidden_neg = False
        
        for sec_aspect, sec_sentiment in sec_dict.items():
            if sec_aspect in ["咨询求助", "其他"]:
                continue
            
            try:
                sec_sent_val = int(sec_sentiment)
            except:
                continue
                
            long_records.append({
                "source_id": row["source_id"],
                "OriginalText": row["OriginalText"],
                "main_aspect": row["Aspect"],
                "main_sentiment": row["Sentiment"],
                "secondary_aspect": sec_aspect,
                "secondary_sentiment": sec_sent_val
            })
            
            if sec_sent_val == -1:
                has_hidden_neg = True
                
        if has_hidden_neg:
            hidden_cases.append(row)
            
    long_df = pd.DataFrame(long_records)
    hidden_df = pd.DataFrame(hidden_cases)
    
    long_df.to_csv(OUT_TABLE_DIR / "secondary_aspect_long.csv", index=False, encoding="utf-8-sig")
    hidden_df.to_csv(OUT_TABLE_DIR / "hidden_negative_cases.csv", index=False, encoding="utf-8-sig")
    
    print(f"检出隐性风险(次级差评)样本数: {len(hidden_df)}")
    
    if len(long_df) == 0:
        print("未提取到有效 SecondaryAspect 字典格式，请检查源数据！")
        return
        
    neg_sec_df = long_df[long_df["secondary_sentiment"] == -1]
    
    summary = neg_sec_df["secondary_aspect"].value_counts().reset_index()
    summary.columns = ["隐性负面维度", "频次"]
    # 隐性负面率 = 出现该次级负面次数 / 主评价非负面样本总数
    summary["隐性负面率(占非负大盘)"] = summary["频次"] / len(core_df)
    summary.to_csv(OUT_TABLE_DIR / "hidden_negative_summary.csv", index=False, encoding="utf-8-sig")
    
    # 获取不同主维度的次级负面分布
    hidden_by_main = neg_sec_df.groupby(["main_aspect", "secondary_aspect"]).size().reset_index(name="频次")
    hidden_by_main.columns = ["主评价维度", "隐性负面维度", "频次"]
    hidden_by_main.to_csv(OUT_TABLE_DIR / "hidden_negative_by_main_aspect.csv", index=False, encoding="utf-8-sig")

    # 代表性原文
    cases = []
    for label in summary["隐性负面维度"].head(5):
        # 找主评价正面，且该 label 为负面的
        mask_case = (long_df["secondary_aspect"] == label) & (long_df["secondary_sentiment"] == -1)
        source_ids = long_df[mask_case]["source_id"].head(5)
        for text in core_df[core_df["source_id"].isin(source_ids)]["OriginalText"]:
            cases.append({"隐性负面维度": label, "代表性原文": text})
    pd.DataFrame(cases).to_csv(OUT_TABLE_DIR / "hidden_negative_representative_cases.csv", index=False, encoding="utf-8-sig")
    
    cross_matrix = pd.crosstab(neg_sec_df["main_aspect"], neg_sec_df["secondary_aspect"])
    cross_matrix.to_csv(OUT_TABLE_DIR / "secondary_transition_matrix.csv", encoding="utf-8-sig")
    
    print("\n========= 检查 Alpha 判断标准 (脚本 8) =========")
    print(f"隐性负面样本量: {len(hidden_df)}")
    if len(hidden_df) > 50:
        print("【达标】样本量足够支撑独立章节。")
    else:
        print("【提示】样本量较小，建议作为补充观察。")
    print("=================================================\n")

    # 图 1：排行榜
    fig, ax = plt.subplots(figsize=(10, 6))
    top_hidden = summary.head(10)
    bars = ax.barh(top_hidden["隐性负面维度"][::-1], top_hidden["频次"][::-1], color="#e74c3c")
    ax.set_title("隐性风险识别 (主评价非负面样本中暗藏的痛点)", fontsize=14, pad=15)
    ax.set_xlabel("作为次要负面被提及频次")
    for bar in bars:
        width = bar.get_width()
        ax.text(width + 0.5, bar.get_y() + bar.get_height()/2, f'{int(width)}', ha='left', va='center')
    plt.tight_layout()
    plt.savefig(OUT_FIG_DIR / "hidden_negative_bar.png", dpi=300, bbox_inches='tight')
    plt.close()
    
    # 图 2：热力图
    top_main = neg_sec_df["main_aspect"].value_counts().head(8).index
    top_sec = neg_sec_df["secondary_aspect"].value_counts().head(8).index
    heat_matrix = cross_matrix.reindex(index=top_main, columns=top_sec).fillna(0)
    
    fig, ax = plt.subplots(figsize=(10, 8))
    import seaborn as sns
    import matplotlib.colors as mcolors
    cmap_base = plt.get_cmap("Reds")
    cmap_custom = mcolors.LinearSegmentedColormap.from_list("custom", cmap_base(np.linspace(0.15, 1.0, 100)))
    sns.heatmap(heat_matrix, cmap=cmap_custom, annot=True, fmt="d", ax=ax, robust=True, cbar_kws={'label': "频次"})
    ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha="right")
    ax.set_yticklabels(ax.get_yticklabels(), rotation=0)
            
    ax.set_title("高满意度表象下的体验链条断点图 (主维度 × 隐性痛点)", fontsize=14)
    ax.set_ylabel("表面主评价维度")
    ax.set_xlabel("隐藏的次级负面维度")
    plt.tight_layout()
    plt.savefig(OUT_FIG_DIR / "main_secondary_negative_heatmap.png", dpi=300, bbox_inches='tight')
    plt.close()

    print("=== 脚本 8 执行完毕 ===")

if __name__ == "__main__":
    main()
