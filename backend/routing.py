from __future__ import annotations
import math
import networkx as nx
from .traffic import weighted_graph, edge_cost, objective_coeffs

def _haversine_km(g, a, b):
    lat1, lon1 = g.nodes[a]["lat"], g.nodes[a]["lon"]
    lat2, lon2 = g.nodes[b]["lat"], g.nodes[b]["lon"]
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))

def _max_free_speed(g):
    speeds = [d["free_speed_kmh"] for _, _, d in g.edges(data=True)]
    return max(speeds) if speeds else 60.0

def admissible_heuristic(g, node, destination, objective, max_speed_kmh):
    """A genuine, provably-admissible lower bound on remaining cost, not a
    trivial zero heuristic: straight-line distance to the destination, costed
    at the *best possible* case (top free-flow speed on the network, zero
    congestion). Since real edges can only be slower/more congested than
    this, the true remaining cost is always >= this estimate, which is
    exactly what A* requires to stay optimal while still pruning search."""
    dist_km = _haversine_km(g, node, destination)
    wd, wt, _wc = objective_coeffs(objective)
    best_case_time_min = dist_km / max_speed_kmh * 60.0
    return wd * dist_km + wt * best_case_time_min

def path_metrics(g, path, objective="balanced"):
    if len(path) < 2:
        return {"cost": 0.0, "distance_km": 0.0, "travel_time_min": 0.0, "congestion": 0.0}
    edges = list(zip(path[:-1], path[1:]))
    total_d = sum(g[u][v]["distance_km"] for u,v in edges)
    total_t = sum(g[u][v]["travel_time_min"] for u,v in edges)
    total_cost = sum(edge_cost(g[u][v], objective) for u,v in edges)
    avg_c = sum(g[u][v]["congestion"] for u,v in edges) / len(edges)
    return {
        "cost": round(total_cost, 4),
        "distance_km": round(total_d, 4),
        "travel_time_min": round(total_t, 4),
        "congestion": round(avg_c, 4),
    }

def shortest_path(g, source, destination, objective="balanced", heuristic=False):
    h = weighted_graph(g, objective)
    if heuristic:
        max_speed = _max_free_speed(g)
        path = nx.astar_path(
            h, source, destination,
            heuristic=lambda a, b: admissible_heuristic(g, a, destination, objective, max_speed),
            weight="weight"
        )
    else:
        path = nx.shortest_path(h, source, destination, weight="weight")
    return path, path_metrics(g, path, objective)

def k_shortest_paths(g, source, destination, objective="balanced", k=3):
    """Yen's algorithm via networkx, on the same traffic-weighted graph used
    everywhere else. Used to show 2-3 realistic alternative routes in the UI
    and as a comparison point for how much QPSO's route improves on the
    plain top-k static alternatives."""
    h = weighted_graph(g, objective)
    gen = nx.shortest_simple_paths(h, source, destination, weight="weight")
    out = []
    for i, path in enumerate(gen):
        if i >= k:
            break
        out.append((path, path_metrics(g, path, objective)))
    return out

def waypoint_path(g, source, destination, waypoints, objective="balanced"):
    points = [source] + list(waypoints) + [destination]
    full = []
    for a,b in zip(points[:-1], points[1:]):
        segment, _ = shortest_path(g, a, b, objective)
        full.extend(segment if not full else segment[1:])
    return full, path_metrics(g, full, objective)

def route_edges(g, path):
    out=[]
    for u,v in zip(path[:-1], path[1:]):
        d=g[u][v]
        out.append({
            "source":u,"target":v,
            "distance_km":round(d["distance_km"],3),
            "time_min":round(d["travel_time_min"],2),
            "congestion":round(d["congestion"],3),
            "speed_kmh":round(d["speed_kmh"],1)
        })
    return out
