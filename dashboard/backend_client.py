# -*- coding: utf-8 -*-
"""FastAPI 后端客户端。

仅当显式设置 BACKEND_URL 时启用；连接失败由上层降级到本地引擎。
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

import pandas as pd
import requests

DEFAULT_TIMEOUT = 2.0


class BackendUnavailable(RuntimeError):
    """后端不可达。"""


class BackendClient:
    def __init__(self, base_url: Optional[str] = None, timeout: float = DEFAULT_TIMEOUT) -> None:
        self.base_url = (base_url or os.getenv("BACKEND_URL") or "").rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    @property
    def configured(self) -> bool:
        return bool(self.base_url)

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        try:
            resp = self.session.get(f"{self.base_url}{path}", params=params, timeout=self.timeout)
        except requests.RequestException as exc:
            raise BackendUnavailable(str(exc)) from exc
        if resp.status_code >= 400:
            raise BackendUnavailable(f"HTTP {resp.status_code}: {resp.text[:200]}")
        return resp.json()

    def _post(self, path: str, json: Optional[Dict[str, Any]] = None, files: Optional[Dict[str, Any]] = None) -> Any:
        try:
            resp = self.session.post(f"{self.base_url}{path}", json=json, files=files, timeout=self.timeout)
        except requests.RequestException as exc:
            raise BackendUnavailable(str(exc)) from exc
        if resp.status_code >= 400:
            raise BackendUnavailable(f"HTTP {resp.status_code}: {resp.text[:200]}")
        return resp.json()

    def health(self) -> Dict[str, Any]:
        return self._get("/health")

    def full_table(self, method: str) -> pd.DataFrame:
        payload = self._get("/api/v1/dataset/full", {"method": method})
        return pd.DataFrame(payload["items"])

    def metric_items(self, method: str) -> pd.DataFrame:
        payload = self._get("/api/v1/anchors", {"method": method, "limit": 20})
        return pd.DataFrame(payload["items"])

    def quality_audit(self) -> pd.DataFrame:
        payload = self._get("/api/v1/quality/audit")
        return pd.DataFrame(payload["rows"])

    def list_runs(self, limit: int = 10) -> list[Dict[str, Any]]:
        return self._get("/api/v1/pipeline/runs", {"limit": limit})

    def run_pipeline(self, method: str, force: bool = False) -> Dict[str, Any]:
        return self._post("/api/v1/pipeline/run", {"method": method, "force": force})

    def ingest(self, filename: str, content: bytes) -> Dict[str, Any]:
        return self._post("/api/v1/ingest", files={"upload": (filename, content)})

    def report_url(self, kind: str, method: str) -> str:
        return f"{self.base_url}/api/v1/reports/{kind}?method={method}"
