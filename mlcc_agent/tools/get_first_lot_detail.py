import logging
from google.adk.tools.tool_context import ToolContext
from ..utils.utils import make_json_serializable
from ..state_keys import lot_key

async def get_first_lot_detail(tool_context: ToolContext, lot_id: str) -> dict:
    """
    REF LOT로 선정된 LOT의 정보를 불러오는 Tool.

    - 결과는 Artifact(Table) 형태로 제시되므로 Markdown 테이블 생성을 지양함.
    - 브리핑 후 다음 단계(설계 시뮬레이션 등)에 대한 컨펌 필요.
    """

    # 1. 컬럼 정의
    lot_common_column = ["chip_prod_id", "lot_id", "cur_site_div"]
    lot_design_column = [
        "electrode_c_avg", "app_type", "active_powder_base",
        "ldn_cv_value", "cast_dsgn_thk"
    ]
    target_columns = lot_common_column + lot_design_column

    # 2. LOT ID 추출 및 유효성 검사
    try:
        target_lot_id = lot_id.strip()
    except (KeyError, AttributeError):
        logging.debug("결과 데이터에 'lot_id' 컬럼이 없거나 형식이 잘못되었습니다.")
        return {"status": "error", "error_reason": "ref lot identifier missing"}

    logging.debug(f"LOT ID [{target_lot_id}]에 대한 상세 정보를 조회합니다.")

    # 3. 데이터베이스 조회
    sql_detail = "SELECT * FROM public.mdh_base_view_dsgnagent_2 WHERE lot_id = %s"
    detail_result = db.execute_read(sql_detail, (target_lot_id,))

    if not detail_result:
        return {
            "status": "error",
            "error_reason": "REF LOT 검색에 실패했습니다. 다른 LOT를 지정하도록 유도하세요.",
        }

    # 4. 결과 가공 및 State 저장
    ref_lot_design_info = [
        {key: row[key] for key in target_columns if key in row}
        for row in detail_result
    ]
    tool_context.state[lot_key(target_lot_id)] = make_json_serializable(detail_result)

    # 5. 사용자 가이드(Hint) 설정
    hint = (
        "선택된 <ref LOT> LOT의 설계 정보입니다.\n"
        "(이미 Artifact에 정보가 표시되었으므로 상세 정보 추가 설명은 생략합니다.)\n\n"
        "다음 단계로 진행 가능한 옵션은 다음과 같습니다:\n"
        "1. 초급 설계 시뮬레이션(자동 추천 설계) 진행\n"
        "2. 고급 설계 시뮬레이션(수동 설계) 진행\n\n"
        "참고: 모재 및 첨가제가 동일한 조건에서 설계 인자만 변경하여 진행합니다.\n"
        "레퍼런스 LOT를 변경하고 싶으시면 말씀해 주세요."
    )

    return {
        "status": "success",
        "ref_lot_design_info": ref_lot_design_info,
        "hint": hint,
    }
