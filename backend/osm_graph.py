from __future__ import annotations
import os
import math
import random
import networkx as nx

"""
Real OpenStreetMap road-network import, via OSMnx.

This module is intentionally decoupled from the rest of the engine: every
other file (traffic.py, routing.py, qpso.py, route_qpso.py, baselines.py)
only ever sees a plain networkx.DiGraph with the node attrs {lat, lon, name}
and edge attrs {distance_km, free_speed_kmh, base_congestion}. Swapping the
demo's synthetic graph_data.py graph for a real OSM extract therefore
requires no changes anywhere else in the codebase.

Requires network access and the `osmnx` package, which is NOT installed by
default (see requirements-osm.txt) because Smart India Hackathon judging
environments are frequently offline. Import is deferred inside the function
bodies so the rest of the app runs fine without osmnx present.

Typical usage (with internet access):

    from backend.osm_graph import build_osm_graph, cache_graph, load_cached_graph
    g = build_osm_graph("Nashik, Maharashtra, India")
    cache_graph(g, "data/nashik.graphml")
    ...
    g2 = load_cached_graph("data/nashik.graphml")   # offline afterwards

Highway-type -> free-flow speed and base congestion defaults are simple,
documented assumptions (no official Indian road-capacity dataset is bundled
here); they are clearly separated in HIGHWAY_SPEED_KMH / HIGHWAY_BASE_CONGESTION
so a team can replace them with real traffic-survey values for their city.
"""

HIGHWAY_SPEED_KMH = {
    "motorway": 80, "trunk": 60, "primary": 50, "secondary": 40,
    "tertiary": 35, "residential": 25, "unclassified": 25,
    "service": 15, "living_street": 12,
}
HIGHWAY_BASE_CONGESTION = {
    "motorway": 0.12, "trunk": 0.15, "primary": 0.20, "secondary": 0.22,
    "tertiary": 0.18, "residential": 0.12, "unclassified": 0.15,
    "service": 0.08, "living_street": 0.08,
}
DEFAULT_SPEED_KMH = 30.0
DEFAULT_BASE_CONGESTION = 0.15


def _first(value, default):
    """OSM tags are sometimes lists (e.g. highway=['residential','service'])."""
    if isinstance(value, (list, tuple)):
        return value[0] if value else default
    return value if value is not None else default


def build_osm_graph(place: str, network_type: str = "drive", simplify: bool = True) -> nx.DiGraph:
    """Download a real road network for `place` (a geocodable string such as
    "Nashik, Maharashtra, India" or "Koregaon Park, Pune, India") and convert
    it into S.T.R.I.D.E.'s internal schema.

    Raises RuntimeError with a clear message if osmnx is not installed or the
    download fails (no internet), so callers can fall back to the synthetic
    demo graph instead of crashing the whole API.
    """
    try:
        import osmnx as ox
    except ImportError as e:
        raise RuntimeError(
            "osmnx is not installed. Run `pip install -r requirements-osm.txt` "
            "and ensure you have internet access, then retry."
        ) from e

    try:
        raw = ox.graph_from_place(place, network_type=network_type, simplify=simplify)
    except Exception as e:
        raise RuntimeError(
            f"Could not download OSM data for '{place}'. Check spelling, "
            f"internet access, and that Nominatim/Overpass are reachable. "
            f"Original error: {e}"
        ) from e

    return _convert_osmnx_graph(raw)


def _convert_osmnx_graph(raw) -> nx.DiGraph:
    g = nx.DiGraph()
    for n, data in raw.nodes(data=True):
        g.add_node(n, lat=float(data["y"]), lon=float(data["x"]), name=str(n))

    seen = set()
    for u, v, data in raw.edges(data=True):
        if (u, v) in seen:
            continue
        seen.add((u, v))
        length_m = float(data.get("length", 0.0)) or _haversine_km(g, u, v) * 1000.0
        distance_km = max(0.01, length_m / 1000.0)
        highway = _first(data.get("highway"), "unclassified")
        maxspeed_tag = data.get("maxspeed")
        try:
            free_speed = float(_first(maxspeed_tag, HIGHWAY_SPEED_KMH.get(highway, DEFAULT_SPEED_KMH)))
        except (TypeError, ValueError):
            free_speed = HIGHWAY_SPEED_KMH.get(highway, DEFAULT_SPEED_KMH)
        base_congestion = HIGHWAY_BASE_CONGESTION.get(highway, DEFAULT_BASE_CONGESTION)
        g.add_edge(u, v, distance_km=distance_km, free_speed_kmh=free_speed,
                   base_congestion=base_congestion, highway=highway)

    # OSM extracts occasionally contain small disconnected islands (service
    # roads, parking aisles). Keep only the largest weakly-connected
    # component so every source/destination pair the UI offers is reachable.
    largest = max(nx.weakly_connected_components(g), key=len)
    if len(largest) < g.number_of_nodes():
        g = g.subgraph(largest).copy()

    return nx.convert_node_labels_to_integers(g, first_label=0, ordering="sorted")


def _haversine_km(g, a, b):
    lat1, lon1 = g.nodes[a]["lat"], g.nodes[a]["lon"]
    lat2, lon2 = g.nodes[b]["lat"], g.nodes[b]["lon"]
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def cache_graph(g: nx.DiGraph, path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    nx.write_graphml(g, path)


def load_cached_graph(path: str) -> nx.DiGraph:
    g = nx.read_graphml(path, node_type=int)
    for _, d in g.nodes(data=True):
        d["lat"] = float(d["lat"]); d["lon"] = float(d["lon"])
    for _, _, d in g.edges(data=True):
        d["distance_km"] = float(d["distance_km"])
        d["free_speed_kmh"] = float(d["free_speed_kmh"])
        d["base_congestion"] = float(d["base_congestion"])
    return g


def load_or_build(place: str, cache_path: str, network_type: str = "drive") -> nx.DiGraph:
    """Convenience wrapper: use a cached graphml file if present (fully
    offline), otherwise download once via OSMnx and cache it for next time."""
    if os.path.exists(cache_path):
        return load_cached_graph(cache_path)
    g = build_osm_graph(place, network_type=network_type)
    cache_graph(g, cache_path)
    return g
