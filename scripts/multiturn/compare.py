"""두 평가 결과 CSV 를 비교한다.

입력 CSV 는 scripts.multiturn.io.write_summary_csv 가 만든 per-subindex 포맷.
subindex row 들을 index 단위로 집계한 뒤 아래 항목을 비교한다:
    - pass 수 (서브인덱스별/케이스별, 전체/공통)
    - 입출력 토큰 합계/평균
    - 케이스별 skill/tool 사용 차이 (턴별 added/removed)
    - 최종 state key/value 차이 (케이스 마지막 턴 state 기준)
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


class CaseAgg:
    """한 index 에 묶이는 subindex row 들의 집계."""

    def __init__(self, index: str) -> None:
        self.index = index
        self.rows: list[dict[str, str]] = []

    def add(self, row: dict[str, str]) -> None:
        self.rows.append(row)

    def sorted_rows(self) -> list[dict[str, str]]:
        return sorted(self.rows, key=lambda r: _parse_int(r.get("subindex")))

    @property
    def turn_count(self) -> int:
        return len(self.rows)

    @property
    def passed(self) -> bool:
        # 모든 subindex row 가 passed=True 여야 케이스 pass
        return all(_parse_bool(r.get("passed")) for r in self.rows) and bool(self.rows)

    @property
    def subindex_pass(self) -> list[bool]:
        return [_parse_bool(r.get("passed")) for r in self.sorted_rows()]

    @property
    def total_input_tokens(self) -> int:
        return sum(_parse_int(r.get("input_tokens")) for r in self.rows)

    @property
    def total_output_tokens(self) -> int:
        return sum(_parse_int(r.get("output_tokens")) for r in self.rows)

    @property
    def total_model_requests(self) -> int:
        return sum(_parse_int(r.get("model_request_count")) for r in self.rows)

    @property
    def total_time(self) -> float:
        return round(sum(_parse_float(r.get("time_taken")) for r in self.rows), 4)

    @property
    def skills_per_turn(self) -> list[list[str]]:
        return [
            _parse_json(r.get("skills_used"), []) for r in self.sorted_rows()
        ]

    @property
    def tools_per_turn(self) -> list[list[str]]:
        return [
            _parse_json(r.get("tools_used"), []) for r in self.sorted_rows()
        ]

    @property
    def final_state_keys(self) -> list[str]:
        rows = self.sorted_rows()
        if not rows:
            return []
        val = _parse_json(rows[-1].get("state_keys"), [])
        return sorted(val) if isinstance(val, list) else sorted(val.keys()) if isinstance(val, dict) else []

    @property
    def first_error(self) -> str:
        for r in self.sorted_rows():
            err = r.get("error_message") or ""
            if err:
                return err
        return ""


def load_csv(path: Path) -> dict[str, CaseAgg]:
    """index 기준으로 subindex row 들을 묶어 CaseAgg dict 반환."""
    cases: dict[str, CaseAgg] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            idx = (row.get("index") or "").strip()
            if not idx:
                continue
            if idx not in cases:
                cases[idx] = CaseAgg(idx)
            cases[idx].add(row)
    return cases


def _per_turn_set_diff(
    old_list: list[list[str]], new_list: list[list[str]]
) -> list[dict[str, Any]]:
    length = max(len(old_list), len(new_list))
    out: list[dict[str, Any]] = []
    for i in range(length):
        old_set = set(old_list[i]) if i < len(old_list) else set()
        new_set = set(new_list[i]) if i < len(new_list) else set()
        if old_set == new_set:
            continue
        out.append(
            {
                "subindex": i,
                "added": sorted(new_set - old_set),
                "removed": sorted(old_set - new_set),
            }
        )
    return out


def _state_keys_diff(
    old_keys: list[str], new_keys: list[str]
) -> dict[str, Any]:
    old_set = set(old_keys)
    new_set = set(new_keys)
    return {
        "added": sorted(new_set - old_set),
        "removed": sorted(old_set - new_set),
    }


def _make_case_item(old: CaseAgg, new: CaseAgg) -> dict[str, Any]:
    return {
        "index": old.index,
        "old_turn_count": old.turn_count,
        "new_turn_count": new.turn_count,
        "old_passed": old.passed,
        "new_passed": new.passed,
        "old_subindex_pass": old.subindex_pass,
        "new_subindex_pass": new.subindex_pass,
        "old_input_tokens": old.total_input_tokens,
        "new_input_tokens": new.total_input_tokens,
        "input_token_delta": new.total_input_tokens - old.total_input_tokens,
        "old_output_tokens": old.total_output_tokens,
        "new_output_tokens": new.total_output_tokens,
        "output_token_delta": new.total_output_tokens - old.total_output_tokens,
        "old_model_requests": old.total_model_requests,
        "new_model_requests": new.total_model_requests,
        "model_request_delta": new.total_model_requests - old.total_model_requests,
        "old_time": old.total_time,
        "new_time": new.total_time,
        "time_delta": round(new.total_time - old.total_time, 4),
        "skills_diff": _per_turn_set_diff(old.skills_per_turn, new.skills_per_turn),
        "tools_diff": _per_turn_set_diff(old.tools_per_turn, new.tools_per_turn),
        "final_state_diff": _state_keys_diff(old.final_state_keys, new.final_state_keys),
        "old_error": old.first_error,
        "new_error": new.first_error,
    }


def summarize(
    old_cases: dict[str, CaseAgg],
    new_cases: dict[str, CaseAgg],
) -> dict[str, Any]:
    all_ids = sorted(set(old_cases) | set(new_cases))
    added = [i for i in all_ids if i not in old_cases]
    removed = [i for i in all_ids if i not in new_cases]

    common_items: list[dict[str, Any]] = []
    for idx in all_ids:
        if idx in old_cases and idx in new_cases:
            common_items.append(_make_case_item(old_cases[idx], new_cases[idx]))

    regressions = [
        it for it in common_items if it["old_passed"] and not it["new_passed"]
    ]
    improvements = [
        it for it in common_items if not it["old_passed"] and it["new_passed"]
    ]
    skill_changed = [it for it in common_items if it["skills_diff"]]
    tool_changed = [it for it in common_items if it["tools_diff"]]
    state_changed = [
        it
        for it in common_items
        if it["final_state_diff"]["added"]
        or it["final_state_diff"]["removed"]
    ]

    def _case_pass(cases: dict[str, CaseAgg]) -> int:
        return sum(1 for c in cases.values() if c.passed)

    def _sub_pass(cases: dict[str, CaseAgg]) -> tuple[int, int]:
        total = sum(c.turn_count for c in cases.values())
        passed = sum(sum(1 for p in c.subindex_pass if p) for c in cases.values())
        return passed, total

    def _avg(values: list[float]) -> float:
        return round(sum(values) / len(values), 2) if values else 0.0

    old_in_all = [c.total_input_tokens for c in old_cases.values()]
    new_in_all = [c.total_input_tokens for c in new_cases.values()]
    old_out_all = [c.total_output_tokens for c in old_cases.values()]
    new_out_all = [c.total_output_tokens for c in new_cases.values()]

    old_sub_pass, old_sub_total = _sub_pass(old_cases)
    new_sub_pass, new_sub_total = _sub_pass(new_cases)

    return {
        "total_old_cases": len(old_cases),
        "total_new_cases": len(new_cases),
        "common_cases": len(common_items),
        "added": added,
        "removed": removed,
        "old_case_pass": _case_pass(old_cases),
        "new_case_pass": _case_pass(new_cases),
        "common_old_case_pass": sum(1 for it in common_items if it["old_passed"]),
        "common_new_case_pass": sum(1 for it in common_items if it["new_passed"]),
        "old_sub_pass": old_sub_pass,
        "old_sub_total": old_sub_total,
        "new_sub_pass": new_sub_pass,
        "new_sub_total": new_sub_total,
        "old_avg_input_tokens": _avg(old_in_all),
        "new_avg_input_tokens": _avg(new_in_all),
        "old_avg_output_tokens": _avg(old_out_all),
        "new_avg_output_tokens": _avg(new_out_all),
        "old_total_input_tokens": sum(old_in_all),
        "new_total_input_tokens": sum(new_in_all),
        "old_total_output_tokens": sum(old_out_all),
        "new_total_output_tokens": sum(new_out_all),
        "regressions": regressions,
        "improvements": improvements,
        "skill_changed": skill_changed,
        "tool_changed": tool_changed,
        "state_changed": state_changed,
        "common_items": common_items,
    }


def _fmt_diff(diffs: list[dict[str, Any]]) -> str:
    if not diffs:
        return "(no change)"
    segs = []
    for d in diffs:
        parts = []
        if d["added"]:
            parts.append(f"+{d['added']}")
        if d["removed"]:
            parts.append(f"-{d['removed']}")
        segs.append(f"t{d['subindex']}:" + ",".join(parts))
    return " ".join(segs)


def print_summary(s: dict[str, Any]) -> None:
    print("=== 평가 결과 비교 요약 ===")
    print(
        f"OLD cases: {s['total_old_cases']}  NEW cases: {s['total_new_cases']}  "
        f"공통: {s['common_cases']}"
    )
    print(f"추가 케이스: {len(s['added'])}  제거 케이스: {len(s['removed'])}")
    print(f"케이스 PASS(전체): {s['old_case_pass']} -> {s['new_case_pass']}")
    print(
        f"케이스 PASS(공통): {s['common_old_case_pass']} -> "
        f"{s['common_new_case_pass']}"
    )
    print(
        f"서브인덱스 PASS: {s['old_sub_pass']}/{s['old_sub_total']} -> "
        f"{s['new_sub_pass']}/{s['new_sub_total']}"
    )
    print(
        f"REGRESSION: {len(s['regressions'])}  IMPROVEMENT: {len(s['improvements'])}"
    )
    print(
        f"입력 토큰 합: {s['old_total_input_tokens']} -> "
        f"{s['new_total_input_tokens']} "
        f"(평균 {s['old_avg_input_tokens']} -> {s['new_avg_input_tokens']})"
    )
    print(
        f"출력 토큰 합: {s['old_total_output_tokens']} -> "
        f"{s['new_total_output_tokens']} "
        f"(평균 {s['old_avg_output_tokens']} -> {s['new_avg_output_tokens']})"
    )
    print()


def print_pass_flips(s: dict[str, Any]) -> None:
    print("=== PASS 변화 케이스 ===")
    if not s["regressions"] and not s["improvements"]:
        print("없음")
        print()
        return

    print(
        "index,kind,old_passed,new_passed,in_delta,out_delta,"
        "model_call_delta,time_delta"
    )
    for it in s["regressions"]:
        print(
            f'{it["index"]},regression,{it["old_passed"]},{it["new_passed"]},'
            f'{it["input_token_delta"]},{it["output_token_delta"]},'
            f'{it["model_request_delta"]},{it["time_delta"]}'
        )
    for it in s["improvements"]:
        print(
            f'{it["index"]},improvement,{it["old_passed"]},{it["new_passed"]},'
            f'{it["input_token_delta"]},{it["output_token_delta"]},'
            f'{it["model_request_delta"]},{it["time_delta"]}'
        )
    print()


def print_token_changes(s: dict[str, Any], top_n: int = 10) -> None:
    print("=== 입력 토큰 변화 TOP ===")
    items = sorted(
        s["common_items"], key=lambda x: abs(x["input_token_delta"]), reverse=True
    )
    items = [it for it in items if it["input_token_delta"] != 0][:top_n]
    if not items:
        print("없음")
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
    items = sorted(
        s["common_items"], key=lambda x: abs(x["output_token_delta"]), reverse=True
    )
    items = [it for it in items if it["output_token_delta"] != 0][:top_n]
    if not items:
        print("없음")
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
    if not s["skill_changed"]:
        print("없음")
    else:
        for it in s["skill_changed"]:
            print(f'- {it["index"]}: {_fmt_diff(it["skills_diff"])}')
    print()

    print("=== Tool 사용 변화 케이스 ===")
    if not s["tool_changed"]:
        print("없음")
    else:
        for it in s["tool_changed"]:
            print(f'- {it["index"]}: {_fmt_diff(it["tools_diff"])}')
    print()


def print_state_diff(s: dict[str, Any]) -> None:
    print("=== 최종 State 차이 케이스 ===")
    if not s["state_changed"]:
        print("없음")
        print()
        return
    for it in s["state_changed"]:
        diff = it["final_state_diff"]
        print(
            f'- {it["index"]}: added={diff["added"]} removed={diff["removed"]}'
        )
    print()


def print_added_removed(s: dict[str, Any]) -> None:
    print("=== 추가된 케이스 ===")
    if not s["added"]:
        print("없음")
    else:
        for idx in s["added"]:
            print(f"- {idx}")
    print()

    print("=== 제거된 케이스 ===")
    if not s["removed"]:
        print("없음")
    else:
        for idx in s["removed"]:
            print(f"- {idx}")
    print()


def main(old_path: str, new_path: str) -> None:
    old_cases = load_csv(Path(old_path))
    new_cases = load_csv(Path(new_path))
    summary = summarize(old_cases, new_cases)
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
