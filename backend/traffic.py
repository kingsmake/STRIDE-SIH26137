from __future__ import annotations
import math
import random
import networkx as nx

def apply_scenario(g: nx.DiGraph, mode="normal", severity=0.65, seed=42):
    rng = random.Random(seed)
    for u, v, data in g.edges(data=True):
        base = float(data.get("base_congestion", 0.15))
        if mode == "normal":
            shock = 0.0
        elif mode == "rush_hour":
            # Spatially structured congestion wave.
            shock = severity * (0.18 + 0.22 * abs(math.sin((u+1)*(v+2))))
        else:  # incident
            shock = severity * (0.12 + 0.50 * (1.0 if (u+v) % 7 == 0 else 0.05))
        noise = rng.uniform(-0.025, 0.025)
        congestion = min(0.97, max(0.03, base + shock + noise))
        data["congestion"] = congestion

        # BPR-like speed degradation. Avoid division by zero at high congestion.
        free_speed = data["free_speed_kmh"]
        effective_speed = max(5.0, free_speed * (1.0 - 0.78 * congestion))
        data["speed_kmh"] = effective_speed
        data["travel_time_min"] = data["distance_km"] / effective_speed * 60.0
    return g

def objective_coeffs(objective="balanced"):
    """(distance, time, congestion) weights used by edge_cost. Exposed
    separately (rather than only inlined) so routing.py can derive a
    genuinely admissible A* heuristic from the same coefficients instead of
    duplicating magic numbers or falling back to a trivial zero heuristic."""
    return {
        "fastest": (0.15, 1.0, 4.0),
        "shortest": (1.0, 0.20, 2.0),
        "low_congestion": (0.20, 0.80, 10.0),
        "balanced": (0.45, 1.0, 6.0),
    }.get(objective, (0.45, 1.0, 6.0))

def edge_cost(data, objective="balanced"):
    d = data["distance_km"]
    t = data["travel_time_min"]
    c = data["congestion"]
    wd, wt, wc = objective_coeffs(objective)
    return wd*d + wt*t + wc*c

def weighted_graph(g, objective):
    h = g.copy()
    for u,v,data in h.edges(data=True):
        data["weight"] = edge_cost(data, objective)
    return h
