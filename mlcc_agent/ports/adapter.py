"""
입력 어댑터 (Input Adapter).

오케스트레이터가 보내는 raw 입력을 AgentInput으로 정규화한다.

변경 정책:
  - 오케스트레이터 입력 포맷이 바뀌면 adapt_input() 내부만 수정한다.
  - AgentInput 스키마는 내부 계약 기준이므로 건드리지 않는다.
"""

from __future__ import annotations

import logging
from pydantic import ValidationError
from .schemas import AgentInput

logger = logging.getLogger(__name__)


def adapt_input(raw: dict) -> dict:
    """오케스트레이터의 입력을 AgentInput 형식으로 정규화한다.

    - extra="ignore" 이므로 오케스트레이터의 내부 필드가 새어 들어오지 않는다.
    - 필수 필드(task) 누락 시 ValidationError를 그대로 전파한다.
      → 잘못된 입력으로 agent가 실행되는 것을 막는 것이 목적.
    - 오케스트레이터가 필드명을 바꾸면 이 함수에서 매핑하고 AgentInput은 유지한다.

    사용 위치: agent를 직접 invoke하는 진입점 (runner, wrapper 등)
    ADK AgentTool로 호출 시에는 LLM이 input_schema를 보고 알아서 채운다.
    """
    try:
        return AgentInput.model_validate(raw).model_dump(exclude_none=True)
    except ValidationError as exc:
        logger.error(
            "[adapter.adapt_input] AgentInput 검증 실패: %s | raw=%s",
            exc,
            raw,
        )
        raise  # 입력 오류는 상위로 전파 — 잘못된 입력으로 agent가 실행되면 안 됨
