# -*- coding: utf-8 -*-
"""
阶段二脚本 1：数据清洗与核心分析子集构建
输入：D:/舆情分析/structured_sentiment.csv
输出：
analysis_outputs/tables/cleaned_structured_sentiment.csv
analysis_outputs/tables/core_experience_subset.csv
analysis_outputs/tables/cleaning_summary.csv
"""

from pathlib import Path
import json
import ast
import pandas as pd
import numpy as np


# =========================
# 1. 路径配置
# =========================

PROJECT_DIR = Path(r"D:\舆情分析")
INPUT_FILE = PROJECT_DIR / "structured_sentiment.csv"

OUTPUT_DIR = PROJECT_DIR / "analysis_outputs"
TABLE_DIR = OUTPUT_DIR / "tables"
FIGURE_DIR = OUTPUT_DIR / "figures"

TABLE_DIR.mkdir(parents=True, exist_ok=True)
FIGURE_DIR.mkdir(parents=True, exist_ok=True)


# =========================
# 2. 全局词表
# =========================

ALLOWED_ASPECTS = [
    "交通出行", "行程规划", "景区游玩", "景观打卡", "休闲娱乐", "餐饮消费",
    "住宿体验", "购物特产", "城市人文", "服务管理", "气候环境", "安全保障",
    "咨询求助", "其他"
]

ALLOWED_PERSONAS = [
    "亲子家庭", "情侣伴侣", "朋友结伴", "独自出行", "银发老人", "未知"
]

ALLOWED_PAINPOINTS = [
    "交通拥堵", "停车困难", "接驳不便", "排队时间长", "人流拥挤", "卫生条件差",
    "价格虚高", "商业欺诈", "服务态度差", "管理混乱", "设施老旧", "气候严寒",
    "防寒不足", "路面湿滑", "安全隐患", "其他痛点"
]

REGION_DICT = {
    # 北方
    "黑龙江": "北方", "吉林": "北方", "辽宁": "北方", "北京": "北方",
    "天津": "北方", "河北": "北方", "山东": "北方", "山西": "北方",
    "内蒙古": "北方", "河南": "北方", "陕西": "北方", "甘肃": "北方",
    "宁夏": "北方", "青海": "北方", "新疆": "北方",

    # 南方
    "上海": "南方", "江苏": "南方", "浙江": "南方", "安徽": "南方",
    "福建": "南方", "江西": "南方", "湖北": "南方", "湖南": "南方",
    "广东": "南方", "广西": "南方", "海南": "南方", "重庆": "南方",
    "四川": "南方", "贵州": "南方", "云南": "南方", "西藏": "南方"
}


# =========================
# 3. 工具函数
# =========================

def read_csv_safely(path: Path) -> pd.DataFrame:
    """兼容 utf-8-sig / utf-8 / gbk 的 CSV 读取。"""
    encodings = ["utf-8-sig", "utf-8", "gbk"]
    last_error = None

    for enc in encodings:
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception as e:
            last_error = e

    raise RuntimeError(f"CSV 读取失败，请检查文件编码。最后错误：{last_error}")


def normalize_text_value(value):
    """将 NaN 统一为空字符串，其余转为字符串并去除首尾空格。"""
    if pd.isna(value):
        return ""
    return str(value).strip()


def normalize_aspect(value):
    value = normalize_text_value(value)
    return value if value in ALLOWED_ASPECTS else "其他"


def normalize_persona(value):
    value = normalize_text_value(value)
    return value if value in ALLOWED_PERSONAS else "未知"


def normalize_sentiment(value):
    try:
        value = int(value)
    except Exception:
        value = 0

    return value if value in [-1, 0, 1] else 0


def split_chinese_list(value):
    """
    将 'A、B、C' 形式的字符串拆成列表。
    空值返回 []。
    """
    value = normalize_text_value(value)
    if not value:
        return []

    items = [x.strip() for x in value.split("、") if x.strip()]
    return items


def normalize_painpoints(value, sentiment):
    """
    清洗 PainPoints：
    - Sentiment 为 0 或 1 时，强制 []
    - Sentiment 为 -1 时，只保留词表内痛点
    - 如果负面但无合法痛点，补 '其他痛点'
    """
    if sentiment in [0, 1]:
        return []

    items = split_chinese_list(value)
    items = [x for x in items if x in ALLOWED_PAINPOINTS]

    if sentiment == -1 and len(items) == 0:
        items = ["其他痛点"]

    # “其他痛点”不与其他痛点并列
    if "其他痛点" in items and len(items) > 1:
        items = [x for x in items if x != "其他痛点"]

    return items[:3]


