"""search_running_chips tool – 설계값으로 현재 공정에 흐르는 실제 칩 정보 검색.

DOE/신뢰성 시뮬레이션에서 도출된 최종 설계값과 유사한 조건으로
현재 실제 생산 라인에서 흐르고 있는 칩들의 정보를 검색한다.
"""

import os
import logging
from ..db import db

# ---------------------------------------------------------------------------
# 샘플 데이터 (mock 모드)
# ---------------------------------------------------------------------------
_SAMPLE_RUNNING_CHIPS = [
    {
        "chip_prod_id": "CL32A106KOY8NNE",
        "lot_id": "BK8ST35",
        "line_name": "LINE-A3",
        "current_process": "적층",
        "active_layer": 158,
        "cast_dsgn_thk": 4.8,
        "electrode_c_avg": 10.5,
        "grinding_l_avg": 1550.0,
        "grinding_w_avg": 560.0,
        "grinding_t_avg": 640.0,
        "production_date": "2025-03-20",
    },
    {
        "chip_prod_id": "CL32A106MOY8NNC",
        "lot_id": "BK9AA12",
        "line_name": "LINE-A3",
        "current_process": "소성",
        "active_layer": 160,
        "cast_dsgn_thk": 4.9,
        "electrode_c_avg": 10.2,
        "grinding_l_avg": 1540.0,
        "grinding_w_avg": 555.0,
        "grinding_t_avg": 635.0,
        "production_date": "2025-03-18",
    },
    {
        "chip_prod_id": "CL10A106MQ8NNNC",
        "lot_id": "AK7BT99",
        "line_name": "LINE-B1",
        "current_process": "연마",
        "active_layer": 120,
        "cast_dsgn_thk": 3.5,
        "electrode_c_avg": 8.2,
        "grinding_l_avg": 1020.0,
        "grinding_w_avg": 510.0,
        "grinding_t_avg": 520.0,
        "production_date": "2025-03-22",
    },
]


def search_running_chips(
    chip_prod_id: str = None,
    active_layer: int = None,
    cast_dsgn_thk: float = None,
    electrode_c_avg: float = None,
    tolerance_pct: float = 10.0,
) -> dict:
    """현재 공정에서 흐르고 있는 실제 칩 정보를 검색한다.

    chip_prod_id 패턴 매칭 또는 설계 파라미터 범위 매칭으로 검색한다.
    두 조건을 동시에 사용할 수도 있다.

    Args:
        chip_prod_id: chip_prod_id 패턴 (ILIKE 지원, '%' 와일드카드 사용 가능). 선택.
        active_layer: 적층수 기준값. 선택. ±tolerance_pct% 범위 매칭.
        cast_dsgn_thk: cast 설계 두께 기준값 (um). 선택. ±tolerance_pct% 범위 매칭.
        electrode_c_avg: 전극 C 평균값 기준값. 선택. ±tolerance_pct% 범위 매칭.
        tolerance_pct: 수치 매칭 허용 오차 비율 (%). 기본 10%.

    Returns:
        dict with:
          - status: 'success' | 'no_match' | 'error'
          - row_count: 매칭 칩 수
          - rows: 매칭된 칩 정보 리스트
          - hint: 사용자 안내 메시지
    """
    if not any([chip_prod_id, active_layer, cast_dsgn_thk, electrode_c_avg]):
        return {
            "status": "error",
            "message": "검색 조건을 하나 이상 지정해야 합니다 (chip_prod_id, active_layer, cast_dsgn_thk, electrode_c_avg).",
            "row_count": 0,
            "rows": [],
        }

    # Production 모드
    if os.environ.get("MLCC_DESIGN_DB_HOST"):
        return _search_production(chip_prod_id, active_layer, cast_dsgn_thk, electrode_c_avg, tolerance_pct)

    # Mock 모드
    return _search_mock(chip_prod_id, active_layer, cast_dsgn_thk, electrode_c_avg, tolerance_pct)


def _search_production(chip_prod_id, active_layer, cast_dsgn_thk, electrode_c_avg, tolerance_pct):
    """실제 DB에서 현재 흐르는 칩 정보를 검색한다."""
    conditions = []
    params = []

    if chip_prod_id:
        conditions.append("chip_prod_id ILIKE %s")
        params.append(chip_prod_id)

    tol = tolerance_pct / 100.0
    if active_layer is not None:
        conditions.append("active_layer BETWEEN %s AND %s")
        params.extend([active_layer * (1 - tol), active_layer * (1 + tol)])

    if cast_dsgn_thk is not None:
        conditions.append("cast_dsgn_thk BETWEEN %s AND %s")
        params.extend([cast_dsgn_thk * (1 - tol), cast_dsgn_thk * (1 + tol)])

    if electrode_c_avg is not None:
        conditions.append("electrode_c_avg BETWEEN %s AND %s")
        params.extend([electrode_c_avg * (1 - tol), electrode_c_avg * (1 + tol)])

    where_clause = " AND ".join(conditions)

    # TODO: 실제 테이블명으로 교체 필요
    sql = f"""
    SELECT *
    FROM public.running_chips_view
    WHERE {where_clause}
    ORDER BY production_date DESC
    LIMIT 50;
    """

    try:
        results = db.execute_read(sql, tuple(params))
        if not results:
            return _no_match_response()
        rows = [dict(r) for r in results]
        return {
            "status": "success",
            "row_count": len(rows),
            "rows": rows,
            "hint": f"해당 설계값 조건으로 현재 흐르고 있는 칩이 {len(rows)}건 확인되었습니다.",
        }
    except Exception as e:
        logging.error(f"[Running Chips Search Error] {e}")
        return {"status": "error", "message": str(e), "row_count": 0, "rows": []}


def _search_mock(chip_prod_id, active_layer, cast_dsgn_thk, electrode_c_avg, tolerance_pct):
    """Mock 데이터에서 칩 정보를 검색한다."""
    import re
    tol = tolerance_pct / 100.0
    matched = []

    for chip in _SAMPLE_RUNNING_CHIPS:
        if chip_prod_id:
            pattern = chip_prod_id.replace("%", ".*").replace("_", ".")
            if not re.match(pattern, chip["chip_prod_id"], re.IGNORECASE):
                continue

        if active_layer is not None:
            if not (active_layer * (1 - tol) <= chip["active_layer"] <= active_layer * (1 + tol)):
                continue

        if cast_dsgn_thk is not None:
            if not (cast_dsgn_thk * (1 - tol) <= chip["cast_dsgn_thk"] <= cast_dsgn_thk * (1 + tol)):
                continue

        if electrode_c_avg is not None:
            if not (electrode_c_avg * (1 - tol) <= chip["electrode_c_avg"] <= electrode_c_avg * (1 + tol)):
                continue

        matched.append(chip)

    if not matched:
        return _no_match_response()

    return {
        "status": "success",
        "row_count": len(matched),
        "rows": matched,
        "hint": f"해당 설계값 조건으로 현재 흐르고 있는 칩이 {len(matched)}건 확인되었습니다.",
    }


def _no_match_response():
    return {
        "status": "no_match",
        "row_count": 0,
        "rows": [],
        "hint": "해당 설계값 조건으로 현재 공정에서 흐르고 있는 칩이 확인되지 않습니다.",
    }
