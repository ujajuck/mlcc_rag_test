"""Mock check_optimal_design tool for testing.

In production, this tool verifies whether a given lot_id has
sufficient reference data to run DOE simulation.

This mock returns sample responses for known test lot IDs,
including the actual factor values for 충족인자.
"""
import os
import math
import requests

from ..db import db
from google.adk.tools.tool_context import ToolContext
from ..state_keys import lot_key, validation_key

# 환경 변수 및 상수 설정
VALIDATION_API_URL = os.getenv("VALIDATION_API_URL")

def check_optimal_design(tool_context: ToolContext, lot_id: str) -> dict:
    """
    Check whether a reference LOT is valid for DOE simulation.
    
    Verifies that the given lot_id has all required reference factors.
    Returns both factor names AND their current values for 충족인자.
    """
    lot_id = lot_id.strip()
    
    # 1. State 체크 및 데이터 로드
    if not tool_context.state.get(lot_key(lot_id)):
        return {
            "status": "error",
            "reason": f"first lot detail Tool을 사용하여 {lot_id}의 정보를 얻어와야함.",
        }

    lot_detail = tool_context.state.get(lot_key(lot_id))
    missing_info = {}
    fulfilled_info = {}
    ver_list = ["ver1", "ver2", "ver3", "ver4"]
    
    # 2. API를 통한 필수 컬럼 정보 수집
    require_columns = []
    for ver in ver_list:
        response = requests.get(url=f"{VALIDATION_API_URL}{ver}")
        result = response.json()
        
        # ver_list의 요소를 키로 사용하는 딕셔너리 생성
        cols = {ver: result['inputs']}
        require_columns.append(cols)

    # 3. 필수 컬럼과 실제 데이터 비교 검증
    for ver_dict in require_columns:
        for version, required_cols in ver_dict.items():
            missing_cols = []
            fulfilled_cols = {}

            for col in required_cols:
                val = lot_detail.get(col)

                # None이거나 NaN인 경우 누락으로 처리
                if val is None or (isinstance(val, float) and math.isnan(val)):
                    missing_cols.append(col)
                else:
                    fulfilled_cols[col] = val
            
            missing_info[version] = missing_cols
            fulfilled_info[version] = fulfilled_cols

    # 4. 결과 상태 결정 및 Context 저장
    # 한 개 이상의 버전이 부족인자 0이면 시뮬레이션 진행 가능 (success)
    fully_satisfied = [v for v, cols in missing_info.items() if len(cols) == 0]
    partially_missing = {v: cols for v, cols in missing_info.items() if len(cols) > 0}
    status = "success" if fully_satisfied else "warning"

    tool_context.state[validation_key(lot_id)] = {
        "충족인자": fulfilled_info,
        "부족인자": missing_info,
        "fully_satisfied_versions": fully_satisfied,
    }

    return {
        "status": status,
        "lot_id": lot_id,
        "fully_satisfied_versions": fully_satisfied,
        "partially_missing_versions": partially_missing,
        "부족인자": missing_info,
        "충족인자": fulfilled_info,
    }