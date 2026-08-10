# -*- coding: utf-8 -*-
"""
阶段三脚本 3：生成质检核验表与策略转译表 (6_quality_and_strategy_outputs.py)
功能：
1. 依据分层抽样原则（100负面，60中立，40正面）提取 200 条人工审核样本。
2. 增加专业的人工核验列，导出为 Excel 文件方便编辑。
3. 生成《数据发现 -> 问题诊断 -> 优化策略》的策略转译表模板。
"""

from pathlib import Path
import pandas as pd
import numpy as np

# =========================
# 1. 路径配置
# =========================

PROJECT_DIR = Path(r"D:\舆情分析")
TABLE_DIR = PROJECT_DIR / "analysis_outputs" / "tables"
INPUT_FILE = TABLE_DIR / "core_experience_subset_recoded.csv"


# =========================
# 2. 工具函数
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


# =========================
# 3. 主流程
# =========================

def main():
    print("读取重编码版核心子集...")
    df = read_csv_safely(INPUT_FILE)
    
    # 确保 Sentiment 为整数
    df["Sentiment"] = pd.to_numeric(df["Sentiment"], errors="coerce").fillna(0).astype(int)
    
    # ========================================
    # 动作 1：分层抽样生成人工核验表
    # ========================================
    print("\n执行分层抽样生成人工核验表...")
    neg_df = df[df["Sentiment"] == -1]
    neu_df = df[df["Sentiment"] == 0]
    pos_df = df[df["Sentiment"] == 1]
    
    n_neg = min(100, len(neg_df))
    n_neu = min(60, len(neu_df))
    n_pos = min(40, len(pos_df))
    
    # 负面样本优先尝试覆盖高频 Aspect（可选逻辑，这里用简单随机但固定随机种子）
    sample_neg = neg_df.sample(n=n_neg, random_state=42)
    sample_neu = neu_df.sample(n=n_neu, random_state=42)
    sample_pos = pos_df.sample(n=n_pos, random_state=42)
    
    sample_df = pd.concat([sample_neg, sample_neu, sample_pos])
    
    # 构造输出列
    out_cols = [
        "source_id", "OriginalText", "Aspect", "Sentiment", "PainPoints", 
        "人工Aspect", "人工Sentiment", "人工PainPoints", "是否一致", "人工备注"
    ]
    
    # 填充空列
    for col in ["人工Aspect", "人工Sentiment", "人工PainPoints", "是否一致", "人工备注"]:
        sample_df[col] = ""
        
    # 保留需要的列并随机打乱顺序，避免审核时有预期倾向
    sample_df = sample_df[out_cols].sample(frac=1, random_state=42).reset_index(drop=True)
    
    out_sample_path = TABLE_DIR / "manual_verification_sample.xlsx"
    try:
        sample_df.to_excel(out_sample_path, index=False)
        print(f"成功导出分层核验表: {out_sample_path} (共 {len(sample_df)} 条)")
    except Exception as e:
        print(f"导出 Excel 失败（可能缺少 openpyxl），回退为 CSV 格式: {e}")
        out_sample_path = TABLE_DIR / "manual_verification_sample.csv"
        sample_df.to_csv(out_sample_path, index=False, encoding="utf-8-sig")
        print(f"成功导出分层核验表: {out_sample_path} (共 {len(sample_df)} 条)")

    
    # ========================================
    # 动作 2：生成策略转译表 (Strategy Mapping)
    # ========================================
    print("\n生成问题诊断与策略映射表 (Demo Template)...")
    strategy_cols = ["数据发现(问题现象)", "关联的核心体验维度", "关联的具体痛点", "影响的空间或服务环节", "优化策略与行动建议"]
    strategy_data = [
        {
            "数据发现(问题现象)": "14.5%的核心体验文本判定为负面，其中气候严寒为高频痛点首位。",
            "关联的核心体验维度": "气候环境, 景区游玩", 
            "关联的具体痛点": "气候严寒, 防寒不足", 
            "影响的空间或服务环节": "户外长时间排队区、无遮挡接驳站点", 
            "优化策略与行动建议": "加急建设临时暖棚与暖流隧道；在核心排队区免费提供姜茶热饮及暖宝宝；开发小程序显示当前排队预估时间以减少盲目室外等待。"
        },
        {
            "数据发现(问题现象)": "负面情绪中“价格虚高”提及频次高，特别是南方游客敏感度强。",
            "关联的核心体验维度": "餐饮消费, 住宿体验", 
            "关联的具体痛点": "价格虚高, 商业欺诈", 
            "影响的空间或服务环节": "景区内餐饮商户、周边热门酒店民宿", 
            "优化策略建议": "启动价格熔断监管机制，推行文旅局官方背书的“平价指导套餐”；开通旅游季专项价格投诉绿色通道，实现24小时内极速退赔响应。"
        },
        {
            "数据发现(问题现象)": "“管理混乱”与“安全隐患”痛点负面率极高，且多关联人员踩踏担忧。",
            "关联的核心体验维度": "安全保障, 服务管理", 
            "关联的具体痛点": "管理混乱, 安全隐患, 人流拥挤", 
            "影响的空间或服务环节": "冰雪大世界主入口、大滑梯等热门项目体验区", 
            "优化策略与行动建议": "建立多级客流预警与分流截流机制；增加安保网格化部署；采用实名制预约换验票，严打黄牛加塞导致的管理失序。"
        }
    ]
    
    strategy_df = pd.DataFrame(strategy_data, columns=strategy_cols)
    out_strategy_path = TABLE_DIR / "strategy_mapping_template.csv"
    strategy_df.to_csv(out_strategy_path, index=False, encoding="utf-8-sig")
    print(f"成功导出策略映射表模板: {out_strategy_path}")

    print("\n====== 脚本 6 (质检与策略输出) 运行完毕 ======")

if __name__ == "__main__":
    main()
