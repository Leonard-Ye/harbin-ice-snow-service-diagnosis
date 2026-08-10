# -*- coding: utf-8 -*-
"""
阶段三脚本 1：时序修复与空间聚合 (4_fix_time_and_space.py)
功能：
1. 强大的混合时间格式解析（按基准日锚定、区分绝对/相对/推断时间）
2. 空间地点长表爆炸与别名合并归一化
3. 导出包含解析质量标志的时间修复表，以及地点相关的长表与聚合热度表。
"""

from pathlib import Path
import pandas as pd
import numpy as np
import re
from datetime import timedelta

# =========================
# 1. 路径配置
# =========================

PROJECT_DIR = Path(r"D:\舆情分析")
TABLE_DIR = PROJECT_DIR / "analysis_outputs" / "tables"
FIGURE_DIR = PROJECT_DIR / "analysis_outputs" / "figures"

INPUT_FILE = TABLE_DIR / "cleaned_structured_sentiment.csv"
CORE_FILE = TABLE_DIR / "core_experience_subset.csv"


# =========================
# 2. 地点别名归一化字典
# =========================
LOCATION_ALIASES = {
    "圣索菲亚教堂": "索菲亚教堂",
    "索菲亚大教堂": "索菲亚教堂",
    "圣索菲亚大教堂": "索菲亚教堂",
    "哈尔滨冰雪大世界": "冰雪大世界",
    "哈尔滨极地公园": "极地公园",
    "极地馆": "极地公园",
    "哈尔滨太阳岛": "太阳岛",
    "中央大街步行街": "中央大街",
    "防洪塔": "防洪纪念塔"
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


def find_base_date(df: pd.DataFrame) -> pd.Timestamp:
    """找出绝对时间中的最大值，作为相对时间推演的锚点（模拟采集日）"""
    valid_dates = pd.to_datetime(df['publish_time_raw'], errors='coerce')
    valid_dates = valid_dates[valid_dates.dt.year >= 2020]
    if valid_dates.empty:
        return pd.Timestamp("2026-06-06") # Default fallback
    return valid_dates.max().normalize()


def parse_xhs_time(raw_time, base_date: pd.Timestamp):
    if pd.isna(raw_time):
        return pd.NaT, "failed"
        
    s = str(raw_time).strip()
    
    # 尝试绝对时间
    try:
        dt = pd.to_datetime(s)
        if dt.year >= 2020:
            return dt.normalize(), "absolute"
    except Exception:
        pass
        
    # 相对时间匹配
    if "今天" in s:
        return base_date, "relative_inferred"
    if "昨天" in s:
        return base_date - timedelta(days=1), "relative_inferred"
    if "分钟前" in s or "小时前" in s or "刚刚" in s:
        return base_date, "relative_inferred"
        
    match = re.search(r"(\d+)天前", s)
    if match:
        days = int(match.group(1))
        return base_date - timedelta(days=days), "relative_inferred"
        
    # MM-DD 格式推演
    match = re.search(r"^(\d{1,2})[-/月](\d{1,2})", s)
    if match:
        m = int(match.group(1))
        d = int(match.group(2))
        
        # 跨年冰雪季逻辑：
        # 如果月份大于 base_date 的月份，说明是上一年的帖子
        year = base_date.year if m <= base_date.month else base_date.year - 1
        try:
            return pd.Timestamp(year=year, month=m, day=d), "month_day_inferred"
        except Exception:
            return pd.NaT, "failed"
            
    return pd.NaT, "failed"


def split_and_normalize_locations(locations_str):
    if pd.isna(locations_str):
        return []
    locs = str(locations_str).split("、")
    normalized = []
    for loc in locs:
        loc = loc.strip()
        if not loc:
            continue
        loc = LOCATION_ALIASES.get(loc, loc)
        normalized.append(loc)
    return normalized


# =========================
# 4. 主流程
# =========================

def main():
    print("读取全量数据...")
    full_df = read_csv_safely(INPUT_FILE)
    base_date = find_base_date(full_df)
    print(f"锚定基准爬取日期 (base_date): {base_date.date()}")
    
    print("开始执行混合时间格式解析...")
    parsed_results = full_df['publish_time_raw'].apply(lambda x: parse_xhs_time(x, base_date))
    full_df['publish_time_parsed'] = [r[0] for r in parsed_results]
    full_df['time_parse_quality'] = [r[1] for r in parsed_results]
    
    # 时间修复质量统计
    quality_counts = full_df['time_parse_quality'].value_counts()
    print("时间解析质量分布：")
    print(quality_counts)
    
    output_time_fixed = TABLE_DIR / "cleaned_structured_sentiment_timefixed.csv"
    full_df.to_csv(output_time_fixed, index=False, encoding="utf-8-sig")
    
    # ======== 空间地点聚合处理 ========
    print("\n读取核心子集进行空间聚合...")
    core_df = read_csv_safely(CORE_FILE)
    
    # 我们需要在 core_df 中也补上修正后的时间（方便长表追溯）
    time_map = full_df.set_index('source_id')[['publish_time_parsed', 'time_parse_quality']]
    core_df = core_df.merge(time_map, on='source_id', how='left')
    
    print("展开 Locations 字段生成长表...")
    # 保存原始地点，生成标准地点
    core_df['loc_list'] = core_df['Locations'].apply(split_and_normalize_locations)
    
    # 构造长表记录
    long_records = []
    for _, row in core_df.iterrows():
        raw_locs = str(row['Locations']).split("、") if pd.notna(row['Locations']) else []
        raw_locs = [x.strip() for x in raw_locs if x.strip()]
        norm_locs = row['loc_list']
        
        # 配对原始和归一化（如果长度一致）
        for i, norm_loc in enumerate(norm_locs):
            raw_loc = raw_locs[i] if i < len(raw_locs) else norm_loc
            long_records.append({
                "source_id": row["source_id"],
                "OriginalText": row["OriginalText"],
                "raw_location": raw_loc,
                "normalized_location": norm_loc,
                "Aspect": row["Aspect"],
                "Sentiment": row["Sentiment"],
                "PainPoints": row["PainPoints"],
                "publish_time_parsed": row["publish_time_parsed"],
                "time_parse_quality": row["time_parse_quality"]
            })
            
    long_df = pd.DataFrame(long_records)
    long_out_path = TABLE_DIR / "location_mentions_long.csv"
    long_df.to_csv(long_out_path, index=False, encoding="utf-8-sig")
    print(f"导出地点长表: {long_out_path} (行数: {len(long_df)})")
    
    # 生成 POI 热度表
    if not long_df.empty:
        # 确保 Sentiment 是 int
        long_df['Sentiment'] = pd.to_numeric(long_df['Sentiment'], errors='coerce').fillna(0).astype(int)
        
        poi_summary = long_df.groupby("normalized_location").agg(
            总提及热度=("source_id", "count"),
            负面提及数=("Sentiment", lambda x: (x == -1).sum())
        )
        poi_summary["负面率"] = poi_summary["负面提及数"] / poi_summary["总提及热度"]
        poi_summary = poi_summary.sort_values("总提及热度", ascending=False).reset_index()
        
        poi_out_path = TABLE_DIR / "poi_sentiment_heat.csv"
        poi_summary.to_csv(poi_out_path, index=False, encoding="utf-8-sig")
        print(f"导出 POI 聚合热度表: {poi_out_path}")
        print("\nTop 5 POI 热度概况：")
        print(poi_summary.head(5))
        
    print("\n====== 脚本 4 (时间与空间修复) 运行完毕 ======")

if __name__ == "__main__":
    main()
