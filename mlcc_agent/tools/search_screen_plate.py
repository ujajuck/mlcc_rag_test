"""search_screen_plate tool – 설계값에 매칭되는 스크린 동판 검색.

DOE/신뢰성 시뮬레이션으로 도출된 최종 설계값의 screen 관련 정보
(길이, 너비, 마진 등)를 충족하는 스크린 동판이 현재 공정에
실제 존재하는지 검색한다.

Production 모드에서는 실제 DB 테이블을 조회하고,
mock 모드에서는 샘플 데이터로 시뮬레이션한다.
"""

import os
import logging
from ..db import db

# ---------------------------------------------------------------------------
# 샘플 데이터 (mock 모드)
# 실제 운영 시에는 DB 조회 결과로 대체됨
# ---------------------------------------------------------------------------
_SAMPLE_SCREEN_PLATES = [
    {
        "screen_plate_id": "SP-2024-001",
        "screen_chip_size_leng": 3200,
        "screen_chip_size_widh": 2500,
        "screen_mrgn_leng": 50,
        "screen_mrgn_widh": 40,
        "screen_durable_spec_name": "ABCDE1FGHIJ2KLM",
        "plate_status": "사용중",
        "registered_date": "2024-11-15",
    },
    {
        "screen_plate_id": "SP-2024-002",
        "screen_chip_size_leng": 3200,
        "screen_chip_size_widh": 2500,
        "screen_mrgn_leng": 55,
        "screen_mrgn_widh": 45,
        "screen_durable_spec_name": "ABCDE2FGHIJ3KLM",
        "plate_status": "사용중",
        "registered_date": "2024-10-20",
    },
    {
        "screen_plate_id": "SP-2024-003",
        "screen_chip_size_leng": 1608,
        "screen_chip_size_widh": 800,
        "screen_mrgn_leng": 30,
        "screen_mrgn_widh": 25,
        "screen_durable_spec_name": "XYZAB1CDEFG2HIJ",
        "plate_status": "사용중",
        "registered_date": "2024-09-05",
    },
]


def search_screen_plate(
    screen_chip_size_leng: float,
    screen_chip_size_widh: float,
    screen_mrgn_leng: float = None,
    screen_mrgn_widh: float = None,
    tolerance: float = 5.0,
) -> dict:
    """설계값의 스크린 치수에 매칭되는 스크린 동판을 검색한다.

    DOE 또는 신뢰성 시뮬레이션 결과에서 도출된 screen 관련 설계값을 입력하면,
    현재 공정에서 사용 가능한 스크린 동판 중 해당 치수를 충족하는 동판을 반환한다.

    Args:
        screen_chip_size_leng: 스크린 칩 사이즈 길이 (um). 필수.
        screen_chip_size_widh: 스크린 칩 사이즈 너비 (um). 필수.
        screen_mrgn_leng: 스크린 마진 길이 (um). 선택. 지정 시 마진도 매칭.
        screen_mrgn_widh: 스크린 마진 너비 (um). 선택. 지정 시 마진도 매칭.
        tolerance: 허용 오차 (um). 기본 5.0um. 각 치수에 ± tolerance 범위로 매칭.

    Returns:
        dict with:
          - status: 'success' | 'no_match' | 'error'
          - row_count: 매칭된 동판 수
          - rows: 매칭된 동판 정보 리스트
          - hint: 사용자에게 안내할 메시지
    """
    # Production 모드 (DB 환경변수 존재 시)
    if os.environ.get("MLCC_DESIGN_DB_HOST"):
        return _search_production(
            screen_chip_size_leng, screen_chip_size_widh,
            screen_mrgn_leng, screen_mrgn_widh, tolerance,
        )

    # Mock 모드
    return _search_mock(
        screen_chip_size_leng, screen_chip_size_widh,
        screen_mrgn_leng, screen_mrgn_widh, tolerance,
    )


def _search_production(
    leng: float, widh: float,
    mrgn_leng: float, mrgn_widh: float,
    tolerance: float,
) -> dict:
    """실제 DB에서 스크린 동판을 검색한다."""
    # TODO: 실제 테이블명/컬럼명은 사용자로부터 확인 후 업데이트 필요
    conditions = [
        "screen_chip_size_leng BETWEEN %s AND %s",
        "screen_chip_size_widh BETWEEN %s AND %s",
    ]
    params = [
        leng - tolerance, leng + tolerance,
        widh - tolerance, widh + tolerance,
    ]

    if mrgn_leng is not None:
        conditions.append("screen_mrgn_leng BETWEEN %s AND %s")
        params.extend([mrgn_leng - tolerance, mrgn_leng + tolerance])

    if mrgn_widh is not None:
        conditions.append("screen_mrgn_widh BETWEEN %s AND %s")
        params.extend([mrgn_widh - tolerance, mrgn_widh + tolerance])

    where_clause = " AND ".join(conditions)

    # TODO: 실제 테이블명으로 교체 필요
    sql = f"""
    SELECT *
    FROM public.screen_plate_master
    WHERE {where_clause}
    ORDER BY registered_date DESC;
    """

    try:
        results = db.execute_read(sql, tuple(params))
        if not results:
            return _no_match_response(leng, widh, mrgn_leng, mrgn_widh)
        rows = [dict(r) for r in results]
        return {
            "status": "success",
            "row_count": len(rows),
            "rows": rows,
            "hint": (
                f"설계값(길이={leng}um, 너비={widh}um)에 매칭되는 스크린 동판이 "
                f"{len(rows)}건 확인되었습니다."
            ),
        }
    except Exception as e:
        logging.error(f"[Screen Plate Search Error] {e}")
        return {"status": "error", "message": str(e)}


def _search_mock(
    leng: float, widh: float,
    mrgn_leng: float, mrgn_widh: float,
    tolerance: float,
) -> dict:
    """Mock 데이터에서 스크린 동판을 검색한다."""
    matched = []
    for plate in _SAMPLE_SCREEN_PLATES:
        if not (abs(plate["screen_chip_size_leng"] - leng) <= tolerance):
            continue
        if not (abs(plate["screen_chip_size_widh"] - widh) <= tolerance):
            continue
        if mrgn_leng is not None and not (abs(plate["screen_mrgn_leng"] - mrgn_leng) <= tolerance):
            continue
        if mrgn_widh is not None and not (abs(plate["screen_mrgn_widh"] - mrgn_widh) <= tolerance):
            continue
        matched.append(plate)

    if not matched:
        return _no_match_response(leng, widh, mrgn_leng, mrgn_widh)

    return {
        "status": "success",
        "row_count": len(matched),
        "rows": matched,
        "hint": (
            f"설계값(길이={leng}um, 너비={widh}um)에 매칭되는 스크린 동판이 "
            f"{len(matched)}건 확인되었습니다."
        ),
    }


def _no_match_response(leng, widh, mrgn_leng, mrgn_widh):
    """매칭 결과가 없을 때 응답."""
    return {
        "status": "no_match",
        "row_count": 0,
        "rows": [],
        "hint": (
            f"설계값(길이={leng}um, 너비={widh}um)에 매칭되는 스크린 동판이 "
            "현재 공정에 존재하지 않습니다. "
            "스크린 동판 신규 제작이 필요할 수 있습니다."
        ),
    }
