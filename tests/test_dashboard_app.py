# -*- coding: utf-8 -*-
"""Dashboard AppTest：应用零异常、页签/控件结构、权重方案切换。"""
import os

import pytest
from streamlit.testing.v1 import AppTest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_PATH = os.path.join(ROOT, "05_streamlit_dashboard", "app.py")


@pytest.fixture(scope="module")
def app():
    at = AppTest.from_file(APP_PATH, default_timeout=120)
    at.run()
    return at


def test_app_runs_without_exception(app):
    assert not app.exception, [e.message for e in app.exception]


def test_app_has_four_tabs(app):
    assert len(app.tabs) == 4


def test_app_widget_structure(app):
    assert len(app.radio) == 1          # 权重方案
    assert len(app.multiselect) >= 2    # 类型筛选 + 表格展示列
    assert len(app.selectbox) >= 3      # 单锚点 + 离群维度 + 指标分布


def test_entropy_mode_switches_cleanly(app):
    if not app.radio:
        pytest.skip("无权重方案 radio")
    app.radio[0].set_value("entropy")
    app.run()
    assert not app.exception, [e.message for e in app.exception]
    assert len(app.tabs) == 4


def test_map_layer_has_id(app):
    """pydeck 图层必须声明 id（on_select 跨 rerun 状态化必需）。"""
    from app import build_map  # noqa: F401  (import 副作用仅验证模块可加载)
    # 静态检查：build_map 中 ScatterplotLayer 带 id="anchors"
    src = open(APP_PATH, encoding="utf-8").read()
    assert 'id="anchors"' in src, "ScatterplotLayer 必须声明 id='anchors' 才能支持选择事件"


def test_resolve_selected_anchor_parses_pydeck_state():
    """按 PydeckSelectionState schema 解析被点击锚点（objects 按 layer id 分组）。"""
    from dashboard_data import resolve_selected_anchor

    # 真实 schema：{"objects": {"anchors": [{"anchor_name": "中央大街", ...}]}}
    selection = {"objects": {"anchors": [{"anchor_name": "中央大街", "SMI": 0.37}]}}
    assert resolve_selected_anchor(selection) == "中央大街"
    # 空 / 结构异常
    assert resolve_selected_anchor(None) == ""
    assert resolve_selected_anchor({}) == ""
    assert resolve_selected_anchor({"objects": {}}) == ""
    assert resolve_selected_anchor({"objects": {"anchors": []}}) == ""
    # objects 是 list（旧版/异常结构）应安全回退
    assert resolve_selected_anchor({"objects": [{"anchor_name": "x"}]}) == ""


def test_indicator_guide_present(app):
    """Dashboard 内应提供五指标语义速查（解决指标意义未讲清问题）。"""
    src = open(APP_PATH, encoding="utf-8").read()
    assert "指标速查" in src
    for name in ["DHI", "SSI", "ERI", "ERI_plus", "SMI"]:
        assert name in src


def test_radar_range_adaptive(app):
    """痛点雷达图径向范围应自适应数据（避免图形挤在中心）。"""
    src = open(APP_PATH, encoding="utf-8").read()
    assert "rmax = max(max(vals) * 1.25, 0.1)" in src
    assert "range=[0, rmax]" in src


def test_histogram_no_cramped_box(app):
    """指标分布图不应使用矮小的 marginal=box（用户反馈看不清），且高度加大。"""
    src = open(APP_PATH, encoding="utf-8").read()
    assert 'marginal="box"' not in src
    assert "height=460" in src
