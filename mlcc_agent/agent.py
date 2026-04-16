"""MLCC Agent – Google ADK root agent definition.

This agent loads three skills via ADK's native skill system:
  1. mlcc-rag-spec-selector: Catalog-based MLCC preselection
  2. mlcc-optimal-design-doe: REF LOT selection/validation + DOE simulation + reliability
  3. mlcc-design-dispatch: Design verification and stacking dispatch

Session state namespace: mlcc_design.* (see skills/session-state.md)
State key helpers: mlcc_agent/state_keys.py
"""

from pathlib import Path
from dotenv import load_dotenv
import os
from google.adk.agents import Agent, LlmAgent
from google.adk.skills import load_skill_from_dir
from google.adk.tools.skill_toolset import SkillToolset
from google.adk.models.lite_llm import LiteLlm
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

spec_selector_skill = load_skill_from_dir(_SKILLS_DIR / "mlcc-rag-spec-selector")
doe_skill = load_skill_from_dir(_SKILLS_DIR / "mlcc-optimal-design-doe")
dispatch_skill = load_skill_from_dir(_SKILLS_DIR / "mlcc-design-dispatch")

mlcc_skill_toolset = SkillToolset(skills=[spec_selector_skill, doe_skill, dispatch_skill])

root_agent = LlmAgent(
    model=LiteLlm(model="openai/gpt-5-mini"),
    name="openai_agent",
    instruction=(
        "당신은 삼성전기 MLCC 개발자를 도와주는 전문 에이전트입니다.\n"
        "세 가지 skill이 등록되어 있으며, 상황에 맞게 자동으로 활성화됩니다.\n"
        "한국어와 영어 모두 지원하되, 사용자의 언어에 맞춰 응답합니다.\n\n"
        "## 핵심 개념 구분\n\n"
        "| 개념 | 예시 | 용도 |\n"
        "|---|---|---|\n"
        "| chip_prod_id | CL32A106KOY8NNE (15~16자, CL로 시작) | 카탈로그 검색, 인접기종 탐색 |\n"
        "| lot_id | AKB45A2 (짧은 영숫자) | DOE 시뮬레이션의 기준 LOT |\n\n"
        "## 3-Skill 파이프라인\n\n"
        "[Skill 1: mlcc-rag-spec-selector]\n"
        "  고객 스펙 → 카탈로그 검색 → 인접기종 탐색 → chip_prod_id 목록 확정\n"
        "  ↓ mlcc_design.session.chip_prod_id_list 저장\n\n"
        "[Skill 2: mlcc-optimal-design-doe]\n"
        "  find_ref_lot_candidate → lot_id 선정 → 검증 → DOE/신뢰성 시뮬레이션 → 최종 설계값 확정\n"
        "  ↓ mlcc_design.final_design.{lot_id} 저장\n\n"
        "[Skill 3: mlcc-design-dispatch]\n"
        "  스크린 동판 검색 → 칩 검색 → 적층투입지시\n\n"
        "## 세션 상태 활용 (mlcc_design.* 네임스페이스)\n\n"
        "이미 기록된 값은 사용자에게 재확인하지 말고 재사용한다.\n"
        "- mlcc_design.session.active_lot_id 있으면 → lot_id 재확인 불필요\n"
        "- mlcc_design.validation.{lot_id} 있으면 → 검증 재실행 불필요\n"
        "- mlcc_design.targets.{lot_id} 있으면 → target 재수집 불필요\n"
        "- mlcc_design.top_candidates.{lot_id} 있으면 → 기존 DOE 결과 재사용 가능\n"
        "- mlcc_design.halt_conditions 있으면 → halt 조건 재확인 불필요\n\n"
        "## 금지사항\n\n"
        "- check_optimal_design 없이 optimal_design을 호출하지 마라\n"
        "- get_first_lot_detail 없이 check_optimal_design을 호출하지 마라\n"
        "- tool이 에러를 반환했는데 성공한 것체럼 응답하지 마라\n"
        "- tool 에러 후 선행 단계를 수행했으면, 에러난 원래 tool을 반드시 재실행하라\n"
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
