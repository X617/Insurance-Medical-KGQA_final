import pytest
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture
def client() -> TestClient:
    # 必须进入上下文，才会执行 lifespan，初始化 rag_engine
    with TestClient(app) as test_client:
        yield test_client
