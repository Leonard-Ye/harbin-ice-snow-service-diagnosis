# -*- coding: utf-8 -*-
"""FastAPI 集成测试：路由、数据契约与报表下载。"""
import io

import pytest
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["components"]["data"] == "ok"


def test_meta_anchors(client):
    resp = client.get("/api/v1/meta/anchors")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 20
    assert items[0]["anchor_name"]


def test_metrics_calculate(client):
    resp = client.post(
        "/api/v1/metrics/calculate",
        json={"scale_km": 3, "method": "equal"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["method"] == "equal"
    assert len(body["items"]) == 20
    ranks = [item["mismatch_rank"] for item in body["items"]]
    assert ranks == list(range(1, 21))


def test_metrics_calculate_entropy(client):
    resp = client.post(
        "/api/v1/metrics/calculate",
        json={"scale_km": 3, "method": "entropy"},
    )
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 20


def test_anchors_list_and_detail(client):
    resp = client.get("/api/v1/anchors?method=equal&limit=5")
    assert resp.status_code == 200
    assert resp.json()["count"] == 5

    detail = client.get("/api/v1/anchors/中央大街?method=equal")
    assert detail.status_code == 200
    body = detail.json()
    assert body["anchor_name"] == "中央大街"
    assert body["diagnosis"]
    assert body["pain_profile"]["xhs_mentions"] >= 0


def test_anchor_not_found(client):
    resp = client.get("/api/v1/anchors/不存在的锚点")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "ANCHOR_NOT_FOUND"


def test_quality_audit(client):
    resp = client.get("/api/v1/quality/audit")
    assert resp.status_code == 200
    rows = resp.json()["rows"]
    assert len(rows) >= 10
    assert any(r["flag"] for r in rows)


def test_reports_excel(client):
    resp = client.get("/api/v1/reports/excel?method=equal")
    assert resp.status_code == 200
    assert resp.content[:2] == b"PK"


def test_reports_html(client):
    resp = client.get("/api/v1/reports/html?method=equal")
    assert resp.status_code == 200
    assert "哈尔滨冰雪旅游服务设施供需诊断报告" in resp.text


def test_reports_pdf(client):
    resp = client.get("/api/v1/reports/pdf?method=equal")
    assert resp.status_code == 200
    assert resp.content[:5] == b"%PDF-"


def test_ingest_generic_csv(client):
    csv_bytes = (
        "name,value,lng,lat\n"
        "a,1,126.6,45.7\n"
        "b,2,126.7,45.8\n"
        "c,2,126.8,45.9\n"
        "d,3,126.9,46.0\n"
        "e,3,127.0,46.0\n"
        "f,4,126.6,45.7\n"
        "g,100,126.7,45.8\n"
        "h,2,200.0,45.9\n"
    ).encode("utf-8")
    resp = client.post(
        "/api/v1/ingest",
        files={"upload": ("sample.csv", io.BytesIO(csv_bytes), "text/csv")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["rows"] == 8
    assert body["columns"] == 4
    assert body["coordinate_issues"] == 1
    assert any(row["column"] == "value" and row["iqr_outliers"] for row in body["audit"])


def test_ingest_rejects_unsupported_type(client):
    resp = client.post(
        "/api/v1/ingest",
        files={"upload": ("bad.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert resp.status_code == 415
    assert resp.json()["detail"]["code"] == "UNSUPPORTED_FILE_TYPE"


def test_pipeline_runs_list(client):
    resp = client.get("/api/v1/pipeline/runs?limit=5")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_ai_placeholder(client):
    resp = client.post("/api/v1/ai/diagnose", json={})
    assert resp.status_code == 501
    assert resp.json()["code"] == "NOT_IMPLEMENTED"
