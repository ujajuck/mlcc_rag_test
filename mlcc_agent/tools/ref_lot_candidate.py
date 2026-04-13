import logging
from google.adk.tools.tool_context import ToolContext
from typing import Literal, List
from ..db import db
from ..ports.adapter import adapt_output
from ..ports.schemas import RefLotResult

# from ..utils.tools import transform_kormap
# from ..utils.utils import save_analysis_result

REF_LOT_TOP_K = 20

# 기본 필터값 (하위호환성 유지)
DEFAULT_EXCLUDE_SCREEN_CODES = ['F', 'L', 'G', 'K', 'E']
DEFAULT_EXCLUDE_SCREEN_TYPES = ['3DJ', 'VLC', 'RHM', 'EXT', 'MPM', 'SHI']
DEFAULT_CUTTING_GRADE_FILTER = ['S 등급', 'A 등급', 'B 등급']
DEFAULT_MEASURE_GRADE_FILTER = ['S 등급', 'A 등급', 'B 등급']


async def find_ref_lot_candidate(
    chip_prod_id_list: List[str],
    cutting_grade_filter: List[str] = None,
    measure_grade_filter: List[str] = None,
    exclude_screen_codes: List[str] = None,
    exclude_screen_types: List[str] = None,
    require_reliability_pass: bool = True,
    top_k: int = REF_LOT_TOP_K,
):
    """
    *** Tool description ***
    find_chip_prod_id 툴 사용해서 찾은 인접기종에 있는 Chip LOT들중 Reference LOT를 선정하기 위하여 사용하는 Tool.
    REF LOT 후보를 검색하여 나온 후보들중 불량률 기준으로 제일 우수한 값을 가지는 lOT를 REF LOT로 선정한다.

    Args:
        chip_prod_id_list: 인접기종 chip_prod_id 리스트 (필수)
        cutting_grade_filter: 커팅 불량률 등급 필터. 기본: ['S 등급', 'A 등급', 'B 등급']
            예: ['S 등급'] (S등급만), ['S 등급', 'A 등급'] (S,A등급만)
        measure_grade_filter: 측정 불량률 등급 필터. 기본: ['S 등급', 'A 등급', 'B 등급']
        exclude_screen_codes: screen_durable_spec_name 6번째 자리 제외 코드. 기본: ['F','L','G','K','E']
        exclude_screen_types: screen_durable_spec_name 11~13번째 자리 제외 코드. 기본: ['3DJ','VLC','RHM','EXT','MPM','SHI']
        require_reliability_pass: 신뢰성 시험(HALT/8585/BURN-IN/DF/ODB) 통과 필수 여부. 기본: True
            False로 설정하면 신뢰성 NG인 LOT도 후보에 포함된다.
        top_k: 반환할 상위 LOT 수. 기본: 20

    | **불량률 기준(품질지표)** | **MES** | **추가 조건** | **상위 Lot 기준** |
    |----------------|-----------|---------------------------------------------------------------|-------------------|
    | 절단 불량율(공정) | RPT40254 | D0001 : 절단불량률 | S or A 등급 (없을 시 가장 높은 등급) |
    | 소성 검사 | RPT40156 | [대공정] 소성 대공정 - [검사] INSP0040 : 소성 검사 (CRACK/DELAM) | 판정 = **OK** |
    | 연마 BDV | RPT40156 | [대공정] 본연마 대공정 - [검사] INSP0209 : 연마 BDV 검사 | BDV AVG 높은 순으로 선정 |
    | 접촉성 불량 | RPT40335 | [검사] INSP0129 : 최종 전소 C/DF 검사 | 접촉성 = **0** |
    | 전극 Short | RPT40335 | [검사] INSP0129 : 최종 전소 C/DF 검사 | Short율 낮은 순으로 선정 |
    | 측정 불량율 | RPT40254 | D0063 : 측정불량률 | S or A 등급 (없을 시 가장 높은 등급) |
    | 신뢰성 HALT | RPT40514 | [검사] INSP0054 : 출하 HALT 검사 - [검사차수] 1 | 판정 = **OK** & Failure.=0 & IRLOW.=0 |
    | 신뢰성 BURN‐IN | RPT40514 | [검사] INSP0054 : 출하 BURN‐IN 검사 - [검사차수] 1 | 판정 = **OK** & Failure.=0 & IRLOW.=0 |
    | 신뢰성 8585 | RPT40514 | [검사] INSP0054 : 출하 8585 검사 - [검사차수] 1 | 판정 = **OK** & Failure.=0 & IRLOW.=0 |
    | 측정 양품 MOLD 검사 | RPT40156 | [대공정] 측정 대공정 - 검사 : INSP0597 : 측정 양품 MOLD 검사 | 판정 = **OK** |
    | DC‐bias | RPT40183 | [검사] INSP0211 : 출하 DC‐BIAS | 판정 = **OK** |
    """
    if not chip_prod_id_list:
        return []

    # 디폴트값 적용
    cutting_grades = cutting_grade_filter or DEFAULT_CUTTING_GRADE_FILTER
    measure_grades = measure_grade_filter or DEFAULT_MEASURE_GRADE_FILTER
    screen_codes = exclude_screen_codes or DEFAULT_EXCLUDE_SCREEN_CODES
    screen_types = exclude_screen_types or DEFAULT_EXCLUDE_SCREEN_TYPES

    lot_common_column = ["chip_prod_id", "lot_id", "cur_site_div", "lot_class"]
    lot_design_column = ["electrode_c_avg", "app_type", "active_powder_base", "ldn_avr_value", "cast_dsgn_thk", "grinding_t_avg", "active_layer"]
    lot_defect_column = ["design_input_date", "fr_def_01", "fr_def_02", "cutting_defect_rate", "tr_short_defect_rate", "bdv_avg", "measure_defect_rate", "pass_halt", "pass_8585", "pass_burn_in", "df_ispass", "odb_pass_yn"]

    target_columns = lot_common_column + lot_design_column + lot_defect_column
    columns_clause = ", ".join(target_columns)

    # 동적 필터 조건 구성
    conditions = ["chip_prod_id = ANY (%s)"]
    params = [chip_prod_id_list]

    # 스크린 제외 코드 필터
    if screen_codes:
        conditions.append("SUBSTRING(screen_durable_spec_name, 6, 1) NOT IN %s")
        params.append(tuple(screen_codes))

    if screen_types:
        conditions.append("SUBSTRING(screen_durable_spec_name, 11, 3) NOT IN %s")
        params.append(tuple(screen_types))

    # 필수 NOT NULL 컬럼 (설계 정보 완전성)
    required_not_null = [
        "grinding_l_avg", "grinding_t_avg", "electrode_c_avg",
        "cast_dsgn_thk", "ldn_avr_value",
        "screen_chip_size_leng", "screen_mrgn_leng",
        "screen_chip_size_widh", "screen_mrgn_widh",
        "cover_sheet_thk", "top_cover_layer_num", "bot_cover_layer_num",
        "active_layer", "ni_paste_metal_xrf", "ni_paste_powder_xrf",
    ]
    for col in required_not_null:
        conditions.append(f"{col} IS NOT NULL")

    # 불량률 등급 필터
    conditions.append("cutting_defect_rate IN %s")
    params.append(tuple(cutting_grades))
    conditions.append("measure_defect_rate IN %s")
    params.append(tuple(measure_grades))

    # 신뢰성 통과 필터 (선택적)
    if require_reliability_pass:
        conditions.append("pass_halt IS DISTINCT FROM 'NG'")
        conditions.append("pass_8585 IS DISTINCT FROM 'NG'")
        conditions.append("pass_burn_in IS DISTINCT FROM 'NG'")
        conditions.append("df_ispass IS DISTINCT FROM 'NG'")
        conditions.append("odb_pass_yn IS DISTINCT FROM 'NG'")

    # 접촉성 불량 0건
    conditions.append("fr_def_01 IS NOT DISTINCT FROM 0")
    conditions.append("fr_def_02 IS NOT DISTINCT FROM 0")

    # 소재/공정 정보 필수
    material_not_null = [
        "tf_chip_size_widh", "slurry_bet", "sintering_temp",
        "bt_import_d50", "active_binder", "active_powder_additives",
    ]
    for col in material_not_null:
        conditions.append(f"{col} IS NOT NULL")
    conditions.append("COALESCE(bt_import_mol_ratio, slurry_mole) IS NOT NULL")
    conditions.append("active_binder <> '실험'")

    where_clause = " AND ".join(conditions)

    # ORDER BY도 사용자 등급 필터에 맞춰 동적 구성
    cutting_order = "ARRAY[" + ", ".join(f"'{g}'" for g in cutting_grades) + "]"
    measure_order = "ARRAY[" + ", ".join(f"'{g}'" for g in measure_grades) + "]"

    sql = f"""
    SELECT {columns_clause}
    FROM public.mdh_base_view_dsgnagent_2
    WHERE {where_clause}
    ORDER BY
        array_position({cutting_order}, cutting_defect_rate),
        tr_short_defect_rate,
        bdv_avg DESC,
        array_position({measure_order}, measure_defect_rate);
    """

    results = db.execute_read(sql, tuple(params))

    if not results:
        hint = (
            "조건에 맞는 REF LOT 후보를 찾지 못하였음."
            "현재 버전에서는 2단자 Normal, MF, 3단자의 설계만 가능하기 때문일수도 있음. "
            "이부분을 사용자가 알수 있게 답변해주어야 함."
            "[예시답변]"
            "Reference LOT 후보군을 검색한 결과, 개발팀에서 요청한 11가지 항목(MCS, 신뢰성) 기준으로 충족하는 LOT이 없습니다."
            "현재 버전에서는 2단자 Normal, MF, 3단자의 설계만 가능하기 때문일수도 있습니다."
            "다시 기종을 선택해주시면 REF 후보 검색을 도와드리겠습니다."
            "[/예시답변]"
        )
        logging.debug("이전 쿼리 결과가 없어 상세 조회를 진행할 수 없습니다.")
        return adapt_output({'status': 'fail', 'error_reason': hint}, RefLotResult)

    ref_lot_candidates_results = [{key: row[key] for key in target_columns} for row in results]
    ref_lot_info = ref_lot_candidates_results[0]
    ref_lot_id = ref_lot_info["lot_id"]
    ref_lot_info_top_k = ref_lot_candidates_results[:top_k]
    
    results_mapping = ref_lot_info_top_k

    hint = (
        "REF LOT 후보를 산출하는 기준 : 불량률결과가 우수한 LOT 선정."
        "사용자에게 'ref_lot_candi_top_k'선정된 'ref_lot_id'에 대해 간단하게 LOT 이름만 언급하고, 후보 산출 근거에 대해 설명\n"
        "이후 추가 진행여부 확인받아야함."
        "브리핑은 간결하게."
        "[답변예시]"
        "선정된 Ref LOT는 BK8ST35 입니다. 선택한 인접기종 내 Lot들 중 여러 항목의 불량률이 낮은 조건으로 정렬하였습니다."
        "해당 LOT의 상세설계정보를 불러와 드릴까요?"
        "혹시 다른 LOT을 원하시면 해당 LOT을 말씀해주세요."
    )

    return adapt_output({
        'status': 'success',
        'ref_lot_id': ref_lot_id,
        'ref_lot_candi_top_k': results_mapping,
        "next_tool_use": "get_first_lot_detail",
        "hint": hint,
    }, RefLotResult)