# -*- coding: utf-8 -*-
"""DataCleaner —— 多源数据清洗模块。

parity_mode=True 时严格复刻 30_multi_source_fusion_v22_04R2.py 的清洗口径：
- normalized_location → clean_loc：去双引号/单引号 → strip '[]'
- 别名映射与白名单筛选由 pipeline.AnchorAligner 负责，不在此模块内。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pandas as pd


@dataclass
class CleaningConfig:
    """清洗配置。增强项默认关闭，保证基线回归不受影响。"""

    parity_mode: bool = True
    strip_quotes: bool = True
    strip_list_artifacts: bool = True
    drop_duplicates: bool = False
    duplicate_subset: Optional[List[str]] = None
    fill_values: Optional[Dict[str, Any]] = None


@dataclass
class CleaningResult:
    """清洗结果：清洗后数据 + 可读清洗报告。"""

    data: pd.DataFrame
    report: pd.DataFrame
    extra: Dict[str, Any] = field(default_factory=dict)


class DataCleaner:
    """面向列的文本清洗与基础质量处理。

    Parameters
    ----------
    config : CleaningConfig, optional
        清洗配置。默认 parity_mode=True，与原脚本逐值一致。
    """

    def __init__(self, config: Optional[CleaningConfig] = None) -> None:
        self.config = config or CleaningConfig()

    # ---------------------------------------------------------------- 文本清洗
    @staticmethod
    def _strip_quotes(s: pd.Series) -> pd.Series:
        return s.str.replace('"', "", regex=False).str.replace("'", "", regex=False)

    @staticmethod
    def _strip_list_artifacts(s: pd.Series) -> pd.Series:
        return s.apply(lambda x: x.strip("[]"))

    def clean_location_text(self, df: pd.DataFrame, col: str = "normalized_location") -> pd.DataFrame:
        """复刻 30 脚本的 clean_loc 生成口径。

        返回新 DataFrame，并增加 ``clean_loc`` 列。
        """
        out = df.copy()
        s = out[col].astype(str)
        if self.config.strip_quotes:
            s = self._strip_quotes(s)
        if self.config.strip_list_artifacts:
            s = self._strip_list_artifacts(s)
        out["clean_loc"] = s
        return out

    # ---------------------------------------------------------------- 通用清洗
    def clean_dataframe(
        self,
        df: pd.DataFrame,
        location_col: Optional[str] = None,
    ) -> CleaningResult:
        """通用清洗入口：可选执行位置列清洗、去重与缺失值填充。

        默认配置下仅执行位置列清洗，输出与 30 脚本一致。
        """
        before = len(df)
        out = df.copy()

        if location_col:
            out = self.clean_location_text(out, location_col)

        rows_before = len(out)
        if self.config.drop_duplicates:
            out = out.drop_duplicates(subset=self.config.duplicate_subset)
        removed_duplicates = rows_before - len(out)

        if self.config.fill_values:
            out = out.fillna(self.config.fill_values)

        report_rows = [
            {
                "metric": "rows_before",
                "value": before,
                "note": "清洗前记录数",
            },
            {
                "metric": "rows_after",
                "value": len(out),
                "note": "清洗后记录数",
            },
            {
                "metric": "duplicates_removed",
                "value": removed_duplicates,
                "note": "去重删除记录数",
            },
        ]
        report = pd.DataFrame(report_rows)
        return CleaningResult(data=out, report=report, extra={"location_col": location_col})

    # ---------------------------------------------------------------- 数据画像
    @staticmethod
    def profile(df: pd.DataFrame, max_unique: int = 20) -> pd.DataFrame:
        """轻量列画像：类型、缺失率、唯一值数与取值范围。"""
        rows = []
        for col in df.columns:
            s = df[col]
            missing = int(s.isna().sum())
            n_unique = int(s.nunique(dropna=True))
            dtype = str(s.dtype)
            try:
                s_num = pd.to_numeric(s, errors="coerce")
                if s_num.notna().any():
                    rows.append(
                        {
                            "column": col,
                            "dtype": dtype,
                            "missing": missing,
                            "missing_rate": round(missing / len(s), 4) if len(s) else 0.0,
                            "n_unique": n_unique,
                            "min": round(float(s_num.min()), 4) if not pd.isna(s_num.min()) else None,
                            "max": round(float(s_num.max()), 4) if not pd.isna(s_num.max()) else None,
                        }
                    )
                    continue
            except (TypeError, ValueError):
                pass
            rows.append(
                {
                    "column": col,
                    "dtype": dtype,
                    "missing": missing,
                    "missing_rate": round(missing / len(s), 4) if len(s) else 0.0,
                    "n_unique": n_unique,
                    "min": None,
                    "max": None,
                }
            )
        return pd.DataFrame(rows)
