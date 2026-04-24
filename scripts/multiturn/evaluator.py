"""턴 단위 pass/fail 판정. scoring 은 하지 않는다."""

from .types import TurnRecord, TurnTestSpec


def evaluate_turn(spec: TurnTestSpec, turn: TurnRecord) -> None:
    """TurnRecord 를 in-place 로 채점한다.

    실패 조건(하나라도 해당되면 fail):
        - 기대 skill 중 하나라도 skills_used 에 없음
        - 기대 tool 중 하나라도 tools_used 에 없음
        - 기대 state 의 key 가 state_snapshot 에 없음
        - 기대 state value 가 None 이 아닌데 actual 과 다름
        - required_keywords 중 하나라도 final_response 에 없음
        - 턴 실행 중 예외가 발생해서 error_message 가 기록됨

    Parameters:
        spec: 이번 턴의 기대값.
        turn: runner 가 채운 턴 결과.
    """
    reasons: list[str] = []

    # 1) skill
    for skill in spec.expected_skills or []:
        if skill not in turn.skills_used:
            reasons.append(f"missing expected skill: {skill}")

    # 2) tool
    for tool in spec.expected_tools or []:
        if tool not in turn.tools_used:
            reasons.append(f"missing expected tool: {tool}")

    # 3) state
    for key, expected_value in (spec.expected_state or {}).items():
        if key not in turn.state_snapshot:
            reasons.append(f"missing state key: {key}")
            continue
        if expected_value is None:
            continue
        actual_value = turn.state_snapshot.get(key)
        if actual_value != expected_value:
            reasons.append(
                f"state mismatch: {key} (expected={expected_value}, actual={actual_value})"
            )

    # 4) required keywords
    lower_response = (turn.final_response or "").lower()
    keyword_result: dict[str, bool] = {}
    for keyword in spec.required_keywords or []:
        present = keyword.lower() in lower_response
        keyword_result[keyword] = present
        if not present:
            reasons.append(f"missing required keyword: {keyword}")
    turn.required_keywords_present = keyword_result

    # 5) error
    if turn.error_message:
        reasons.append(f"turn error: {turn.error_message}")

    turn.fail_reasons = reasons
    turn.passed = len(reasons) == 0
