"""
对运行中的后端逐条 POST /chat，输出简报。

用法（项目根目录）：
  python scripts/week3_regression_runner.py --base-url http://127.0.0.1:8000

回归样例见 `tests/data/week3_regression_cases.json`。

说明：
- 多轮用例会以上一轮 assistant 回答文本写入 history，再发下一轮用户话。
- 本脚本不自动判定“对错”，仅记录状态码、trace、回答长度；人工对照样例文件中的 notes。
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from frontend.kgqa_http import ChatAPIError, post_chat  # noqa: E402


def _load_cases() -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    path = ROOT / "tests" / "data" / "week3_regression_cases.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return data, list(data["cases"])


def _run_case(
    base_url: str, case: Dict[str, Any], timeout_s: float
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    history: List[Dict[str, str]] = []
    cid = case["id"]

    if not case["multi_turn"]:
        queries = [case["query"]]
    else:
        queries = list(case["queries"])

    for step_i, q in enumerate(queries, start=1):
        tid = str(uuid.uuid4())
        t0 = time.perf_counter()
        ok = False
        code = ""
        msg = ""
        trace = tid
        ans_len = 0
        rw = ""

        try:
            data = post_chat(base_url.rstrip("/"), q.strip(), history, trace_id=tid, timeout_s=timeout_s)
            ok = True
            ans_len = len((data.get("answer") or "").strip())
            rw = str(data.get("rewritten_query") or "")
            assistant_text = data.get("answer") or ""
            history.append({"role": "user", "content": q.strip()})
            history.append({"role": "assistant", "content": assistant_text})
        except ChatAPIError as exc:
            code = exc.code
            msg = exc.message[:500]
            trace = exc.trace_id
        except Exception as exc:  # noqa: BLE001
            code = "CLIENT_ERROR"
            msg = repr(exc)

        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        rows.append(
            {
                "case_id": cid,
                "category": case.get("category", ""),
                "step": step_i,
                "query": q,
                "ok": ok,
                "http_or_error_code": code,
                "error_message": msg,
                "trace_id": trace,
                "latency_ms": elapsed_ms,
                "answer_len": ans_len,
                "rewritten_query": rw,
            }
        )
        if not ok:
            break

    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--max-cases", type=int, default=0, help="0 表示全部")
    parser.add_argument(
        "--out-csv",
        default="",
        help="若指定，将逐行结果写入该 CSV（相对项目根目录或绝对路径）",
    )
    args = parser.parse_args()

    meta, cases = _load_cases()
    if args.max_cases and args.max_cases > 0:
        cases = cases[: args.max_cases]

    print(f"title={meta.get('title')!r} cases={len(cases)} base={args.base_url!r}")

    all_rows: List[Dict[str, Any]] = []
    fail = 0
    for case in cases:
        rows = _run_case(args.base_url.rstrip("/"), case, args.timeout)
        all_rows.extend(rows)
        if any(not r["ok"] for r in rows):
            fail += 1
            print(f"[FAIL] {case['id']} step={rows[-1]['step']} err={rows[-1].get('http_or_error_code')}")
        else:
            print(f"[ OK ] {case['id']} steps={len(rows)} last_len={rows[-1]['answer_len']}")

    if args.out_csv:
        out_path = Path(args.out_csv)
        if not out_path.is_absolute():
            out_path = ROOT / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if all_rows:
            keys = list(all_rows[0].keys())
            with out_path.open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=keys)
                w.writeheader()
                w.writerows(all_rows)
        print(f"wrote {out_path}")

    print(f"summary: total_cases={len(cases)} cases_with_any_step_fail={fail}")
    return 0 if fail == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
