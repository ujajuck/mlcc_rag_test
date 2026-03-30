"""Mock update_lot_reference tool for testing.

In production, this tool would update the in-memory reference state
for a given lot_id by overriding specific factor values provided
by the user — typically to fill in 부족인자 (missing factors).

This mock maintains a simple in-memory dict that persists within
the same process. It layers user-provided overrides on top of
the base reference data from check_optimal_design.
"""

from .check_optimal_design import _VALID_LOTS

# In-memory override store: {lot_id: {factor_name: value}}
_overrides: dict[str, dict] = {}


def update_lot_reference(lot_id: str, factors: dict) -> dict:
    """Apply user-provided values to a LOT's missing factors.

    Use this after check_optimal_design reveals 부족인자.
    The user supplies the missing values, and this tool merges them
    into the reference so subsequent simulations can proceed.

    Args:
        lot_id: The reference LOT identifier.
        factors: Dict of factor names and their values to override.
                 Example: {"유전체 두께": 3.2, "Cover 두께": 28, "유전상수": 2600}

    Returns:
        A dict with:
        - status: "success"
        - lot_id: the lot
        - updated_factors: which factors were set/changed
        - ref_values: the full merged reference (base + overrides)
        - remaining_부족인자: factors still missing after this update
    """
    lot_id = lot_id.strip()

    if lot_id not in _overrides:
        _overrides[lot_id] = {}

    _overrides[lot_id].update(factors)

    # Build merged ref_values from base + overrides
    base = {}
    missing_base = []
    if lot_id in _VALID_LOTS:
        data = _VALID_LOTS[lot_id]
        base = dict(data["충족인자"])
        missing_base = list(data["부족인자"])
    else:
        base = {"Sheet 두께": 4.5, "전극 폭": 660}
        missing_base = ["전극 수", "유전체 두께", "Cover 두께", "유전상수", "Margin L", "Margin W"]

    merged = dict(base)
    merged.update(_overrides[lot_id])

    # Determine what's still missing
    remaining = [f for f in missing_base if f not in _overrides[lot_id]]

    return {
        "status": "success",
        "lot_id": lot_id,
        "updated_factors": factors,
        "ref_values": merged,
        "remaining_부족인자": remaining,
    }
