import asyncio
import csv
import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import requests
from google.adk.plugins.base_plugin import BasePlugin
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext
from google.genai import types

from mlcc_agent.agent import root_agent


APP_NAME = "mlcc_skill_regression"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEST_CASE_PATH = PROJECT_ROOT / "tests" / "test_cases_mlcc.csv"
RESULT_DIR = PROJECT_ROOT / "artifacts" / "eval_results"
RESULT_DIR.mkdir(parents=True, exist_ok=True)

PROMPT_TRACE_DIR = PROJECT_ROOT / "artifacts" / "prompt_traces"
PROMPT_TRACE_DIR.mkdir(parents=True, exist_ok=True)

# 실제 환경에 맞게 변경
VLLM_TOKENIZE_URL = "http://ip:port/gpt-oss-120b/tokenize"


@dataclass
class MlccTestCase:
    """Single regression test case for MLCC skill evaluation.

    Parameters:
        case_id: Unique test case identifier.
        category: Logical bucket for grouping failures.
        user_input: Natural language input sent to the ADK agent.
        expected_constraints_json: Expected parsed constraints as JSON string.
        expected_search_rag_calls_max: Max allowed search_rag calls.
        expected_search_groups: Allowed/expected search_group values as JSON list.
        expected_state_keys: Expected keys in session.state as JSON list.
        expected_must_not_claim_keywords: Forbidden phrases in final response.
        expected_must_include_keywords: Required phrases in final response.
        expected_search_plan_groups: Required search_group values in search_plan.
        expected_code_mapping_json: Expected partial code_mapping key/value JSON.
        expected_candidate_partial: Whether candidate skeleton is expected partial.

    Returns:
        MlccTestCase instance.
    """

    case_id: str
    category: str
    user_input: str
    expected_constraints_json: str
    expected_search_rag_calls_max: int
    expected_search_groups: str
    expected_state_keys: str
    expected_must_not_claim_keywords: str
    expected_must_include_keywords: str
    expected_search_plan_groups: str
    expected_code_mapping_json: str
    expected_candidate_partial: str


@dataclass
class ToolTrace:
    """Structured record of one tool invocation.

    Parameters:
        tool_name: Tool name exposed to ADK.
        tool_args: Raw tool arguments.
        result_preview: Truncated result preview for CSV readability.
        error: Error message if tool failed.

    Returns:
        ToolTrace instance.
    """

    tool_name: str
    tool_args: dict[str, Any]
    result_preview: str
    error: Optional[str] = None


@dataclass
class ModelTrace:
    """Structured record of one model invocation.

    Parameters:
        request_chars: Flattened request text length.
        estimated_input_tokens: Estimated input token count.
        response_chars: Flattened response text length.
        estimated_output_tokens: Estimated output token count.

    Returns:
        ModelTrace instance.
    """

    request_chars: int
    estimated_input_tokens: int
    response_chars: int = 0
    estimated_output_tokens: int = 0


@dataclass
class MlccCaseResult:
    """Evaluation output for a single test case.

    Parameters:
        case_id: Source test case id.
        category: Source category.
        final_response: Final assistant text collected from the run.
        actual_search_rag_calls: Count of search_rag invocations.
        actual_search_groups: Distinct search_group values used.
        state_snapshot_json: Final session state snapshot serialized as JSON.
        tool_trace_json: Full tool trace serialized as JSON.
        model_request_count: Number of model calls in the run.
        estimated_input_tokens: Summed estimated input tokens.
        estimated_output_tokens: Summed estimated output tokens.
        prompt_trace_path: File path to detailed model trace JSON.
        score: Total score in [0, 100].
        passed: Whether the case passed.
        fail_reasons: JSON list of failure reasons.

    Returns:
        MlccCaseResult instance.
    """

    case_id: str
    category: str
    final_response: str
    actual_search_rag_calls: int
    actual_search_groups: str
    state_snapshot_json: str
    tool_trace_json: str
    model_request_count: int
    estimated_input_tokens: int
    estimated_output_tokens: int
    prompt_trace_path: str
    score: float
    passed: bool
    fail_reasons: str


