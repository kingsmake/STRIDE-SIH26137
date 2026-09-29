from __future__ import annotations
from .baselines import (run_dijkstra, run_astar, run_classical_pso, run_greedy,
                          run_classical_pso_route, run_ga_route)
from .qpso import QPSO
from .route_qpso import RouteQPSO

def compare(g, req):
    d=run_dijkstra(g,req.source,req.destination,req.objective)
    a=run_astar(g,req.source,req.destination,req.objective)
    if req.waypoints:
        q=QPSO(g,req.source,req.destination,req.objective,req.waypoints,req.particles,req.iterations,req.seed).run()
        p=run_classical_pso(g,req.source,req.destination,req.objective,req.waypoints,req.particles,req.iterations,req.seed)
        gr=run_greedy(g,req.source,req.destination,req.objective,req.waypoints)
        results=[q,d,a,p,gr]
    else:
        # No waypoints: the real SIH26137 problem (point-to-point
        # traffic-aware routing), so all three metaheuristics run on the
        # identical priority encoding for a fair comparison.
        q=RouteQPSO(g,req.source,req.destination,req.objective,req.particles,req.iterations,req.seed).run()
        p=run_classical_pso_route(g,req.source,req.destination,req.objective,req.particles,req.iterations,req.seed)
        ga=run_ga_route(g,req.source,req.destination,req.objective,req.particles,req.iterations,req.seed)
        results=[q,d,a,p,ga]
    return {"results":results, "objective":req.objective}

def serialise_result(g, result):
    from .routing import route_edges
    out=dict(result)
    out["edges"]=route_edges(g,result["path"])
    return out
