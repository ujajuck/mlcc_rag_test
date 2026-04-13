"""
오케스트레이터 ↔ subagent 간 출력 계약 (Output Schemas).

각 tool이 반환하는 dict의 최소 계약을 Pydantic 모델로 정의한다.

규칙:
  - 모든 tool 반환은 adapt_output(raw, SomeResult) 을 거쳐야 한다.
  - 스키마에 없는 필드는 extra="allow" 이므로 LLM까지 그대로 전달된다.
  - 스키마에 선언된 필드는 타입이 보장된다. 오케스트레이터는 이 필드만 의존할 것.
  - 내부 구현이 바뀌어도 스키마 필드가 유지되는 한 오케스트레이터 코드는 바꿀 필요 없다.
"""

from __future__ import annotations
from pydantic import BaseModel, ConfigDict


class ToolResult(BaseModel):
    """모든 tool 반환값의 기본 계약.

    status 값 규칙:
      'success'              – 정상 완료
      'error'                – 처리 실패
      'warning'              – 완료됐으나 주의 필요 (e.g. 부족인자 있음)
      'fail'                 – 조건 불충족으로 결과 없음
      'no_match'             – 검색 결과 없음
      'awaiting_confirmation'– 사용자 확인 대기 중
    """
    model_config = ConfigDict(extra="allow")  # 선언 외 필드도 LLM에 그대로 전달

    status: str


# ── Skill 1: mlcc-rag-spec-selector ──────────────────────────────────────────

class RefLotResult(ToolResult):
    """find_ref_lot_candidate 출력 계약."""
    ref_lot_id: str | None = None
    ref_lot_candi_top_k: list[dict] = []
    next_tool_use: str | None = None
    hint: str | None = None
    error_reason: str | None = None


# ── Skill 2: mlcc-optimal-design-doe ─────────────────────────────────────────

class LotDetailResult(ToolResult):
    """get_first_lot_detail 출력 계약."""
    ref_lot_design_info: list[dict] | None = None
    hint: str | None = None
    error_reason: str | None = None


class ValidationResult(ToolResult):
    """check_optimal_design 출력 계약."""
    lot_id: str | None = None
    fully_satisfied_versions: list[str] = []
    partially_missing_versions: dict[str, list] = {}
    부족인자: dict[str, list] = {}
    충족인자: dict[str, dict] = {}
    reason: str | None = None


class LotUpdateResult(ToolResult):
    """update_lot_reference 출력 계약."""
    lot_id: str | None = None
    updated_factors: dict = {}
    ref_values: dict | None = None
    remaining_부족인자: list[str] = []
    reason: str | None = None


class SimulationResult(ToolResult):
    """optimal_design 출력 계약."""
    lot_id: str | None = None
    targets: dict | None = None
    top_candidates: list[dict] = []
    error_reason: str | None = None
    reason: str | None = None


class ReliabilityResult(ToolResult):
    """reliability_simulation 출력 계약."""
    lot_id: str | None = None
    design: dict | None = None
    reliability_pass_rate: str | None = None
    error_reason: str | None = None


# ── Skill 3: mlcc-design-dispatch ────────────────────────────────────────────

class ScreenPlateResult(ToolResult):
    """search_screen_plate 출력 계약."""
    row_count: int = 0
    rows: list[dict] = []
    hint: str | None = None
    message: str | None = None


class DispatchResult(ToolResult):
    """dispatch_stacking_order 출력 계약."""
    message: str | None = None
    dispatch_id: str | None = None
    chip_prod_id: str | None = None
    lot_id: str | None = None
    design_values: dict | None = None
    hint: str | None = None
