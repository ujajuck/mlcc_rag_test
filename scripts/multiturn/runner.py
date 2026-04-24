"""멀티턴 케이스 실행기.

한 케이스 = 한 ADK 세션. 턴 간 컨텍스트/state/artifact 는 이어진다.
"""

import time
import uuid
from pathlib import Path
from typing import Any, Optional

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from scripts.common.utils import compute_dict_delta

from .evaluator import evaluate_turn
from .io import save_case_details_json
from .plugins import MultiturnTrackingPlugin
from .types import CaseResult, MultiturnTestCase, TurnRecord


async def _snapshot_artifacts(
    artifact_service: Any,
    app_name: str,
    user_id: str,
    session_id: str,
) -> dict[str, Any]:
    """현재 세션의 artifact 키/메타를 best-effort 로 덤프.

    ADK 버전/구현에 따라 API 가 달라질 수 있어 예외는 무시한다.
    """
    if artifact_service is None:
        return {}

    list_fn = getattr(artifact_service, "list_artifact_keys", None)
    if list_fn is None:
        return {}

    try:
        keys = await list_fn(
            app_name=app_name, user_id=user_id, session_id=session_id
        )
    except Exception as exc:
        return {"__error__": f"list_artifact_keys failed: {exc}"}

    if not keys:
        return {}

    result: dict[str, Any] = {}
    load_fn = getattr(artifact_service, "load_artifact", None)
    for key in keys:
        if load_fn is None:
            result[key] = {"type": "key_only"}
            continue
        try:
            part = await load_fn(
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
                filename=key,
            )
            result[key] = {"type": type(part).__name__}
        except Exception as exc:
            result[key] = {"type": "unknown", "error": str(exc)}
    return result


def _build_artifact_service() -> Any:
    """InMemoryArtifactService 를 시도해서 가져오고, 실패 시 None."""
    try:
        from google.adk.artifacts import InMemoryArtifactService

        return InMemoryArtifactService()
    except Exception:
        return None


async def _run_turn_message(
    runner: Runner,
    user_id: str,
    session_id: str,
    user_text: str,
) -> str:
    """한 턴 메시지를 전송하고 final response 텍스트를 리턴."""
    message = types.Content(
        role="user",
        parts=[types.Part.from_text(text=user_text)],
    )

    final_response = ""
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=message,
    ):
        is_final = getattr(event, "is_final_response", None)
        if callable(is_final) and event.is_final_response():
            content = getattr(event, "content", None)
            parts = getattr(content, "parts", None) if content else None
            if parts:
                texts = [
                    getattr(p, "text", "").strip()
                    for p in parts
                    if getattr(p, "text", None)
                ]
                final_response = "\n".join(t for t in texts if t).strip()
            break
    return final_response


async def run_case(
    test_case: MultiturnTestCase,
    root_agent: Any,
    app_name: str,
    details_dir: Path,
) -> CaseResult:
    """한 멀티턴 케이스를 실행해 CaseResult 를 반환한다."""
    session_service = InMemorySessionService()
    plugin = MultiturnTrackingPlugin()
    artifact_service = _build_artifact_service()

    runner_kwargs: dict[str, Any] = dict(
        agent=root_agent,
        app_name=app_name,
        session_service=session_service,
        plugins=[plugin],
    )
    if artifact_service is not None:
        runner_kwargs["artifact_service"] = artifact_service
    runner = Runner(**runner_kwargs)

    user_id = "mt_user"
    session_id = f"{test_case.index}_{uuid.uuid4().hex[:8]}"
    await session_service.create_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session_id,
        state={"eval_index": test_case.index},
    )

    turns: list[TurnRecord] = []
    prev_state: dict[str, Any] = {}
    prev_artifacts: dict[str, Any] = {}
    case_error: Optional[str] = None

    for spec in test_case.turns:
        turn = TurnRecord(
            subindex=spec.subindex,
            user_input=spec.query,
        )
        plugin.attach_turn(turn)

        start = time.perf_counter()
        try:
            turn.final_response = await _run_turn_message(
                runner=runner,
                user_id=user_id,
                session_id=session_id,
                user_text=spec.query,
            )
        except Exception as exc:
            turn.error_message = str(exc)
            case_error = case_error or str(exc)
        finally:
            turn.elapsed_seconds = round(time.perf_counter() - start, 4)
            plugin.detach_turn()

        updated_session = await session_service.get_session(
            app_name=app_name, user_id=user_id, session_id=session_id
        )
        state_snapshot = dict(updated_session.state) if updated_session else {}
        turn.state_snapshot = state_snapshot
        turn.state_delta = compute_dict_delta(prev_state, state_snapshot)
        prev_state = state_snapshot

        artifact_snapshot = await _snapshot_artifacts(
            artifact_service, app_name, user_id, session_id
        )
        turn.artifact_snapshot = artifact_snapshot
        turn.artifact_delta = compute_dict_delta(prev_artifacts, artifact_snapshot)
        prev_artifacts = artifact_snapshot

        turn.input_tokens = sum(m.input_tokens for m in turn.model_calls)
        turn.output_tokens = sum(m.output_tokens for m in turn.model_calls)
        turn.model_request_count = len(turn.model_calls)

        evaluate_turn(spec, turn)
        turns.append(turn)

    details_path = details_dir / f"{test_case.index}.json"
    save_case_details_json(details_path, test_case, turns)

    passed = (case_error is None) and all(t.passed for t in turns)

    return CaseResult(
        index=test_case.index,
        turn_count=len(turns),
        turns=turns,
        passed=passed,
        total_input_tokens=sum(t.input_tokens for t in turns),
        total_output_tokens=sum(t.output_tokens for t in turns),
        total_model_requests=sum(t.model_request_count for t in turns),
        total_elapsed_seconds=round(sum(t.elapsed_seconds for t in turns), 4),
        details_json_path=str(details_path),
        error_message=case_error,
    )
