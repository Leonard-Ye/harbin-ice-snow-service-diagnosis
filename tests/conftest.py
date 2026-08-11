# -*- coding: utf-8 -*-
"""pytest 全局配置：确保仓库根可导入（src/ 与 dashboard_data）。"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
