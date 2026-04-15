"""두 개의 멀티턴 평가 결과 CSV 를 비교한다.

scoring 대신 아래 항목을 중심으로 diff 를 뽑는다:
    - pass 수 변화 (전체/공통)
    - 입출력 토큰 합/평균 변화
    - 케이스별 skill/tool 사용 차이
    - 최종 state key/value 차이
    - pass flip, added/removed 케이스
"""

import csv
import json
import sys
from pathlib import Path
from typing import Any


def _parse_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _parse_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _parse_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _parse_json(value: Any, default: Any) -> Any:
    if value is None or value == "":
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


def load_csv(path: Path) -> dict[str, dict[str, str]]:
    """index 기준 dict 로 로드."""
    with path.open("r", encoding="utf-8-sig", newline="") as fp:
        reader = csv.DictReader(fp)
        return {row["index"]: row for row in reader if row.get("index")}


def _flatten_per_turn_list(value: Any) -> list[Any]:
    """per_turn_* 컬럼(JSON 문자열)을 list 로 변환."""
    data = _parse_json(value, [])
    return data if isinstance(data, list) else []


def _per_turn_set_diff(
    old_list: list[list[str]], new_list: list[list[str]]
) -> list[dict[str, Any]]:
    """turn 별로 (added, removed) 집합 diff 생성."""
    length = max(len(old_list), len(new_list))
    out: list[dict[str, Any]] = []
    for i in range(length):
        old_set = set(old_list[i]) if i < len(old_list) else set()
        new_set = set(new_list[i]) if i < len(new_list) else set()
        out.append(
            {
                "turn_index": i,
                "added": sorted(new_set - old_set),
                "removed": sorted(old_set - new_set),
            }
        )
    return out


def _state_value_diff(
    old_state: dict[str, Any], new_state: dict[str, Any]
) -> dict[str, Any]:
    added = sorted(k for k in new_state if k not in old_state)
    removed = sorted(k for k in old_state if k not in new_state)
    changed = sorted(
        k
        for k in new_state
        if k in old_state and old_state[k] != new_state[k]
    )
    return {"added": added, "removed": removed, "changed": changed}


def _make_case_item(
    index: str, old_row: dict[str, str], new_row: dict[str, str]
) -> dict[str, Any]:
    """공통 케이스 하나에 대한 비교 엔트리."""
    old_passed = _parse_bool(old_row.get("passed"))
    new_passed = _parse_bool(new_row.get("passed"))

    old_in = _parse_int(old_row.get("total_input_tokens"))
    new_in = _parse_int(new_row.get("total_input_tokens"))
    old_out = _parse_int(old_row.get("total_output_tokens"))
    new_out = _parse_int(new_row.get("total_output_tokens"))
    old_calls = _parse_int(old_row.get("total_model_requests"))
    new_calls = _parse_int(new_row.get("total_model_requests"))
    old_sec = _parse_float(old_row.get("total_elapsed_seconds"))
    new_sec = _parse_float(new_row.get("total_elapsed_seconds"))

    old_per_turn_passed = _flatten_per_turn_list(old_row.get("per_turn_passed"))
    new_per_turn_passed = _flatten_per_turn_list(new_row.get("per_turn_passed"))

    old_skills_per_turn = _flatten_per_turn_list(old_row.get("per_turn_skills_used"))
    new_skills_per_turn = _flatten_per_turn_list(new_row.get("per_turn_skills_used"))
    old_tools_per_turn = _flatten_per_turn_list(old_row.get("per_turn_tools_used"))
    new_tools_per_turn = _flatten_per_turn_list(new_row.get("per_turn_tools_used"))

    old_final_state = _parse_json(old_row.get("final_state_snapshot_json"), {})
    new_final_state = _parse_json(new_row.get("final_state_snapshot_json"), {})

    return {
        "index": index,
        "old_turn_count": _parse_int(old_row.get("turn_count")),
        "new_turn_count": _parse_int(new_row.get("turn_count")),
        "old_passed": old_passed,
        "new_passed": new_passed,
        "old_input_tokens": old_in,
        "new_input_tokens": new_in,
        "input_token_delta": new_in - old_in,
        "old_output_tokens": old_out,
        "new_output_tokens": new_out,
        "output_token_delta": new_out - old_out,
        "old_model_requests": old_calls,
        "new_model_requests": new_calls,
        "model_request_delta": new_calls - old_calls,
        "old_elapsed_seconds": old_sec,
        "new_elapsed_seconds": new_sec,
        "elapsed_delta": round(new_sec - old_sec, 4),
        "old_per_turn_passed": old_per_turn_passed,
        "new_per_turn_passed": new_per_turn_passed,
        "skills_per_turn_diff": _per_turn_set_diff(
            old_skills_per_turn, new_skills_per_turn
        ),
        "tools_per_turn_diff": _per_turn_set_diff(
            old_tools_per_turn, new_tools_per_turn
        ),
        "final_state_diff": _state_value_diff(old_final_state, new_final_state),
        "old_error": old_row.get("error_message", ""),
        "new_error": new_row.get("error_message", ""),
    }


