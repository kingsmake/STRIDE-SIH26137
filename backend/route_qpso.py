from __future__ import annotations
import math
import random
import statistics
from .priority_encoding import decode_priority_route, num_dimensions
from .routing import path_metrics

class RouteQPSO:
    """Quantum-behaved PSO (delta-potential-well model, Sun et al.) operating
    directly on the priority-encoding from priority_encoding.py. Unlike the
    waypoint-ordering QPSO in qpso.py (which only reorders a fixed stop
    list), this searches the *entire* space of loop-free source -> destination
    routes on the traffic-weighted graph, which is the actual SIH26137
    problem: point-to-point traffic-aware route optimization, not multi-stop
    tour ordering.
    """

    def __init__(self, graph, source, destination, objective="balanced",
                 particles=30, iterations=40, seed=42):
        self.g = graph
        self.source = source
        self.destination = destination
        self.objective = objective
        self.dim = num_dimensions(graph)
        self.particles = particles
        self.iterations = iterations
        self.seed = seed
        self.rng = random.Random(seed)

    def _evaluate(self, position):
        path, _ = decode_priority_route(self.g, self.source, self.destination, position, self.objective)
        if path is None:
            return float("inf"), None, None
        metrics = path_metrics(self.g, path, self.objective)
        return metrics["cost"], path, metrics

    def run(self):
        d = self.dim
        X = [[self.rng.uniform(-1, 1) for _ in range(d)] for _ in range(self.particles)]
        P = [x[:] for x in X]
        pbest = [self._evaluate(x)[0] for x in X]
        gidx = min(range(self.particles), key=lambda i: pbest[i])
        G = P[gidx][:]
        gscore = pbest[gidx]
        convergence = [round(gscore, 5)]

        alpha_start, alpha_end = 1.0, 0.5
        for it in range(self.iterations):
            mbest = [statistics.mean(P[i][k] for i in range(self.particles)) for k in range(d)]
            alpha = alpha_start - (it / max(1, self.iterations - 1)) * (alpha_start - alpha_end)

            for i in range(self.particles):
                for k in range(d):
                    phi = self.rng.random()
                    local = phi * P[i][k] + (1 - phi) * G[k]
                    u = max(1e-12, self.rng.random())
                    sign = 1 if self.rng.random() < 0.5 else -1
                    X[i][k] = local + sign * alpha * abs(mbest[k] - X[i][k]) * math.log(1 / u)

                score, _, _ = self._evaluate(X[i])
                if score < pbest[i]:
                    P[i] = X[i][:]
                    pbest[i] = score
                    if score < gscore:
                        gscore = score
                        G = X[i][:]

            convergence.append(round(gscore, 5))

        score, path, metrics = self._evaluate(G)
        return {
            "algorithm": "QPSO",
            "path": path,
            "metrics": metrics,
            "convergence": convergence,
            "iterations": self.iterations,
            "particles": self.particles,
            "seed": self.seed,
            "encoding": "priority-based full-route (Gen & Cheng style), dim=%d" % d,
            "note": ("Each particle is a per-node priority vector decoded into a "
                     "loop-free source-to-destination path via priority-guided "
                     "spanning-tree growth (see priority_encoding.py). Runs on "
                     "conventional classical hardware; 'quantum' refers to the "
                     "delta-potential-well update rule, not quantum computing."),
        }
