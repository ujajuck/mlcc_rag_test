"""단일/멀티턴 통합 평가 엔트리.

tests/test_cases_mlcc.csv 를 index 기준으로 그룹핑해 각 케이스를 한 ADK
세션에서 subindex 순서로 실행한다. subindex 가 하나인 케이스는 단일턴,
여러 개면 멀티턴 이다.

실행 결과:
    - artifacts/eval_results/mlcc_eval_<timestamp>.csv (subindex 당 한 행)
    - artifacts/eval_results/details/<index>.json (index 당 한 파일)
"""

import asyncio
from pathlib import Path

from mlcc_agent.agent import root_agent

from scripts.multiturn.io import load_test_cases, write_summary_csv
from scripts.multiturn.runner import run_case


APP_NAME = "mlcc_eval"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEST_CASE_PATH = PROJECT_ROOT / "tests" / "test_cases_mlcc.csv"
RESULT_DIR = PROJECT_ROOT / "artifacts" / "eval_results"
DETAILS_DIR = RESULT_DIR / "details"

# ADK SkillToolset 이 tool 인터페이스로 노출하는 skill 이름.
# 여기 나열된 이름은 plugin 에서 'skill 호출' 로 분류된다.
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
