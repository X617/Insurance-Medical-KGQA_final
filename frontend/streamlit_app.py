"""
Insurance Medical KGQA — Streamlit 前端骨架（第 1 周）。
通过环境变量 INSURANCE_KGQA_API_BASE 配置后端根地址，默认 http://127.0.0.1:8000
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

import httpx
import streamlit as st


def _api_base() -> str:
    return os.environ.get("INSURANCE_KGQA_API_BASE", "http://127.0.0.1:8000").rstrip("/")


def post_chat(api_base: str, query: str, history: List[Dict[str, str]]) -> Dict[str, Any]:
    """调用后端 POST /chat，返回 JSON 字典。"""
    url = f"{api_base}/chat"
    payload = {"query": query, "history": history}
    with httpx.Client(timeout=120.0) as client:
        response = client.post(url, json=payload)
        response.raise_for_status()
        return response.json()


def get_health(api_base: str) -> Dict[str, Any]:
    url = f"{api_base}/health"
    with httpx.Client(timeout=10.0) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.json()


def main() -> None:
    st.set_page_config(page_title="医保知识图谱问答", page_icon="💬", layout="centered")
    st.title("医保知识图谱问答")
    st.caption("第 1 周：页面骨架 + 联调 `/chat`（回答来自后端，含占位 Mock）")

    api_base = _api_base()
    with st.sidebar:
        st.subheader("服务配置")
        api_input = st.text_input("API 根地址", value=api_base, help="需先启动 FastAPI，例如 uvicorn src.api.main:app")
        if st.button("检查 /health"):
            try:
                h = get_health(api_input.rstrip("/"))
                st.success(f"正常：{h}")
            except Exception as exc:  # noqa: BLE001 — 展示给用户
                st.error(f"无法连接：{exc}")
        if st.button("清空会话"):
            st.session_state.pop("messages", None)
            st.session_state.pop("last_chat_debug", None)
            st.rerun()
        if st.session_state.get("last_chat_debug"):
            with st.expander("最近一次请求的调试信息"):
                st.json(st.session_state["last_chat_debug"])

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("请输入您的问题…"):
        history_payload: List[Dict[str, str]] = [
            {"role": m["role"], "content": m["content"]} for m in st.session_state.messages
        ]
        base = api_input.rstrip("/")
        with st.spinner("正在请求后端…"):
            try:
                data = post_chat(base, prompt.strip(), history_payload)
                answer = data.get("answer") or "（空回答）"
                st.session_state["last_chat_debug"] = {
                    "context": data.get("context"),
                    "intent": data.get("intent"),
                    "rewritten_query": data.get("rewritten_query"),
                }
            except Exception as exc:  # noqa: BLE001
                answer = (
                    f"【占位】无法连接 `{base}`：{exc}\n"
                    "请先启动 API：`uvicorn src.api.main:app --reload`"
                )
                st.session_state.pop("last_chat_debug", None)

        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.messages.append({"role": "assistant", "content": answer})
        st.rerun()


if __name__ == "__main__":
    main()
