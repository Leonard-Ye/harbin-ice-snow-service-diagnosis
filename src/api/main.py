# -*- coding: utf-8 -*-
"""FastAPI 应用入口。

运行：
    python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
文档：
    http://127.0.0.1:8000/docs
"""
from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.api.config import settings  # noqa: E402
from src.api.routers import ai, anchors, health, ingest, metrics, pipeline, quality, reports  # noqa: E402
from src.api.swagger_ui import DESCRIPTIONS, register_docs_routes  # noqa: E402
from src.storage.run_store import RunStore  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.ensure_upload_dir()
    try:
        store = RunStore(settings.project_root / "data" / "platform.db")
        store.initialize()
        store.close()
    except Exception:
        # 服务仍可启动，健康检查会报告 database 状态
        pass
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description=DESCRIPTIONS["zh"] + "\n\n---\n\n" + DESCRIPTIONS["en"],
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(anchors.router)
app.include_router(metrics.router)
app.include_router(quality.router)
app.include_router(pipeline.router)
app.include_router(ingest.router)
app.include_router(reports.router)
app.include_router(ai.router)

app.mount("/static", StaticFiles(directory=Path(__file__).resolve().parent / "static"), name="static")
register_docs_routes(app)


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {
        "name": settings.app_name,
        "version": settings.version,
        "docs": "/docs",
        "health": "/health",
    }
