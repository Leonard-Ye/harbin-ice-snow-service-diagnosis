# -*- coding: utf-8 -*-
"""ui_theme 单元测试：hex→RGB 转换与地图气泡颜色列（deck.gl 渲染输入）。"""
import pytest

import ui_theme
from dashboard_data import add_diagnosis, full_table


@pytest.mark.parametrize(
    "hex_color,expected",
    [
        ("#EF5350", [239, 83, 80, 255]),   # 红
        ("#66BB6A", [102, 187, 106, 255]), # 绿
        ("#90A4AE", [144, 164, 174, 255]), # 灰
    ],
)
def test_hex_to_rgb_basic(hex_color, expected):
    assert ui_theme.hex_to_rgb(hex_color) == expected


def test_hex_to_rgb_invalid_fallback():
    assert ui_theme.hex_to_rgb(None) == [128, 128, 128, 255]
    assert ui_theme.hex_to_rgb("red") == [128, 128, 128, 255]
    assert ui_theme.hex_to_rgb("#FFF") == [128, 128, 128, 255]  # 长度不符


def test_type_color_column_is_rgb_list():
    """地图气泡颜色列必须是 deck.gl 可用的 RGB[4] 列表（hex 字符串会渲染为黑色）。"""
    df = add_diagnosis(full_table())
    df["type_color"] = (
        df["diagnosis"].map(ui_theme.type_colors("dark")).apply(ui_theme.hex_to_rgb)
    )
    assert len(df) == 20
    for c in df["type_color"]:
        assert isinstance(c, list) and len(c) == 4, f"颜色应为 [r,g,b,a]: {c}"
        assert c[3] == 255, "alpha 应为 255"
        assert not (c[0] == 0 and c[1] == 0 and c[2] == 0), "不应出现纯黑气泡"


def test_type_color_has_diagnosis_variety():
    """不同诊断类型应映射到不同颜色（≥5 种），体现类型差异。"""
    df = add_diagnosis(full_table())
    df["type_color"] = (
        df["diagnosis"].map(ui_theme.type_colors("dark")).apply(ui_theme.hex_to_rgb)
    )
    uniq = {tuple(c[:3]) for c in df["type_color"]}
    assert len(uniq) >= 5, f"应有 ≥5 种类型色，实际 {len(uniq)}"
