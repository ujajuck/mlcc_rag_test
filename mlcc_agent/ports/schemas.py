"""
오케스트레이터 ↔ subagent I/O 계약 (Agent-level Schemas).

이 파일이 관리하는 유일한 계약:
  AgentInput  – 오케스트레이터 → subagent 입력 형식
  AgentOutput – subagent → 오케스트레이터 출력 형식

변경 정책:
  - 오케스트레이터 포맷이 바뀌면 이 파일 + adapter.adapt_input() 만 수정한다.
  - tool 내부 반환 구조는 이 파일과 무관하다.
"""

from __future__ import annotations
from pydantic import BaseModel, ConfigDict


class AgentInput(BaseModel):
    """오케스트레이터 → subagent 입력 계약.

    파이프라인 단계별 필수/선택 필드:
      Skill 1 (스펙 선정)  : task 필수, 나머지 없음
      Skill 2 (DOE)       : task + chip_prod_id_list
      Skill 3 (dispatch)  : task + lot_id + design_values
    """
    model_config = ConfigDict(extra="ignore")  # 오케스트레이터 내부 필드 유입 차단

    task: str                                   # 수행할 작업 자연어 지시
    chip_prod_id_list: list[str] | None = None  # Skill 2 진입 시
    lot_id: str | None = None                   # Skill 3 진입 시
    design_values: dict | None = None           # Skill 3 dispatch 시


class AgentOutput(BaseModel):
    """subagent → 오케스트레이터 출력 계약.

    agent.py 의 output_schema 로 등록 → LLM이 이 JSON 구조로 응답을 강제한다.

    status 값:
      'completed'          – 요청 작업 완료
      'needs_confirmation' – 사용자 확인 대기 (dispatch 전 등)
      'error'              – 처리 실패
      'in_progress'        – 다음 단계 필요 (파이프라인 중간 결과)
    """
    model_config = ConfigDict(extra="forbid")   # 계약 외 필드 반환 금지

    status: str
    summary: str                                # 결과 요약 (사람이 읽을 수 있는 텍스트)
    next_step: str | None = None                # 오케스트레이터 다음 수행 작업 힌트
    payload: dict | None = None                 # 다음 단계로 넘길 구조화 데이터
                                                # e.g. {"chip_prod_id_list": [...]}
                                                #      {"lot_id": "AKB45A2"}
                                                #      {"design_values": {...}}
