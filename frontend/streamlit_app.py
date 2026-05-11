"""
Insurance Medical KGQA — Streamlit 前端：真实 RAG 联调、多轮会话、错误与 trace 展示。

环境变量：
- INSURANCE_KGQA_API_BASE：后端根地址，默认 http://127.0.0.1:8000

启动（项目根目录）：
  streamlit run frontend/streamlit_app.py
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from frontend.kgqa_http import ChatAPIError, get_health, post_chat


def _api_base() -> str:
    return os.environ.get("INSURANCE_KGQA_API_BASE", "http://127.0.0.1:8000").rstrip("/")


def _trace_id() -> str:
    if "client_trace_id" not in st.session_state:
        st.session_state.client_trace_id = str(uuid.uuid4())
    return st.session_state.client_trace_id


def main() -> None:
    st.set_page_config(page_title="医保知识图谱问答", page_icon="💬", layout="centered")
    st.title("医保知识图谱问答")
    st.caption(
        "完整联调 RAG 主流程；支持多轮追问（历史随请求发送），"
        "侧栏可查看本轮意图、改写问句与检索上下文摘要。"
    )

    api_base = _api_base()
    with st.sidebar:
        st.subheader("服务配置")
        api_input = st.text_input(
            "API 根地址",
            value=api_base,
            help="先启动后端：uvicorn src.api.main:app --reload",
        )
        st.caption(f"本会话 trace（部分请求头 x-trace-id）：`{_trace_id()[:8]}…`")

        if st.button("检查 /health"):
            try:
                h = get_health(api_input.rstrip("/"))
                neo = h.get("neo4j_connected")
                st.success(f"正常：{h}")
                if neo is False:
                    st.warning("Neo4j 未连通时检索上下文可能为空，回答会不稳定。")
            except Exception as exc:  # noqa: BLE001
                st.error(f"无法连接：{exc}")

        if st.button("清空会话（含 trace）"):
            for key in ("messages", "last_chat_debug", "last_chat_error", "client_trace_id"):
                st.session_state.pop(key, None)
            st.rerun()

        st.markdown("---")
        st.subheader("多轮说明")
        st.markdown(
            "- 继续在下方输入框追问即可，**完整对话历史**会随 `POST /chat` 发送。\n"
            "- 若问「上面的」「刚才推荐的」等，应主要依据上一轮助手回答（由后端策略控制检索）。"
        )

        dbg = st.session_state.get("last_chat_debug")
        if dbg:
            with st.expander("本轮检索与意图（调试用）", expanded=False):
                st.markdown(f"**rewritten_query**：`{dbg.get('rewritten_query')!r}`")
                st.markdown("**intent**：")
                st.json(dbg.get("intent") or {})
                ctx = dbg.get("context") or ""
                preview = ctx if len(ctx) <= 6000 else ctx[:6000] + "\n…(truncated)"
                st.markdown("**context 预览：**")
                st.text(preview)

        err = st.session_state.get("last_chat_error")
        if err:
            with st.expander("最近一次错误（可复制给研发团队）", expanded=False):
                st.code(err, language="text")

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
        tid = _trace_id()
        st.session_state.pop("last_chat_error", None)

        with st.spinner("正在请求后端…"):
            try:
                data = post_chat(base, prompt.strip(), history_payload, trace_id=tid)
                answer = data.get("answer") or "（空回答）"
                st.session_state["last_chat_debug"] = {
                    "context": data.get("context"),
                    "intent": data.get("intent"),
                    "rewritten_query": data.get("rewritten_query"),
                    "trace_id": tid,
                }
            except ChatAPIError as exc:
                answer = (
                    f"请求失败：**{exc.code}**\n\n{exc.message}\n\n"
                    f"- trace_id: `{exc.trace_id}`\n"
                    "- 请将侧栏错误块或日志交给研发侧排查。"
                )
                st.session_state["last_chat_error"] = str(exc)
                if exc.raw_body:
                    st.session_state["last_chat_error"] += "\n\n--- raw ---\n" + exc.raw_body
                st.session_state.pop("last_chat_debug", None)
            except Exception as exc:  # noqa: BLE001
                answer = (
                    f"无法连接 `{base}`：{exc}\n\n"
                    "请确认后端已启动：`uvicorn src.api.main:app --reload`"
                )
                st.session_state["last_chat_error"] = repr(exc)
                st.session_state.pop("last_chat_debug", None)

        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.messages.append({"role": "assistant", "content": answer})
        st.rerun()


if __name__ == "__main__":
    main()
