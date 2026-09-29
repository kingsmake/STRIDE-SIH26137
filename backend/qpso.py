from __future__ import annotations
import math
import random
import statistics
from .routing import waypoint_path, path_metrics

class QPSO:
    """
    Discrete-route QPSO:
    - Particle position is continuous random-key vector.
    - Keys are decoded by rank into an ordering of optional waypoints.
    - Each ordering is converted into a feasible road path by shortest-path
      routing between consecutive selected points.
    - This makes the continuous QPSO state usable for a discrete road graph.
    """

    def __init__(self, graph, source, destination, objective="balanced",
                 waypoints=None, particles=28, iterations=60, seed=42):
        self.g = graph
        self.source = source
        self.destination = destination
        self.objective = objective
        self.waypoints = list(waypoints or [])
        self.m = max(1, len(self.waypoints))
        self.particles = particles
        self.iterations = iterations
        self.rng = random.Random(seed)
        self.seed = seed

    def decode(self, position):
        if not self.waypoints:
            return []
        order = sorted(range(len(self.waypoints)), key=lambda i: position[i])
        return [self.waypoints[i] for i in order]

    def evaluate(self, position):
        order = self.decode(position)
        path, metrics = waypoint_path(self.g, self.source, self.destination, order, self.objective)
        return metrics["cost"], path, metrics, order

    def run(self):
        dim = self.m
        if dim == 0:
            # QPSO is not useful when there is no permutation search space.
            path, metrics = waypoint_path(self.g, self.source, self.destination, [], self.objective)
            return {
                "algorithm":"QPSO",
                "path":path, "waypoints":[], "metrics":metrics,
                "convergence":[metrics["cost"]], "iterations":0,
                "note":"No optional waypoints: direct weighted path used."
            }

        X = [[self.rng.uniform(-1,1) for _ in range(dim)] for _ in range(self.particles)]
        P = [x[:] for x in X]
        pbest = []
        for x in X:
            pbest.append(self.evaluate(x)[0])
        gidx = min(range(self.particles), key=lambda i:pbest[i])
        G = P[gidx][:]
        gscore = pbest[gidx]
        convergence=[]

        alpha_start, alpha_end = 1.0, 0.5
        for it in range(self.iterations):
            mbest = [statistics.mean(P[i][d] for i in range(self.particles)) for d in range(dim)]
            alpha = alpha_start - (it/max(1,self.iterations-1))*(alpha_start-alpha_end)

            for i in range(self.particles):
                for d in range(dim):
                    phi = self.rng.random()
                    local = phi*P[i][d] + (1-phi)*G[d]
                    u = max(1e-12, self.rng.random())
                    sign = 1 if self.rng.random() < 0.5 else -1
                    X[i][d] = local + sign*alpha*abs(mbest[d]-X[i][d])*math.log(1/u)

                score, _, _, _ = self.evaluate(X[i])
                if score < pbest[i]:
                    P[i] = X[i][:]
                    pbest[i] = score
                    if score < gscore:
                        gscore = score
                        G = X[i][:]

            convergence.append(round(gscore, 5))

        score, path, metrics, order = self.evaluate(G)
        return {
            "algorithm":"QPSO",
            "path":path,
            "waypoints":order,
            "metrics":metrics,
            "convergence":convergence,
            "iterations":self.iterations,
            "seed":self.seed,
            "note":"Continuous random-key particles are decoded into waypoint permutations; road feasibility is supplied by the graph router."
        }
