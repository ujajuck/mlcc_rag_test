import asyncio
import csv
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from mlcc_agent.agent import root_agent
from scripts.run_skill_regression import (
    MlccModelTracePlugin,
    MlccSkillTracePlugin,
    ModelTrace,
    ToolTrace,
    _extract_expected_constraints,
    _flatten_dict,
    _safe_json_dumps,
    _safe_json_loads,
)


APP_NAME = "mlcc_multiturn_regression"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEST_CASE_PATH = PROJECT_ROOT / "tests" / "test_cases_mlcc_multiturn.csv"
RESULT_DIR = PROJECT_ROOT / "artifacts" / "eval_multiturn_results"
RESULT_DIR.mkdir(parents=True, exist_ok=True)

PROMPT_TRACE_DIR = PROJECT_ROOT / "artifacts" / "prompt_traces_multiturn"
PROMPT_TRACE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class MlccMultiturnTestCase:
    """Multi-turn regression test case definition.

    Parameters:
        case_id: Unique test case identifier.
        category: Logical bucket for grouping failures.
        turns_json: JSON list of user input strings, one per turn.
        expected_per_turn_json: JSON list of per-turn expectation dicts.
            Each dict may contain any subset of:
                - must_include_keywords: list[str]
                - must_not_claim_keywords: list[str]
                - search_rag_calls_max: int (turn-level delta cap)
                - search_groups: list[str] (allowed groups this turn)
                - state_keys: list[str] (keys expected after this turn)
                - constraints: dict (parsed_constraints subset expected after turn)
                - code_mapping: dict (code_mapping subset expected after turn)
                - search_plan_groups: list[str]
                - candidate_partial: "true"|"false"
        expected_total_search_rag_calls_max: Max search_rag calls across all turns.
        expected_final_state_keys: JSON list of keys required in final state.
        expected_final_must_include_keywords: JSON list required in last-turn response.
        expected_final_must_not_claim_keywords: JSON list forbidden in last-turn response.

    Returns:
        MlccMultiturnTestCase instance.
    """

    case_id: str
    category: str
    turns_json: str
    expected_per_turn_json: str
    expected_total_search_rag_calls_max: int
    expected_final_state_keys: str
    expected_final_must_include_keywords: str
    expected_final_must_not_claim_keywords: str


@dataclass
class TurnTrace:
    """Per-turn trace collected during a multi-turn run.

    Parameters:
        turn_index: Zero-based turn index.
        user_input: User input for this turn.
        final_response: Assistant final response for this turn.
        search_rag_calls: search_rag tool call count (this turn only).
        search_groups: Distinct search_group values used (this turn only).
        tool_traces: Tool trace objects captured during this turn.
        model_traces: Model trace objects captured during this turn.
        model_request_count: Number of model calls this turn.
        estimated_input_tokens: Summed estimated input tokens this turn.
        estimated_output_tokens: Summed estimated output tokens this turn.
        state_snapshot: Session state snapshot after this turn.
        score: Turn-level score.
        passed: Whether this turn passed its own checks.
        fail_reasons: Failure reasons for this turn.

    Returns:
        TurnTrace instance.
    """

    turn_index: int
    user_input: str
    final_response: str
    search_rag_calls: int
    search_groups: list[str]
    tool_traces: list[ToolTrace]
    model_traces: list[ModelTrace]
    model_request_count: int
    estimated_input_tokens: int
    estimated_output_tokens: int
    state_snapshot: dict[str, Any] = field(default_factory=dict)
    score: float = 100.0
    passed: bool = True
    fail_reasons: list[str] = field(default_factory=list)


