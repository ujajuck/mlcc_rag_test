"""
State key helpers — 다른 subagent와 state 충돌 방지용 네임스페이스.

이 에이전트가 세션 state에 쓰는 모든 키는 이 모듈을 통해서만 만든다.
같은 세션을 공유하는 다른 subagent와 key가 겹치지 않도록 'mlcc_design' prefix를 붙인다.
"""

_NS = "mlcc_design"


def lot_key(lot_id: str) -> str:
    """lot 상세정보 저장 key. get_first_lot_detail → check/update/optimal_design 에서 사용."""
    return f"{_NS}.lot.{lot_id}"


def validation_key(lot_id: str) -> str:
    """check_optimal_design 검증 결과 저장 key. optimal_design / update_lot_reference 에서 읽음."""
    return f"{_NS}.validation.{lot_id}"
