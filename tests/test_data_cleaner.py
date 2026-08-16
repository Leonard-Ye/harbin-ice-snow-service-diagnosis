# -*- coding: utf-8 -*-
"""DataCleaner 单元测试：parity 清洗口径与通用画像。"""
import pandas as pd

from src.cleaning.data_cleaner import DataCleaner, CleaningConfig


def _sample_df():
    return pd.DataFrame(
        {
            "normalized_location": ['"中央大街"', "[索菲亚]", "大世界", None],
            "lon": [126.6, 126.6, 126.5, None],
            "lat": [45.7, 45.7, 45.7, None],
        }
    )


def test_parity_cleaning_matches_30_script():
    out = DataCleaner().clean_location_text(_sample_df(), "normalized_location")
    assert out["clean_loc"].tolist() == ["中央大街", "索菲亚", "大世界", "None"]


def test_cleaning_result_report():
    df = pd.DataFrame({"a": [1, 1, 2], "b": ["x", "y", "z"]})
    cfg = CleaningConfig(drop_duplicates=True, duplicate_subset=["a"])
    result = DataCleaner(cfg).clean_dataframe(df)
    assert len(result.data) == 2
    assert result.report.set_index("metric").loc["duplicates_removed", "value"] == 1


def test_profile_reports_missing_and_range():
    df = pd.DataFrame({"v": [1.0, None, 3.0], "s": ["a", "b", "c"]})
    prof = DataCleaner.profile(df)
    assert "v" in prof["column"].tolist()
    row = prof[prof["column"] == "v"].iloc[0]
    assert row["missing"] == 1
    assert row["min"] == 1.0 and row["max"] == 3.0
