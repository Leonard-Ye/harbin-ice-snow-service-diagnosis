# -*- coding: utf-8 -*-
"""RunStore 单元测试：运行记录与指标快照持久化。"""
import pandas as pd

from src.storage.run_store import RunStore


def test_run_store_roundtrip(tmp_path):
    store = RunStore(tmp_path / "test.db")
    store.initialize()
    store.start_run("r1", "equal", 3, {"method": "equal"}, "2026-08-16T00:00:00+08:00")
    store.finish_run("r1", "succeeded", "2026-08-16T00:00:01+08:00", 1000, "in-sha", "out-sha")
    metrics = pd.DataFrame(
        {
            "anchor_name": ["A", "B"],
            "DHI": [0.1, -0.1],
            "SSI": [0.2, -0.2],
            "ERI": [0.3, -0.3],
            "ERI_plus": [0.4, -0.4],
            "SMI": [0.5, -0.5],
            "mismatch_rank": [1, 2],
        }
    )
    store.record_metric_snapshots("r1", metrics, 3)
    run = store.get_run("r1")
    assert run["status"] == "succeeded"
    assert run["input_sha256"] == "in-sha"
    store.close()
