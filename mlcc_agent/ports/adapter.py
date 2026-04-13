"""
출력 어댑터 (Output Adapter).

모든 tool의 반환값은 이 모듈의 adapt_output 을 거쳐야 한다.

역할:
  1. 내부 구현 결과를 schemas.py 에 정의된 계약 스키마로 검증
  2. 검증 실패 시 오류를 오케스트레이터에 노출하지 않고 error status 로 래핑
  3. 오케스트레이터 기대 포맷이 바뀌면 이 파일만 수정

사용 예:
    from ..ports.adapter import adapt_output
    from ..ports.schemas import LotDetailResult

    return adapt_output(raw_dict, LotDetailResult)
"""

from __future__ import annotations

import logging
from typing import Type

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


def adapt_output(raw: dict, schema_cls: Type[BaseModel]) -> dict:
    """tool 내부 결과(raw dict)를 오케스트레이터 계약 스키마로 검증·정제한다.

    - 성공: 스키마 필드 타입이 보장된 dict 반환 (extra 필드도 포함, LLM 컨텍스트 보존)
    - 실패: 내부 오류를 숨기고 {"status": "error", "error_reason": "..."} 반환

    오케스트레이터는 이 함수를 거친 결과만 본다.
    내부 구현이 바뀌어도 스키마 계약이 유지되면 오케스트레이터 코드는 그대로다.
    """
    try:
        validated = schema_cls.model_validate(raw)
        return validated.model_dump(exclude_none=True)
    except ValidationError as exc:
        logger.error(
            "[adapter] %s 출력 스키마 검증 실패: %s | raw=%s",
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
