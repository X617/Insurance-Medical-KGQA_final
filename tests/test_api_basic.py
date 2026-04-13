"""基础 API 验收用例：/health 与 /chat（与 RAGEngine Mock 联调）。"""

from fastapi.testclient import TestClient


def test_health_ok(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "ok"
    assert "neo4j_connected" in body


def test_chat_returns_mock_answer(client: TestClient) -> None:
    r = client.post("/chat", json={"query": "hello mock", "history": []})
    assert r.status_code == 200
    data = r.json()
    assert "answer" in data
    assert "context" in data
    assert "hello mock" in data["answer"] or "Mock" in data["answer"]


def test_chat_empty_query_400(client: TestClient) -> None:
    r = client.post("/chat", json={"query": "   ", "history": []})
    assert r.status_code == 400
    err = r.json()
    assert err.get("code") == "HTTP_ERROR"
