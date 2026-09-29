from __future__ import annotations
import math
import statistics
import time
from .qpso import QPSO
from .route_qpso import RouteQPSO
from .baselines import (run_dijkstra, run_astar, run_classical_pso_route, run_ga_route,
                          run_classical_pso, run_ga_waypoints, brute_force_waypoint_order)
from .graph_gen import generate_graph, endpoints_far_apart
from .traffic import apply_scenario

"""
Experiment utilities backing the claims in the benchmark report: repeated-
seed statistics (mean +/- std, not a single lucky run), a per-iteration
convergence comparison of QPSO vs classical PSO vs GA, and a scalability
sweep across graph sizes. Pure-python + statistics module only (no extra
runtime dependency for the API); experiments/generate_report.py additionally
uses matplotlib/pandas which are experiment-only tooling (see
requirements-experiments.txt), never imported by the FastAPI app itself.
"""

ALGORITHMS = ("QPSO", "Classical PSO", "GA", "Dijkstra", "A*")

def _mean_std(values):
    if not values:
        return 0.0, 0.0
    if len(values) == 1:
        return values[0], 0.0
    return statistics.mean(values), statistics.pstdev(values)

def run_repeated_seed_benchmark(g, source, destination, objective="balanced",
                                 seeds=(1, 2, 3, 4, 5, 6, 7, 8, 9, 10),
                                 particles=30, iterations=40):
    """Runs QPSO / Classical PSO / GA across many seeds (Dijkstra and A* are
    deterministic, so they're run once each) and returns per-algorithm
    mean +/- std for cost and runtime. This is what item 4 of the roadmap
    means by "repeated-seed benchmarking" - a single seed's result can be a
    lucky/unlucky draw for a stochastic optimizer, so no comparative claim in
    the report is drawn from n=1.
    """
    records = {name: {"cost": [], "runtime_ms": []} for name in ALGORITHMS}

    d = run_dijkstra(g, source, destination, objective)
    a = run_astar(g, source, destination, objective)
    records["Dijkstra"]["cost"].append(d["metrics"]["cost"])
    records["Dijkstra"]["runtime_ms"].append(d["runtime_ms"])
    records["A*"]["cost"].append(a["metrics"]["cost"])
    records["A*"]["runtime_ms"].append(a["runtime_ms"])

    for seed in seeds:
        t0 = time.perf_counter()
        q = RouteQPSO(g, source, destination, objective, particles, iterations, seed).run()
        q_rt = (time.perf_counter() - t0) * 1000
        p = run_classical_pso_route(g, source, destination, objective, particles, iterations, seed)
        ga = run_ga_route(g, source, destination, objective, particles, iterations, seed)

        records["QPSO"]["cost"].append(q["metrics"]["cost"])
        records["QPSO"]["runtime_ms"].append(q_rt)
        records["Classical PSO"]["cost"].append(p["metrics"]["cost"])
        records["Classical PSO"]["runtime_ms"].append(p["runtime_ms"])
        records["GA"]["cost"].append(ga["metrics"]["cost"])
        records["GA"]["runtime_ms"].append(ga["runtime_ms"])

    summary = []
    for name, vals in records.items():
        cost_mean, cost_std = _mean_std(vals["cost"])
        rt_mean, rt_std = _mean_std(vals["runtime_ms"])
        summary.append({
            "algorithm": name, "n_runs": len(vals["cost"]),
            "cost_mean": round(cost_mean, 4), "cost_std": round(cost_std, 4),
            "runtime_ms_mean": round(rt_mean, 3), "runtime_ms_std": round(rt_std, 3),
        })
    return summary

def run_convergence_study(g, source, destination, objective="balanced",
                           seeds=(1, 2, 3, 4, 5, 6, 7, 8), particles=30, iterations=40):
    """Averages the per-iteration best-cost-so-far curve across seeds for
    QPSO and Classical PSO (same encoding, see priority_encoding.py), so the
    "QPSO converges faster" claim is a mean curve with a std band, not one
    cherry-picked run.
    """
    curves = {"QPSO": [], "Classical PSO": []}
    for seed in seeds:
        q = RouteQPSO(g, source, destination, objective, particles, iterations, seed).run()
        p = run_classical_pso_route(g, source, destination, objective, particles, iterations, seed)
        curves["QPSO"].append(q["convergence"])
        curves["Classical PSO"].append(p["convergence"])

    out = {}
    for name, runs in curves.items():
        length = min(len(r) for r in runs)
        mean_curve, std_curve = [], []
        for it in range(length):
            vals = [r[it] for r in runs]
            m, s = _mean_std(vals)
            mean_curve.append(round(m, 5))
            std_curve.append(round(s, 5))
        out[name] = {"mean": mean_curve, "std": std_curve, "n_seeds": len(runs)}
    return out

def run_waypoint_ordering_convergence(g, source, destination, waypoints, objective="balanced",
                                       seeds=(1, 2, 3, 4, 5, 6, 7, 8), particles=30, iterations=40):
    """Per-iteration mean +/- std convergence curves for QPSO, classical PSO
    and GA on the combinatorial waypoint-ordering problem (see
    run_waypoint_ordering_benchmark for why this, not the trivial
    point-to-point case, is where convergence-speed differences are
    meaningful)."""
    curves = {"QPSO": [], "Classical PSO": [], "GA": []}
    for seed in seeds:
        q = QPSO(g, source, destination, objective, waypoints, particles, iterations, seed).run()
        p = run_classical_pso(g, source, destination, objective, waypoints, particles, iterations, seed)
        ga = run_ga_waypoints(g, source, destination, objective, waypoints, particles, iterations, seed)
        curves["QPSO"].append(q["convergence"])
        curves["Classical PSO"].append(p["convergence"])
        curves["GA"].append(ga["convergence"])

    out = {}
    for name, runs in curves.items():
        length = min(len(r) for r in runs)
        mean_curve, std_curve = [], []
        for it in range(length):
            vals = [r[it] for r in runs]
            m, s = _mean_std(vals)
            mean_curve.append(round(m, 5))
            std_curve.append(round(s, 5))
        out[name] = {"mean": mean_curve, "std": std_curve, "n_seeds": len(runs)}
    return out

