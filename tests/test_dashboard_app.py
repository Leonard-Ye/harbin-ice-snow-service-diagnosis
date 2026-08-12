# -*- coding: utf-8 -*-
"""Dashboard AppTest：应用零异常、页签/控件结构、权重方案切换。"""
import os

import pytest
from streamlit.testing.v1 import AppTest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_PATH = os.path.join(ROOT, "dashboard", "app.py")


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


def test_no_emoji_in_ui(app):
    """界面不应出现 emoji（雪花/天平/齿轮等），改用文字或 Material 图标。"""
    import re

    src = open(APP_PATH, encoding="utf-8").read()
    emojis = re.findall(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]", src)
    assert not emojis, f"残留 emoji: {[hex(ord(e)) for e in emojis]}"
    assert "❄️" not in src and "⚖️" not in src
    assert ":material/" in src  # 用 Material 图标替代


def test_overview_layout_gives_side_column_space(app):
    """总览页右栏（SMI Top10）需有足够宽度，列比 [3,2] 而非 [7,3]。"""
    src = open(APP_PATH, encoding="utf-8").read()
    assert "col_map, col_side = st.columns([3, 2])" in src
    # SMI 排名图标题（用户版为 title=dict 写法），说明已移到 caption
    assert "SMI 服务错配排名 Top 10" in src
    assert "SMI = z(DHI) + z(ERI) − z(SSI)" in src


def test_narrative_has_indicator_table(app):
    """研究叙事必须内置五指标释义表（HR 不读文档也能看懂成果）。"""
    src = open(APP_PATH, encoding="utf-8").read()
    assert "5 项自研指标怎么读" in src
    for name in ["DHI 需求热度", "SSI 服务供给", "ERI 体验风险", "ERI_plus 餐饮压力", "SMI 服务错配"]:
        assert name in src


def test_narrative_no_markdown_asterisks(app):
    """研究叙事不应出现 ** 加粗语法（渲染为字面 **** 的瑕疵）。"""
    src = open(APP_PATH, encoding="utf-8").read()
    start = src.index("#### 为什么做")
    end = src.index("#### 发现了什么")
    narrative = src[start:end]
    assert "**" not in narrative, "研究叙事含未处理的 ** 加粗语法"


def test_entropy_is_default_weighting(app):
    """熵权法（数据驱动）应为默认权重方案，等权仅作对照。"""
    assert app.radio[0].value == "entropy", f"默认权重应为 entropy，实际 {app.radio[0].value}"


def test_first_screen_has_conclusions_before_tabs(app):
    """首屏（tab 之前）必须含核心结论，HR 打开即见。"""
    src = open(APP_PATH, encoding="utf-8").read()
    kpi_pos = src.index("kpi_cols = st.columns(4)")
    tab_pos = src.index('st.tabs(\n    ["总览地图"')
    between = src[kpi_pos:tab_pos]
    assert "核心结论" in between, "核心结论应位于 KPI 与 tabs 之间（首屏）"
    assert 'class="insight-card"' in between, "结论应为卡片形式"


def test_no_duplicate_insights(app):
    """核心结论全局唯一（首屏一份，总览页无重复）。"""
    src = open(APP_PATH, encoding="utf-8").read()
    assert src.count('<div class="section-title">核心结论</div>') == 1
    # 导出按钮 key 唯一
    assert src.count('key="dl_excel"') == 1 and src.count('key="dl_html"') == 1


def test_quality_page_has_guide(app):
    """数据质量页应含权重对比与审计内容（HR 视角可读）。"""
    src = open(APP_PATH, encoding="utf-8").read()
    assert "指标权重方案对比" in src
    assert "数据质量审计" in src


def test_footer_has_data_timestamp(app):
    """页脚必须有数据快照时间与口径说明（回答「数据多新」）。"""
    src = open(APP_PATH, encoding="utf-8").read()
    assert "本项目基于多源数据融合快照" in src
    assert "页脚" in src


def test_tab_guide_present(app):
    """tabs 下方应有页签导览（标注各页适用人群）。"""
    src = open(APP_PATH, encoding="utf-8").read()
    assert "页签导览" in src


def test_theme_refresh_hint(app):
    """侧边栏应提示切换主题后刷新页面（避免显示异常）。"""
    src = open(APP_PATH, encoding="utf-8").read()
    assert "切换主题后请刷新页面" in src


def test_background_zoning_present(app):
    """页面应有背景分区（Material 阴影卡片，无渐变），建立视觉重心。"""
    src = open(APP_PATH, encoding="utf-8").read()
    assert 'with st.container(key="hero")' in src, "hero 容器缺失"
    assert 'key="export"' in src, "导出卡片容器缺失"
    assert 'class="section-title"' in src, "色条区块标题缺失"
    theme_src = open(os.path.join(ROOT, "dashboard", "ui_theme.py"), encoding="utf-8").read()
    assert "hero_gradient" not in theme_src, "渐变方案已废弃，不应残留"
    assert "shadow" in theme_src and "surface" in theme_src, "Material 阴影卡片样式缺失"
    assert "box-shadow" in theme_src
    assert ".st-key-hero" in theme_src and ".st-key-export" in theme_src
    assert ".section-title" in theme_src