def parse_secondary_aspect(value):
    """
    清洗 SecondaryAspect：
    输入可能是：
    - JSON 字符串
    - Python list 字符串
    - 空字符串
    - NaN

    输出统一为合法 list[dict]。
    """
    if pd.isna(value):
        return []

    if isinstance(value, list):
        raw = value
    else:
        text = str(value).strip()
        if not text or text in ["[]", "nan", "None"]:
            return []

        try:
            raw = json.loads(text)
        except Exception:
            try:
                raw = ast.literal_eval(text)
            except Exception:
                return []

    if not isinstance(raw, list):
        return []

    cleaned = []
    for item in raw:
        if not isinstance(item, dict):
            continue

        aspect = item.get("Aspect")
        sentiment = item.get("Sentiment")

        aspect = normalize_text_value(aspect)
        sentiment = normalize_sentiment(sentiment)

        if aspect not in ALLOWED_ASPECTS:
            continue

        cleaned.append({
            "Aspect": aspect,
            "Sentiment": sentiment
        })

    return cleaned


def map_region(value):
    province = normalize_text_value(value)
    if not province:
        return "其他/未知"
    return REGION_DICT.get(province, "其他/未知")


def validate_required_columns(df: pd.DataFrame):
    required_cols = [
        "source_id", "OriginalText", "Locations", "Aspect", "Sentiment",
        "PainPoints", "TouristPersona", "SecondaryAspect",
        "ip_location", "publish_time", "extract_status"
    ]

    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(f"输入文件缺少必要字段：{missing}")


# =========================
# 4. 主流程
# =========================

def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"找不到输入文件：{INPUT_FILE}\n"
            f"请确认 structured_sentiment.csv 位于 D:\\舆情分析\\ 目录下。"
        )

    print("读取 structured_sentiment.csv ...")
    df = read_csv_safely(INPUT_FILE)
    validate_required_columns(df)

    original_count = len(df)

    print(f"原始数据量：{original_count}")

    # source_id 规范化
    df["source_id"] = pd.to_numeric(df["source_id"], errors="coerce").astype("Int64")

    # 核心字段清洗
    df["Aspect"] = df["Aspect"].apply(normalize_aspect)
    df["TouristPersona"] = df["TouristPersona"].apply(normalize_persona)
    df["Sentiment"] = df["Sentiment"].apply(normalize_sentiment)

    # PainPoints 清洗
    df["PainPoints_list"] = df.apply(
        lambda row: normalize_painpoints(row["PainPoints"], row["Sentiment"]),
        axis=1
    )
    df["PainPoints"] = df["PainPoints_list"].apply(lambda x: "、".join(x))

    # SecondaryAspect 全量合法性过滤
    df["SecondaryAspect_list"] = df["SecondaryAspect"].apply(parse_secondary_aspect)
    df["SecondaryAspect"] = df["SecondaryAspect_list"].apply(
        lambda x: json.dumps(x, ensure_ascii=False)
    )

    # ip_location 与 Region
    df["ip_location"] = df["ip_location"].apply(normalize_text_value)
    df["Region"] = df["ip_location"].apply(map_region)

    # publish_time 解析
    df["publish_time_raw"] = df["publish_time"]
    df["publish_time"] = pd.to_datetime(df["publish_time"], errors="coerce")
    df["publish_date"] = df["publish_time"].dt.date
    df["publish_month"] = df["publish_time"].dt.to_period("M").astype(str)

    # 清理辅助 list 列，避免输出冗余结构
    output_df = df.drop(columns=["PainPoints_list", "SecondaryAspect_list"])

    cleaned_path = TABLE_DIR / "cleaned_structured_sentiment.csv"
    output_df.to_csv(cleaned_path, index=False, encoding="utf-8-sig")

    # 构建核心体验子集：排除“其他”和“咨询求助”
    core_df = output_df[~output_df["Aspect"].isin(["其他", "咨询求助"])].copy()

    core_path = TABLE_DIR / "core_experience_subset.csv"
    core_df.to_csv(core_path, index=False, encoding="utf-8-sig")

    # 生成清洗摘要
    summary = {
        "total_rows": original_count,
        "cleaned_rows": len(output_df),
        "core_experience_rows": len(core_df),
        "excluded_other_rows": int((output_df["Aspect"] == "其他").sum()),
        "excluded_consulting_rows": int((output_df["Aspect"] == "咨询求助").sum()),
        "negative_rows_total": int((output_df["Sentiment"] == -1).sum()),
        "negative_rows_core": int((core_df["Sentiment"] == -1).sum()),
        "invalid_publish_time_rows": int(output_df["publish_time"].isna().sum()),
        "region_north_rows": int((output_df["Region"] == "北方").sum()),
        "region_south_rows": int((output_df["Region"] == "南方").sum()),
        "region_unknown_rows": int((output_df["Region"] == "其他/未知").sum())
    }

    summary_df = pd.DataFrame([summary])
    summary_path = TABLE_DIR / "cleaning_summary.csv"
    summary_df.to_csv(summary_path, index=False, encoding="utf-8-sig")

    print("\n====== 数据清洗完成 ======")
    print(f"全量清洗数据：{cleaned_path}")
    print(f"核心体验子集：{core_path}")
    print(f"清洗摘要：{summary_path}")
    print("\n====== 摘要 ======")
    for k, v in summary.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