def summarize(
    old_rows: dict[str, dict[str, str]],
    new_rows: dict[str, dict[str, str]],
) -> dict[str, Any]:
    all_ids = sorted(set(old_rows) | set(new_rows))
    added = [new_rows[i] for i in all_ids if i not in old_rows]
    removed = [old_rows[i] for i in all_ids if i not in new_rows]

    common_items: list[dict[str, Any]] = []
    for idx in all_ids:
        if idx in old_rows and idx in new_rows:
            common_items.append(_make_case_item(idx, old_rows[idx], new_rows[idx]))

    regressions = [
        it for it in common_items if it["old_passed"] and not it["new_passed"]
    ]
    improvements = [
        it for it in common_items if not it["old_passed"] and it["new_passed"]
    ]
    same_pass_changed_skills = [
        it
        for it in common_items
        if it["old_passed"] == it["new_passed"]
        and any(
            d["added"] or d["removed"] for d in it["skills_per_turn_diff"]
        )
    ]
    same_pass_changed_tools = [
        it
        for it in common_items
        if it["old_passed"] == it["new_passed"]
        and any(d["added"] or d["removed"] for d in it["tools_per_turn_diff"])
    ]
    state_diff_cases = [
        it
        for it in common_items
        if it["final_state_diff"]["added"]
        or it["final_state_diff"]["removed"]
        or it["final_state_diff"]["changed"]
    ]

    def _pass_count(rows: dict[str, dict[str, str]]) -> int:
        return sum(1 for r in rows.values() if _parse_bool(r.get("passed")))

    def _avg(values: list[float]) -> float:
        return round(sum(values) / len(values), 2) if values else 0.0

    old_in_all = [_parse_int(r.get("total_input_tokens")) for r in old_rows.values()]
    new_in_all = [_parse_int(r.get("total_input_tokens")) for r in new_rows.values()]
    old_out_all = [_parse_int(r.get("total_output_tokens")) for r in old_rows.values()]
    new_out_all = [_parse_int(r.get("total_output_tokens")) for r in new_rows.values()]

    common_old_in = [it["old_input_tokens"] for it in common_items]
    common_new_in = [it["new_input_tokens"] for it in common_items]
    common_old_out = [it["old_output_tokens"] for it in common_items]
    common_new_out = [it["new_output_tokens"] for it in common_items]

    return {
        "total_old": len(old_rows),
        "total_new": len(new_rows),
        "common": len(common_items),
        "added": added,
        "removed": removed,
        "old_pass_count_all": _pass_count(old_rows),
        "new_pass_count_all": _pass_count(new_rows),
        "common_old_pass_count": sum(1 for it in common_items if it["old_passed"]),
        "common_new_pass_count": sum(1 for it in common_items if it["new_passed"]),
        "old_avg_input_tokens_all": _avg(old_in_all),
        "new_avg_input_tokens_all": _avg(new_in_all),
        "common_old_avg_input_tokens": _avg(common_old_in),
        "common_new_avg_input_tokens": _avg(common_new_in),
        "old_avg_output_tokens_all": _avg(old_out_all),
        "new_avg_output_tokens_all": _avg(new_out_all),
        "common_old_avg_output_tokens": _avg(common_old_out),
        "common_new_avg_output_tokens": _avg(common_new_out),
        "regressions": regressions,
        "improvements": improvements,
        "same_pass_changed_skills": same_pass_changed_skills,
        "same_pass_changed_tools": same_pass_changed_tools,
        "state_diff_cases": state_diff_cases,
        "common_items": common_items,
    }


def _fmt_per_turn_set_diff(diffs: list[dict[str, Any]]) -> str:
    segs = []
    for d in diffs:
        if not d["added"] and not d["removed"]:
            continue
        parts = []
        if d["added"]:
            parts.append(f"+{d['added']}")
        if d["removed"]:
            parts.append(f"-{d['removed']}")
        segs.append(f"t{d['turn_index']}:" + ",".join(parts))
    return " ".join(segs) if segs else "(no change)"


def print_summary(s: dict[str, Any]) -> None:
    print("=== 멀티턴 평가 비교 요약 ===")
    print(f"OLD 전체: {s['total_old']}  NEW 전체: {s['total_new']}  공통: {s['common']}")
    print(f"추가: {len(s['added'])}  제거: {len(s['removed'])}")
    print(f"PASS(전체): {s['old_pass_count_all']} -> {s['new_pass_count_all']}")
    print(
        f"PASS(공통): {s['common_old_pass_count']} -> {s['common_new_pass_count']}"
    )
    print(f"REGRESSION: {len(s['regressions'])}  IMPROVEMENT: {len(s['improvements'])}")
    print(
        f"평균 입력 토큰(전체): {s['old_avg_input_tokens_all']} -> "
        f"{s['new_avg_input_tokens_all']}"
    )
    print(
        f"평균 입력 토큰(공통): {s['common_old_avg_input_tokens']} -> "
        f"{s['common_new_avg_input_tokens']}"
    )
    print(
        f"평균 출력 토큰(전체): {s['old_avg_output_tokens_all']} -> "
        f"{s['new_avg_output_tokens_all']}"
    )
    print(
        f"평균 출력 토큰(공통): {s['common_old_avg_output_tokens']} -> "
        f"{s['common_new_avg_output_tokens']}"
    )
    print()


