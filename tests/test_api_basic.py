"""基础 API 验收用例：/health 与 /chat（RAGEngine 在测试中通过 monkeypatch 隔离）。"""

from typing import List, Optional

import pytest
from fastapi.testclient import TestClient

from src.api import main as api_main
from src.api.main import app


@pytest.fixture
def client():
    """必须进入上下文，才会执行 lifespan，初始化 rag_engine。"""
    with TestClient(app) as test_client:
        yield test_client


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "ok"
    assert "neo4j_connected" in body


def test_chat_returns_fields_from_engine(client, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_chat(user_query: str, history: Optional[List] = None) -> dict:
        return {
            "answer": f"Echo: {user_query}",
            "context": "test-context",
            "intent": {"type": "test"},
            "rewritten_query": user_query,
        }

    assert api_main.rag_engine is not None
    monkeypatch.setattr(api_main.rag_engine, "chat", fake_chat)

    r = client.post("/chat", json={"query": "hello mock", "history": []})
    assert r.status_code == 200
    data = r.json()
    assert data["answer"] == "Echo: hello mock"
    assert data["context"] == "test-context"
    assert data.get("intent", {}).get("type") == "test"
    assert data.get("rewritten_query") == "hello mock"


def test_chat_rag_exception_returns_500_contract(client, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(_user_query: str, _history: Optional[List] = None) -> dict:
        raise RuntimeError("neo4j down")

    assert api_main.rag_engine is not None
    monkeypatch.setattr(api_main.rag_engine, "chat", boom)

    r = client.post("/chat", json={"query": "any", "history": []})
    assert r.status_code == 500
    err = r.json()
    assert err.get("code") == "RAG_PIPELINE_ERROR"
    assert "trace_id" in err


def test_chat_empty_query_400(client) -> None:
    r = client.post("/chat", json={"query": "   ", "history": []})
    assert r.status_code == 400
    err = r.json()
    assert err.get("code") == "HTTP_ERROR"
