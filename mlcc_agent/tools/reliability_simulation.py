"""Mock reliability_simulation tool for testing.

In production, this tool runs a reliability simulation for a single
MLCC design point, returning a pass probability (신뢰성 통과확률).

Unlike optimal_design which takes parameter ranges (lists) for DOE sweep,
this tool takes scalar values for one specific design configuration.
"""

import random


def reliability_simulation(
    lot_id: str,
    sheet_t: float,
    electrode_w: float,
    margin_l: float,
    margin_w: float,
    cover_t: float,
    electrode_count: int,
) -> dict:
    """Run reliability simulation for a single MLCC design point.

    Evaluates the reliability pass probability for one specific set of
    design values. All parameters are scalar (not lists).

    This is different from optimal_design:
    - optimal_design: takes param lists for DOE sweep, returns top 5 candidates
    - reliability_simulation: takes single design point, returns pass probability

    Args:
        lot_id: Reference LOT identifier (must pass check_optimal_design first).
        sheet_t: Sheet thickness in um.
        electrode_w: Electrode width in um.
        margin_l: Margin length in um.
        margin_w: Margin width in um.
        cover_t: Cover thickness in um.
        electrode_count: Number of electrodes (EA).

    Returns:
        A dict with:
        - status: "success"
        - lot_id: the lot
        - design: the input design values
        - reliability_pass_rate: float 0.0~1.0 (신뢰성 통과확률)
    """
    # Deterministic mock based on input hash
    seed = hash((lot_id, sheet_t, electrode_w, margin_l, margin_w,
                 cover_t, electrode_count)) % 2**32
    random.seed(seed)

    # Mock: higher margin and cover thickness → better reliability
    # This simulates realistic-ish behavior for testing
    base_rate = 0.70
    margin_bonus = min((margin_l - 70) * 0.003, 0.10) if margin_l > 70 else -0.05
    cover_bonus = min((cover_t - 25) * 0.005, 0.08) if cover_t > 25 else -0.05
    electrode_penalty = max((electrode_count - 170) * 0.002, 0) if electrode_count > 170 else 0
    noise = random.uniform(-0.03, 0.03)

    pass_rate = base_rate + margin_bonus + cover_bonus - electrode_penalty + noise
    pass_rate = max(0.0, min(1.0, pass_rate))

    return {
        "status": "success",
        "lot_id": lot_id,
        "design": {
            "sheet_t": sheet_t,
            "electrode_w": electrode_w,
            "margin_l": margin_l,
            "margin_w": margin_w,
            "cover_t": cover_t,
            "electrode_count": electrode_count,
        },
        "reliability_pass_rate": round(pass_rate, 4),
    }
