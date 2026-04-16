"""
State key helpers — 다른 subagent와 state 충돌 방지용 네임스페이스.

이 에이전트가 세션 state에 쓰는 모든 키는 이 모듈을 통해서만 만든다.
같은 세션을 공유하는 다른 subagent와 key가 겹치지 않도록 'mlcc_design' prefix를 붙인다.

키 목록 전체와 스킬 간 흐름은 skills/session-state.md를 참고한다.
"""

_NS = "mlcc_design"


# ─── LOT 데이터 ───────────────────────────────────────────────────────────────

def lot_key(lot_id: str) -> str:
    """lot 상세정보 저장 key. get_first_lot_detail → check/update/optimal_design에서 사용."""
    return f"{_NS}.lot.{lot_id}"


def validation_key(lot_id: str) -> str:
    """check_optimal_design 검증 결과 저장 key.

    저장 구조: {fully_satisfied_versions, 충족인자, 부족인자}
    optimal_design / update_lot_reference에서 읽음.
    """
    return f"{_NS}.validation.{lot_id}"


# ─── 세션 식별자 ──────────────────────────────────────────────────────────────

def session_key(field: str) -> str:
    """세션 수준 단일 값 저장 key.

    field 예시:
      'chip_prod_id_list'   — 인접기종 chip_prod_id 목록 (mlcc-rag-spec-selector 출력)
      'active_lot_id'       — 현재 세션 활성 lot_id (mlcc-lot-validation 출력)
      'active_chip_prod_id' — active_lot_id의 chip_prod_id (mlcc-lot-validation 출력)
    """
    return f"{_NS}.session.{field}"


# ─── DOE 설정 (lot_id 스코프) ─────────────────────────────────────────────────

def targets_key(lot_id: str) -> str:
    """optimal_design target 5개 저장 key. 사용자 입력 후 기록.

    저장 구조: {
        target_electrode_c_avg: float (uF),
        target_grinding_l_avg: float (um),
        target_grinding_w_avg: float (um),
        target_grinding_t_avg: float (um),
        target_dc_cap: float (uF),
    }
    """
    return f"{_NS}.targets.{lot_id}"


def params_key(lot_id: str) -> str:
    """optimal_design params 10개 저장 key.

    초기 DOE: 각 항목이 다중 포인트 list.
    재실행: 각 항목이 단일값 list [value].

    저장 구조: {
        active_layer: list[int],
        ldn_avr_value: list[float],
        cast_dsgn_thk: list[float],
        screen_chip_size_leng: list[float],
        screen_mrgn_leng: list[float],
        screen_chip_size_widh: list[float],
        screen_mrgn_widh: list[float],
        cover_sheet_thk: list[float],
        total_cover_layer_num: list[int],
        gap_sheet_thk: list[float],
    }
    """
    return f"{_NS}.params.{lot_id}"


def top_candidates_key(lot_id: str) -> str:
    """optimal_design 결과 top_candidates 저장 key.

    저장 구조: list[{rank, design, predicted, gap}]
    """
    return f"{_NS}.top_candidates.{lot_id}"


# ─── 신뢰성 설정 (세션 전체 스코프) ─────────────────────────────────────────

def halt_conditions_key() -> str:
    """reliability_simulation halt 조건 저장 key. lot_id 변경 시에도 유지.

    저장 구조: {halt_voltage: float, halt_temperature: float}
    세션 중 한 번만 사용자에게 확인하면 된다.
    """
    return f"{_NS}.halt_conditions"


# ─── 최종 설계 (lot_id 스코프) ────────────────────────────────────────────────

def final_design_key(lot_id: str) -> str:
    """사용자 확정 최종 설계값 저장 key. mlcc-design-dispatch가 읽음.

    저장 구조: {
        chip_prod_id: str,
        lot_id: str,
        active_layer: int,
        cast_dsgn_thk: float,
        electrode_c_avg: float,
        ldn_avr_value: float,
        screen_chip_size_leng: float,
        screen_chip_size_widh: float,
        screen_mrgn_leng: float,
        screen_mrgn_widh: float,
        cover_sheet_thk: float,
    }
    """
    return f"{_NS}.final_design.{lot_id}"
