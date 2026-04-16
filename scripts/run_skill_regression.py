"""단일턴 regression 실행 엔트리 (얇은 래퍼).

멀티턴 인프라(scripts.multiturn.*)를 그대로 재사용한다.
단일턴 케이스는 1턴짜리 MultiturnTestCase 로 변환되어 동일 runner/evaluator 로
평가된다. scoring 없이 state/tool/skill 추적 + pass/fail 만 수집한다.
"""

import asyncio
from pathlib import Path

from mlcc_agent.agent import root_agent

from scripts.multiturn.io import load_single_turn_cases, write_summary_csv
from scripts.multiturn.runner import run_case


APP_NAME = "mlcc_skill_regression"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEST_CASE_PATH = PROJECT_ROOT / "tests" / "test_cases_mlcc.csv"
RESULT_DIR = PROJECT_ROOT / "artifacts" / "eval_results"
DETAILS_DIR = RESULT_DIR / "details"

# ADK SkillToolset 에 tool 로 노출되는 skill 이름.
# 여기 나열된 이름은 plugin 에서 'skill 호출' 로 분류된다.
KNOWN_SKILLS: set[str] = {
    "mlcc-rag-spec-selector",
    "mlcc-optimal-design-doe",
    "mlcc-design-dispatch",
}


async def main() -> None:
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)

    cases = load_single_turn_cases(TEST_CASE_PATH)
    print(f"[LOAD] cases={len(cases)} from {TEST_CASE_PATH}")

    results = []
    for case in cases:
        print(f"[RUN] {case.index}")
        result = await run_case(
            test_case=case,
            root_agent=root_agent,
            app_name=APP_NAME,
            details_dir=DETAILS_DIR,
            known_skill_names=KNOWN_SKILLS,
        )
        results.append(result)
        turn = result.turns[0] if result.turns else None
        skills = turn.skills_used if turn else []
        tools = turn.tools_used if turn else []
        print(
            f"  -> passed={result.passed} "
            f"skills={skills} tools={tools} "
            f"tokens in/out={result.total_input_tokens}/{result.total_output_tokens} "
            f"model_calls={result.total_model_requests} "
            f"elapsed={result.total_elapsed_seconds}s"
        )

    summary_path = write_summary_csv(RESULT_DIR, results)
    passed_n = sum(1 for r in results if r.passed)

    print("\n=== SUMMARY ===")
    print(f"total={len(results)} passed={passed_n} failed={len(results) - passed_n}")
    print(f"summary_csv={summary_path}")
    print(f"details_dir={DETAILS_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
