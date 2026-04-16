"""Mock optimal_design tool for testing.

In production, this tool runs the DOE simulation engine to find
optimal MLCC design candidates given targets and parameter ranges.

This mock returns sample top-5 results so the agent dialogue flow
(result presentation, rerun with overrides) can be tested.

params.* are lists:
  - Multi-point list for DOE sweep: [4.8, 4.9, 5.0, 5.1, 5.2]
  - Single-value list for rerun/pinpoint: [5.0]
"""
import requests
import os
from ..utils.utils import fill_missing_columns, make_json_serializable
from google.adk.tools.tool_context import ToolContext
from ..schema.grid_search_input import API_FULL_COLUMN_LIST, TARGET_COLMNS
from ..db import db
from ..state_keys import lot_key, validation_key, targets_key, params_key, top_candidates_key

GRID_SEARCH_API_URL = os.getenv("GRID_SEARCH_API_URL")

def _get_sim_final_size(datas):
    ref_data = datas.get("datas", {}).get("ref", {})
    chip_prod_id = ref_data.get("chip_prod_id")
    active_powder_base = ref_data.get("active_powder_base")
    active_powder_additives = ref_data.get("active_powder_additives")

    query = """ 
        SELECT elec_l_thk, elec_w_thk, elec_t_thk 
        FROM public.mdh_elec_thk 
        WHERE chip_prod_id = %s 
          AND active_powder_base = %s 
          AND active_powder_additives = %s 
    """
    
    db_results = db.execute_read(query, (chip_prod_id, active_powder_base, active_powder_additives))

    if db_results:
        elec_l_thk = db_results[0]["elec_l_thk"]
        elec_w_thk = db_results[0]["elec_w_thk"]
        elec_t_thk = db_results[0]["elec_t_thk"]
        
        sim_list = datas.get("datas", {}).get("sim", [])
        for item in sim_list:
            try:
                item["final_l_pred"] = float(item.get("grinding_l_avg", 0)) + (float(elec_l_thk) * 1000)
            except:
                item["final_l_pred"] = None
            try:
                item["final_w_pred"] = float(item.get("grinding_w_avg", 0)) + (float(elec_w_thk) * 1000)
            except:
                item["final_w_pred"] = None
            try:
                item["final_t_pred"] = float(item.get("grinding_t_avg", 0)) + (float(elec_t_thk) * 1000)
            except:
                item["final_t_pred"] = None
        return datas
    else:
        sim_list = datas.get("datas", {}).get("sim", [])
        for item in sim_list:
            item["final_l_pred"] = None
            item["final_w_pred"] = None
            item["final_t_pred"] = None
        return datas

