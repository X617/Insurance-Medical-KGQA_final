"""
前后端联调用的轻量 HTTP 客户端（无 Streamlit 依赖）。
供 `streamlit_app.py` 与 `scripts/week3_regression_runner.py` 复用。
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

import httpx


class ChatAPIError(Exception):
    """POST /chat 返回 4xx/5xx 时抛出（body 若为统一错误结构则解析 code/message/trace_id）。"""

    def __init__(self, status_code: int, code: str, message: str, trace_id: str, raw_body: str = "") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.trace_id = trace_id
        self.raw_body = raw_body

    def __str__(self) -> str:
        return f"[{self.status_code}] {self.code}: {self.message} (trace_id={self.trace_id})"


def post_chat(
    api_base: str,
    query: str,
    history: List[Dict[str, str]],
    *,
    trace_id: Optional[str] = None,
    timeout_s: float = 120.0,
) -> Dict[str, Any]:
    """调用 POST /chat，成功时返回 JSON 字典（含 answer/context/intent/rewritten_query）。"""
    url = f"{api_base.rstrip('/')}/chat"
    payload = {"query": query, "history": history}
    tid = trace_id or str(uuid.uuid4())
    headers = {"x-trace-id": tid}
    with httpx.Client(timeout=timeout_s) as client:
        response = client.post(url, json=payload, headers=headers)
        if response.status_code >= 400:
            body: Dict[str, Any]
            try:
                body = response.json()
            except Exception:
                body = {}
            raise ChatAPIError(
                status_code=response.status_code,
                code=str(body.get("code", "HTTP_ERROR")),
                message=str(body.get("message", response.text[:800])),
                trace_id=str(body.get("trace_id", tid)),
                raw_body=response.text[:2000],
            )
        return response.json()


def get_health(api_base: str, *, timeout_s: float = 10.0) -> Dict[str, Any]:
    url = f"{api_base.rstrip('/')}/health"
    with httpx.Client(timeout=timeout_s) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.json()
