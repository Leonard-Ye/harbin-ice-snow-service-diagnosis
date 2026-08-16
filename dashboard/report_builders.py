# -*- coding: utf-8 -*-
"""报表生成器：Excel / HTML 与数据质量审计。

从 dashboard/app.py 抽出，保持无 Streamlit 依赖，
供 Streamlit 看板与 FastAPI 报表接口复用同一实现。
"""
import io

import pandas as pd

from dashboard.dashboard_data import INDEX_COLS, get_weight_sets, load_scale
from src.detectors.anomaly_detector import AnomalyDetector
from src.engines.metrics_engine import PAIN_RATE_COLS, SUPPLY_COLS

AUDIT_COLS = SUPPLY_COLS + ["xhs_mentions", "dp_review_count"] + PAIN_RATE_COLS
LOG_COLS = SUPPLY_COLS + ["xhs_mentions", "dp_review_count"]


def weights_comparison_df(method: str) -> pd.DataFrame:
    """等权与当前方案的三组指标权重对比表。"""
    w_eq = get_weight_sets("equal")
    w_cur = get_weight_sets(method)
    grp_cn = {"supply": "SSI 服务供给", "eri": "ERI 体验风险", "dp": "ERI_plus 餐饮压力"}
    rows = []
    for grp in ["supply", "eri", "dp"]:
        for key in w_eq[grp]:
            rows.append(
                {
                    "指标组": grp_cn[grp],
                    "维度": key,
                    "等权": w_eq[grp][key],
                    "当前方案": w_cur[grp][key],
                }
            )
    dfw = pd.DataFrame(rows)
    dfw["差异"] = (dfw["当前方案"] - dfw["等权"]).round(4)
    return dfw


def build_audit_df() -> pd.DataFrame:
    """3km 底表的 IQR/Z-score 质量审计（Dashboard 展示口径）。"""
    scale3 = load_scale()
    scale3 = scale3[scale3["scale_km"] == 3].copy()
    audit = AnomalyDetector().quality_report(scale3, AUDIT_COLS, log_transform=LOG_COLS)
    audit["iqr_outliers"] = audit["iqr_outliers"].apply(lambda x: "、".join(x) if x else "—")
    audit["zscore_outliers"] = audit["zscore_outliers"].apply(lambda x: "、".join(x) if x else "—")
    return audit


def build_excel_bytes(df: pd.DataFrame, method: str) -> bytes:
    """打包指标明细 / 数据质量审计 / 指标权重为多 sheet Excel。"""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df[["anchor_name", "mismatch_rank", "diagnosis"] + INDEX_COLS].to_excel(
            writer, sheet_name="指标明细", index=False
        )
        build_audit_df().to_excel(writer, sheet_name="数据质量审计", index=False)
        weights_comparison_df(method).to_excel(writer, sheet_name="指标权重", index=False)
    return buf.getvalue()


def build_html_summary(df: pd.DataFrame, method: str) -> str:
    """生成诊断报告 HTML 摘要（Top 10 锚点 + 诊断分布 + 口径说明）。"""
    rows = "".join(
        f"<tr><td>{i}</td><td>{r.anchor_name}</td><td>{r.SMI:.2f}</td>"
        f"<td>{r.DHI:.2f}</td><td>{r.SSI:.2f}</td><td>{r.ERI:.2f}</td>"
        f"<td>{r.diagnosis}</td></tr>"
        for i, r in df.head(10).iterrows()
    )
    dist = df["diagnosis"].value_counts().to_dict()
    dist_html = "".join(f"<li>{k}: {v} 个锚点</li>" for k, v in dist.items())
    method_name = "等权（基线方案）" if method == "equal" else "熵权法（数据驱动）"
    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>哈尔滨冰雪旅游服务设施供需诊断报告</title>
<style>body{{font-family:'Microsoft YaHei',sans-serif;margin:24px;}}
table{{border-collapse:collapse;width:100%;}} th,td{{border:1px solid #ccc;padding:6px 10px;font-size:13px;}}
th{{background:#f0f4f8;}} h1{{font-size:20px;}} .note{{color:#666;font-size:12px;}}</style>
</head><body>
<h1>哈尔滨冰雪旅游服务设施供需诊断报告（Top 10 错配锚点）</h1>
<p>权重方案：{method_name}　|　生成时间：{pd.Timestamp.now():%Y-%m-%d %H:%M}</p>
<table><tr><th>排名</th><th>锚点</th><th>SMI</th><th>DHI</th><th>SSI</th><th>ERI</th><th>诊断类型</th></tr>{rows}</table>
<h2>诊断类型分布</h2><ul>{dist_html}</ul>
<p class="note">口径说明：所有指标为 20 个核心锚点样本内 Z-score 相对值（0=样本均值），SMI = z(DHI)+z(ERI)−z(SSI)。数据为聚合统计，不含任何原始评论。</p>
</body></html>"""
