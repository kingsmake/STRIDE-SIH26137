from __future__ import annotations
import math
import networkx as nx

# A compact synthetic urban road graph centered around a Nashik-like coordinate.
# It is intentionally deterministic and offline for reproducible SIH demos.

NODES = {
    0: (19.9975, 73.7898, "Central"),
    1: (19.9993, 73.7828, "West Gate"),
    2: (20.0024, 73.7787, "College"),
    3: (20.0060, 73.7818, "Junction A"),
    4: (20.0088, 73.7880, "Market"),
    5: (20.0062, 73.7950, "Junction B"),
    6: (20.0010, 73.8008, "East Gate"),
    7: (19.9947, 73.8018, "Depot East"),
    8: (19.9895, 73.7970, "South East"),
    9: (19.9872, 73.7890, "River Road"),
    10: (19.9890, 73.7812, "South West"),
    11: (19.9940, 73.7758, "Bus Stand"),
    12: (20.0120, 73.7895, "North Market"),
    13: (20.0142, 73.7982, "North East"),
    14: (20.0145, 73.7798, "North West"),
    15: (20.0037, 73.7718, "Outer West"),
    16: (19.9960, 73.8110, "Outer East"),
    17: (20.0115, 73.8060, "Tech Park"),
}

# Undirected street topology. Each pair becomes two directed edges.
EDGES = [
    (0,1),(0,5),(0,11),(0,6),
    (1,2),(1,11),(1,15),
    (2,3),(2,14),(2,15),
    (3,4),(3,12),(3,14),
    (4,5),(4,12),(4,13),
    (5,6),(5,4),
    (6,7),(6,13),(6,16),
    (7,8),(7,16),
    (8,9),(8,16),
    (9,10),(9,11),
    (10,11),(10,15),
    (11,1),(11,0),
    (12,13),(12,17),(12,4),
    (13,17),(13,6),
    (14,12),(14,3),
    (15,14),(15,10),
    (16,17),(16,6),
    (17,13),(17,16),(17,12),
]

def haversine_km(a, b):
    lat1, lon1 = NODES[a][:2]
    lat2, lon2 = NODES[b][:2]
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2-lat1)
    dl = math.radians(lon2-lon1)
    h = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*r*math.asin(math.sqrt(h))

def build_graph():
    g = nx.DiGraph()
    for node, (lat, lon, name) in NODES.items():
        g.add_node(node, lat=lat, lon=lon, name=name)
    seen = set()
    for u, v in EDGES:
        if (u, v) in seen:
            continue
        seen.add((u, v))
        d = haversine_km(u, v)
        # Free-flow speeds are intentionally varied by road segment.
        speed = 32.0 + ((u * 17 + v * 11) % 24)
        g.add_edge(u, v, distance_km=d, free_speed_kmh=speed, base_congestion=0.10 + ((u+v)%5)*0.035)

    # A couple of physically restricted segments, so the constraint-check
    # step (backend/constraints.py) has something real to reject rather than
    # only being illustrated in a video. Values are illustrative for the demo.
    RESTRICTED = [
        ((3, 4), {"max_height_m": 3.2}),   # Junction A -> Market: low underpass
        ((4, 3), {"max_height_m": 3.2}),
        ((8, 9), {"max_weight_t": 7.5}),   # South East -> River Road: light bridge
        ((9, 8), {"max_weight_t": 7.5}),
    ]
    for (u, v), attrs in RESTRICTED:
        if g.has_edge(u, v):
            g.edges[u, v].update(attrs)
    return g

def serialise_graph(g):
    return {
        "nodes": [
            {"id": n, "lat": g.nodes[n]["lat"], "lon": g.nodes[n]["lon"], "name": g.nodes[n]["name"]}
            for n in g.nodes
        ],
        "edges": [
            {"source": u, "target": v, **{k: float(val) for k,val in d.items()}}
            for u,v,d in g.edges(data=True)
        ]
    }