@dataclass
class MlccMultiturnCaseResult:
    """Aggregated evaluation output for a single multi-turn test case.

    Parameters:
        case_id: Source test case id.
        category: Source category.
        turn_count: Number of turns executed.
        per_turn_responses_json: JSON list of final responses per turn.
        per_turn_search_rag_calls_json: JSON list of per-turn search_rag counts.
        per_turn_search_groups_json: JSON list of per-turn distinct search_groups.
        per_turn_input_tokens_json: JSON list of per-turn estimated input tokens.
        per_turn_output_tokens_json: JSON list of per-turn estimated output tokens.
        per_turn_model_request_count_json: JSON list of per-turn model calls.
        per_turn_scores_json: JSON list of per-turn scores.
        per_turn_passed_json: JSON list of per-turn pass flags.
        per_turn_fail_reasons_json: JSON list of per-turn fail reasons.
        total_search_rag_calls: Total search_rag count across turns.
        total_search_groups: Union of search_groups across turns (JSON list).
        final_state_snapshot_json: Final session state snapshot JSON.
        tool_trace_json: All tool traces across turns (JSON list of dicts).
        model_request_count: Total model call count across turns.
        estimated_input_tokens: Summed estimated input tokens across turns.
        estimated_output_tokens: Summed estimated output tokens across turns.
        prompt_trace_path: File path to detailed model trace JSON per turn.
        score: Aggregate score in [0, 100].
        passed: Whether the case passed overall.
        fail_reasons: Aggregate failure reasons (JSON list).

    Returns:
        MlccMultiturnCaseResult instance.
    """

    case_id: str
    category: str
    turn_count: int
    per_turn_responses_json: str
    per_turn_search_rag_calls_json: str
    per_turn_search_groups_json: str
    per_turn_input_tokens_json: str
    per_turn_output_tokens_json: str
    per_turn_model_request_count_json: str
    per_turn_scores_json: str
    per_turn_passed_json: str
    per_turn_fail_reasons_json: str
    total_search_rag_calls: int
    total_search_groups: str
    final_state_snapshot_json: str
    tool_trace_json: str
    model_request_count: int
    estimated_input_tokens: int
    estimated_output_tokens: int
    prompt_trace_path: str
    score: float
    passed: bool
    fail_reasons: str


def save_multiturn_prompt_trace(case_id: str, turns: list[TurnTrace]) -> str:
    """Save per-turn prompt trace to JSON file and return path.

    Parameters:
        case_id: Source case id.
        turns: Collected per-turn traces.

    Returns:
        File path as string.
    """
    path = PROMPT_TRACE_DIR / f"{case_id}.json"
    payload = [
        {
            "turn_index": t.turn_index,
            "user_input": t.user_input,
            "model_traces": [asdict(m) for m in t.model_traces],
            "tool_traces": [asdict(tt) for tt in t.tool_traces],
        }
        for t in turns
    ]
    with path.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=2)
    return str(path)


def load_multiturn_test_cases(csv_path: Path) -> list[MlccMultiturnTestCase]:
    """Load multi-turn regression test cases from CSV.

    Parameters:
        csv_path: Path to multi-turn test case CSV file.

    Returns:
        List of MlccMultiturnTestCase rows.
    """
    rows: list[MlccMultiturnTestCase] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            rows.append(
                MlccMultiturnTestCase(
                    case_id=row["case_id"],
                    category=row["category"],
                    turns_json=row.get("turns_json", "[]"),
                    expected_per_turn_json=row.get("expected_per_turn_json", "[]"),
                    expected_total_search_rag_calls_max=int(
                        row.get("expected_total_search_rag_calls_max", "0") or 0
                    ),
                    expected_final_state_keys=row.get("expected_final_state_keys", "[]"),
                    expected_final_must_include_keywords=row.get(
                        "expected_final_must_include_keywords", "[]"
                    ),
                    expected_final_must_not_claim_keywords=row.get(
                        "expected_final_must_not_claim_keywords", "[]"
                    ),
                )
            )
    return rows


