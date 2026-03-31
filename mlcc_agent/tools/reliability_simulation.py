"""Mock reliability_simulation tool for testing.

In production, this tool runs a reliability simulation for a single
MLCC design point, returning a pass probability (신뢰성 통과확률).

Unlike optimal_design which takes parameter ranges (lists) for DOE sweep,
this tool takes scalar values for one specific design configuration.
"""

import random


def reliability_simulation(
    lot_id: str,
    active_layer: int,
    ldn_avr_value: float,
    cast_dsgn_thk: float,
    screen_chip_size_leng: float,
    screen_mrgn_leng: float,
    screen_chip_size_widh: float,
    screen_mrgn_widh: float,
    cover_sheet_thk: float,
    total_cover_layer_num: int,
    gap_sheet_thk: float,
) -> dict:
    """Run reliability simulation for a single MLCC design point.

    Evaluates the reliability pass probability for one specific set of
    design values. All parameters are scalar (not lists).

    This is different from optimal_design:
    - optimal_design: takes param lists for DOE sweep, returns top 5 candidates
    - reliability_simulation: takes single design point, returns pass probability

    Args:
        lot_id: Reference LOT identifier (must pass check_optimal_design first).
        active_layer: Active layer count (EA).
        ldn_avr_value: Laydown average value.
        cast_dsgn_thk: Sheet T thickness in um.
        screen_chip_size_leng: Screen chip size length in um.
        screen_mrgn_leng: Screen margin length in um.
        screen_chip_size_widh: Screen chip size width in um.
        screen_mrgn_widh: Screen margin width in um.
        cover_sheet_thk: Cover sheet thickness in um.
        total_cover_layer_num: Total cover layer number (upper+lower, EA).
        gap_sheet_thk: Gap sheet thickness in um.

    Returns:
        A dict with:
        - status: "success"
        - lot_id: the lot
        - design: the input design values
        - reliability_pass_rate: float 0.0~1.0 (신뢰성 통과확률)
    """
    # Deterministic mock based on input hash
    seed = hash((lot_id, active_layer, ldn_avr_value, cast_dsgn_thk,
                 screen_chip_size_leng, screen_mrgn_leng,
                 screen_chip_size_widh, screen_mrgn_widh,
                 cover_sheet_thk, total_cover_layer_num, gap_sheet_thk)) % 2**32
    random.seed(seed)

    # Mock: higher margin and cover thickness → better reliability
    base_rate = 0.70
    margin_bonus = min((screen_mrgn_leng - 70) * 0.003, 0.10) if screen_mrgn_leng > 70 else -0.05
    cover_bonus = min((cover_sheet_thk - 25) * 0.005, 0.08) if cover_sheet_thk > 25 else -0.05
    layer_penalty = max((active_layer - 170) * 0.002, 0) if active_layer > 170 else 0
    noise = random.uniform(-0.03, 0.03)

    pass_rate = base_rate + margin_bonus + cover_bonus - layer_penalty + noise
    pass_rate = max(0.0, min(1.0, pass_rate))

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
            "gap_sheet_thk": gap_sheet_thk,
        },
        "reliability_pass_rate": round(pass_rate, 4),
    }
