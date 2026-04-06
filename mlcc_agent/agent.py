"""MLCC Agent – Google ADK root agent definition.

This agent loads three skills via ADK's native skill system:
  1. mlcc-rag-spec-selector: Catalog-based MLCC preselection
  2. mlcc-optimal-design-doe: DOE optimal design simulation
  3. mlcc-design-dispatch: Design verification and stacking dispatch

Skills are loaded from their SKILL.md files using load_skill_from_dir,
preserving the progressive-disclosure structure (SKILL.md body + references/).

Additional tools provided:
  - search_rag: Query the SEMCO MLCC catalog vector DB
  - active_lineup_lookup: Check currently flowing chip_prod_id
  - search_query_database: Execute SQL SELECT on mdh_contiguous_condition_view_dsgnagent for adjacent-model search
  - check_optimal_design: Validate a reference LOT
  - optimal_design: Run DOE simulation
  - find_ref_lot_candidate: Select reference LOT from adjacent products
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
from .tools import (
    search_rag,
    active_lineup_lookup,
    search_query_database,
    check_optimal_design,
    optimal_design,
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
    instruction=(
        "당신은 삼성전기 MLCC 개발자를 도와주는 전문 에이전트입니다.\n"
        "세 가지 skill이 등록되어 있으며, 상황에 맞게 자동으로 활성화됩니다.\n\n"
        "- MLCC 스펙 선정, 기종 추천, 카탈로그 검색 → mlcc-rag-spec-selector skill\n"
        "- lot_id 기준 최적설계, DOE, 시뮬레이션 → mlcc-optimal-design-doe skill\n"
        "- 설계값 검증, 스크린 동판 검색, 적층투입지시 → mlcc-design-dispatch skill\n\n"
        "skill의 reference 문서는 각 skill 내부에서 자동으로 참조됩니다.\n"
        "한국어와 영어 모두 지원하되, 사용자의 언어에 맞춰 응답합니다."
    ),
    tools=[
        mlcc_skill_toolset,
        search_rag,
        active_lineup_lookup,
        search_query_database,
        check_optimal_design,
        optimal_design,
        find_ref_lot_candidate,
        search_screen_plate,
        search_running_chips,
        dispatch_stacking_order,
    ],
)