async def _run_one_turn(
    runner: Runner,
    user_id: str,
    session_id: str,
    user_text: str,
    tool_plugin: MlccSkillTracePlugin,
    model_plugin: MlccModelTracePlugin,
) -> tuple[str, list[ToolTrace], list[ModelTrace]]:
    """Run a single turn and return (final_response, new_tool_traces, new_model_traces).

    The plugins accumulate across turns, so this function snapshots the pre-turn
    lengths and returns only new entries captured during this turn.
    """
    pre_tool = len(tool_plugin.tool_traces)
    pre_model = len(model_plugin.model_traces)

    new_message = types.Content(
        role="user",
        parts=[types.Part.from_text(text=user_text)],
    )

    final_response = ""
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=new_message,
    ):
        is_final_response = getattr(event, "is_final_response", None)
        if callable(is_final_response) and event.is_final_response():
            content = getattr(event, "content", None)
            parts = getattr(content, "parts", None) if content else None

            texts: list[str] = []
            if parts:
                for part in parts:
                    text = getattr(part, "text", None)
                    if text:
                        texts.append(text.strip())
            final_response = "\n".join([t for t in texts if t]).strip()
            break

    new_tool = tool_plugin.tool_traces[pre_tool:]
    new_model = model_plugin.model_traces[pre_model:]
    return final_response, new_tool, new_model


def _evaluate_turn(
    expected: dict[str, Any],
    response: str,
    state_snapshot: dict[str, Any],
    tool_traces: list[ToolTrace],
) -> tuple[float, bool, list[str]]:
    """Score a single turn against optional per-turn expectations.

    Parameters:
        expected: Per-turn expectation dict (possibly empty).
        response: Final assistant response for this turn.
        state_snapshot: Session state snapshot after this turn.
        tool_traces: Tool traces captured during this turn only.

    Returns:
        (score, passed, fail_reasons)
    """
    fail_reasons: list[str] = []
    score = 100.0

    search_rag_traces = [t for t in tool_traces if t.tool_name == "search_rag"]
    actual_search_groups = sorted(
        {
            str(t.tool_args.get("search_group"))
            for t in search_rag_traces
            if t.tool_args.get("search_group") is not None
        }
    )

    # turn search_rag cap
    search_rag_calls_max = expected.get("search_rag_calls_max")
    if isinstance(search_rag_calls_max, int):
        if len(search_rag_traces) > search_rag_calls_max:
            fail_reasons.append(
                f"turn search_rag {len(search_rag_traces)} > max {search_rag_calls_max}"
            )
            score -= 15

    # allowed search_groups
    allowed_groups = expected.get("search_groups")
    if isinstance(allowed_groups, list) and allowed_groups:
        unexpected = [g for g in actual_search_groups if g not in allowed_groups]
        if unexpected:
            fail_reasons.append(f"unexpected turn search_group: {unexpected}")
            score -= 10

    # state keys present after turn
    state_keys = expected.get("state_keys")
    if isinstance(state_keys, list):
        for key in state_keys:
            if key not in state_snapshot:
                fail_reasons.append(f"missing state key after turn: {key}")
                score -= 8

    # parsed_constraints
    expected_constraints_raw = expected.get("constraints")
    if isinstance(expected_constraints_raw, dict) and expected_constraints_raw:
        expected_constraints = _extract_expected_constraints(expected_constraints_raw)
        actual_constraint_merged: dict[str, Any] = {}
        parsed_constraints = state_snapshot.get("parsed_constraints", {})
        if isinstance(parsed_constraints, dict):
            for bucket in ["hard", "soft", "validation_only"]:
                bucket_data = parsed_constraints.get(bucket, {})
                if isinstance(bucket_data, dict):
                    actual_constraint_merged.update(bucket_data)
        for key, expected_value in expected_constraints.items():
            if key not in actual_constraint_merged:
                fail_reasons.append(f"missing parsed constraint: {key}")
                score -= 6
            elif actual_constraint_merged[key] != expected_value:
                fail_reasons.append(
                    f"parsed constraint mismatch: {key} "
                    f"(expected={expected_value}, actual={actual_constraint_merged[key]})"
                )
                score -= 6

    # code_mapping
    expected_code_mapping = expected.get("code_mapping")
    if isinstance(expected_code_mapping, dict) and expected_code_mapping:
        flat_expected = _flatten_dict(expected_code_mapping)
        code_mapping = state_snapshot.get("code_mapping", {})
        flat_actual = _flatten_dict(code_mapping) if isinstance(code_mapping, dict) else {}
        for key, expected_value in flat_expected.items():
            actual_value = flat_actual.get(key)
            if actual_value != expected_value:
                fail_reasons.append(
                    f"code_mapping mismatch: {key} (expected={expected_value}, actual={actual_value})"
                )
                score -= 6

    # search_plan groups
    expected_plan_groups = expected.get("search_plan_groups")
    if isinstance(expected_plan_groups, list) and expected_plan_groups:
        search_plan = state_snapshot.get("search_plan", [])
        actual_plan_groups = sorted(
            {
                str(item.get("search_group"))
                for item in search_plan
                if isinstance(item, dict) and item.get("search_group") is not None
            }
        )
        for group in expected_plan_groups:
            if group not in actual_plan_groups:
                fail_reasons.append(f"missing search_plan group: {group}")
                score -= 8

    # candidate partial
    raw_partial = str(expected.get("candidate_partial", "")).strip().lower()
    if raw_partial in {"true", "false"}:
        expected_partial = raw_partial == "true"
        candidate_skeletons = state_snapshot.get("candidate_skeletons", [])
        actual_partial = False
        if candidate_skeletons:
            for skeleton in candidate_skeletons:
                if isinstance(skeleton, dict):
                    if skeleton.get("confidence") == "partial":
                        actual_partial = True
                        break
                    if skeleton.get("missing_fields"):
                        actual_partial = True
                        break
        if actual_partial != expected_partial:
            fail_reasons.append(
                f"candidate partial mismatch: expected={expected_partial}, actual={actual_partial}"
            )
            score -= 8

    # keyword checks on turn response
    lower_response = response.lower()
    for keyword in expected.get("must_include_keywords", []) or []:
        if keyword.lower() not in lower_response:
            fail_reasons.append(f"turn missing required keyword: {keyword}")
            score -= 6
    for keyword in expected.get("must_not_claim_keywords", []) or []:
        if keyword.lower() in lower_response:
            fail_reasons.append(f"turn forbidden keyword found: {keyword}")
            score -= 10

    if not response.strip():
        fail_reasons.append("empty turn response")
        score = 0.0

    return max(0.0, round(score, 2)), len(fail_reasons) == 0, fail_reasons


