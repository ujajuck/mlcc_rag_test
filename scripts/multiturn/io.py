"""CSV 입력 로더 + 결과 CSV/JSON 저장기."""

import csv
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from scripts.common.utils import safe_json_dumps, safe_json_loads

from .types import CaseResult, MultiturnTestCase, TurnRecord, TurnTestSpec


def _row_to_spec(row: dict, multiturn_index: int) -> TurnTestSpec:
    """CSV row → TurnTestSpec."""
    return TurnTestSpec(
        multiturn_index=multiturn_index,
        query=row.get("query", ""),
        expected_skills=safe_json_loads(row.get("expected_skills"), []),
        expected_tools=safe_json_loads(row.get("expected_tools"), []),
        expected_state=safe_json_loads(row.get("expected_state"), {}),
        required_keywords=safe_json_loads(row.get("required_keywords"), []),
    )


def load_single_turn_cases(csv_path: Path) -> list[MultiturnTestCase]:
    """단일턴 CSV 로더.

    CSV 컬럼: index, query, expected_skills, expected_tools,
             expected_state, required_keywords
    각 row 는 1턴짜리 MultiturnTestCase 로 변환된다.
    """
    cases: list[MultiturnTestCase] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            idx = row.get("index", "").strip()
            if not idx:
                continue
            cases.append(
                MultiturnTestCase(index=idx, turns=[_row_to_spec(row, 0)])
            )
    return cases


def load_test_cases(csv_path: Path) -> list[MultiturnTestCase]:
    """멀티턴 CSV 를 읽어 index 기준으로 턴을 그룹핑.

    CSV 컬럼:
        index, multiturn_index, query,
        expected_skills, expected_tools, expected_state, required_keywords
    """
    by_index: dict[str, list[TurnTestSpec]] = {}
    order: list[str] = []

    with csv_path.open("r", encoding="utf-8-sig", newline="") as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            idx = row.get("index", "").strip()
            if not idx:
                continue
            spec = _row_to_spec(row, int(row.get("multiturn_index", "0") or 0))
            if idx not in by_index:
                by_index[idx] = []
                order.append(idx)
            by_index[idx].append(spec)

    cases: list[MultiturnTestCase] = []
    for idx in order:
        turns = sorted(by_index[idx], key=lambda t: t.multiturn_index)
        cases.append(MultiturnTestCase(index=idx, turns=turns))
    return cases


def save_case_details_json(
    path: Path,
    test_case: MultiturnTestCase,
    turns: list[TurnRecord],
) -> None:
    """케이스별 상세 JSON 저장.

    CSV 에 다 담기 어려운 prompt/응답 전체 텍스트, tool 인자, state/artifact
    스냅샷, delta 등을 담는다.
    """
    payload = {
        "index": test_case.index,
        "turn_count": len(turns),
        "turns": [
            {
                "multiturn_index": t.multiturn_index,
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
                "elapsed_seconds": t.elapsed_seconds,
                "error_message": t.error_message,
                "required_keywords_present": t.required_keywords_present,
                "passed": t.passed,
                "fail_reasons": t.fail_reasons,
            }
            for t in turns
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=2, default=str)


SUMMARY_FIELDS = [
    "index",
    "turn_count",
    "passed",
    "total_input_tokens",
    "total_output_tokens",
    "total_model_requests",
    "total_elapsed_seconds",
    "per_turn_passed",
    "per_turn_input_tokens",
    "per_turn_output_tokens",
    "per_turn_model_request_count",
    "per_turn_elapsed_seconds",
    "per_turn_skills_used",
    "per_turn_tools_used",
    "per_turn_required_keywords_present",
    "per_turn_state_keys",
    "per_turn_state_delta_keys",
    "per_turn_artifact_keys",
    "per_turn_fail_reasons",
    "final_state_snapshot_json",
    "error_message",
    "details_json_path",
]


def _turn_state_keys(turn: TurnRecord) -> list[str]:
    return sorted(turn.state_snapshot.keys())


def _turn_state_delta_keys(turn: TurnRecord) -> dict[str, list[str]]:
    return {
        "added": sorted(turn.state_delta.get("added", {}).keys()),
        "removed": sorted(turn.state_delta.get("removed", {}).keys()),
        "changed": sorted(turn.state_delta.get("changed", {}).keys()),
    }


def _turn_artifact_keys(turn: TurnRecord) -> list[str]:
    return sorted(turn.artifact_snapshot.keys())


def write_summary_csv(result_dir: Path, results: list[CaseResult]) -> Path:
    """케이스 단위 요약 CSV 저장. 파일명은 타임스탬프 포함."""
    result_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = result_dir / f"mlcc_multiturn_eval_{timestamp}.csv"

    with output_path.open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()

        for r in results:
            final_state = r.turns[-1].state_snapshot if r.turns else {}
            row = {
                "index": r.index,
                "turn_count": r.turn_count,
                "passed": r.passed,
                "total_input_tokens": r.total_input_tokens,
                "total_output_tokens": r.total_output_tokens,
                "total_model_requests": r.total_model_requests,
                "total_elapsed_seconds": r.total_elapsed_seconds,
                "per_turn_passed": safe_json_dumps([t.passed for t in r.turns]),
                "per_turn_input_tokens": safe_json_dumps(
                    [t.input_tokens for t in r.turns]
                ),
                "per_turn_output_tokens": safe_json_dumps(
                    [t.output_tokens for t in r.turns]
                ),
                "per_turn_model_request_count": safe_json_dumps(
                    [t.model_request_count for t in r.turns]
                ),
                "per_turn_elapsed_seconds": safe_json_dumps(
                    [t.elapsed_seconds for t in r.turns]
                ),
                "per_turn_skills_used": safe_json_dumps(
                    [t.skills_used for t in r.turns]
                ),
                "per_turn_tools_used": safe_json_dumps(
                    [t.tools_used for t in r.turns]
                ),
                "per_turn_required_keywords_present": safe_json_dumps(
                    [t.required_keywords_present for t in r.turns]
                ),
                "per_turn_state_keys": safe_json_dumps(
                    [_turn_state_keys(t) for t in r.turns]
                ),
                "per_turn_state_delta_keys": safe_json_dumps(
                    [_turn_state_delta_keys(t) for t in r.turns]
                ),
                "per_turn_artifact_keys": safe_json_dumps(
                    [_turn_artifact_keys(t) for t in r.turns]
                ),
                "per_turn_fail_reasons": safe_json_dumps(
                    [t.fail_reasons for t in r.turns]
                ),
                "final_state_snapshot_json": safe_json_dumps(final_state),
                "error_message": r.error_message or "",
                "details_json_path": r.details_json_path,
            }
            writer.writerow(row)

    return output_path
