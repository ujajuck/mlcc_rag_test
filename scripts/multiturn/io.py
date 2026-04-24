"""CSV 입력 로더 + 결과 CSV/JSON 저장기.

입력 CSV 스키마 (서브인덱스별 한 행):
    index, subindex, query,
    expected_skills, expected_tools, expected_state, required_keywords

결과 CSV 스키마 (서브인덱스별 한 행):
    index, subindex, query,
    skills_used, tools_used, state_keys, required_keywords_check,
    passed, fail_reasons,
    input_tokens, output_tokens, model_request_count, time_taken,
    final_response, error_message, artifact_keys, details_json_path

상세 JSON 은 index 단위로 1 파일 (모든 subindex 의 prompt/response/tool 인자/
state/artifact snapshot/delta 등 전부 포함).
"""

import csv
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from scripts.common.utils import safe_json_dumps, safe_json_loads

from .types import CaseResult, MultiturnTestCase, TurnRecord, TurnTestSpec


INPUT_FIELDS = [
    "index",
    "subindex",
    "query",
    "expected_skills",
    "expected_tools",
    "expected_state",
    "required_keywords",
]


def load_test_cases(csv_path: Path) -> list[MultiturnTestCase]:
    """입력 CSV 를 index 기준으로 그룹핑해 MultiturnTestCase 리스트로.

    같은 index 의 row 들은 subindex 오름차순으로 한 케이스 안에 정렬된다.
    subindex 가 하나인 케이스 = 단일턴, 여러 개 = 멀티턴.
    """
    by_index: dict[str, list[TurnTestSpec]] = {}
    order: list[str] = []

    with csv_path.open("r", encoding="utf-8-sig", newline="") as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            idx = (row.get("index") or "").strip()
            if not idx:
                continue
            spec = TurnTestSpec(
                subindex=int(row.get("subindex", "0") or 0),
                query=row.get("query", ""),
                expected_skills=safe_json_loads(row.get("expected_skills"), []),
                expected_tools=safe_json_loads(row.get("expected_tools"), []),
                expected_state=safe_json_loads(row.get("expected_state"), {}),
                required_keywords=safe_json_loads(row.get("required_keywords"), []),
            )
            if idx not in by_index:
                by_index[idx] = []
                order.append(idx)
            by_index[idx].append(spec)

    cases: list[MultiturnTestCase] = []
    for idx in order:
        turns = sorted(by_index[idx], key=lambda t: t.subindex)
        cases.append(MultiturnTestCase(index=idx, turns=turns))
    return cases


def save_case_details_json(
    path: Path,
    test_case: MultiturnTestCase,
    turns: list[TurnRecord],
) -> None:
    """케이스별 상세 JSON 저장 (index 단위 1 파일)."""
    payload = {
        "index": test_case.index,
        "turn_count": len(turns),
        "turns": [
            {
                "subindex": t.subindex,
                "user_input": t.user_input,
                "final_response": t.final_response,
                "skills_used": t.skills_used,
                "tools_used": t.tools_used,
                "tool_calls": [asdict(c) for c in t.tool_calls],
                "model_calls": [asdict(m) for m in t.model_calls],
                "state_snapshot": t.state_snapshot,
                "artifact_snapshot": t.artifact_snapshot,
                "state_delta": t.state_delta,
                "artifact_delta": t.artifact_delta,
                "input_tokens": t.input_tokens,
                "output_tokens": t.output_tokens,
                "model_request_count": t.model_request_count,
                "time_taken": t.elapsed_seconds,
                "error_message": t.error_message,
                "required_keywords_check": t.required_keywords_present,
                "passed": t.passed,
                "fail_reasons": t.fail_reasons,
            }
            for t in turns
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=2, default=str)


OUTPUT_FIELDS = [
    "index",
    "subindex",
    "query",
    "skills_used",
    "tools_used",
    "state_keys",
    "required_keywords_check",
    "passed",
    "fail_reasons",
    "input_tokens",
    "output_tokens",
    "model_request_count",
    "time_taken",
    "final_response",
    "error_message",
    "artifact_keys",
    "details_json_path",
]


def write_summary_csv(result_dir: Path, results: list[CaseResult]) -> Path:
    """서브인덱스별 한 행씩 요약 CSV 저장."""
    result_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = result_dir / f"mlcc_eval_{timestamp}.csv"

    with output_path.open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(
            fp, fieldnames=OUTPUT_FIELDS, quoting=csv.QUOTE_ALL
        )
        writer.writeheader()
        for r in results:
            for t in r.turns:
                writer.writerow(
                    {
                        "index": r.index,
                        "subindex": t.subindex,
                        "query": t.user_input,
                        "skills_used": safe_json_dumps(t.skills_used),
                        "tools_used": safe_json_dumps(t.tools_used),
                        "state_keys": safe_json_dumps(t.state_snapshot),
                        "required_keywords_check": safe_json_dumps(
                            t.required_keywords_present
                        ),
                        "passed": t.passed,
                        "fail_reasons": "\n".join(t.fail_reasons) if t.fail_reasons else "",
                        "input_tokens": t.input_tokens,
                        "output_tokens": t.output_tokens,
                        "model_request_count": t.model_request_count,
                        "time_taken": t.elapsed_seconds,
                        "final_response": t.final_response or "",
                        "error_message": t.error_message or "",
                        "artifact_keys": safe_json_dumps(
                            sorted(t.artifact_snapshot.keys())
                        ),
                        "details_json_path": r.details_json_path,
                    }
                )

    return output_path