def optimal_design(
    tool_context: ToolContext,
    lot_id: str,
    target_electrode_c_avg: float,  # 타겟용량 (uF)
    target_grinding_l_avg: float,   # 타겟 연마L사이즈 (um)
    target_grinding_w_avg: float,   # 타겟 연마W사이즈 (um)
    target_grinding_t_avg: float,   # 타겟 연마T사이즈 (um)
    target_dc_cap: float,           # 타겟DC용량 (uF)
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
) -> dict:
    """
    Run DOE optimal design simulation.
    Calculates the top 5 optimal MLCC design candidates based on the reference LOT,
    target specifications, and DOE input parameters.

    Target units: electrode_c_avg/dc_cap in uF, grinding sizes (L/W/T) in um.
    Params units: sizes in um, thicknesses in um, layer counts in EA.
    """
    simulation_ver = 'ver4'
    lot_detail = tool_context.state.get(lot_key(lot_id))

    # 검증 프로세스
    validation = tool_context.state.get(validation_key(lot_id))
    if validation is None:
        return {
            "status": "error",
            "reason": "check_optimal_design 검증이 진행되지 않았음.",
        }
    if validation['부족인자'].get(simulation_ver, []) != []:
        return {
            "status": "error",
            "reason": f"check_optimal_design 검증에서 {simulation_ver}에 대해 부족인자가 존재함.",
        }

    processed_data = fill_missing_columns(lot_detail, API_FULL_COLUMN_LIST)
    
    if processed_data['grinding_w_avg'] == -1:
        processed_data['grinding_w_avg'] = processed_data['grinding_t_avg']

    payload = {
        "sim_type": f"{simulation_ver}",
        "data": {
            "ref": processed_data,
            "sim": processed_data
        },
        "targets": {
            "target_electrode_c_avg": round(target_electrode_c_avg, 5),
            "target_grinding_l_avg": round(target_grinding_l_avg, 1),
            "target_grinding_w_avg": round(target_grinding_w_avg, 1),
            "target_grinding_t_avg": round(target_grinding_t_avg, 1),
            "target_dc_cap": -1
        },
        "params": {
            "active_layer": active_layer,
            "ldn_avr_value": ldn_avr_value,
            "cast_dsgn_thk": cast_dsgn_thk,
            "screen_chip_size_leng": screen_chip_size_leng,
            "screen_mrgn_leng": screen_mrgn_leng,
            "screen_chip_size_widh": screen_chip_size_widh,
            "screen_mrgn_widh": screen_mrgn_widh,
            "cover_sheet_thk": cover_sheet_thk,
            "total_cover_layer_num": total_cover_layer_num,
            "gap_sheet_thk": gap_sheet_thk,
        }
    }

    payload['data']['sim']['optical_connectivity'] = 0.9
    clean_payload = make_json_serializable(payload)
    
    response = requests.post(GRID_SEARCH_API_URL, json=clean_payload, timeout=300)
    response.raise_for_status()
    datas = response.json()

    if not datas.get("datas").get("sim"):
        return {'status': 'error', 'error_reason': "시뮬레이션 결과 만족하는 설계값이 없음"}

    datas = _get_sim_final_size(datas)

    length = len(datas["datas"]["sim"])
    datas["datas"]["sim"].insert(0, datas["datas"]["ref"])
    datas["datas"]["sim"][0]["rank"] = "reference"

    top_k_value = 5
    if length < top_k_value:
        result = datas["datas"]["sim"][:length + 1]
    else:
        result = datas["datas"]["sim"][:6]

    filtered_result = [
        {
            key: round(float(row[key]), 4) if key in row and row[key] is not None 
                 and str(row[key]).replace('.', '', 1).isdigit() 
                 else row.get(key) 
            for key in TARGET_COLMNS
        } for row in result
    ]

    # 세션 state 저장: 이후 재실행·신뢰성 시뮬레이션에서 이 값을 재사용해 사용자에게 재확인하지 않음
    tool_context.state[top_candidates_key(lot_id)] = make_json_serializable(filtered_result)
    tool_context.state[targets_key(lot_id)] = {
        "target_electrode_c_avg": target_electrode_c_avg,
        "target_grinding_l_avg": target_grinding_l_avg,
        "target_grinding_w_avg": target_grinding_w_avg,
        "target_grinding_t_avg": target_grinding_t_avg,
        "target_dc_cap": target_dc_cap,
    }
    tool_context.state[params_key(lot_id)] = {
        "active_layer": active_layer,
        "ldn_avr_value": ldn_avr_value,
        "cast_dsgn_thk": cast_dsgn_thk,
        "screen_chip_size_leng": screen_chip_size_leng,
        "screen_mrgn_leng": screen_mrgn_leng,
        "screen_chip_size_widh": screen_chip_size_widh,
        "screen_mrgn_widh": screen_mrgn_widh,
        "cover_sheet_thk": cover_sheet_thk,
        "total_cover_layer_num": total_cover_layer_num,
        "gap_sheet_thk": gap_sheet_thk,
    }

    return {
        "status": "success",
        "lot_id": lot_id,
        "targets": {
            "target_electrode_c_avg": target_electrode_c_avg,
            "target_grinding_l_avg": target_grinding_l_avg,
            "target_grinding_w_avg": target_grinding_w_avg,
            "target_grinding_t_avg": target_grinding_t_avg,
            "target_dc_cap": target_dc_cap,
        },
        "top_candidates": filtered_result,
    }