async def run_single_multiturn_case(test_case: MlccMultiturnTestCase) -> MlccMultiturnCaseResult:
    """Execute one multi-turn regression case against the current root agent.

    A single session is created and all turns are delivered sequentially so the
    agent accumulates context across turns.

    Parameters:
        test_case: Multi-turn case definition to run.

    Returns:
        MlccMultiturnCaseResult with per-turn and aggregate metrics.
    """
    turns_inputs = _safe_json_loads(test_case.turns_json, [])
    if not isinstance(turns_inputs, list) or not turns_inputs:
        raise ValueError(f"case {test_case.case_id}: turns_json must be non-empty JSON list")

    per_turn_expected = _safe_json_loads(test_case.expected_per_turn_json, [])
    if not isinstance(per_turn_expected, list):
        per_turn_expected = []

    session_service = InMemorySessionService()
    tool_plugin = MlccSkillTracePlugin()
    model_plugin = MlccModelTracePlugin()

    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service,
        plugins=[tool_plugin, model_plugin],
    )

    user_id = "regression_multiturn_user"
    session_id = f"{test_case.case_id}_{uuid.uuid4().hex[:8]}"

    await session_service.create_session(
        app_name=APP_NAME,
        user_id=user_id,
        session_id=session_id,
        state={
            "eval_case_id": test_case.case_id,
            "eval_category": test_case.category,
            "eval_multiturn": True,
        },
    )

    turns: list[TurnTrace] = []

    for idx, user_text in enumerate(turns_inputs):
        final_response, new_tool, new_model = await _run_one_turn(
            runner=runner,
            user_id=user_id,
            session_id=session_id,
            user_text=str(user_text),
            tool_plugin=tool_plugin,
            model_plugin=model_plugin,
        )

        updated_session = await session_service.get_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id,
        )
        state_snapshot = dict(updated_session.state) if updated_session else {}

        search_rag_traces = [t for t in new_tool if t.tool_name == "search_rag"]
        search_groups = sorted(
            {
                str(t.tool_args.get("search_group"))
                for t in search_rag_traces
                if t.tool_args.get("search_group") is not None
            }
        )

        turn_expected = per_turn_expected[idx] if idx < len(per_turn_expected) else {}
        if not isinstance(turn_expected, dict):
            turn_expected = {}

        turn_score, turn_passed, turn_fails = _evaluate_turn(
            expected=turn_expected,
            response=final_response,
            state_snapshot=state_snapshot,
            tool_traces=new_tool,
        )

        turns.append(
            TurnTrace(
                turn_index=idx,
                user_input=str(user_text),
                final_response=final_response,
                search_rag_calls=len(search_rag_traces),
                search_groups=search_groups,
                tool_traces=new_tool,
                model_traces=new_model,
                model_request_count=len(new_model),
                estimated_input_tokens=sum(m.estimated_input_tokens for m in new_model),
                estimated_output_tokens=sum(m.estimated_output_tokens for m in new_model),
                state_snapshot=state_snapshot,
                score=turn_score,
                passed=turn_passed,
                fail_reasons=turn_fails,
            )
        )

    # Aggregate evaluation
    final_state = turns[-1].state_snapshot if turns else {}
    final_response_last = turns[-1].final_response if turns else ""

    fail_reasons: list[str] = []
    aggregate_score = 100.0

    total_search_rag = sum(t.search_rag_calls for t in turns)
    if total_search_rag > test_case.expected_total_search_rag_calls_max:
        fail_reasons.append(
            f"total search_rag {total_search_rag} > max "
            f"{test_case.expected_total_search_rag_calls_max}"
        )
        aggregate_score -= 15

    expected_final_state_keys = _safe_json_loads(test_case.expected_final_state_keys, [])
    for key in expected_final_state_keys or []:
        if key not in final_state:
            fail_reasons.append(f"missing final state key: {key}")
            aggregate_score -= 8

    lower_final = final_response_last.lower()
    for keyword in _safe_json_loads(test_case.expected_final_must_include_keywords, []) or []:
        if keyword.lower() not in lower_final:
            fail_reasons.append(f"final response missing required keyword: {keyword}")
            aggregate_score -= 8
    for keyword in _safe_json_loads(test_case.expected_final_must_not_claim_keywords, []) or []:
        if keyword.lower() in lower_final:
            fail_reasons.append(f"final response forbidden keyword: {keyword}")
            aggregate_score -= 15

    # Incorporate per-turn failures into aggregate
    for turn in turns:
        if not turn.passed:
            fail_reasons.append(f"turn {turn.turn_index} failed: {turn.fail_reasons}")
    if turns:
        avg_turn_score = sum(t.score for t in turns) / len(turns)
        # blend turn avg into aggregate: lose 0.3 of the gap to avg
        aggregate_score = round(
            max(0.0, min(aggregate_score, aggregate_score - 0.3 * (100.0 - avg_turn_score))),
            2,
        )

    total_search_groups_union = sorted({g for t in turns for g in t.search_groups})
    all_tool_traces = [tt for t in turns for tt in t.tool_traces]
    all_model_traces_count = sum(t.model_request_count for t in turns)
    total_input_tokens = sum(t.estimated_input_tokens for t in turns)
    total_output_tokens = sum(t.estimated_output_tokens for t in turns)

    prompt_trace_path = save_multiturn_prompt_trace(test_case.case_id, turns)

    passed = (len(fail_reasons) == 0) and all(t.passed for t in turns)

    return MlccMultiturnCaseResult(
        case_id=test_case.case_id,
        category=test_case.category,
        turn_count=len(turns),
        per_turn_responses_json=_safe_json_dumps([t.final_response for t in turns]),
        per_turn_search_rag_calls_json=_safe_json_dumps([t.search_rag_calls for t in turns]),
        per_turn_search_groups_json=_safe_json_dumps([t.search_groups for t in turns]),
        per_turn_input_tokens_json=_safe_json_dumps([t.estimated_input_tokens for t in turns]),
        per_turn_output_tokens_json=_safe_json_dumps([t.estimated_output_tokens for t in turns]),
        per_turn_model_request_count_json=_safe_json_dumps(
            [t.model_request_count for t in turns]
        ),
        per_turn_scores_json=_safe_json_dumps([t.score for t in turns]),
        per_turn_passed_json=_safe_json_dumps([t.passed for t in turns]),
        per_turn_fail_reasons_json=_safe_json_dumps([t.fail_reasons for t in turns]),
        total_search_rag_calls=total_search_rag,
        total_search_groups=_safe_json_dumps(total_search_groups_union),
        final_state_snapshot_json=_safe_json_dumps(final_state),
        tool_trace_json=_safe_json_dumps([asdict(t) for t in all_tool_traces]),
        model_request_count=all_model_traces_count,
        estimated_input_tokens=total_input_tokens,
        estimated_output_tokens=total_output_tokens,
        prompt_trace_path=prompt_trace_path,
        score=aggregate_score,
        passed=passed,
        fail_reasons=_safe_json_dumps(fail_reasons),
    )


