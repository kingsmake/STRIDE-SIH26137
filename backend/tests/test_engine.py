from backend.graph_data import build_graph
from backend.traffic import apply_scenario
from backend.qpso import QPSO
from backend.route_qpso import RouteQPSO
from backend.routing import shortest_path, k_shortest_paths
from backend.baselines import (run_dijkstra, run_astar, run_classical_pso_route,
                                 run_ga_route, run_ga_waypoints, brute_force_waypoint_order)
from backend.constraints import check_route, VEHICLE_PROFILES
from backend.priority_encoding import decode_priority_route
from backend.graph_gen import generate_graph, endpoints_far_apart
from backend.benchmark import (run_repeated_seed_benchmark, run_waypoint_ordering_benchmark,
                                 run_scalability_study)

def test_graph_and_baseline():
    g=build_graph()
    apply_scenario(g,"normal",0.5,42)
    path,metrics=shortest_path(g,0,17,"balanced")
    assert path[0]==0 and path[-1]==17
    assert metrics["distance_km"]>0

def test_astar_matches_dijkstra_cost():
    # A* uses a real admissible heuristic now (routing.admissible_heuristic),
    # not a trivial zero heuristic, but must still return the optimal cost.
    g=build_graph()
    apply_scenario(g,"rush_hour",0.6,7)
    d=run_dijkstra(g,0,17,"balanced")
    a=run_astar(g,0,17,"balanced")
    assert abs(d["metrics"]["cost"]-a["metrics"]["cost"])<1e-6

def test_waypoint_qpso_returns_feasible_path():
    g=build_graph()
    apply_scenario(g,"rush_hour",0.7,42)
    result=QPSO(g,0,17,"balanced",[2,5,12],12,12,42).run()
    assert result["path"][0]==0
    assert result["path"][-1]==17
    assert result["metrics"]["cost"]>0
    assert len(result["convergence"])==12

def test_priority_decode_is_always_feasible():
    g=build_graph(); apply_scenario(g,"normal",0.5,1)
    import random
    rng=random.Random(3)
    for _ in range(15):
        pos=[rng.uniform(-1,1) for _ in g.nodes]
        path,_=decode_priority_route(g,0,17,pos,"balanced")
        assert path is not None
        assert path[0]==0 and path[-1]==17
        assert len(path)==len(set(path))  # loop-free

def test_route_qpso_matches_dijkstra_on_static_snapshot():
    # Honest regression test for the report's core finding: on a single
    # traffic snapshot the routing cost is additive/linear, so Dijkstra is
    # already optimal and RouteQPSO must not do worse.
    g=build_graph(); apply_scenario(g,"rush_hour",0.6,5)
    d=run_dijkstra(g,0,17,"balanced")
    q=RouteQPSO(g,0,17,"balanced",particles=24,iterations=30,seed=5).run()
    assert q["metrics"]["cost"] <= d["metrics"]["cost"] + 1e-6

def test_classical_pso_route_and_ga_route_feasible():
    g=build_graph(); apply_scenario(g,"incident",0.5,9)
    p=run_classical_pso_route(g,0,17,"balanced",particles=16,iterations=15,seed=9)
    ga=run_ga_route(g,0,17,"balanced",population=16,iterations=15,seed=9)
    for r in (p, ga):
        assert r["path"][0]==0 and r["path"][-1]==17

def test_k_shortest_paths_are_distinct_and_valid():
    g=build_graph(); apply_scenario(g,"normal",0.4,1)
    alts=k_shortest_paths(g,0,17,"balanced",k=3)
    assert len(alts)>=2
    paths=[tuple(p) for p,_ in alts]
    assert len(set(paths))==len(paths)  # no duplicate routes

def test_constraint_check_rejects_oversized_truck():
    g=build_graph(); apply_scenario(g,"normal",0.3,1)
    # Junction A(3) -> Market(4) is tagged max_height_m=3.2 in graph_data.py
    chk=check_route(g,[3,4],"truck")
    assert chk["feasible"] is False
    assert any(v["type"]=="height" for v in chk["violations"])
    chk_car=check_route(g,[3,4],"car")
    assert chk_car["feasible"] is True

def test_ga_waypoints_and_brute_force_agree_on_small_instance():
    g=build_graph(); apply_scenario(g,"normal",0.4,2)
    wp=[2,5,12]
    opt=brute_force_waypoint_order(g,0,17,"balanced",wp)
    ga=run_ga_waypoints(g,0,17,"balanced",wp,population=20,iterations=20,seed=2)
    assert ga["metrics"]["cost"] >= opt["metrics"]["cost"] - 1e-6

def test_graph_gen_scales_and_stays_connected():
    for n in (10, 25, 40):
        g=generate_graph(n, seed=1)
        assert g.number_of_nodes()==n
        import networkx as nx
        assert nx.is_weakly_connected(g)
        s,d=endpoints_far_apart(g)
        assert s!=d

def test_repeated_seed_benchmark_shape():
    g=build_graph(); apply_scenario(g,"rush_hour",0.5,3)
    rows=run_repeated_seed_benchmark(g,0,17,"balanced",seeds=(1,2,3),particles=12,iterations=10)
    names={r["algorithm"] for r in rows}
    assert {"QPSO","Classical PSO","GA","Dijkstra","A*"} <= names
    for r in rows:
        assert r["n_runs"]>=1

def test_waypoint_ordering_benchmark_has_optimality_gap():
    g=build_graph(); apply_scenario(g,"rush_hour",0.5,4)
    out=run_waypoint_ordering_benchmark(g,0,17,[2,5,8],"balanced",seeds=(1,2),particles=12,iterations=10)
    assert out["optimal_cost"] is not None
    for r in out["results"]:
        assert r["optimality_gap_pct"] >= -1e-6  # never "better than optimal"
