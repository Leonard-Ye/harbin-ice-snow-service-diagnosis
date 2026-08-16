# -*- coding: utf-8 -*-
"""API 配置：环境变量优先，提供安全默认值。"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class ApiSettings:
    app_name: str = "智能多源数据自动化与分析平台 API"
    version: str = "1.0.0"
    api_prefix: str = "/api/v1"
    project_root: Path = PROJECT_ROOT
    pipeline_config_path: Path = field(default_factory=lambda: PROJECT_ROOT / "configs" / "pipeline.toml")
    upload_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "uploads")
    max_upload_bytes: int = 20 * 1024 * 1024
    cors_origins: list[str] = field(
        default_factory=lambda: [
            x.strip()
            for x in os.getenv(
                "BACKEND_CORS_ORIGINS",
                "http://localhost:8501,http://127.0.0.1:8501",
            ).split(",")
            if x.strip()
        ]
    )
    enable_write_endpoints: bool = field(default_factory=lambda: _env_bool("ENABLE_WRITE_ENDPOINTS", True))
    job_timeout_seconds: int = 3600

    def ensure_upload_dir(self) -> None:
        self.upload_dir.mkdir(parents=True, exist_ok=True)


settings = ApiSettings()