def write_multiturn_results(results: list[MlccMultiturnCaseResult]) -> Path:
    """Write multi-turn regression results to timestamped CSV.

    Parameters:
        results: Evaluated case results.

    Returns:
        Output CSV path.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = RESULT_DIR / f"mlcc_multiturn_eval_{timestamp}.csv"

    with output_path.open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(
            fp,
            fieldnames=[
                "case_id",
                "category",
                "turn_count",
                "per_turn_responses_json",
                "per_turn_search_rag_calls_json",
                "per_turn_search_groups_json",
                "per_turn_input_tokens_json",
                "per_turn_output_tokens_json",
                "per_turn_model_request_count_json",
                "per_turn_scores_json",
                "per_turn_passed_json",
                "per_turn_fail_reasons_json",
                "total_search_rag_calls",
                "total_search_groups",
                "final_state_snapshot_json",
                "tool_trace_json",
                "model_request_count",
                "estimated_input_tokens",
                "estimated_output_tokens",
                "prompt_trace_path",
                "score",
                "passed",
                "fail_reasons",
            ],
        )
        writer.writeheader()
        for result in results:
            writer.writerow(asdict(result))

    return output_path


async def main() -> None:
    """Run all MLCC multi-turn regression cases and save CSV results."""
    test_cases = load_multiturn_test_cases(TEST_CASE_PATH)
    results: list[MlccMultiturnCaseResult] = []

    for test_case in test_cases:
        print(f"[RUN] {test_case.case_id} - {test_case.category}")
        result = await run_single_multiturn_case(test_case)
        results.append(result)
        print(
            f"  -> turns={result.turn_count}, "
            f"passed={result.passed}, score={result.score}, "
            f"total_search_rag={result.total_search_rag_calls}, "
            f"model_calls={result.model_request_count}, "
            f"in~={result.estimated_input_tokens}, out~={result.estimated_output_tokens}"
        )

    output_path = write_multiturn_results(results)
    pass_count = sum(1 for r in results if r.passed)

    print("\n=== SUMMARY ===")
    print(f"total={len(results)} passed={pass_count} failed={len(results) - pass_count}")
    print(f"saved={output_path}")
    print(f"prompt_traces={PROMPT_TRACE_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
