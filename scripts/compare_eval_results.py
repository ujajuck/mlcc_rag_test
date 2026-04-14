import csv
import json
import sys
from pathlib import Path
from typing import Any


def load_csv(path: Path) -> dict[str, dict[str, str]]:
    """Load result CSV into a dict keyed by case_id."""
    with path.open("r", encoding="utf-8-sig", newline="") as fp:
        reader = csv.DictReader(fp)
        return {row["case_id"]: row for row in reader if row.get("case_id")}


def parse_bool(value: Any) -> bool:
    """Parse CSV boolean-like string into bool."""
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def parse_float(value: Any) -> float:
    """Parse numeric string into float with safe fallback."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def parse_int(value: Any) -> int:
    """Parse numeric string into int with safe fallback."""
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def compact_fail_reasons(value: str, max_items: int = 3) -> str:
    """Convert JSON fail reasons into compact printable text."""
    try:
        items = json.loads(value)
        if isinstance(items, list):
            preview = items[:max_items]
            text = " | ".join(str(x) for x in preview)
            if len(items) > max_items:
                text += f" ... (+{len(items) - max_items})"
            return text
    except Exception:
        pass
    return str(value)


def make_case_item(case_id: str, old_row: dict[str, str], new_row: dict[str, str]) -> dict[str, Any]:
    """Build a normalized comparison item for one shared case."""
    old_score = parse_float(old_row.get("score", 0))
    new_score = parse_float(new_row.get("score", 0))
    old_passed = parse_bool(old_row.get("passed", ""))
    new_passed = parse_bool(new_row.get("passed", ""))

    old_in_tokens = parse_int(old_row.get("estimated_input_tokens", 0))
    new_in_tokens = parse_int(new_row.get("estimated_input_tokens", 0))
    old_out_tokens = parse_int(old_row.get("estimated_output_tokens", 0))
    new_out_tokens = parse_int(new_row.get("estimated_output_tokens", 0))

    delta = round(new_score - old_score, 2)
    in_delta = new_in_tokens - old_in_tokens
    out_delta = new_out_tokens - old_out_tokens

    return {
        "case_id": case_id,
        "category_old": old_row.get("category", ""),
        "category_new": new_row.get("category", ""),
        "old_score": old_score,
        "new_score": new_score,
        "delta": delta,
        "old_passed": old_passed,
        "new_passed": new_passed,
        "old_input_tokens": old_in_tokens,
        "new_input_tokens": new_in_tokens,
        "input_token_delta": in_delta,
        "old_output_tokens": old_out_tokens,
        "new_output_tokens": new_out_tokens,
        "output_token_delta": out_delta,
        "old_model_request_count": parse_int(old_row.get("model_request_count", 0)),
        "new_model_request_count": parse_int(new_row.get("model_request_count", 0)),
        "model_request_delta": parse_int(new_row.get("model_request_count", 0))
        - parse_int(old_row.get("model_request_count", 0)),
        "old_fail_reasons": old_row.get("fail_reasons", ""),
        "new_fail_reasons": new_row.get("fail_reasons", ""),
        "old_prompt_trace_path": old_row.get("prompt_trace_path", ""),
        "new_prompt_trace_path": new_row.get("prompt_trace_path", ""),
    }


def summarize_changes(
    old_rows: dict[str, dict[str, str]],
    new_rows: dict[str, dict[str, str]],
) -> dict[str, Any]:
    """Summarize result changes between two evaluation CSV files."""
    all_case_ids = sorted(set(old_rows.keys()) | set(new_rows.keys()))

    regressions: list[dict[str, Any]] = []
    improvements: list[dict[str, Any]] = []
    unchanged: list[dict[str, Any]] = []
    added: list[dict[str, str]] = []
    removed: list[dict[str, str]] = []
    token_changed: list[dict[str, Any]] = []

    old_scores_all: list[float] = []
    new_scores_all: list[float] = []
    old_input_tokens_all: list[int] = []
    new_input_tokens_all: list[int] = []
    old_output_tokens_all: list[int] = []
    new_output_tokens_all: list[int] = []

    common_old_scores: list[float] = []
    common_new_scores: list[float] = []
    common_old_input_tokens: list[int] = []
    common_new_input_tokens: list[int] = []
    common_old_output_tokens: list[int] = []
    common_new_output_tokens: list[int] = []

    old_pass_count_all = 0
    new_pass_count_all = 0
    common_old_pass_count = 0
    common_new_pass_count = 0

    for row in old_rows.values():
        old_scores_all.append(parse_float(row.get("score", 0)))
        old_input_tokens_all.append(parse_int(row.get("estimated_input_tokens", 0)))
        old_output_tokens_all.append(parse_int(row.get("estimated_output_tokens", 0)))
        if parse_bool(row.get("passed", "")):
            old_pass_count_all += 1

    for row in new_rows.values():
        new_scores_all.append(parse_float(row.get("score", 0)))
        new_input_tokens_all.append(parse_int(row.get("estimated_input_tokens", 0)))
        new_output_tokens_all.append(parse_int(row.get("estimated_output_tokens", 0)))
        if parse_bool(row.get("passed", "")):
            new_pass_count_all += 1

    for case_id in all_case_ids:
        old_row = old_rows.get(case_id)
        new_row = new_rows.get(case_id)

        if old_row is None and new_row is not None:
            added.append(new_row)
            continue

        if old_row is not None and new_row is None:
            removed.append(old_row)
            continue

        item = make_case_item(case_id, old_row, new_row)

        common_old_scores.append(item["old_score"])
        common_new_scores.append(item["new_score"])
        common_old_input_tokens.append(item["old_input_tokens"])
        common_new_input_tokens.append(item["new_input_tokens"])
        common_old_output_tokens.append(item["old_output_tokens"])
        common_new_output_tokens.append(item["new_output_tokens"])

        if item["old_passed"]:
            common_old_pass_count += 1
        if item["new_passed"]:
            common_new_pass_count += 1

        if item["input_token_delta"] != 0 or item["output_token_delta"] != 0:
            token_changed.append(item)

        if item["old_passed"] and not item["new_passed"]:
            regressions.append(item)
        elif (not item["old_passed"]) and item["new_passed"]:
            improvements.append(item)
        elif item["new_score"] < item["old_score"]:
            regressions.append(item)
        elif item["new_score"] > item["old_score"]:
            improvements.append(item)
        else:
            unchanged.append(item)

    summary = {
        "total_old": len(old_rows),
        "total_new": len(new_rows),
        "total_compared": len(all_case_ids) - len(added) - len(removed),
        "added_count": len(added),
        "removed_count": len(removed),
        "regression_count": len(regressions),
        "improvement_count": len(improvements),
        "unchanged_count": len(unchanged),
        "old_pass_count_all": old_pass_count_all,
        "new_pass_count_all": new_pass_count_all,
        "common_old_pass_count": common_old_pass_count,
        "common_new_pass_count": common_new_pass_count,
        "old_avg_score_all": round(sum(old_scores_all) / len(old_scores_all), 2) if old_scores_all else 0.0,
        "new_avg_score_all": round(sum(new_scores_all) / len(new_scores_all), 2) if new_scores_all else 0.0,
        "common_old_avg_score": round(sum(common_old_scores) / len(common_old_scores), 2)
        if common_old_scores
        else 0.0,
        "common_new_avg_score": round(sum(common_new_scores) / len(common_new_scores), 2)
        if common_new_scores
        else 0.0,
        "old_avg_input_tokens_all": round(sum(old_input_tokens_all) / len(old_input_tokens_all), 2)
        if old_input_tokens_all
        else 0.0,
        "new_avg_input_tokens_all": round(sum(new_input_tokens_all) / len(new_input_tokens_all), 2)
        if new_input_tokens_all
        else 0.0,
        "common_old_avg_input_tokens": round(sum(common_old_input_tokens) / len(common_old_input_tokens), 2)
        if common_old_input_tokens
        else 0.0,
        "common_new_avg_input_tokens": round(sum(common_new_input_tokens) / len(common_new_input_tokens), 2)
        if common_new_input_tokens
        else 0.0,
        "old_avg_output_tokens_all": round(sum(old_output_tokens_all) / len(old_output_tokens_all), 2)
        if old_output_tokens_all
        else 0.0,
        "new_avg_output_tokens_all": round(sum(new_output_tokens_all) / len(new_output_tokens_all), 2)
        if new_output_tokens_all
        else 0.0,
        "common_old_avg_output_tokens": round(sum(common_old_output_tokens) / len(common_old_output_tokens), 2)
        if common_old_output_tokens
        else 0.0,
        "common_new_avg_output_tokens": round(sum(common_new_output_tokens) / len(common_new_output_tokens), 2)
        if common_new_output_tokens
        else 0.0,
        "regressions": regressions,
        "improvements": improvements,
        "unchanged": unchanged,
        "added": added,
        "removed": removed,
        "token_changed": token_changed,
    }
    return summary


def print_summary(summary: dict[str, Any]) -> None:
    """Print human-readable summary."""
    print("=== 비교 요약 ===")
    print(f"OLD 전체 케이스 수: {summary['total_old']}")
    print(f"NEW 전체 케이스 수: {summary['total_new']}")
    print(f"공통 비교 케이스 수: {summary['total_compared']}")
    print(f"개선된 케이스 수: {summary['improvement_count']}")
    print(f"동일한 케이스 수: {summary['unchanged_count']}")
    print(f"악화된 케이스 수: {summary['regression_count']}")
    print(f"추가된 케이스 수: {summary['added_count']}")
    print(f"제거된 케이스 수: {summary['removed_count']}")
    print()
    print(
        f"PASS 변화(전체 기준): "
        f"{summary['old_pass_count_all']} -> {summary['new_pass_count_all']}"
    )
    print(
        f"PASS 변화(공통 기준): "
        f"{summary['common_old_pass_count']} -> {summary['common_new_pass_count']}"
    )
    print(
        f"평균 점수 변화(전체 기준): "
        f"{summary['old_avg_score_all']} -> {summary['new_avg_score_all']}"
    )
    print(
        f"평균 점수 변화(공통 기준): "
        f"{summary['common_old_avg_score']} -> {summary['common_new_avg_score']}"
    )
    print(
        f"평균 입력 토큰 변화(전체 기준): "
        f"{summary['old_avg_input_tokens_all']} -> {summary['new_avg_input_tokens_all']}"
    )
    print(
        f"평균 입력 토큰 변화(공통 기준): "
        f"{summary['common_old_avg_input_tokens']} -> {summary['common_new_avg_input_tokens']}"
    )
    print(
        f"평균 출력 토큰 변화(전체 기준): "
        f"{summary['old_avg_output_tokens_all']} -> {summary['new_avg_output_tokens_all']}"
    )
    print(
        f"평균 출력 토큰 변화(공통 기준): "
        f"{summary['common_old_avg_output_tokens']} -> {summary['common_new_avg_output_tokens']}"
    )
    print()


def print_regressions(summary: dict[str, Any]) -> None:
    """Print regressions only."""
    print("=== 악화된 케이스 ===")
    if not summary["regressions"]:
        print("없음")
        print()
        return

    print(
        "case_id,old_score,new_score,delta,old_passed,new_passed,"
        "old_model_calls,new_model_calls,model_call_delta,"
        "old_input_tokens,new_input_tokens,input_token_delta,"
        "old_output_tokens,new_output_tokens,output_token_delta,new_fail_reasons"
    )
    for item in summary["regressions"]:
        fail_reasons = compact_fail_reasons(item["new_fail_reasons"]).replace('"', "'")
        print(
            f'{item["case_id"]},{item["old_score"]},{item["new_score"]},'
            f'{item["delta"]},{item["old_passed"]},{item["new_passed"]},'
            f'{item["old_model_request_count"]},{item["new_model_request_count"]},{item["model_request_delta"]},'
            f'{item["old_input_tokens"]},{item["new_input_tokens"]},{item["input_token_delta"]},'
            f'{item["old_output_tokens"]},{item["new_output_tokens"]},{item["output_token_delta"]},'
            f'"{fail_reasons}"'
        )
    print()


def print_improvements(summary: dict[str, Any]) -> None:
    """Print improvements only."""
    print("=== 개선된 케이스 ===")
    if not summary["improvements"]:
        print("없음")
        print()
        return

    print(
        "case_id,old_score,new_score,delta,old_passed,new_passed,"
        "old_model_calls,new_model_calls,model_call_delta,"
        "old_input_tokens,new_input_tokens,input_token_delta,"
        "old_output_tokens,new_output_tokens,output_token_delta"
    )
    for item in summary["improvements"]:
        print(
            f'{item["case_id"]},{item["old_score"]},{item["new_score"]},'
            f'{item["delta"]},{item["old_passed"]},{item["new_passed"]},'
            f'{item["old_model_request_count"]},{item["new_model_request_count"]},{item["model_request_delta"]},'
            f'{item["old_input_tokens"]},{item["new_input_tokens"]},{item["input_token_delta"]},'
            f'{item["old_output_tokens"]},{item["new_output_tokens"]},{item["output_token_delta"]}'
        )
    print()


def print_input_token_changes(summary: dict[str, Any], top_n: int = 10) -> None:
    """Print largest input token changes."""
    print("=== 입력 토큰 변화가 큰 케이스 TOP ===")
    token_changed = sorted(
        summary["token_changed"],
        key=lambda x: abs(x["input_token_delta"]),
        reverse=True,
    )
    if not token_changed:
        print("없음")
        print()
        return

    print(
        "case_id,old_score,new_score,delta,"
        "old_input_tokens,new_input_tokens,input_token_delta,"
        "old_output_tokens,new_output_tokens,output_token_delta"
    )
    for item in token_changed[:top_n]:
        print(
            f'{item["case_id"]},{item["old_score"]},{item["new_score"]},{item["delta"]},'
            f'{item["old_input_tokens"]},{item["new_input_tokens"]},{item["input_token_delta"]},'
            f'{item["old_output_tokens"]},{item["new_output_tokens"]},{item["output_token_delta"]}'
        )
    print()


def print_output_token_changes(summary: dict[str, Any], top_n: int = 10) -> None:
    """Print largest output token changes."""
    print("=== 출력 토큰 변화가 큰 케이스 TOP ===")
    token_changed = sorted(
        summary["token_changed"],
        key=lambda x: abs(x["output_token_delta"]),
        reverse=True,
    )
    if not token_changed:
        print("없음")
        print()
        return

    print(
        "case_id,old_score,new_score,delta,"
        "old_input_tokens,new_input_tokens,input_token_delta,"
        "old_output_tokens,new_output_tokens,output_token_delta"
    )
    for item in token_changed[:top_n]:
        print(
            f'{item["case_id"]},{item["old_score"]},{item["new_score"]},{item["delta"]},'
            f'{item["old_input_tokens"]},{item["new_input_tokens"]},{item["input_token_delta"]},'
            f'{item["old_output_tokens"]},{item["new_output_tokens"]},{item["output_token_delta"]}'
        )
    print()


def print_efficiency_wins(summary: dict[str, Any]) -> None:
    """Print unchanged-score cases with reduced input tokens."""
    print("=== 점수 유지 + 입력 토큰 감소 케이스 ===")
    wins = [item for item in summary["unchanged"] if item["input_token_delta"] < 0]
    wins = sorted(wins, key=lambda x: x["input_token_delta"])

    if not wins:
        print("없음")
        print()
        return

    print(
        "case_id,score,input_tokens_old,input_tokens_new,input_token_delta,"
        "output_tokens_old,output_tokens_new,output_token_delta,"
        "model_calls_old,model_calls_new,model_call_delta"
    )
    for item in wins:
        print(
            f'{item["case_id"]},{item["new_score"]},'
            f'{item["old_input_tokens"]},{item["new_input_tokens"]},{item["input_token_delta"]},'
            f'{item["old_output_tokens"]},{item["new_output_tokens"]},{item["output_token_delta"]},'
            f'{item["old_model_request_count"]},{item["new_model_request_count"]},{item["model_request_delta"]}'
        )
    print()


def print_added_removed(summary: dict[str, Any]) -> None:
    """Print added and removed case ids."""
    print("=== 추가된 케이스 ===")
    if not summary["added"]:
        print("없음")
    else:
        for row in summary["added"]:
            print(f'- {row.get("case_id", "")} ({row.get("category", "")})')
    print()

    print("=== 제거된 케이스 ===")
    if not summary["removed"]:
        print("없음")
    else:
        for row in summary["removed"]:
            print(f'- {row.get("case_id", "")} ({row.get("category", "")})')
    print()


def main(old_path: str, new_path: str) -> None:
    """Compare two evaluation CSV files and print summary + diffs."""
    old_rows = load_csv(Path(old_path))
    new_rows = load_csv(Path(new_path))

    summary = summarize_changes(old_rows, new_rows)
    print_summary(summary)
    print_regressions(summary)
    print_improvements(summary)
    print_input_token_changes(summary)
    print_output_token_changes(summary)
    print_efficiency_wins(summary)
    print_added_removed(summary)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(
            "usage: python scripts/compare_eval_results.py OLD.csv NEW.csv"
        )
    main(sys.argv[1], sys.argv[2])