# -*- coding: utf-8 -*-
"""PDF 报告生成冒烟测试：输出合法 PDF、字体初始化正常。"""
from dashboard_data import add_diagnosis, full_table
from pdf_report import FONT_NAME, build_visual_pdf_bytes


def test_pdf_report_generates_valid_pdf():
    df = add_diagnosis(full_table())
    data = build_visual_pdf_bytes(df, "equal")
    assert data[:5] == b"%PDF-", "PDF 应以 %PDF 魔数开头"
    assert len(data) > 5000, "PDF 内容不应为空"


def test_pdf_font_init_returns_usable_name():
    assert isinstance(FONT_NAME, str) and FONT_NAME
    # 跨平台：Windows 解析到 SimHei/MicrosoftYaHei，Linux 解析到 NotoSansCJK 等，
    # 全部回退 Helvetica。断言只要求非空（具体字体随平台变化）。
    assert FONT_NAME in (
        "SimHei", "MicrosoftYaHei", "NotoSansCJK", "WenQuanYiZenHei",
        "PingFang", "Helvetica",
    )
