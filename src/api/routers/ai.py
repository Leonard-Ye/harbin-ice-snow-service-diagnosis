# -*- coding: utf-8 -*-
"""AI 诊断路由占位。

P5 阶段实现 RuleBasedAdvisor / LLMAdvisor 后替换 501 实现。
当前先提供稳定的接口契约，供前端联调。
"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])


@router.post("/diagnose", status_code=501)
def diagnose() -> dict:
    return {
        "code": "NOT_IMPLEMENTED",
        "message": "AI 诊断顾问将在 P5 阶段开放；当前请使用规则化诊断策略接口。",
    }
