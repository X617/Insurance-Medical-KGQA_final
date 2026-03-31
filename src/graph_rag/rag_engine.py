from typing import Dict, List


class RAGEngine:
    """
    Week-1 placeholder engine.
    Keep the signature stable for future integration.
    """

    def __init__(self) -> None:
        self.retriever = None

    def chat(self, query: str, history: List[Dict[str, str]] | None = None) -> Dict:
        history = history or []
        return {
            "answer": f"【Mock回答】已收到问题：{query}",
            "context": "week1-mock-context",
            "intent": {"type": "unknown", "entities": [], "history_len": len(history)},
            "rewritten_query": query,
        }

    def close(self) -> None:
        return
