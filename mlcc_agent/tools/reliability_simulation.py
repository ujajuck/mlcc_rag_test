"""Mock reliability_simulation tool for testing.

In production, this tool runs a reliability simulation for a single
MLCC design point, returning a pass probability (신뢰성 통과확률).

Unlike optimal_design which takes parameter ranges (lists) for DOE sweep,
this tool takes scalar values for one specific design configuration.
"""
import os
import copy
import requests
import logging
from pydantic import Field
from typing import Optional, Annotated
from google.adk.tools.tool_context import ToolContext
from ..db import db
from ..utils.utils import make_json_serializable, validate_required_columns, save_analysis_result

RELIABILITY_API_URL = os.getenv("RELIABILITY_API_URL")

async def reliability_simulation(
    tool_context: ToolContext, 
    lot_id: str, 
    active_layer: float, 
    ldn_avr_value: float, 
    cast_dsgn_thk: float, 
    screen_chip_size_leng: float, 
    screen_mrgn_leng: float, 
    screen_chip_size_widh: float, 
    screen_mrgn_widh: float, 
    cover_sheet_thk: float, 
    total_cover_layer_num: float, 
    halt_voltage: Annotated[Optional[float], Field(description="장기신뢰성 측정에 필요한 전압. 사용자가 단위를 입력한 경우 생략하고 숫자만 입력. Example: 6.3 ")] = 5, 
    halt_temperature: Annotated[Optional[float], Field(description="장기신뢰성 측정에 필요한 온도. 사용자가 단위를 입력한 경우 생략하고 숫자만 입력. Example: 85도 -> 85")] = 5,
):
    """ """
    # ref_lot_id = tool_context.state['ref_lot_id']
    # lot_detail = tool_context.state['ref_lot_detail_result']
    
    params_chip = {'lot_id': f'%{lot_id}%'}
    logging.debug(f"ref_lot={lot_id} 으로 신뢰성 예측을 위한 payload 생성")
    
    sql = """ 
    SELECT * FROM public.mdh_ai_design_base_view_dsgnagent WHERE lot_id LIKE %(lot_id)s 
    """
    
    payload = db.execute_read(sql, params_chip)[0]
    
    # 기본값 설정
    payload["dc_time"] = 1
    payload["dc_freq"] = 1
    payload["bias_volt"] = 1
    payload["long_term_halt_volt"] = halt_voltage
    payload["long_term_halt_tmpt"] = halt_temperature
    payload["bot_cover_layer_num"] = payload["top_cover_layer_num"]
    
    # 예외 처리: 둘 중 하나는 데이터가 있어서 missing에 없고, 나머지 하나만 missing에 있는 경우
    if payload.get("bt_import_mol_ratio") and payload.get("slurry_mole") is None:
        payload["slurry_mole"] = 0
    elif payload.get("slurry_mole") and payload.get("bt_import_mol_ratio") is None:
        payload["bt_import_mol_ratio"] = 0
        
    try:
        # 입력 파라미터 매핑
        payload["active_layer"] = active_layer
        payload["top_cover_thk"] = cover_sheet_thk
        payload["bot_cover_thk"] = cover_sheet_thk
        payload["cover_sheet_thk_type"] = cover_sheet_thk
        payload["top_cover_layer_num"] = total_cover_layer_num / 2
        payload["bot_cover_layer_num"] = total_cover_layer_num / 2
        payload["ldn_avr_value"] = ldn_avr_value
        payload["cast_dsgn_thk_type"] = cast_dsgn_thk
        payload["tf_chip_size_leng"] = screen_chip_size_leng
        payload["tf_mrgn_leng"] = screen_mrgn_leng
        payload["tf_chip_size_widh"] = screen_chip_size_widh
        payload["tf_mrgn_widh"] = screen_mrgn_widh
        
        # 계산 필드
        payload["tf_ovrl_leng"] = payload["tf_chip_size_leng"] - payload["tf_mrgn_leng"]
        payload["tf_ovrl_widh"] = payload["tf_chip_size_widh"] - payload["tf_mrgn_widh"]
        payload["tf_ovrl_area"] = payload["tf_ovrl_leng"] * payload["tf_ovrl_widh"]
        
        # 데이터 직렬화 및 API 요청
        clean_payload = make_json_serializable(payload)
        response = requests.post(RELIABILITY_API_URL, json={"data": clean_payload}, timeout=300)
        response.raise_for_status()
        
        datas = response.json()
        longterm_halt_reliability_prob = datas['results']['longterm_halt_reliability_prob'] * 100
        
        return {
            "status": "success",
            "lot_id": lot_id,
            "design": {
                "active_layer": active_layer,
                "ldn_avr_value": ldn_avr_value,
                "cast_dsgn_thk": cast_dsgn_thk,
                "screen_chip_size_leng": screen_chip_size_leng,
                "screen_mrgn_leng": screen_mrgn_leng,
                "screen_chip_size_widh": screen_chip_size_widh,
                "screen_mrgn_widh": screen_mrgn_widh,
                "cover_sheet_thk": cover_sheet_thk,
                "total_cover_layer_num": total_cover_layer_num,
            },
            "reliability_pass_rate": f"{round(longterm_halt_reliability_prob, 3)}%",
        }

    except requests.exceptions.Timeout:
        reason = "[API Error] 요청 시간이 초과되었습니다. (Timeout)"
        return {"status": "error", "error_reason": reason}
    except requests.exceptions.ConnectionError:
        reason = "[API Error] 서버에 연결할 수 없습니다. URL을 확인해주세요."
        return {"status": "error", "error_reason": reason}
    except requests.exceptions.HTTPError as e:
        reason = f"[API Error] 서버가 에러를 반환했습니다: {e}"
        return {"status": "error", "error_reason": reason}
    except Exception as e:
        reason = f"[API Error] 알 수 없는 오류 발생: {e}"
        return {"status": "error", "error_reason": reason}