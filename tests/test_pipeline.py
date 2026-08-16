# -*- coding: utf-8 -*-
"""Pipeline 冒烟测试：使用 tests/fixtures 下的小型合成四源数据。

该测试不依赖未入库的原始数据，可在公开 clone / CI 环境运行；
同时覆盖 AnchorAligner、BufferAggregator、RiskCalculator、RunStore。
"""
from pathlib import Path

import pandas as pd
import pytest

from src.pipeline.anchor_aligner import AnchorAligner
from src.pipeline.config import PipelineConfig, RawDataUnavailableError
from src.pipeline.orchestrator import PipelineRunner

FIXTURES = Path(__file__).parent / "fixtures"
ROOT = Path(__file__).resolve().parents[1]


def _fixture_config(tmp_path: Path) -> PipelineConfig:
    return PipelineConfig(
        project_root=ROOT,
        xhs_path=FIXTURES / "sample_xhs.csv",
        dp_path=FIXTURES / "sample_dp.csv",
        amap_path=FIXTURES / "sample_amap.csv",
        ctrip_path=FIXTURES / "sample_ctrip.csv",
        out_dir=tmp_path / "out",
        db_path=tmp_path / "run.db",
    )


def test_aligner_excludes_non_geographic_terms():
    df = pd.read_csv(FIXTURES / "sample_xhs.csv")
    cleaned = df.copy()
    cleaned["clean_loc"] = (
        df["normalized_location"]
        .astype(str)
        .str.replace('"', "", regex=False)
        .str.replace("'", "", regex=False)
        .apply(lambda x: x.strip("[]"))
    )
    alignment = AnchorAligner().align(cleaned)
    terms = alignment.excluded_terms["term"].tolist()
    assert "冰箱贴" in terms
    assert "亚布力" in terms
    assert set(alignment.master["anchor_name"]).issuperset({"中央大街", "圣索菲亚教堂", "冰雪大世界"})


def test_full_pipeline_smoke_on_sample_data(tmp_path):
    cfg = _fixture_config(tmp_path)
    result = PipelineRunner(cfg).run()
    assert result.status == "succeeded", result.error
    assert result.metrics_rows == 3
    assert result.input_sha256 and result.output_sha256

    index = pd.read_csv(cfg.out_dir / "anchor_index_v22_04R2.csv", encoding="utf-8-sig")
    assert list(index.columns) == [
        "anchor_name", "lng", "lat", "DHI", "SSI", "ERI", "ERI_plus", "SMI", "mismatch_rank",
    ]
    assert index["mismatch_rank"].tolist() == [1, 2, 3]

    audit = pd.read_csv(cfg.out_dir / "data_quality_audit_v22_04R2.csv", encoding="utf-8-sig")
    assert not audit.empty

    latest = PipelineRunner(cfg).run()
    assert latest.status == "succeeded"


def test_missing_raw_data_raises_gracefully(tmp_path):
    cfg = PipelineConfig(
        project_root=ROOT,
        xhs_path=tmp_path / "no_such.csv",
        dp_path=FIXTURES / "sample_dp.csv",
        amap_path=FIXTURES / "sample_amap.csv",
        ctrip_path=FIXTURES / "sample_ctrip.csv",
        out_dir=tmp_path / "out",
        db_path=tmp_path / "run.db",
    )
    runner = PipelineRunner(cfg)
    with pytest.raises(RawDataUnavailableError):
        runner.run()

    # 失败任务必须落库，保证 API 轮询可查到失败原因
    from src.storage.run_store import RunStore

    store = RunStore(cfg.db_path)
    store.initialize()
    latest = store.latest_run()
    store.close()
    assert latest is not None
    assert latest["status"] == "failed"
    assert "原始数据缺失" in (latest["error"] or "")
