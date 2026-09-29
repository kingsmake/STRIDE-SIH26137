from __future__ import annotations
import random
import time
import statistics
from .routing import shortest_path, waypoint_path, path_metrics
from .priority_encoding import decode_priority_route, num_dimensions

def run_dijkstra(g, source, destination, objective):
    t=time.perf_counter()
    path, metrics=shortest_path(g,source,destination,objective,False)
    return {"algorithm":"Dijkstra","path":path,"metrics":metrics,"runtime_ms":(time.perf_counter()-t)*1000}

def run_astar(g, source, destination, objective):
    t=time.perf_counter()
    path, metrics=shortest_path(g,source,destination,objective,True)
    return {"algorithm":"A*","path":path,"metrics":metrics,"runtime_ms":(time.perf_counter()-t)*1000}

def run_classical_pso(g, source, destination, objective, waypoints=None, particles=28, iterations=60, seed=42):
    # Same random-key representation as QPSO, but with velocity/inertia update.
    rng=random.Random(seed)
    wp=list(waypoints or [])
    dim=len(wp)
    if dim==0:
        path, metrics=waypoint_path(g,source,destination,[],objective)
        return {"algorithm":"Classical PSO","path":path,"metrics":metrics,"runtime_ms":0.0,"convergence":[metrics["cost"]],"iterations":0}

    t=time.perf_counter()
    X=[[rng.uniform(-1,1) for _ in range(dim)] for _ in range(particles)]
    V=[[0.0]*dim for _ in range(particles)]
    P=[x[:] for x in X]
    def evalx(x):
        order=[wp[i] for i in sorted(range(dim),key=lambda i:x[i])]
        path,metrics=waypoint_path(g,source,destination,order,objective)
        return metrics["cost"],path,metrics,order
    pb=[evalx(x)[0] for x in X]
    gi=min(range(particles),key=lambda i:pb[i]); G=P[gi][:]; gs=pb[gi]
    conv=[]
    for it in range(iterations):
        inertia=0.80-0.50*(it/max(1,iterations-1))
        for i in range(particles):
            for d in range(dim):
                r1,r2=rng.random(),rng.random()
                V[i][d]=inertia*V[i][d]+1.4*r1*(P[i][d]-X[i][d])+1.4*r2*(G[d]-X[i][d])
                X[i][d]+=V[i][d]
            score,_,_,_=evalx(X[i])
            if score<pb[i]:
                P[i]=X[i][:]; pb[i]=score
                if score<gs:
                    gs=score; G=X[i][:]
        conv.append(round(gs,5))
    score,path,metrics,order=evalx(G)
    return {"algorithm":"Classical PSO","path":path,"waypoints":order,"metrics":metrics,
            "runtime_ms":(time.perf_counter()-t)*1000,"convergence":conv,"iterations":iterations}

def _evaluate_priority(g, source, destination, position, objective):
    path, _ = decode_priority_route(g, source, destination, position, objective)
    if path is None:
        return float("inf"), None, None
    metrics = path_metrics(g, path, objective)
    return metrics["cost"], path, metrics

