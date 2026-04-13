"""
어댑터 (Port Adapters).

오케스트레이터 ↔ subagent 경계의 양방향 변환을 담당한다.

  adapt_input()  – 입력 어댑터: 오케스트레이터 → subagent
  adapt_output() – 출력 어댑터: tool 내부 결과 → 계약 스키마 검증 (내부 계약)

오케스트레이터 포맷이 바뀌면 이 파일과 schemas.py 만 수정한다.
tools/*.py 는 건드리지 않는다.
"""

from __future__ import annotations

import logging
from typing import Type

from pydantic import BaseModel, ValidationError

from .schemas import AgentInput

logger = logging.getLogger(__name__)


# ── 입력 어댑터 ───────────────────────────────────────────────────────────────

def adapt_input(raw: dict) -> dict:
    """오케스트레이터의 입력을 subagent 내부 형식(AgentInput)으로 정규화한다.

    - extra="ignore" 이므로 오케스트레이터의 내부 필드가 새어 들어오지 않는다.
    - 필수 필드(task) 누락 시 ValidationError를 그대로 전파한다.
      → subagent가 잘못된 입력으로 실행되는 것을 막는 것이 목적.
    - 오케스트레이터가 필드명을 바꾸면 이 함수에서 매핑하고 AgentInput은 유지한다.

    사용 위치: agent를 직접 invoke하는 진입점 (runner, wrapper 등)
    ADK AgentTool로 호출 시에는 LLM이 input_schema를 보고 알아서 채운다.
    """
    try:
        normalized = AgentInput.model_validate(raw)
        return normalized.model_dump(exclude_none=True)
    except ValidationError as exc:
        logger.error(
            "[adapter.adapt_input] AgentInput 검증 실패: %s | raw=%s",
            exc,
            raw,
        )
        raise  # 입력 오류는 상위로 전파 — 잘못된 입력으로 agent가 실행되면 안 됨


# ── 출력 어댑터 (내부 tool 계약) ──────────────────────────────────────────────

def adapt_output(raw: dict, schema_cls: Type[BaseModel]) -> dict:
    """tool 내부 결과(raw dict)를 계약 스키마로 검증·정제한다.

    - 성공: 스키마 필드 타입 보장 + extra 필드도 포함 (LLM 컨텍스트 보존)
    - 실패: 내부 오류를 오케스트레이터에 노출하지 않고 error status로 래핑

    이 함수는 tool → 내부LLM 방향의 내부 계약 검증이다.
    subagent → 오케스트레이터 최종 출력 계약은 agent.py의 output_schema 참고.
    """
    try:
        validated = schema_cls.model_validate(raw)
        return validated.model_dump(exclude_none=True)
    except ValidationError as exc:
        logger.error(
            "[adapter.adapt_output] %s 출력 스키마 검증 실패: %s | raw=%s",
            schema_cls.__name__,
            exc,
            raw,
        )
        return {
            "status": "error",
            "error_reason": (
                f"{schema_cls.__name__} 출력 계약 위반 — "
                "내부 구현을 확인하세요."
            ),
        }
