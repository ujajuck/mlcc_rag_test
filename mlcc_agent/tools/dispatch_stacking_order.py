"""dispatch_stacking_order tool – 적층투입지시 API 호출.

DOE/신뢰성 시뮬레이션에서 확정된 최종 설계값으로
적층 공정에 투입 지시를 실행한다.

이 tool은 실제 생산 라인에 영향을 주는 행위이므로,
스킬에서 반드시 사용자 최종 확인을 거친 후에만 호출해야 한다.
"""

import os
import logging
import requests

# ---------------------------------------------------------------------------
# API 엔드포인트 (환경변수)
# ---------------------------------------------------------------------------
DISPATCH_API_URL = os.environ.get("DISPATCH_API_URL", "")


def dispatch_stacking_order(
    chip_prod_id: str,
    lot_id: str,
    design_values: dict,
    user_confirmed: bool = False,
) -> dict:
    """최종 설계값으로 적층투입지시를 실행한다.

    이 tool은 실제 생산 라인에 투입 명령을 보내는 위험한 행위이다.
    반드시 user_confirmed=True가 설정된 상태에서만 실행된다.
    스킬에서 사용자에게 최종 설계값을 보여주고 "투입하시겠습니까?" 확인을 받은 후
    이 tool을 호출해야 한다.

    Args:
        chip_prod_id: 대상 chip_prod_id (필수)
        lot_id: 대상 lot_id (필수)
        design_values: 최종 설계값 dict. 최소한 아래 필드를 포함해야 한다:
            - active_layer (int): 적층수
            - cast_dsgn_thk (float): cast 설계 두께
            - electrode_c_avg (float): 전극 C 평균
            - ldn_avr_value (float): LDN 평균값
            - screen_chip_size_leng (float): 스크린 칩 길이
            - screen_chip_size_widh (float): 스크린 칩 너비
            - screen_mrgn_leng (float): 스크린 마진 길이
            - screen_mrgn_widh (float): 스크린 마진 너비
            - cover_sheet_thk (float): 커버시트 두께
            - gap_sheet (float): 갭시트
        user_confirmed: 사용자 최종 확인 여부. False이면 투입하지 않고 확인 요청 반환.

    Returns:
        dict with:
          - status: 'success' | 'awaiting_confirmation' | 'error'
          - message: 결과 메시지
          - dispatch_id: 투입지시 ID (성공 시)
    """
    # 사용자 확인 미완료 시 → 확인 요청 반환
    if not user_confirmed:
        return {
            "status": "awaiting_confirmation",
            "message": "적층투입지시를 실행하기 전에 사용자 최종 확인이 필요합니다.",
            "hint": (
                "아래 설계값으로 적층투입지시를 실행합니다. 확인해주세요.\n"
                f"  chip_prod_id: {chip_prod_id}\n"
                f"  lot_id: {lot_id}\n"
                f"  설계값: {design_values}\n"
                "투입을 진행하시겠습니까? (예/아니오)"
            ),
            "chip_prod_id": chip_prod_id,
            "lot_id": lot_id,
            "design_values": design_values,
        }

    # 필수 필드 검증
    required_fields = [
        "active_layer", "cast_dsgn_thk", "electrode_c_avg", "ldn_avr_value",
        "screen_chip_size_leng", "screen_chip_size_widh",
        "screen_mrgn_leng", "screen_mrgn_widh",
        "cover_sheet_thk",
    ]
    missing = [f for f in required_fields if f not in design_values]
    if missing:
        return {
            "status": "error",
            "message": f"설계값에 필수 필드가 누락되었습니다: {missing}",
        }

    # Production 모드 (API URL 존재 시)
    if DISPATCH_API_URL:
        return _dispatch_production(chip_prod_id, lot_id, design_values)

    # Mock 모드
    return _dispatch_mock(chip_prod_id, lot_id, design_values)


def _dispatch_production(chip_prod_id: str, lot_id: str, design_values: dict) -> dict:
    """실제 적층투입지시 API를 호출한다."""
    # TODO: 실제 API 엔드포인트/요청 형식은 사용자 확인 후 교체
    payload = {
        "chip_prod_id": chip_prod_id,
        "lot_id": lot_id,
        "design_values": design_values,
    }

    try:
        response = requests.post(
            f"{DISPATCH_API_URL}/dispatch",
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        result = response.json()

        return {
            "status": "success",
            "message": (
                f"적층투입지시가 성공적으로 실행되었습니다.\n"
                f"chip_prod_id: {chip_prod_id}, lot_id: {lot_id}"
            ),
            "dispatch_id": result.get("dispatch_id", "N/A"),
            "chip_prod_id": chip_prod_id,
            "lot_id": lot_id,
        }
    except requests.exceptions.RequestException as e:
        logging.error(f"[Dispatch API Error] {e}")
        return {
            "status": "error",
            "message": f"적층투입지시 API 호출 실패: {str(e)}",
        }


def _dispatch_mock(chip_prod_id: str, lot_id: str, design_values: dict) -> dict:
    """Mock 모드: 투입지시를 시뮬레이션한다."""
    import uuid
    mock_dispatch_id = f"MOCK-{uuid.uuid4().hex[:8].upper()}"

    return {
        "status": "success",
        "message": (
            f"[MOCK] 적층투입지시가 성공적으로 실행되었습니다.\n"
            f"chip_prod_id: {chip_prod_id}, lot_id: {lot_id}\n"
            f"dispatch_id: {mock_dispatch_id}"
        ),
        "dispatch_id": mock_dispatch_id,
        "chip_prod_id": chip_prod_id,
        "lot_id": lot_id,
        "design_values": design_values,
    }