def run_classical_pso_route(g, source, destination, objective="balanced",
                             particles=30, iterations=40, seed=42,
                             w=0.72, c1=1.49, c2=1.49):
    """Classical (inertia/velocity) PSO on the SAME priority encoding used by
    RouteQPSO, so the QPSO-vs-PSO comparison in benchmark.py isolates the
    search-update rule as the only variable, rather than comparing two
    different problem representations."""
    rng = random.Random(seed)
    d = num_dimensions(g)
    t = time.perf_counter()
    X = [[rng.uniform(-1, 1) for _ in range(d)] for _ in range(particles)]
    V = [[0.0] * d for _ in range(particles)]
    P = [x[:] for x in X]
    pbest = [_evaluate_priority(g, source, destination, x, objective)[0] for x in X]
    gidx = min(range(particles), key=lambda i: pbest[i])
    G = P[gidx][:]
    gscore = pbest[gidx]
    conv = [round(gscore, 5)]
    for _ in range(iterations):
        for i in range(particles):
            for k in range(d):
                r1, r2 = rng.random(), rng.random()
                V[i][k] = w*V[i][k] + c1*r1*(P[i][k]-X[i][k]) + c2*r2*(G[k]-X[i][k])
                X[i][k] += V[i][k]
            score, _, _ = _evaluate_priority(g, source, destination, X[i], objective)
            if score < pbest[i]:
                P[i] = X[i][:]; pbest[i] = score
                if score < gscore:
                    gscore = score; G = X[i][:]
        conv.append(round(gscore, 5))
    score, path, metrics = _evaluate_priority(g, source, destination, G, objective)
    return {"algorithm": "Classical PSO", "path": path, "metrics": metrics,
            "runtime_ms": (time.perf_counter()-t)*1000, "convergence": conv,
            "iterations": iterations, "particles": particles, "seed": seed,
            "encoding": "priority-based full-route, dim=%d" % d}

