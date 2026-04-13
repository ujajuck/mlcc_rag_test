"""
오케스트레이터 ↔ subagent I/O 계약 (Schemas).

계층 구조:
  ┌──────────────────────────────────────┐
  │  오케스트레이터                        │
  │   ↓  AgentInput   (입력 어댑터 계약)   │
  │  subagent LLM + tools               │
  │   ↕  ToolResult 계열 (내부 계약)      │
  │   ↑  AgentOutput  (출력 어댑터 계약)   │
  │  오케스트레이터                        │
  └──────────────────────────────────────┘

규칙:
  - 오케스트레이터 경계: AgentInput / AgentOutput 만 의존
  - 내부 tool 반환: 각 ToolResult 서브클래스 + adapt_output() 을 통해 계약 검증
  - 오케스트레이터 포맷 변경 → AgentInput / AgentOutput 만 수정
  - 내부 구현 변경 → ToolResult 서브클래스 조정 (오케스트레이터 무관)
"""

from __future__ import annotations
from pydantic import BaseModel, ConfigDict


# ══════════════════════════════════════════════════════════════════════════════
# 오케스트레이터 경계 I/O (에이전트 레벨)
# ══════════════════════════════════════════════════════════════════════════════

class AgentInput(BaseModel):
    """오케스트레이터 → subagent 입력 계약.

    오케스트레이터가 이 subagent를 호출할 때 전달하는 구조.
    adapt_input()이 이 스키마로 정규화한 뒤 agent에 전달한다.

    파이프라인 단계별 필수/선택 필드:
      Skill 1 (스펙 선정)  : task 필수, 나머지 없음
      Skill 2 (DOE)       : task + chip_prod_id_list
      Skill 3 (dispatch)  : task + lot_id + design_values
    """
    model_config = ConfigDict(extra="ignore")  # 오케스트레이터 내부 필드 유입 차단

    task: str                               # 수행할 작업 자연어 지시
    chip_prod_id_list: list[str] | None = None  # Skill 2 진입 시
    lot_id: str | None = None              # Skill 3 진입 시
    design_values: dict | None = None      # Skill 3 dispatch 시


class AgentOutput(BaseModel):
    """subagent → 오케스트레이터 출력 계약.

    이 agent가 오케스트레이터에 반환하는 최종 구조.
    agent.py 의 output_schema 로 등록하면 LLM이 이 형식으로 응답을 강제한다.

    status 값:
      'completed'          – 요청 작업 완료
      'needs_confirmation' – 사용자 확인 대기 (dispatch 전 등)
      'error'              – 처리 실패
      'in_progress'        – 다음 단계 필요 (파이프라인 중간 결과)
    """
    model_config = ConfigDict(extra="forbid")  # 계약 외 필드 반환 금지

    status: str
    summary: str                            # 오케스트레이터가 파싱할 결과 요약
    next_step: str | None = None            # 오케스트레이터가 다음에 수행할 작업 힌트
    payload: dict | None = None             # 다음 단계로 넘길 구조화 데이터
                                            # e.g. {"chip_prod_id_list": [...]}
                                            #      {"lot_id": "AKB45A2"}
                                            #      {"design_values": {...}}


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
