"""校验回归问答样例 JSON 的结构与数量；不调用真实 LLM / Neo4j。"""

import json
from pathlib import Path

import pytest

CASES_PATH = Path(__file__).resolve().parent / "data" / "week3_regression_cases.json"


def _load_cases() -> list:
    data = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    return list(data["cases"])


def test_week3_regression_cases_file_exists() -> None:
    assert CASES_PATH.is_file()


def test_week3_regression_cases_count_in_range() -> None:
    cases = _load_cases()
    assert 30 <= len(cases) <= 55


@pytest.mark.parametrize("case", _load_cases(), ids=lambda c: str(c["id"]))
def test_week3_case_schema(case: dict) -> None:
    assert isinstance(case.get("id"), str) and case["id"]
    assert case.get("category") in (
        "insurance",
        "nursing_home",
        "medical",
        "general",
        "mixed",
    )
    assert isinstance(case.get("multi_turn"), bool)
    mt = bool(case["multi_turn"])
    if not mt:
        assert isinstance(case.get("query"), str) and case["query"].strip()
        assert "queries" not in case or case.get("queries") in (None, [])
    else:
        qs = case.get("queries")
        assert isinstance(qs, list) and len(qs) >= 2
        assert all(isinstance(x, str) and x.strip() for x in qs)
