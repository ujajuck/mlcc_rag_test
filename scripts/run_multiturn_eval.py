"""멀티턴 평가 실행 엔트리.

CSV (tests/test_cases_mlcc_multiturn_v2.csv) 를 읽어 각 케이스를 한 세션에서
턴 순서대로 실행하고, 요약 CSV + 케이스별 상세 JSON 을 저장한다.
"""

import asyncio
from pathlib import Path

from mlcc_agent.agent import root_agent

from scripts.multiturn.io import load_test_cases, write_summary_csv
from scripts.multiturn.runner import run_case


APP_NAME = "mlcc_multiturn_eval"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEST_CASE_PATH = PROJECT_ROOT / "tests" / "test_cases_mlcc_multiturn_v2.csv"
RESULT_DIR = PROJECT_ROOT / "artifacts" / "multiturn_eval"
DETAILS_DIR = RESULT_DIR / "details"

# ADK SkillToolset 에 실려 tool 로 노출되는 skill 이름.
# 필요 시 추가/수정. 여기 나열된 이름은 plugin 에서 'skill 호출' 로 분류된다.
KNOWN_SKILLS: set[str] = {
    "mlcc-rag-spec-selector",
    "mlcc-optimal-design-doe",
    "mlcc-design-dispatch",
}


async def main() -> None:
    DETAILS_DIR.mkdir(parents=True, exist_ok=True)

    cases = load_test_cases(TEST_CASE_PATH)
    print(f"[LOAD] cases={len(cases)} from {TEST_CASE_PATH}")

    results = []
    for case in cases:
        print(f"[RUN] {case.index} (turns={len(case.turns)})")
        result = await run_case(
            test_case=case,
            root_agent=root_agent,
            app_name=APP_NAME,
            details_dir=DETAILS_DIR,
            known_skill_names=KNOWN_SKILLS,
        )
        results.append(result)
        per_turn_pass = [t.passed for t in result.turns]
        print(
            f"  -> passed={result.passed} turns_passed={per_turn_pass} "
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