def print_pass_flips(s: dict[str, Any]) -> None:
    print("=== PASS 변화 케이스 ===")
    if not s["regressions"] and not s["improvements"]:
        print("없음")
        print()
        return

    print("index,kind,old_passed,new_passed,in_delta,out_delta,model_call_delta,elapsed_delta")
    for it in s["regressions"]:
        print(
            f'{it["index"]},regression,{it["old_passed"]},{it["new_passed"]},'
            f'{it["input_token_delta"]},{it["output_token_delta"]},'
            f'{it["model_request_delta"]},{it["elapsed_delta"]}'
        )
    for it in s["improvements"]:
        print(
            f'{it["index"]},improvement,{it["old_passed"]},{it["new_passed"]},'
            f'{it["input_token_delta"]},{it["output_token_delta"]},'
            f'{it["model_request_delta"]},{it["elapsed_delta"]}'
        )
    print()


def print_token_changes(s: dict[str, Any], top_n: int = 10) -> None:
    print("=== 입력 토큰 변화 TOP ===")
    items = sorted(s["common_items"], key=lambda x: abs(x["input_token_delta"]), reverse=True)
    items = [it for it in items if it["input_token_delta"] != 0][:top_n]
    if not items:
        print("없음")
        print()
    else:
        print("index,old_in,new_in,in_delta,old_out,new_out,out_delta")
        for it in items:
            print(
                f'{it["index"]},{it["old_input_tokens"]},{it["new_input_tokens"]},'
                f'{it["input_token_delta"]},{it["old_output_tokens"]},'
                f'{it["new_output_tokens"]},{it["output_token_delta"]}'
            )
        print()

    print("=== 출력 토큰 변화 TOP ===")
    items = sorted(s["common_items"], key=lambda x: abs(x["output_token_delta"]), reverse=True)
    items = [it for it in items if it["output_token_delta"] != 0][:top_n]
    if not items:
        print("없음")
        print()
    else:
        print("index,old_out,new_out,out_delta,old_in,new_in,in_delta")
        for it in items:
            print(
                f'{it["index"]},{it["old_output_tokens"]},{it["new_output_tokens"]},'
                f'{it["output_token_delta"]},{it["old_input_tokens"]},'
                f'{it["new_input_tokens"]},{it["input_token_delta"]}'
            )
        print()


def print_skill_tool_diff(s: dict[str, Any]) -> None:
    print("=== Skill 사용 변화 케이스 ===")
    cases = s["same_pass_changed_skills"] + s["regressions"] + s["improvements"]
    seen: set[str] = set()
    uniq = []
    for it in cases:
        if it["index"] in seen:
            continue
        seen.add(it["index"])
        if any(d["added"] or d["removed"] for d in it["skills_per_turn_diff"]):
            uniq.append(it)
    if not uniq:
        print("없음")
    else:
        for it in uniq:
            print(
                f'- {it["index"]}: {_fmt_per_turn_set_diff(it["skills_per_turn_diff"])}'
            )
    print()

    print("=== Tool 사용 변화 케이스 ===")
    seen.clear()
    uniq = []
    for it in s["same_pass_changed_tools"] + s["regressions"] + s["improvements"]:
        if it["index"] in seen:
            continue
        seen.add(it["index"])
        if any(d["added"] or d["removed"] for d in it["tools_per_turn_diff"]):
            uniq.append(it)
    if not uniq:
        print("없음")
    else:
        for it in uniq:
            print(
                f'- {it["index"]}: {_fmt_per_turn_set_diff(it["tools_per_turn_diff"])}'
            )
    print()


def print_state_diff(s: dict[str, Any]) -> None:
    print("=== 최종 State 차이 케이스 ===")
    if not s["state_diff_cases"]:
        print("없음")
        print()
        return
    for it in s["state_diff_cases"]:
        diff = it["final_state_diff"]
        print(
            f'- {it["index"]}: added={diff["added"]} removed={diff["removed"]} '
            f'changed={diff["changed"]}'
        )
    print()


def print_added_removed(s: dict[str, Any]) -> None:
    print("=== 추가된 케이스 ===")
    if not s["added"]:
        print("없음")
    else:
        for r in s["added"]:
            print(f'- {r.get("index", "")}')
    print()

    print("=== 제거된 케이스 ===")
    if not s["removed"]:
        print("없음")
    else:
        for r in s["removed"]:
            print(f'- {r.get("index", "")}')
    print()


def main(old_path: str, new_path: str) -> None:
    old_rows = load_csv(Path(old_path))
    new_rows = load_csv(Path(new_path))
    summary = summarize(old_rows, new_rows)
    print_summary(summary)
    print_pass_flips(summary)
    print_token_changes(summary)
    print_skill_tool_diff(summary)
    print_state_diff(summary)
    print_added_removed(summary)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(
            "usage: python -m scripts.multiturn.compare OLD.csv NEW.csv"
        )
    main(sys.argv[1], sys.argv[2])
