"""Mock optimal_design tool for testing.

In production, this tool runs the DOE simulation engine to find
optimal MLCC design candidates given targets and parameter ranges.

This mock returns sample top-5 results so the agent dialogue flow
(result presentation, rerun with overrides) can be tested.

params.* are lists:
  - Multi-point list for DOE sweep: [4.8, 4.9, 5.0, 5.1, 5.2]
  - Single-value list for rerun/pinpoint: [5.0]
"""

import random


def optimal_design(
    lot_id: str,
    target_electrode_c_avg: float,
    target_grinding_l_avg: float,
    target_grinding_w_avg: float,
    target_grinding_t_avg: float,
    target_dc_cap: float,
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
    """Run DOE optimal design simulation.

    Calculates the top 5 optimal MLCC design candidates based on the
    reference LOT, target specifications, and DOE input parameters.

    Each params field is a list of values to explore:
    - For DOE sweep: provide multiple points, e.g. [4.8, 4.9, 5.0, 5.1, 5.2]
    - For rerun with specific values: provide a single-element list, e.g. [5.0]

    Args:
        lot_id: Reference LOT identifier (must pass check_optimal_design first).
        target_electrode_c_avg: Target electrode capacitance average (uF).
        target_grinding_l_avg: Target grinding L size average (mm).
        target_grinding_w_avg: Target grinding W size average (mm).
        target_grinding_t_avg: Target grinding T size average (mm).
        target_dc_cap: Target DC capacitance (uF).
        active_layer: Active layer count values (EA, list).
        ldn_avr_value: Laydown average values (list).
        cast_dsgn_thk: Sheet T thickness values in um (list).
        screen_chip_size_leng: Screen chip size length values in um (list).
        screen_mrgn_leng: Screen margin length values in um (list).
        screen_chip_size_widh: Screen chip size width values in um (list).
        screen_mrgn_widh: Screen margin width values in um (list).
        cover_sheet_thk: Cover sheet thickness values in um (list).
        total_cover_layer_num: Total cover layer number (upper+lower) values (EA, list).
        gap_sheet_thk: Gap sheet thickness values in um (list).

    Returns:
        A dict with 'status', 'lot_id', 'targets', and 'top_candidates'.
        Each candidate contains design values and predicted performance.
    """
    # Use center values as seed for reproducibility
    center_cast = cast_dsgn_thk[len(cast_dsgn_thk) // 2]
    center_active = active_layer[len(active_layer) // 2]
    random.seed(hash((lot_id, target_electrode_c_avg, center_cast, center_active)) % 2**32)

    candidates = []
    for rank in range(1, 6):
        # Pick from the provided parameter ranges
        al = random.choice(active_layer) + random.randint(-2, 2)
        lav = random.choice(ldn_avr_value) + random.uniform(-0.05, 0.05)
        cdt = random.choice(cast_dsgn_thk) + random.uniform(-0.1, 0.1)
        scsl = random.choice(screen_chip_size_leng) + random.uniform(-5, 5)
        sml = random.choice(screen_mrgn_leng) + random.uniform(-2, 2)
        scsw = random.choice(screen_chip_size_widh) + random.uniform(-5, 5)
        smw = random.choice(screen_mrgn_widh) + random.uniform(-2, 2)
        cst = random.choice(cover_sheet_thk) + random.uniform(-1, 1)
        tcln = random.choice(total_cover_layer_num) + random.randint(-1, 1)
        gst = random.choice(gap_sheet_thk) + random.uniform(-0.5, 0.5)

        pred_electrode_c = target_electrode_c_avg * random.uniform(0.97, 1.04)
        pred_grinding_l = target_grinding_l_avg * random.uniform(0.98, 1.02)
        pred_grinding_w = target_grinding_w_avg * random.uniform(0.99, 1.01)
        pred_grinding_t = target_grinding_t_avg * random.uniform(0.98, 1.02)
        pred_dc_cap = target_dc_cap * random.uniform(0.97, 1.04)

        candidates.append({
            "rank": rank,
            "design": {
                "active_layer": al,
                "ldn_avr_value": round(lav, 3),
                "cast_dsgn_thk": round(cdt, 2),
                "screen_chip_size_leng": round(scsl, 1),
                "screen_mrgn_leng": round(sml, 1),
                "screen_chip_size_widh": round(scsw, 1),
                "screen_mrgn_widh": round(smw, 1),
                "cover_sheet_thk": round(cst, 1),
                "total_cover_layer_num": tcln,
                "gap_sheet_thk": round(gst, 2),
            },
            "predicted": {
                "electrode_c_avg": round(pred_electrode_c, 3),
                "grinding_l_avg": round(pred_grinding_l, 4),
                "grinding_w_avg": round(pred_grinding_w, 4),
                "grinding_t_avg": round(pred_grinding_t, 4),
                "dc_cap": round(pred_dc_cap, 3),
            },
            "gap": {
                "electrode_c_avg_delta": round(pred_electrode_c - target_electrode_c_avg, 3),
                "grinding_l_avg_delta": round(pred_grinding_l - target_grinding_l_avg, 4),
                "grinding_w_avg_delta": round(pred_grinding_w - target_grinding_w_avg, 4),
                "grinding_t_avg_delta": round(pred_grinding_t - target_grinding_t_avg, 4),
                "dc_cap_delta": round(pred_dc_cap - target_dc_cap, 3),
            },
        })

    # Sort by combined gap (capacity weights higher)
    candidates.sort(
        key=lambda c: (
            abs(c["gap"]["electrode_c_avg_delta"]) * 2
            + abs(c["gap"]["grinding_t_avg_delta"]) * 10
            + abs(c["gap"]["dc_cap_delta"]) * 2
        )
    )
    for i, c in enumerate(candidates, 1):
        c["rank"] = i

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
        "top_candidates": candidates,
    }
