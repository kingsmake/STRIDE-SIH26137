#!/usr/bin/env python3
"""
Run all S.T.R.I.D.E. benchmark experiments and export results as CSV + JSON
into experiments/results/, so a judge (or teammate) can inspect actual
numbers instead of only a live demo.

Usage:
    cd STRIDE_SIH26137
    python -m experiments.run_experiments
    # or: python experiments/run_experiments.py   (run from repo root)

Produces:
    experiments/results/repeated_seed_benchmark.csv / .json
    experiments/results/convergence_study.json
    experiments/results/scalability_study.csv / .json
"""
from __future__ import annotations
import csv
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.graph_data import build_graph
from backend.traffic import apply_scenario
from backend.benchmark import (run_repeated_seed_benchmark, run_convergence_study,
                                 run_scalability_study, run_waypoint_ordering_benchmark,
                                 run_waypoint_ordering_convergence)

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")

def _write_csv(path, rows, fieldnames):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)

def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    seeds = tuple(range(1, 11))       # 10 repeated seeds
    particles, iterations = 30, 40
    source, destination, objective = 0, 17, "balanced"
    scenario, severity = "rush_hour", 0.6

    print("[1/4] Repeated-seed benchmark on the 18-node demo city "
          f"(source={source}, dest={destination}, {len(seeds)} seeds)...")
    g = build_graph()
    apply_scenario(g, scenario, severity, seed=42)
    repeated = run_repeated_seed_benchmark(g, source, destination, objective,
                                            seeds=seeds, particles=particles, iterations=iterations)
    _write_csv(os.path.join(RESULTS_DIR, "repeated_seed_benchmark.csv"), repeated,
               fieldnames=["algorithm", "n_runs", "cost_mean", "cost_std", "runtime_ms_mean", "runtime_ms_std"])
    with open(os.path.join(RESULTS_DIR, "repeated_seed_benchmark.json"), "w") as f:
        json.dump({"source": source, "destination": destination, "objective": objective,
                    "scenario": scenario, "severity": severity, "seeds": list(seeds),
                    "particles": particles, "iterations": iterations, "results": repeated}, f, indent=2)
    for r in repeated:
        print(f"    {r['algorithm']:<15} cost={r['cost_mean']:.3f}+/-{r['cost_std']:.3f}  "
              f"runtime_ms={r['runtime_ms_mean']:.2f}+/-{r['runtime_ms_std']:.2f}  (n={r['n_runs']})")

    print("\n[2/4] Waypoint-ordering benchmark (combinatorial case, graded against brute-force optimum)...")
    wp = [2, 5, 8, 11, 13, 15]   # 6 waypoints -> 720 permutations, brute-forceable
    wp_bench = run_waypoint_ordering_benchmark(g, source, destination, wp, objective,
                                                seeds=seeds, particles=particles, iterations=iterations)
    with open(os.path.join(RESULTS_DIR, "waypoint_ordering_benchmark.json"), "w") as f:
        json.dump(wp_bench, f, indent=2)
    _write_csv(os.path.join(RESULTS_DIR, "waypoint_ordering_benchmark.csv"), wp_bench["results"],
               fieldnames=["algorithm", "n_runs", "cost_mean", "cost_std", "runtime_ms_mean",
                           "runtime_ms_std", "optimality_gap_pct"])
    print(f"    {len(wp)} waypoints -> {wp_bench['n_permutations']} permutations, "
          f"optimal cost = {wp_bench['optimal_cost']}")
    for r in wp_bench["results"]:
        gap = r.get("optimality_gap_pct")
        print(f"    {r['algorithm']:<15} cost={r['cost_mean']:.3f}+/-{r['cost_std']:.3f}  "
              f"gap={gap}%  runtime_ms={r['runtime_ms_mean']:.2f}")

    wp_conv = run_waypoint_ordering_convergence(g, source, destination, wp, objective,
                                                 seeds=tuple(range(1, 9)), particles=particles, iterations=iterations)
    with open(os.path.join(RESULTS_DIR, "waypoint_ordering_convergence.json"), "w") as f:
        json.dump({"waypoints": wp, "particles": particles, "iterations": iterations,
                    "curves": wp_conv}, f, indent=2)
    print("    (waypoint-ordering convergence curves written for the report's headline chart)")

    print("\n[3/4] Convergence study: QPSO vs Classical PSO, point-to-point (8 seeds)...")
    conv = run_convergence_study(g, source, destination, objective,
                                  seeds=tuple(range(1, 9)), particles=particles, iterations=iterations)
    with open(os.path.join(RESULTS_DIR, "convergence_study.json"), "w") as f:
        json.dump({"source": source, "destination": destination, "objective": objective,
                    "particles": particles, "iterations": iterations, "curves": conv}, f, indent=2)
    for name, curve in conv.items():
        print(f"    {name:<15} start={curve['mean'][0]:.3f}  end={curve['mean'][-1]:.3f}  n_seeds={curve['n_seeds']}")

    print("\n[4/4] Scalability sweep: 10/20/30/40/50-node synthetic graphs, 3 seeds each...")
    scal = run_scalability_study(node_counts=(10, 20, 30, 40, 50), seeds=(1, 2, 3),
                                  objective=objective, particles=particles, iterations=iterations,
                                  scenario=scenario, severity=severity)
    _write_csv(os.path.join(RESULTS_DIR, "scalability_study.csv"), scal,
               fieldnames=["nodes", "algorithm", "runtime_ms", "cost", "n_runs"])
    with open(os.path.join(RESULTS_DIR, "scalability_study.json"), "w") as f:
        json.dump(scal, f, indent=2)
    for row in scal:
        print(f"    n={row['nodes']:<3} {row['algorithm']:<15} runtime_ms={row['runtime_ms']:<8.2f} cost={row['cost']}")

    print(f"\nDone. Results written to {RESULTS_DIR}/")
    print("Run `python experiments/generate_report.py` next to build the charts + Markdown report.")

if __name__ == "__main__":
    main()
