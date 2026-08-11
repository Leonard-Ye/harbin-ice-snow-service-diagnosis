# -*- coding: utf-8 -*-
"""pytest 全局配置：确保仓库根与 dashboard 目录可导入。"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, "05_streamlit_dashboard")):
    if p not in sys.path:
        sys.path.insert(0, p)
