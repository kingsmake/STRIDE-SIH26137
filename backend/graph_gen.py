from __future__ import annotations
import math
import random
import networkx as nx

"""
Procedural road-network generator.

This is NOT the demo map (see graph_data.py for the fixed 18-node city used by
the dashboard). It exists purely for controlled experiments where we need the
*same* edge/cost schema as the real graph but at a chosen size, so that
scalability claims ("how does runtime grow with network size?") are measured
on a consistent, reproducible family of graphs rather than one fixed map.

Design:
- Nodes are laid out on a slightly-perturbed grid (deterministic per seed) so
  every generated graph has real lat/lon-like coordinates and the A* heuristic
  in routing.py stays meaningful.
- Each grid cell connects to its right/down neighbour, plus a sparse set of
  diagonal "shortcut" roads, to avoid a purely-rectangular Manhattan graph
  (which would trivially favour certain algorithms).
- Edge attributes (distance_km, free_speed_kmh, base_congestion) follow the
  same conventions as graph_data.py so every downstream module (traffic.py,
  routing.py, qpso.py, route_qpso.py, baselines.py) works unmodified.
"""

def _grid_dims(n_nodes: int) -> tuple[int, int]:
    cols = max(2, round(math.sqrt(n_nodes)))
    rows = max(2, math.ceil(n_nodes / cols))
    return rows, cols

def generate_graph(n_nodes: int, seed: int = 42, shortcut_prob: float = 0.15) -> nx.DiGraph:
    """Build a deterministic, connected, scalable road-like graph.

    Parameters
    ----------
    n_nodes : target node count (actual count may be rows*cols >= n_nodes,
              trimmed back down to exactly n_nodes by dropping the last
              row's overflow nodes while keeping the graph connected).
    seed    : RNG seed for reproducibility across repeated-seed benchmarks.
    """
    rng = random.Random(seed)
    rows, cols = _grid_dims(n_nodes)

    g = nx.DiGraph()
    ids = {}
    idx = 0
    base_lat, base_lon = 20.00, 73.79  # arbitrary but realistic Indian-city origin
    for r in range(rows):
        for c in range(cols):
            if idx >= n_nodes:
                break
            jitter_lat = rng.uniform(-0.0015, 0.0015)
            jitter_lon = rng.uniform(-0.0015, 0.0015)
            lat = base_lat + r * 0.0065 + jitter_lat
            lon = base_lon + c * 0.0065 + jitter_lon
            ids[(r, c)] = idx
            g.add_node(idx, lat=lat, lon=lon, name=f"N{idx}")
            idx += 1
        if idx >= n_nodes:
            break

    def haversine_km(a, b):
        lat1, lon1 = g.nodes[a]["lat"], g.nodes[a]["lon"]
        lat2, lon2 = g.nodes[b]["lat"], g.nodes[b]["lon"]
        R = 6371.0
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dp = math.radians(lat2 - lat1)
        dl = math.radians(lon2 - lon1)
        h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        return 2 * R * math.asin(math.sqrt(h))

    def add_edge(u, v):
        if u == v or g.has_edge(u, v):
            return
        d = haversine_km(u, v)
        speed = 30.0 + ((u * 13 + v * 7) % 25)
        base_c = 0.10 + ((u + v) % 5) * 0.03
        g.add_edge(u, v, distance_km=d, free_speed_kmh=speed, base_congestion=base_c)

    coords = list(ids.keys())
    for (r, c), u in ids.items():
        if (r, c + 1) in ids:
            v = ids[(r, c + 1)]
            add_edge(u, v); add_edge(v, u)
        if (r + 1, c) in ids:
            v = ids[(r + 1, c)]
            add_edge(u, v); add_edge(v, u)
        # occasional diagonal shortcut road, keeps the graph non-trivial
        if (r + 1, c + 1) in ids and rng.random() < shortcut_prob:
            v = ids[(r + 1, c + 1)]
            add_edge(u, v); add_edge(v, u)

    # Guarantee full connectivity (grid construction already ensures this,
    # but if n_nodes didn't fill the last row exactly, patch any stray node).
    und = g.to_undirected()
    if not nx.is_connected(und):
        comps = list(nx.connected_components(und))
        main = max(comps, key=len)
        for comp in comps:
            if comp is main:
                continue
            u = min(comp)
            v = min(main)
            add_edge(u, v); add_edge(v, u)

    return g

def endpoints_far_apart(g: nx.DiGraph) -> tuple[int, int]:
    """Pick a (source, destination) pair that are graph-distant, for
    experiments where we want a non-trivial route rather than two
    adjacent nodes."""
    nodes = list(g.nodes)
    source = min(nodes)
    # BFS from source on the undirected view, take the farthest node
    und = g.to_undirected()
    lengths = nx.single_source_shortest_path_length(und, source)
    destination = max(lengths, key=lengths.get)
    return source, destination
