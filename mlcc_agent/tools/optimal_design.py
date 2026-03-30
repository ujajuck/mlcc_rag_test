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
    target_capacity: float,
    target_thickness: float,
    target_length: float,
    target_width: float,
    sheet_t: list[float],
    electrode_w: list[float],
    margin_l: list[float],
    margin_w: list[float],
    cover_t: list[float],
    electrode_count: list[int],
) -> dict:
    """Run DOE optimal design simulation.

    Calculates the top 5 optimal MLCC design candidates based on the
    reference LOT, target specifications, and DOE input parameters.

    Each params field is a list of values to explore:
    - For DOE sweep: provide multiple points, e.g. [4.8, 4.9, 5.0, 5.1, 5.2]
    - For rerun with specific values: provide a single-element list, e.g. [5.0]

    Args:
        lot_id: Reference LOT identifier (must pass check_optimal_design first).
        target_capacity: Target capacitance in uF.
        target_thickness: Target chip thickness in mm.
        target_length: Target chip length in mm.
        target_width: Target chip width in mm.
        sheet_t: Sheet thickness values in um (list).
        electrode_w: Electrode width values in um (list).
        margin_l: Margin length values in um (list).
        margin_w: Margin width values in um (list).
        cover_t: Cover thickness values in um (list).
        electrode_count: Number of electrodes values in EA (list).

    Returns:
        A dict with 'status', 'lot_id', 'targets', and 'top_candidates'.
        Each candidate contains design values and predicted performance.
    """
    # Use center values as seed for reproducibility
    center_st = sheet_t[len(sheet_t) // 2]
    center_ec = electrode_count[len(electrode_count) // 2]
    random.seed(hash((lot_id, target_capacity, center_st, center_ec)) % 2**32)

    candidates = []
    for rank in range(1, 6):
        # Pick from the provided parameter ranges
        st = random.choice(sheet_t) + random.uniform(-0.1, 0.1)
        ew = random.choice(electrode_w) + random.uniform(-5, 5)
        ml = random.choice(margin_l) + random.uniform(-2, 2)
        mw = random.choice(margin_w) + random.uniform(-2, 2)
        ct = random.choice(cover_t) + random.uniform(-1, 1)
        ec = random.choice(electrode_count) + random.randint(-2, 2)

        pred_cap = target_capacity * random.uniform(0.97, 1.04)
        pred_thick = target_thickness * random.uniform(0.98, 1.02)
        pred_length = target_length * random.uniform(0.99, 1.01)
        pred_width = target_width * random.uniform(0.99, 1.01)

        candidates.append({
            "rank": rank,
            "design": {
                "sheet_t": round(st, 2),
                "electrode_w": round(ew, 1),
                "margin_l": round(ml, 1),
                "margin_w": round(mw, 1),
                "cover_t": round(ct, 1),
                "electrode_count": ec,
            },
            "predicted": {
                "capacity_uF": round(pred_cap, 3),
                "thickness_mm": round(pred_thick, 4),
                "length_mm": round(pred_length, 4),
                "width_mm": round(pred_width, 4),
            },
            "gap": {
                "capacity_delta_uF": round(pred_cap - target_capacity, 3),
                "thickness_delta_mm": round(pred_thick - target_thickness, 4),
                "length_delta_mm": round(pred_length - target_length, 4),
                "width_delta_mm": round(pred_width - target_width, 4),
            },
        })

    # Sort by combined gap (capacity weight higher)
    candidates.sort(
        key=lambda c: (
            abs(c["gap"]["capacity_delta_uF"]) * 2
            + abs(c["gap"]["thickness_delta_mm"]) * 10
        )
    )
    for i, c in enumerate(candidates, 1):
        c["rank"] = i

    return {
        "status": "success",
        "lot_id": lot_id,
        "targets": {
            "capacity_uF": target_capacity,
            "thickness_mm": target_thickness,
            "length_mm": target_length,
            "width_mm": target_width,
        },
        "top_candidates": candidates,
    }
