"""Mock check_optimal_design tool for testing.

In production, this tool verifies whether a given lot_id has
sufficient reference data to run DOE simulation.

This mock returns sample responses for known test lot IDs,
including the actual factor values for 충족인자.
"""

# Sample reference data for testing — now includes actual values
_VALID_LOTS = {
    "L240301-A": {
        "충족인자": {
            "Sheet 두께": 5.0,
            "전극 폭": 680,
            "전극 수": 162,
            "Margin L": 85,
            "Margin W": 60,
            "유전체 두께": 3.5,
            "Cover 두께": 30,
            "유전상수": 2800,
        },
        "부족인자": [],
    },
    "L240215-B": {
        "충족인자": {
            "Sheet 두께": 4.8,
            "전극 폭": 670,
            "전극 수": 158,
            "Margin L": 80,
        },
        "부족인자": ["유전체 두께", "Cover 두께", "유전상수", "Margin W"],
    },
}


def check_optimal_design(lot_id: str) -> dict:
    """Check whether a reference LOT is valid for DOE simulation.

    Verifies that the given lot_id has all required reference factors
    to run the optimal_design or reliability_simulation.

    Returns both factor names AND their current values for 충족인자,
    so the user can see what the reference LOT provides.
    If 부족인자 exist, the user can supply values via update_lot_reference.

    Args:
        lot_id: The reference LOT identifier to validate.
                Example: "L240301-A"

    Returns:
        A dict with:
        - status: "success"
        - lot_id: the lot
        - 충족인자: dict of {factor_name: value} for factors with data
        - 부족인자: list of factor names that are missing
        - ref_values: full dict of all factors (충족인자 values + 부족인자 as null)
    """
    lot_id = lot_id.strip()

    if lot_id in _VALID_LOTS:
        data = _VALID_LOTS[lot_id]
        ref_values = dict(data["충족인자"])
        for missing in data["부족인자"]:
            ref_values[missing] = None
        return {
            "status": "success",
            "lot_id": lot_id,
            "충족인자": data["충족인자"],
            "부족인자": data["부족인자"],
            "ref_values": ref_values,
        }

    # Unknown lot_id -> treat as having missing factors for safety
    known = {"Sheet 두께": 4.5, "전극 폭": 660}
    missing = ["전극 수", "유전체 두께", "Cover 두께", "유전상수", "Margin L", "Margin W"]
    ref_values = dict(known)
    for m in missing:
        ref_values[m] = None
    return {
        "status": "success",
        "lot_id": lot_id,
        "충족인자": known,
        "부족인자": missing,
        "ref_values": ref_values,
    }