def run_waypoint_ordering_benchmark(g, source, destination, waypoints, objective="balanced",
                                     seeds=(1, 2, 3, 4, 5, 6, 7, 8, 9, 10),
                                     particles=30, iterations=40):
    """The honest counterpart to run_repeated_seed_benchmark: on a plain
    point-to-point query, Dijkstra/A* are already provably optimal (edge
    costs are an additive linear snapshot), so no metaheuristic can beat
    them - our own experiments confirm this (see repeated_seed_benchmark
    results, where QPSO/PSO/GA match Dijkstra's cost exactly every seed).

    Ordering a fixed set of waypoints is different: it's a combinatorial
    search over len(waypoints)! permutations, which Dijkstra cannot solve
    directly (it only finds shortest paths between two fixed points, not the
    best visiting order of several). This is where QPSO/PSO/GA earn their
    place, and - for small waypoint counts - we can grade them against the
    true optimum via brute force to report a real optimality gap, not just
    a relative ranking between heuristics.
    """
    records = {"QPSO": {"cost": [], "runtime_ms": []},
               "Classical PSO": {"cost": [], "runtime_ms": []},
               "GA": {"cost": [], "runtime_ms": []}}

    optimal = None
    if len(waypoints) <= 8:
        optimal = brute_force_waypoint_order(g, source, destination, objective, waypoints)

    for seed in seeds:
        t0 = time.perf_counter()
        q = QPSO(g, source, destination, objective, waypoints, particles, iterations, seed).run()
        q_rt = (time.perf_counter() - t0) * 1000
        p = run_classical_pso(g, source, destination, objective, waypoints, particles, iterations, seed)
        ga = run_ga_waypoints(g, source, destination, objective, waypoints, particles, iterations, seed)
        records["QPSO"]["cost"].append(q["metrics"]["cost"])
        records["QPSO"]["runtime_ms"].append(q_rt)
        records["Classical PSO"]["cost"].append(p["metrics"]["cost"])
        records["Classical PSO"]["runtime_ms"].append(p["runtime_ms"])
        records["GA"]["cost"].append(ga["metrics"]["cost"])
        records["GA"]["runtime_ms"].append(ga["runtime_ms"])

    summary = []
    for name, vals in records.items():
        cost_mean, cost_std = _mean_std(vals["cost"])
        rt_mean, rt_std = _mean_std(vals["runtime_ms"])
        row = {"algorithm": name, "n_runs": len(vals["cost"]),
               "cost_mean": round(cost_mean, 4), "cost_std": round(cost_std, 4),
               "runtime_ms_mean": round(rt_mean, 3), "runtime_ms_std": round(rt_std, 3)}
        if optimal:
            row["optimality_gap_pct"] = round(100 * (cost_mean - optimal["metrics"]["cost"]) / optimal["metrics"]["cost"], 2)
        summary.append(row)
    return {"waypoints": waypoints, "n_permutations": math.factorial(len(waypoints)),
            "optimal_cost": optimal["metrics"]["cost"] if optimal else None,
            "results": summary}

def run_scalability_study(node_counts=(10, 20, 30, 40, 50), seeds=(1, 2, 3),
                           objective="balanced", particles=30, iterations=40,
                           scenario="rush_hour", severity=0.6):
    """Generates a scalable synthetic graph per size (graph_gen.py) and
    records how QPSO/PSO/GA/Dijkstra/A* runtime and solution cost change as
    the network grows, averaged over a few seeds per size.
    """
    rows = []
    for n in node_counts:
        g = generate_graph(n, seed=100 + n)
        apply_scenario(g, scenario, severity, seed=100 + n)
        source, destination = endpoints_far_apart(g)

        d = run_dijkstra(g, source, destination, objective)
        a = run_astar(g, source, destination, objective)
        rows.append({"nodes": n, "algorithm": "Dijkstra", "runtime_ms": round(d["runtime_ms"], 3),
                     "cost": d["metrics"]["cost"], "n_runs": 1})
        rows.append({"nodes": n, "algorithm": "A*", "runtime_ms": round(a["runtime_ms"], 3),
                     "cost": a["metrics"]["cost"], "n_runs": 1})

        for name, runner in (
            ("QPSO", lambda seed: RouteQPSO(g, source, destination, objective, particles, iterations, seed).run()),
            ("Classical PSO", lambda seed: run_classical_pso_route(g, source, destination, objective, particles, iterations, seed)),
            ("GA", lambda seed: run_ga_route(g, source, destination, objective, particles, iterations, seed)),
        ):
            costs, times = [], []
            for seed in seeds:
                t0 = time.perf_counter()
                r = runner(seed)
                rt = r.get("runtime_ms", (time.perf_counter() - t0) * 1000)
                costs.append(r["metrics"]["cost"]); times.append(rt)
            cm, _ = _mean_std(costs)
            tm, _ = _mean_std(times)
            rows.append({"nodes": n, "algorithm": name, "runtime_ms": round(tm, 3),
                         "cost": round(cm, 4), "n_runs": len(seeds)})
    return rows
