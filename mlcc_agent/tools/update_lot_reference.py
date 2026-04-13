"""Mock update_lot_reference tool for testing.

In production, this tool would update the in-memory reference state
for a given lot_id by overriding specific factor values provided
by the user — typically to fill in 부족인자 (missing factors).

This mock maintains a simple in-memory dict that persists within
the same process. It layers user-provided overrides on top of
the base reference data from check_optimal_design.
"""
# from .check_optimal_design import _VALID_LOTS
from google.adk.tools.tool_context import ToolContext
from ..ports.state_keys import lot_key, validation_key

# In-memory override store: {lot_id: {factor_name: value}}
_overrides: dict[str, dict] = {}

def update_lot_reference(tool_context: ToolContext, lot_id: str, factors: dict) -> dict:
    """
    Apply user-provided values to a LOT's missing factors.
    Use this after check_optimal_design reveals 부족인자.
    The user supplies the missing values, and this tool merges them into the reference 
    so subsequent simulations can proceed.

    Args:
        lot_id: The reference LOT identifier.
        factors: Dict of factor names and their values to override.

    Returns:
        A dict with:
        - status: "success"
        - lot_id: the lot
        - updated_factors: which factors were set/changed
        - ref_values: the full merged reference (base + overrides)
        - remaining_부족인자: factors still missing after this update
    """
    lot_id = lot_id.strip()
    lot_detail = tool_context.state.get(lot_key(lot_id))

    if not lot_detail:
        return {
            "status": "error",
            "reason": f"first lot detail Tool을 사용하여 {lot_id}의 정보를 얻어와야함."
        }

    lot_detail.update(factors)
    tool_context.state[lot_key(lot_id)] = lot_detail

    validation = tool_context.state.get(validation_key(lot_id))
    missing_base = validation['부족인자'] if validation else None

    remaining = [f for f in missing_base if f not in factors]

    return {
        "status": "success",
        "lot_id": lot_id,
        "updated_factors": factors,
        "ref_values": lot_detail,
        "remaining_부족인자": remaining,
    }