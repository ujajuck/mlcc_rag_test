"""
State key helpers for MLCC subagent.

오케스트레이터나 다른 subagent의 state와 키 충돌을 막기 위해
이 에이전트가 쓰는 모든 state key에 'mlcc' prefix를 붙인다.

사용 규칙:
  - state 쓰기/읽기는 반드시 이 모듈의 함수를 통해서만 한다.
  - tools/*.py 에서 bare string key (e.g. state[lot_id]) 를 직접 쓰지 않는다.
"""

_NS = "mlcc"


def lot_key(lot_id: str) -> str:
    """lot 상세정보 저장 key. (get_first_lot_detail, check_optimal_design, update_lot_reference 에서 사용)"""
    return f"{_NS}.lot.{lot_id}"


def validation_key(lot_id: str) -> str:
    """check_optimal_design 검증 결과 저장 key. (optimal_design, update_lot_reference 에서 읽음)"""
    return f"{_NS}.validation.{lot_id}"