class MlccSkillTracePlugin(BasePlugin):
    """Capture tool execution traces for MLCC skill regression.

    This plugin records every tool call before/after execution so we can
    compare trajectory quality, tool count, and search_group usage.

    Success:
        Appends structured ToolTrace objects to self.tool_traces.

    Failure:
        If a tool raises, the error is captured in self.tool_traces and the
        original exception flow is preserved.

    Example:
        plugin = MlccSkillTracePlugin()
    """

    def __init__(self) -> None:
        super().__init__(name="mlcc_skill_trace_plugin")
        self.tool_traces: list[ToolTrace] = []

    async def before_tool_callback(
        self,
        *,
        tool: BaseTool,
        tool_args: dict[str, Any],
        tool_context: ToolContext,
    ) -> Optional[dict]:
        """Observe tool start without altering execution.

        Parameters:
            tool: ADK tool object.
            tool_args: Parsed tool arguments.
            tool_context: ADK tool context.

        Returns:
            None to allow normal execution.
        """
        self.tool_traces.append(
            ToolTrace(
                tool_name=tool.name,
                tool_args=tool_args,
                result_preview="__PENDING__",
                error=None,
            )
        )
        return None

    async def after_tool_callback(
        self,
        *,
        tool: BaseTool,
        tool_args: dict[str, Any],
        tool_context: ToolContext,
        result: dict,
    ) -> Optional[dict]:
        """Observe successful tool completion.

        Parameters:
            tool: ADK tool object.
            tool_args: Parsed tool arguments.
            tool_context: ADK tool context.
            result: Tool return payload.

        Returns:
            None to preserve original result.
        """
        for trace in reversed(self.tool_traces):
            if trace.tool_name == tool.name and trace.result_preview == "__PENDING__":
                trace.result_preview = _truncate_text(_safe_json_dumps(result))
                break
        return None

    async def on_tool_error_callback(
        self,
        *,
        tool: BaseTool,
        tool_args: dict[str, Any],
        tool_context: ToolContext,
        error: Exception,
    ) -> Optional[dict]:
        """Observe failed tool execution.

        Parameters:
            tool: ADK tool object.
            tool_args: Parsed tool arguments.
            tool_context: ADK tool context.
            error: Raised exception.

        Returns:
            None to preserve original exception behavior.
        """
        for trace in reversed(self.tool_traces):
            if trace.tool_name == tool.name and trace.result_preview == "__PENDING__":
                trace.result_preview = ""
                trace.error = str(error)
                break
        return None


class MlccModelTracePlugin(BasePlugin):
    """Capture model request/response size traces for regression analysis."""

    def __init__(self) -> None:
        super().__init__(name="mlcc_model_trace_plugin")
        self.model_traces: list[ModelTrace] = []

    async def before_model_callback(
        self,
        *,
        callback_context,
        llm_request,
    ) -> Optional[Any]:
        """Capture request size before the model call."""
        request_text = flatten_llm_request_to_text(llm_request)
        self.model_traces.append(
            ModelTrace(
                request_chars=len(request_text),
                estimated_input_tokens=estimate_tokens_from_text(request_text),
            )
        )
        return None

    async def after_model_callback(
        self,
        *,
        callback_context,
        llm_response,
        llm_request=None,
    ) -> Optional[Any]:
        """Capture response size after the model call."""
        if not self.model_traces:
            return None

        response_text = flatten_llm_response_to_text(llm_response)
        trace = self.model_traces[-1]
        trace.response_chars = len(response_text)
        trace.estimated_output_tokens = estimate_tokens_from_text(response_text)
        return None


def _truncate_text(value: str, max_len: int = 800) -> str:
    """Return a safely truncated string for CSV storage."""
    if len(value) <= max_len:
        return value
    return value[: max_len - 3] + "..."


def _safe_json_loads(raw: str, default: Any) -> Any:
    """Parse JSON string with fallback default."""
    if raw is None or raw == "":
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def _safe_json_dumps(value: Any) -> str:
    """Serialize values safely for CSV storage."""
    return json.dumps(value, ensure_ascii=False, default=str)


