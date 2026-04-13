"""MLCC Agent – Google ADK root agent definition.

This agent loads three skills via ADK's native skill system:
  1. mlcc-rag-spec-selector: Catalog-based MLCC preselection
  2. mlcc-optimal-design-doe: DOE optimal design simulation
  3. mlcc-design-dispatch: Design verification and stacking dispatch

Skills are loaded from their SKILL.md files using load_skill_from_dir,
preserving the progressive-disclosure structure (SKILL.md body + references/).

Additional tools provided:
  - get_first_lot_detail: Load reference LOT design info into session state
  - search_rag: Query the SEMCO MLCC catalog vector DB
  - active_lineup_lookup: Check currently flowing chip_prod_id
  - search_query_database: Execute SQL SELECT on mdh_contiguous_condition_view_dsgnagent for adjacent-model search
  - check_optimal_design: Validate a reference LOT for simulation readiness
  - update_lot_reference: Fill missing factors for additional simulation versions
  - optimal_design: Run DOE simulation (params as lists)
  - reliability_simulation: Run reliability simulation (params as scalars)
  - find_ref_lot_candidate: Select reference LOT from adjacent products (chip_prod_id_list → lot_id)
  - search_screen_plate: Search screen plates matching design values
  - search_running_chips: Search chips currently in production
  - dispatch_stacking_order: Execute stacking dispatch order
"""

from pathlib import Path
from dotenv import load_dotenv
import os
from google.adk.agents import Agent, LlmAgent
from google.adk.skills import load_skill_from_dir
from google.adk.tools.skill_toolset import SkillToolset
from google.adk.models.lite_llm import LiteLlm
from .ports.schemas import AgentInput, AgentOutput
from .tools import (
    get_first_lot_detail,
    search_rag,
    active_lineup_lookup,
    search_query_database,
    check_optimal_design,
    update_lot_reference,
    optimal_design,
    reliability_simulation,
    find_ref_lot_candidate,
    search_screen_plate,
    search_running_chips,
    dispatch_stacking_order,
)

load_dotenv()

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SKILLS_DIR = _PROJECT_ROOT / "skills"

# Load skills from their directories via ADK's native skill system
spec_selector_skill = load_skill_from_dir(_SKILLS_DIR / "mlcc-rag-spec-selector")
doe_skill = load_skill_from_dir(_SKILLS_DIR / "mlcc-optimal-design-doe")
dispatch_skill = load_skill_from_dir(_SKILLS_DIR / "mlcc-design-dispatch")

mlcc_skill_toolset = SkillToolset(skills=[spec_selector_skill, doe_skill, dispatch_skill])

root_agent = LlmAgent(
    model=LiteLlm(model="openai/gpt-5-mini"), # LiteLLM model string format
    name="openai_agent",
    # ── 오케스트레이터 I/O 어댑터 ──────────────────────────────────────────────
    # input_schema:  오케스트레이터가 보내는 구조를 AgentInput으로 강제.
    #                오케스트레이터 포맷이 바뀌어도 ports/schemas.py 만 수정하면 됨.
    # output_schema: 이 agent의 최종 응답을 AgentOutput 구조로 강제.
    #                오케스트레이터는 자유 형식 텍스트 대신 이 계약된 JSON을 받음.
    #                내부 구현(tool, skill)이 바뀌어도 오케스트레이터 파싱 코드 불변.
    input_schema=AgentInput,
    output_schema=AgentOutput,
    instruction=(
        "당신은 삼성전기 MLCC 개발자를 도와주는 전문 에이전트입니다.\n"
        "세 가지 skill이 등록되어 있으며, 상황에 맞게 자동으로 활성화됩니다.\n"
        "한국어와 영어 모두 지원하되, 사용자의 언어에 맞춰 응답합니다.\n\n"
        "## 핵심 개념 구분 — 반드시 숙지\n\n"
        "| 개념 | 설명 | 예시 형태 | 용도 |\n"
        "| chip_prod_id | 제품 기종 코드 | CL32A106KOY8NNE (15~16자, CL로 시작) | 카탈로그 검색, 인접기종 탐색 |\n"
        "| lot_id | 제조 LOT 식별자 | AKB45A2 (짧은 영숫자) | DOE 시뮬레이션의 기준 LOT |\n\n"
        "## 전체 워크플로우 파이프라인\n\n"
        "[Skill 1: mlcc-rag-spec-selector]\n"
        "  고객 스펙 → 카탈로그 검색 → 인접기종 탐색 → chip_prod_id 목록 획득\n"
        "       ↓ chip_prod_id_list 전달\n"
        "[Skill 2: mlcc-optimal-design-doe]\n"
        "  find_ref_lot_candidate(chip_prod_id_list) → lot_id 선정\n"
        "  → get_first_lot_detail(lot_id) → check_optimal_design(lot_id)\n"
        "  → optimal_design / reliability_simulation → 최종 설계값 확정\n"
        "       ↓ 설계값(design_values) 전달\n"
        "[Skill 3: mlcc-design-dispatch]\n"
        "  스크린 동판 검색 → 칩 검색 → 적층투입지시\n\n"
        "인접기종 검색 후 사용자가 다음 단계를 요청하면:\n"
        "chip_prod_id_list → find_ref_lot_candidate → lot_id 확보 → DOE 스킬로 진행\n\n"
        "[금지사항]\n"
        "3. check_optimal_design 없이 optimal_design을 호출하지 마라.\n"
        "4. tool이 에러를 반환했는데 성공한 것처럼 응답하지 마라.\n"
        "5. tool 에러 후 선행 단계를 수행했으면, 에러가 났던 원래 tool을 반드시 재실행하라. 이전 에러 결과를 재사용하지 마라.\n\n"
        "## 응답 형식 (output_schema 준수)\n\n"
        "모든 최종 응답은 다음 JSON 구조로 반환해야 한다:\n"
        "  status  : 'completed' | 'needs_confirmation' | 'error' | 'in_progress'\n"
        "  summary : 수행 결과 요약 (사람이 읽을 수 있는 텍스트)\n"
        "  next_step: 오케스트레이터가 다음에 수행할 작업 힌트 (선택)\n"
        "  payload : 다음 단계로 넘길 구조화 데이터 (선택)\n"
        "            예: {\"chip_prod_id_list\": [...]}\n"
        "                {\"lot_id\": \"AKB45A2\"}\n"
        "                {\"design_values\": {...}}\n"
    ),
    tools=[
        mlcc_skill_toolset,
        get_first_lot_detail,
        search_rag,
        active_lineup_lookup,
        search_query_database,
        check_optimal_design,
        update_lot_reference,
        optimal_design,
        reliability_simulation,
        find_ref_lot_candidate,
        search_screen_plate,
        search_running_chips,
        dispatch_stacking_order,
    ],
)
