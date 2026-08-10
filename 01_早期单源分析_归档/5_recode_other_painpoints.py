# -*- coding: utf-8 -*-
"""
阶段三脚本 2：重编码“其他痛点” (5_recode_other_painpoints.py)
功能：
1. 提取核心子集中包含“其他痛点”的负面样本（共 280 条）
2. 基于高频词条正则匹配规则进行细分回推
3. 生成不覆盖原数据的审计补丁表 (other_painpoint_recode_patch.csv)
4. 生成打补丁后的全新核心子集 (core_experience_subset_recoded.csv)
"""

from pathlib import Path
import pandas as pd
import re

# =========================
# 1. 路径配置
# =========================

PROJECT_DIR = Path(r"D:\舆情分析")
TABLE_DIR = PROJECT_DIR / "analysis_outputs" / "tables"
INPUT_FILE = TABLE_DIR / "core_experience_subset.csv"


# =========================
# 2. 细分正则重编码字典
# =========================

# 采用从细到粗的匹配顺序
RECODE_RULES = {
    r"(导游|强制|推销|买东西|购物)": "导游强制消费",
    r"(隔音|被子脏|床|酒店|民宿|没暖气)": "住宿条件差",
    r"(大巴|司机|出租车|拼车|打车|黑车|网约车)": "接驳运力不足",
    r"(退票|客服|不接电话|投诉|热线)": "售后维权困难",
    r"(态度|恶劣|骂人|不理人|拉脸)": "服务态度差",
    r"(冷|冻|感冒|暖宝宝|保暖|冻透)": "防寒不足",
    r"(贵|坑|天价|宰客|不值|刺客)": "价格虚高",
    r"(厕所|卫生间|垃圾|很脏)": "卫生条件差",
    r"(挤|人多|踩踏|根本走不动)": "人流拥挤",
    r"(排队|等太久|两小时)": "排队时间长",
    r"(安全|摔|滑|危险|医护)": "安全隐患"
}


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
    raise RuntimeError(f"CSV 读取失败: {last_error}")


def split_painpoints(value):
    if pd.isna(value):
        return []
    text = str(value).strip()
    if not text:
        return []
    return [x.strip() for x in text.split("、") if x.strip()]


def recode_text(text):
    if pd.isna(text):
        return "无法细分(保持原样)", "文本为空"
    text = str(text)
    
    for pattern, new_pp in RECODE_RULES.items():
        if re.search(pattern, text):
            return new_pp, f"命中正则: {pattern}"
            
    return "无法细分(保持原样)", "无匹配规则"


# =========================
# 4. 主流程
# =========================

def main():
    print("读取核心体验子集...")
    df = read_csv_safely(INPUT_FILE)
    
    # 筛选负面且包含“其他痛点”的记录
    mask = (df["Sentiment"] == -1) & (df["PainPoints"].astype(str).str.contains("其他痛点"))
    target_df = df[mask].copy()
    print(f"找到 {len(target_df)} 条包含“其他痛点”的负面样本需要重编码。")
    
    patch_records = []
    
    # 执行重编码
    for idx, row in target_df.iterrows():
        old_pp_list = split_painpoints(row["PainPoints"])
        
        # 将“其他痛点”移出
        cleaned_pp = [p for p in old_pp_list if p != "其他痛点"]
        
        # 根据原文本进行推断
        new_specific_pp, reason = recode_text(row["OriginalText"])
        
        if new_specific_pp != "无法细分(保持原样)":
            if new_specific_pp not in cleaned_pp:
                cleaned_pp.append(new_specific_pp)
            new_pp_str = "、".join(cleaned_pp)
        else:
            # 还原
            cleaned_pp.append("其他痛点")
            new_pp_str = "、".join(cleaned_pp)
            
        patch_records.append({
            "source_id": row["source_id"],
            "OriginalText": row["OriginalText"],
            "old_painpoints": row["PainPoints"],
            "new_painpoints": new_pp_str,
            "recode_reason": reason
        })
        
        # 更新原 DataFrame (利用索引映射)
        df.at[idx, "PainPoints"] = new_pp_str
        
    # 保存补丁表
    patch_df = pd.DataFrame(patch_records)
    patch_out_path = TABLE_DIR / "other_painpoint_recode_patch.csv"
    patch_df.to_csv(patch_out_path, index=False, encoding="utf-8-sig")
    print(f"生成补丁表: {patch_out_path}")
    
    success_recode = len(patch_df[patch_df["recode_reason"] != "无匹配规则"])
    print(f"成功细分痛点: {success_recode} 条，保持原样: {len(patch_df) - success_recode} 条。")
    
    # 保存 Recoded 子集
    recoded_out_path = TABLE_DIR / "core_experience_subset_recoded.csv"
    df.to_csv(recoded_out_path, index=False, encoding="utf-8-sig")
    print(f"生成重编码版新核心子集: {recoded_out_path}")
    
    print("\n====== 脚本 5 (重编码) 运行完毕 ======")

if __name__ == "__main__":
    main()