def _flatten_dict(data: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Flatten nested dict into dot-path keys."""
    flat: dict[str, Any] = {}
    for key, value in data.items():
        new_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            flat.update(_flatten_dict(value, new_key))
        else:
            flat[new_key] = value
    return flat


def _extract_expected_constraints(expected_constraints: dict[str, Any]) -> dict[str, Any]:
    """Extract comparable expected constraints.

    Accept both:
    {"temperature_family":"X5R", ...}
    and
    {"hard": {...}, "soft": {...}, "validation_only": {...}}
    """
    if any(k in expected_constraints for k in ["hard", "soft", "validation_only"]):
        merged: dict[str, Any] = {}
        for section in ["hard", "soft", "validation_only"]:
            section_data = expected_constraints.get(section, {})
            if isinstance(section_data, dict):
                merged.update(section_data)
        return merged
    return expected_constraints


def _truncate_for_estimation(text: str, limit: int = 8000) -> str:
    """Keep head and tail for long prompt token estimation."""
    if len(text) <= limit:
        return text

    half = limit // 2
    head = text[:half]
    tail = text[-half:]
    return head + "\n...\n" + tail


@lru_cache(maxsize=1024)
def _cached_tokenize(text: str) -> int:
    """Tokenize text using external vLLM tokenize endpoint with fallback."""
    try:
        response = requests.post(
            VLLM_TOKENIZE_URL,
            json={"text": text},
            timeout=5,
        )
        response.raise_for_status()

        data = response.json()

        tokens = data.get("tokens") or data.get("token_ids")
        if tokens is not None:
            return len(tokens)

        if "count" in data:
            return int(data["count"])

        return 0

    except Exception:
        return max(1, len(text) // 4)


def estimate_tokens_from_text(text: str) -> int:
    """Estimate token count from text.

    Prefer external tokenizer endpoint. Fall back to char-based estimate.
    """
    if not text:
        return 0

    text = _truncate_for_estimation(text, limit=8000)
    return _cached_tokenize(text)


def flatten_llm_request_to_text(llm_request: Any) -> str:
    """Convert an ADK LLM request object into a comparable text blob."""
    parts: list[str] = []

    system_instruction = getattr(llm_request, "system_instruction", None)
    if system_instruction:
        parts.append(str(system_instruction))

    contents = getattr(llm_request, "contents", None) or []
    for content in contents:
        role = getattr(content, "role", None)
        if role:
            parts.append(f"[{role}]")
        for part in getattr(content, "parts", []) or []:
            text = getattr(part, "text", None)
            if text:
                parts.append(text)
            elif hasattr(part, "function_call") and getattr(part, "function_call", None):
                parts.append(str(getattr(part, "function_call")))
            elif hasattr(part, "function_response") and getattr(part, "function_response", None):
                parts.append(str(getattr(part, "function_response")))

    tools = getattr(llm_request, "tools", None)
    if tools:
        parts.append(str(tools))

    return "\n".join(parts)


def flatten_llm_response_to_text(llm_response: Any) -> str:
    """Convert an ADK LLM response object into plain text for logging."""
    parts: list[str] = []

    content = getattr(llm_response, "content", None)
    if content:
        for part in getattr(content, "parts", []) or []:
            text = getattr(part, "text", None)
            if text:
                parts.append(text)
            elif hasattr(part, "function_call") and getattr(part, "function_call", None):
                parts.append(str(getattr(part, "function_call")))
            elif hasattr(part, "function_response") and getattr(part, "function_response", None):
                parts.append(str(getattr(part, "function_response")))

    return "\n".join(parts)


def save_prompt_trace(case_id: str, traces: list[ModelTrace]) -> str:
    """Save prompt trace to JSON file and return file path."""
    path = PROMPT_TRACE_DIR / f"{case_id}.json"
    with path.open("w", encoding="utf-8") as fp:
        json.dump([asdict(t) for t in traces], fp, ensure_ascii=False, indent=2)
    return str(path)


def load_test_cases(csv_path: Path) -> list[MlccTestCase]:
    """Load regression test cases from CSV.

    Parameters:
        csv_path: Path to test case CSV file.

    Returns:
        List of MlccTestCase rows.
    """
    rows: list[MlccTestCase] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            rows.append(
                MlccTestCase(
                    case_id=row["case_id"],
                    category=row["category"],
                    user_input=row["user_input"],
                    expected_constraints_json=row.get("expected_constraints_json", "{}"),
                    expected_search_rag_calls_max=int(row["expected_search_rag_calls_max"]),
                    expected_search_groups=row.get("expected_search_groups", "[]"),
                    expected_state_keys=row.get("expected_state_keys", "[]"),
                    expected_must_not_claim_keywords=row.get("expected_must_not_claim_keywords", "[]"),
                    expected_must_include_keywords=row.get("expected_must_include_keywords", "[]"),
                    expected_search_plan_groups=row.get("expected_search_plan_groups", "[]"),
                    expected_code_mapping_json=row.get("expected_code_mapping_json", "{}"),
                    expected_candidate_partial=row.get("expected_candidate_partial", ""),
                )
            )
    return rows


async def run_single_case(test_case: MlccTestCase) -> MlccCaseResult:
    """Execute one regression case against the current root agent.

    Parameters:
        test_case: Case definition to run.

    Returns:
        MlccCaseResult with trajectory, state snapshot, and score.
    """
    session_service = InMemorySessionService()
    tool_plugin = MlccSkillTracePlugin()
    model_plugin = MlccModelTracePlugin()

    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service,
        plugins=[tool_plugin, model_plugin],
    )

    user_id = "regression_user"
    session_id = f"{test_case.case_id}_{uuid.uuid4().hex[:8]}"

    await session_service.create_session(
        app_name=APP_NAME,
        user_id=user_id,
        session_id=session_id,
        state={
            "eval_case_id": test_case.case_id,
            "eval_category": test_case.category,
        },
    )

    final_response = ""

    user_message = types.Content(
        role="user",
        parts=[types.Part.from_text(text=test_case.user_input)],
    )

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=user_message,
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

    updated_session = await session_service.get_session(
        app_name=APP_NAME,
        user_id=user_id,
        session_id=session_id,
    )

    evaluation = evaluate_case_result(
        test_case=test_case,
        final_response=final_response,
        state_snapshot=updated_session.state if updated_session else {},
        tool_traces=tool_plugin.tool_traces,
        model_traces=model_plugin.model_traces,
    )
    return evaluation


def evaluate_case_result(
    test_case: MlccTestCase,
    final_response: str,
    state_snapshot: dict[str, Any],
    tool_traces: list[ToolTrace],
    model_traces: list[ModelTrace],
) -> MlccCaseResult:
    """Score one run using state, trajectory, and response guardrails.

    Parameters:
        test_case: Expected case definition.
        final_response: Final assistant response text.
        state_snapshot: Final session state.
        tool_traces: Tool execution traces.
        model_traces: Model request/response traces.

    Returns:
        MlccCaseResult with pass/fail reasons and score.
    """
    fail_reasons: list[str] = []
    score = 100.0

    parsed_constraints = state_snapshot.get("parsed_constraints", {})
    code_mapping = state_snapshot.get("code_mapping", {})
    candidate_skeletons = state_snapshot.get("candidate_skeletons", [])
    search_plan = state_snapshot.get("search_plan", [])

    search_rag_traces = [t for t in tool_traces if t.tool_name == "search_rag"]
    actual_search_groups = sorted(
        {
            str(t.tool_args.get("search_group"))
            for t in search_rag_traces
            if t.tool_args.get("search_group") is not None
        }
    )

    # 1) search_rag call count
    if len(search_rag_traces) > test_case.expected_search_rag_calls_max:
        fail_reasons.append(
            f"search_rag called {len(search_rag_traces)} times "
            f"(max {test_case.expected_search_rag_calls_max})"
        )
        score -= 20

    # 2) unexpected search_group
    expected_search_groups = _safe_json_loads(test_case.expected_search_groups, [])
    if expected_search_groups:
        unexpected_groups = [g for g in actual_search_groups if g not in expected_search_groups]
        if unexpected_groups:
            fail_reasons.append(f"unexpected search_group used: {unexpected_groups}")
            score -= 15

    # 3) missing search_group in search_rag
    for trace in search_rag_traces:
        if "search_group" not in trace.tool_args or not trace.tool_args.get("search_group"):
            fail_reasons.append("search_rag called without search_group")
            score -= 20
            break

    # 4) expected state keys
    expected_state_keys = _safe_json_loads(test_case.expected_state_keys, [])
    for key in expected_state_keys:
        if key not in state_snapshot:
            fail_reasons.append(f"missing expected state key: {key}")
            score -= 10

    # 5) parsed_constraints evaluation
    expected_constraints_raw = _safe_json_loads(test_case.expected_constraints_json, {})
    expected_constraints = _extract_expected_constraints(expected_constraints_raw)

    actual_constraint_merged: dict[str, Any] = {}
    if isinstance(parsed_constraints, dict):
        for bucket in ["hard", "soft", "validation_only"]:
            bucket_data = parsed_constraints.get(bucket, {})
            if isinstance(bucket_data, dict):
                actual_constraint_merged.update(bucket_data)

    for key, expected_value in expected_constraints.items():
        if key not in actual_constraint_merged:
            fail_reasons.append(f"missing parsed constraint: {key}")
            score -= 8
        elif actual_constraint_merged[key] != expected_value:
            fail_reasons.append(
                f"parsed constraint mismatch: {key} "
                f"(expected={expected_value}, actual={actual_constraint_merged[key]})"
            )
            score -= 8

    # 6) code_mapping evaluation
    expected_code_mapping = _safe_json_loads(test_case.expected_code_mapping_json, {})
    flat_expected_code_mapping = (
        _flatten_dict(expected_code_mapping) if isinstance(expected_code_mapping, dict) else {}
    )
    flat_actual_code_mapping = _flatten_dict(code_mapping) if isinstance(code_mapping, dict) else {}

    for key, expected_value in flat_expected_code_mapping.items():
        actual_value = flat_actual_code_mapping.get(key)
        if actual_value != expected_value:
            fail_reasons.append(
                f"code_mapping mismatch: {key} "
                f"(expected={expected_value}, actual={actual_value})"
            )
            score -= 8

    # 7) search_plan evaluation
    expected_search_plan_groups = _safe_json_loads(test_case.expected_search_plan_groups, [])
    actual_search_plan_groups = sorted(
        {
            str(item.get("search_group"))
            for item in search_plan
            if isinstance(item, dict) and item.get("search_group") is not None
        }
    )

    for group in expected_search_plan_groups:
        if group not in actual_search_plan_groups:
            fail_reasons.append(f"missing expected search_plan group: {group}")
            score -= 10

    # 8) candidate partial evaluation
    raw_partial = (test_case.expected_candidate_partial or "").strip().lower()
    if raw_partial in {"true", "false"}:
        expected_partial = raw_partial == "true"
        actual_partial = False

        if candidate_skeletons:
            for skeleton in candidate_skeletons:
                if isinstance(skeleton, dict):
                    if skeleton.get("confidence") == "partial":
                        actual_partial = True
                        break
                    missing_fields = skeleton.get("missing_fields", [])
                    if missing_fields:
                        actual_partial = True
                        break

        if actual_partial != expected_partial:
            fail_reasons.append(
                f"candidate partial mismatch: expected={expected_partial}, actual={actual_partial}"
            )
            score -= 10

    # 9) forbidden response keywords
    forbidden_keywords = _safe_json_loads(test_case.expected_must_not_claim_keywords, [])
    lower_response = final_response.lower()
    for keyword in forbidden_keywords:
        if keyword.lower() in lower_response:
            fail_reasons.append(f"forbidden claim found in response: {keyword}")
            score -= 15

    # 10) required response keywords
    required_keywords = _safe_json_loads(test_case.expected_must_include_keywords, [])
    for keyword in required_keywords:
        if keyword.lower() not in lower_response:
            fail_reasons.append(f"required keyword missing in response: {keyword}")
            score -= 8

    # 11) empty final response
    if not final_response.strip():
        fail_reasons.append("empty final response")
        score = 0.0

    score = max(0.0, round(score, 2))

    model_request_count = len(model_traces)
    estimated_input_tokens = sum(t.estimated_input_tokens for t in model_traces)
    estimated_output_tokens = sum(t.estimated_output_tokens for t in model_traces)
    prompt_trace_path = save_prompt_trace(test_case.case_id, model_traces)

    return MlccCaseResult(
        case_id=test_case.case_id,
        category=test_case.category,
        final_response=final_response,
        actual_search_rag_calls=len(search_rag_traces),
        actual_search_groups=_safe_json_dumps(actual_search_groups),
        state_snapshot_json=_safe_json_dumps(state_snapshot),
        tool_trace_json=_safe_json_dumps([asdict(t) for t in tool_traces]),
        model_request_count=model_request_count,
        estimated_input_tokens=estimated_input_tokens,
        estimated_output_tokens=estimated_output_tokens,
        prompt_trace_path=prompt_trace_path,
        score=score,
        passed=(len(fail_reasons) == 0),
        fail_reasons=_safe_json_dumps(fail_reasons),
    )


def write_results(results: list[MlccCaseResult]) -> Path:
    """Write regression results to timestamped CSV.

    Parameters:
        results: Evaluated case results.

    Returns:
        Output CSV path.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = RESULT_DIR / f"mlcc_skill_eval_{timestamp}.csv"

    with output_path.open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(
            fp,
            fieldnames=[
                "case_id",
                "category",
                "final_response",
                "actual_search_rag_calls",
                "actual_search_groups",
                "state_snapshot_json",
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
    """Run all MLCC regression cases and save CSV results."""
    test_cases = load_test_cases(TEST_CASE_PATH)
    results: list[MlccCaseResult] = []

    for test_case in test_cases:
        print(f"[RUN] {test_case.case_id} - {test_case.category}")
        result = await run_single_case(test_case)
        results.append(result)
        print(
            f"  -> passed={result.passed}, "
            f"score={result.score}, "
            f"search_rag_calls={result.actual_search_rag_calls}, "
            f"model_calls={result.model_request_count}, "
            f"in_tokens~={result.estimated_input_tokens}, "
            f"out_tokens~={result.estimated_output_tokens}"
        )

    output_path = write_results(results)
    pass_count = sum(1 for r in results if r.passed)

    print("\n=== SUMMARY ===")
    print(f"total={len(results)} passed={pass_count} failed={len(results) - pass_count}")
    print(f"saved={output_path}")
    print(f"prompt_traces={PROMPT_TRACE_DIR}")


if __name__ == "__main__":
    asyncio.run(main())