def run_ga_route(g, source, destination, objective="balanced",
                  population=30, iterations=40, seed=42,
                  mutation_rate=0.15, elite_frac=0.1):
    """Real-valued genetic algorithm (blend crossover + Gaussian mutation +
    elitism) on the same priority encoding, for a three-way metaheuristic
    comparison (QPSO / PSO / GA) rather than only QPSO vs two shortest-path
    baselines."""
    rng = random.Random(seed)
    d = num_dimensions(g)
    t = time.perf_counter()
    pop = [[rng.uniform(-1, 1) for _ in range(d)] for _ in range(population)]
    n_elite = max(1, int(population*elite_frac))

    def fitness(ind):
        return _evaluate_priority(g, source, destination, ind, objective)[0]

    scores = [fitness(ind) for ind in pop]
    order = sorted(range(population), key=lambda i: scores[i])
    best = pop[order[0]][:]; best_score = scores[order[0]]
    conv = [round(best_score, 5)]

    for _ in range(iterations):
        order = sorted(range(population), key=lambda i: scores[i])
        elites = [pop[i][:] for i in order[:n_elite]]
        new_pop = [e[:] for e in elites]
        while len(new_pop) < population:
            a = pop[order[rng.randint(0, population//2)]]
            b = pop[order[rng.randint(0, population//2)]]
            beta = rng.random()
            child = [beta*a[k] + (1-beta)*b[k] for k in range(d)]
            if rng.random() < mutation_rate:
                k = rng.randrange(d)
                child[k] += rng.gauss(0, 0.3)
            new_pop.append(child)
        pop = new_pop
        scores = [fitness(ind) for ind in pop]
        gi = min(range(population), key=lambda i: scores[i])
        if scores[gi] < best_score:
            best_score = scores[gi]; best = pop[gi][:]
        conv.append(round(best_score, 5))

    score, path, metrics = _evaluate_priority(g, source, destination, best, objective)
    return {"algorithm": "GA", "path": path, "metrics": metrics,
            "runtime_ms": (time.perf_counter()-t)*1000, "convergence": conv,
            "iterations": iterations, "population": population, "seed": seed,
            "encoding": "priority-based full-route, dim=%d" % d}

def run_ga_waypoints(g, source, destination, objective="balanced", waypoints=None,
                      population=30, iterations=40, seed=42, mutation_rate=0.2, elite_frac=0.1):
    """Permutation GA (order crossover + swap mutation + elitism) for
    ordering a fixed waypoint set - the direct GA counterpart to QPSO's and
    classical PSO's ordering search in this file, so all three metaheuristics
    are compared on the identical combinatorial problem."""
    rng = random.Random(seed)
    wp = list(waypoints or [])
    dim = len(wp)
    if dim == 0:
        path, metrics = waypoint_path(g, source, destination, [], objective)
        return {"algorithm": "GA", "path": path, "metrics": metrics, "runtime_ms": 0.0,
                "convergence": [metrics["cost"]], "iterations": 0}

    t = time.perf_counter()

    def fitness(order):
        _, m = waypoint_path(g, source, destination, order, objective)
        return m["cost"]

    def order_crossover(p1, p2):
        a, b = sorted(rng.sample(range(dim), 2)) if dim > 1 else (0, 0)
        child = [None] * dim
        child[a:b+1] = p1[a:b+1]
        fill = [x for x in p2 if x not in child]
        j = 0
        for i in range(dim):
            if child[i] is None:
                child[i] = fill[j]; j += 1
        return child

    pop = []
    base = wp[:]
    for _ in range(population):
        ind = base[:]
        rng.shuffle(ind)
        pop.append(ind)

    n_elite = max(1, int(population * elite_frac))
    scores = [fitness(ind) for ind in pop]
    order_idx = sorted(range(population), key=lambda i: scores[i])
    best = pop[order_idx[0]][:]
    best_score = scores[order_idx[0]]
    conv = [round(best_score, 5)]

    for _ in range(iterations):
        order_idx = sorted(range(population), key=lambda i: scores[i])
        elites = [pop[i][:] for i in order_idx[:n_elite]]
        new_pop = [e[:] for e in elites]
        pool = order_idx[:max(2, population // 2)]
        while len(new_pop) < population:
            p1 = pop[rng.choice(pool)]
            p2 = pop[rng.choice(pool)]
            child = order_crossover(p1, p2)
            if dim > 1 and rng.random() < mutation_rate:
                i, j = rng.sample(range(dim), 2)
                child[i], child[j] = child[j], child[i]
            new_pop.append(child)
        pop = new_pop
        scores = [fitness(ind) for ind in pop]
        gi = min(range(population), key=lambda i: scores[i])
        if scores[gi] < best_score:
            best_score = scores[gi]; best = pop[gi][:]
        conv.append(round(best_score, 5))

    path, metrics = waypoint_path(g, source, destination, best, objective)
    return {"algorithm": "GA", "path": path, "waypoints": best, "metrics": metrics,
            "runtime_ms": (time.perf_counter() - t) * 1000, "convergence": conv,
            "iterations": iterations, "population": population, "seed": seed}

def brute_force_waypoint_order(g, source, destination, objective="balanced", waypoints=None):
    """Exact optimum by exhaustive permutation search. Only tractable for
    small waypoint counts (<=8, i.e. <=40320 permutations) - used purely to
    compute an optimality-gap % for the metaheuristics in benchmark.py, not
    as a production endpoint."""
    import itertools
    wp = list(waypoints or [])
    if len(wp) > 8:
        raise ValueError("brute_force_waypoint_order is only for <=8 waypoints (factorial blow-up)")
    t = time.perf_counter()
    best_cost = float("inf"); best_path = None; best_order = None
    for perm in itertools.permutations(wp):
        path, m = waypoint_path(g, source, destination, list(perm), objective)
        if m["cost"] < best_cost:
            best_cost = m["cost"]; best_path = path; best_order = list(perm)
    return {"algorithm": "Brute force (optimal)", "path": best_path, "waypoints": best_order,
            "metrics": {"cost": round(best_cost, 4)}, "runtime_ms": (time.perf_counter()-t)*1000}

def run_greedy(g, source, destination, objective, waypoints=None):
    t=time.perf_counter()
    remaining=set(waypoints or [])
    cur=source
    path=[cur]
    while remaining:
        best=None
        best_cost=float("inf")
        for w in remaining:
            try:
                seg,m=shortest_path(g,cur,w,objective)
            except Exception:
                continue
            if m["cost"]<best_cost:
                best_cost=m["cost"]; best=(w,seg)
        if best is None: break
        w,seg=best
        path.extend(seg[1:]); cur=w; remaining.remove(w)
    seg,_=shortest_path(g,cur,destination,objective)
    path.extend(seg[1:])
    from .routing import path_metrics
    return {"algorithm":"Greedy waypoint","path":path,"metrics":path_metrics(g,path,objective),
            "runtime_ms":(time.perf_counter()-t)*1000}
