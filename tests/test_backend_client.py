# -*- coding: utf-8 -*-
"""BackendClient 降级行为测试。"""
import pytest

from backend_client import BackendClient, BackendUnavailable


def test_backend_client_configured_flag():
    assert BackendClient("http://127.0.0.1:8000").configured is True
    assert BackendClient("").configured is False


def test_backend_client_raises_on_unreachable():
    client = BackendClient("http://127.0.0.1:1", timeout=0.2)
    with pytest.raises(BackendUnavailable):
        client.health()
