from __future__ import annotations

"""
Route/vehicle feasibility constraints.

Each edge may carry optional physical limits: max_height_m (underpass/bridge
clearance) and max_weight_t (bridge/road weight limit). A vehicle profile
declares its own height/weight. A route that uses any edge whose limit is
violated is rejected with a specific, human-readable reason - this is what
backs the "check constraints, reject an invalid route" step of the demo,
rather than only being illustrated in the video.
"""

VEHICLE_PROFILES = {
    "car": {"height_m": 1.6, "weight_t": 1.8, "label": "Car"},
    "van": {"height_m": 2.4, "weight_t": 3.5, "label": "Delivery van"},
    "truck": {"height_m": 4.0, "weight_t": 12.0, "label": "Delivery truck"},
}

def check_route(g, path, vehicle="car"):
    """Returns {"feasible": bool, "violations": [...]} — never raises, so
    callers can always show *why* a route was rejected."""
    profile = VEHICLE_PROFILES.get(vehicle, VEHICLE_PROFILES["car"])
    violations = []
    for u, v in zip(path[:-1], path[1:]):
        d = g[u][v]
        max_h = d.get("max_height_m")
        max_w = d.get("max_weight_t")
        if max_h is not None and profile["height_m"] > max_h:
            violations.append({
                "edge": [u, v], "type": "height",
                "limit_m": max_h, "vehicle_m": profile["height_m"],
                "reason": f"Underpass clearance {max_h} m < vehicle height {profile['height_m']} m",
            })
        if max_w is not None and profile["weight_t"] > max_w:
            violations.append({
                "edge": [u, v], "type": "weight",
                "limit_t": max_w, "vehicle_t": profile["weight_t"],
                "reason": f"Road weight limit {max_w} t < vehicle weight {profile['weight_t']} t",
            })
    return {"feasible": len(violations) == 0, "violations": violations, "vehicle": profile["label"]}

def first_feasible(g, candidates, vehicle="car"):
    """candidates: list of (path, metrics) e.g. from routing.k_shortest_paths.
    Returns (path, metrics, check) for the first feasible one, or the best
    infeasible candidate with its violation list if none qualify, so callers
    can always show *something* plus the reason nothing better was usable."""
    checked = [(path, metrics, check_route(g, path, vehicle)) for path, metrics in candidates]
    for path, metrics, chk in checked:
        if chk["feasible"]:
            return path, metrics, chk
    return checked[0] if checked else (None, None, None)
