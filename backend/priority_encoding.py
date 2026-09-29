from __future__ import annotations
from .traffic import weighted_graph

"""
Priority-based route encoding (Gen & Cheng style), adapted for continuous
swarm/evolutionary optimizers.

Why this exists
----------------
The most common shortcut in student SIH projects (including the reference
implementation we benchmarked against) is to only let the metaheuristic
choose an *ordering of a fixed, user-supplied set of waypoints*, then stitch
the gaps with plain shortest paths. That sidesteps the actual hard question:
how does a continuous particle position become an arbitrary, loop-free road
route between any source and destination, with no waypoints supplied at all?

Encoding
--------
A particle's position is one real-valued "priority" per node in the graph,
`position[i]` for node `i`. Higher = more attractive to visit early.

Decoding (`decode_priority_route`)
-----------------------------------
This is a Prim-style spanning-tree growth, exactly like Prim's MST algorithm
except the *next node to attach* is chosen by highest priority among the
current frontier (not by lowest edge weight), while the *edge used to attach
it* is still chosen to minimise traffic-weighted cost among the available
frontier edges reaching that node. This guarantees, for *every* real-valued
priority vector:
  - the decoded structure is a tree (loop-free by construction),
  - every node is reachable from the source (feasibility is automatic,
    it can never produce a broken/disconnected route),
  - the source -> destination path can be read off the tree in O(V).

This means QPSO/PSO/GA never waste search effort on infeasible candidates,
and never need a repair operator - every point in the continuous search
space decodes to a valid road route. The metaheuristics differ only in how
they *move* through this shared priority space, which keeps the algorithm
comparison in benchmark.py an apples-to-apples test of search strategy
rather than encoding tricks.
"""

def decode_priority_route(g, source, destination, priority, objective="balanced"):
    """priority: sequence indexed the same way as sorted(g.nodes) -> a value.
    Returns (path, tree_parent) where path is [source, ..., destination]."""
    h = weighted_graph(g, objective)
    nodes = sorted(g.nodes)
    prio = {n: priority[i] for i, n in enumerate(nodes)}

    visited = {source}
    parent = {source: None}
    # frontier[node] = (best_known_cost_to_attach, via_parent)
    frontier = {}
    for _, v, d in h.out_edges(source, data=True):
        if v not in visited:
            frontier[v] = (d["weight"], source)

    while destination not in visited and frontier:
        # choose next node purely by priority (this is what makes the
        # encoding "continuous-friendly": ties/ordering come from the real
        # numbers the optimizer controls)
        next_node = max(frontier.keys(), key=lambda n: prio.get(n, float("-inf")))
        _, via = frontier.pop(next_node)
        visited.add(next_node)
        parent[next_node] = via

        for _, v, d in h.out_edges(next_node, data=True):
            if v in visited:
                continue
            cand_cost = d["weight"]
            if v not in frontier or cand_cost < frontier[v][0]:
                frontier[v] = (cand_cost, next_node)

    if destination not in visited:
        # graph disconnected from source (shouldn't happen for a connected
        # road network, but fail safely with an explicit signal rather than
        # a silent wrong answer)
        return None, parent

    path = [destination]
    cur = destination
    while parent[cur] is not None:
        cur = parent[cur]
        path.append(cur)
    path.reverse()
    return path, parent

def num_dimensions(g) -> int:
    return g.number_of_nodes()
