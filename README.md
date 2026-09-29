# S.T.R.I.D.E. — SIH26137

**Swarm-based Traffic Routing & Intelligent Density Engine**

> Smart India Hackathon 2026 — Problem Statement SIH26137
> Quantum-Inspired Intelligent Traffic Route Optimization in Transportation Systems Using Metaheuristic Optimization

S.T.R.I.D.E. is a traffic-aware routing engine and dashboard. It models a road network as a weighted directed graph, turns changing congestion into dynamic edge costs, and searches for a good source → destination route using a quantum-behaved particle swarm (QPSO), benchmarked honestly against Dijkstra, A*, classical PSO and a genetic algorithm.

## What's actually in this repository (not just claimed)

Every feature below has a working implementation and a test in `backend/tests/test_engine.py` — nothing here is illustrated only in a video or a slide.

- **Full-route QPSO**, not just waypoint reordering. `backend/priority_encoding.py` implements a priority-based encoding (Gen & Cheng style): each particle is one real-valued "priority" per graph node, decoded via a priority-guided spanning-tree construction that is **always loop-free and feasible for any real-valued input** — no repair operator needed. `backend/route_qpso.py` runs the quantum delta-potential-well update rule (Sun et al.) directly on this encoding to solve arbitrary point-to-point queries, which is the actual SIH26137 problem. The older waypoint-ordering QPSO (`backend/qpso.py`) is kept for the multi-stop extension (see below).
- **A real A\* heuristic.** `backend/routing.py` uses an admissible straight-line lower bound (best-case free-flow speed, zero congestion) derived from the same cost coefficients as the live objective — not a placeholder zero heuristic that silently degrades A* into Dijkstra.
- **Vehicle/route constraint checking that actually rejects routes.** `backend/constraints.py` checks height/weight limits against vehicle profiles (car/van/truck) and returns specific violation reasons; `backend/graph_data.py` tags two real edges with limits so this is demonstrable, not just described.
- **Repeated-seed benchmarking, not single-run anecdotes.** `backend/benchmark.py` + `experiments/run_experiments.py` run every stochastic algorithm across 10 seeds and report **mean ± standard deviation**, never a lone number.
- **Convergence and scalability studies with real charts.** `experiments/generate_report.py` produces PNG charts and a Markdown report (`experiments/REPORT.md`) from the exported CSV/JSON in `experiments/results/` — a judge can read the report standalone without re-running anything.
- **Real OSM import**, via `backend/osm_graph.py` (OSMnx). Requires internet the first time; caches to a local `.graphml` file afterwards. The 18-node `backend/graph_data.py` map is the offline fallback used everywhere else.
- **Scalable synthetic graphs** (`backend/graph_gen.py`) for 10/20/30/40+-node experiments, independent of the fixed demo city.
- Classical PSO **and** a genetic algorithm as baselines, on the *same* priority encoding as QPSO (`run_classical_pso_route` / `run_ga_route` in `backend/baselines.py`), so the QPSO-vs-PSO-vs-GA comparison isolates the search strategy rather than comparing different problem representations.

## An honest technical finding, not a marketing claim

We benchmarked before writing this section, and report what we found rather than what would sound best:

**On a single point-to-point query with a fixed traffic snapshot, Dijkstra and A\* are already provably optimal.** The routing cost is a linear sum over edges, so no metaheuristic can beat an exact shortest-path algorithm there — and our repeated-seed experiment confirms it: QPSO, classical PSO and GA all converge to the *identical* Dijkstra-optimal cost across every seed, at 300–600x the runtime (`experiments/REPORT.md`, section 1).

**Where QPSO genuinely earns its place is multi-stop waypoint ordering** — a combinatorial problem Dijkstra cannot solve directly (it only finds a shortest path between two fixed points, not the best visiting order of several). Graded against a brute-force ground truth on a 6-stop / 720-permutation instance, QPSO's optimality gap (4.4%) beats classical PSO (7.3%) and GA (9.4%), and it also converges faster (`experiments/REPORT.md`, section 2). This is the real, defensible value proposition — and it directly generalises toward the kind of capacitated multi-stop delivery routing (CVRP) that a full logistics platform would need.

We'd rather hand judges this honest, two-part story than a single inflated "QPSO always wins" number that doesn't survive a repeated-seed check.

## Architecture

```text
                 React + Vite Dashboard (map / controls / charts)
                                |  REST
                       FastAPI Service (scenario + routing API)
                                |
     -----------------------------------------------------------
     |             |               |              |            |
  Graph        Traffic         Priority       Baselines     Constraint
 (fixed /     scenario        encoding      Dijkstra/A*/    checking
  OSM /      (dynamic         + QPSO/          PSO/GA        (vehicle
 scalable)     costs)          PSO/GA                        profiles)
     -----------------------------------------------------------
                                |
                benchmark.py / experiments/
              (mean +/- std, convergence, scalability)
```

## Repository layout

```text
STRIDE_SIH26137/
|-- backend/
|   |-- app.py                 FastAPI routes
|   |-- models.py              Pydantic request/response schemas
|   |-- graph_data.py          Fixed 18-node offline demo city
|   |-- graph_gen.py           Scalable synthetic graph generator (10..N nodes)
|   |-- osm_graph.py           Real OSMnx import + local caching (needs internet)
|   |-- traffic.py             Scenario -> dynamic congestion & edge costs
|   |-- routing.py             Dijkstra / A* (real heuristic) / k-shortest-paths
|   |-- priority_encoding.py   Shared priority-based route decoder
|   |-- route_qpso.py          Full-route QPSO (no waypoints needed)
|   |-- qpso.py                Waypoint-ordering QPSO (multi-stop extension)
|   |-- baselines.py           Dijkstra/A* wrappers, PSO, GA, greedy, brute force
|   |-- constraints.py         Vehicle height/weight feasibility checking
|   |-- benchmark.py           Repeated-seed, convergence & scalability studies
|   |-- metrics.py             /api/compare orchestration
|   |-- requirements.txt       Core API dependencies only
|   `-- tests/test_engine.py   14 tests covering all of the above
|-- experiments/
|   |-- run_experiments.py     Exports CSV/JSON to experiments/results/
|   |-- generate_report.py     Builds PNG charts + REPORT.md
|   |-- results/               Sample results already committed
|   |-- figures/               Sample charts already committed
|   `-- REPORT.md              Pre-generated report -- read this first
|-- requirements-osm.txt         Optional: osmnx, for real map import
|-- requirements-experiments.txt Optional: matplotlib/pandas/tabulate, for reports
|-- frontend/                  React + Vite + Leaflet dashboard
|-- data/
|-- .env.example
|-- .gitignore
|-- run_backend.bat / run_frontend.bat
`-- LICENSE
```

## Running it

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open the URL Vite prints (normally `http://localhost:5173`).

### Tests

```bash
cd backend
pip install -r requirements.txt   # includes pytest
pytest tests/ -v
```

### Experiments & report (optional, separate deps)

```bash
pip install -r requirements-experiments.txt
python experiments/run_experiments.py     # writes experiments/results/*.csv/.json
python experiments/generate_report.py     # writes experiments/figures/*.png + REPORT.md
```

Sample results and charts are already committed under `experiments/`, so a judge can read `experiments/REPORT.md` without running anything.

### Real OSM map (optional, needs internet)

```bash
pip install -r requirements-osm.txt
python -c "
from backend.osm_graph import load_or_build
g = load_or_build('Nashik, Maharashtra, India', 'data/nashik.graphml')
print(g.number_of_nodes(), 'nodes,', g.number_of_edges(), 'edges')
"
```

Point `backend/app.py`'s `GRAPH = build_graph()` at `load_cached_graph('data/nashik.graphml')` to switch the API to the real network — every other module (traffic, routing, QPSO, constraints) works unchanged, since they only depend on the shared node/edge schema.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness check |
| GET | `/api/network` | Current graph (nodes + edges + live congestion) |
| GET | `/api/scenario` | Current traffic scenario summary |
| POST | `/api/scenario` | Apply a traffic scenario (`normal`/`rush_hour`/`incident`) |
| GET | `/api/alternatives` | 2-3 static shortest-path alternatives, each vehicle-feasibility checked |
| POST | `/api/check_route` | Check an arbitrary path against a vehicle profile |
| POST | `/api/optimize` | Run QPSO (full-route if no waypoints, ordering QPSO if waypoints given) + constraint check |
| POST | `/api/compare` | QPSO vs Dijkstra vs A* vs PSO vs GA on the same query |

Example `/api/optimize` request (point-to-point, no waypoints -- uses `RouteQPSO`):

```json
{
  "source": 0,
  "destination": 17,
  "waypoints": [],
  "objective": "balanced",
  "vehicle": "truck",
  "particles": 30,
  "iterations": 40,
  "seed": 42
}
```

## Demo sequence

1. Select source and destination; view 2-3 static alternatives (`/api/alternatives`).
2. Apply a traffic scenario (rush hour / incident) and watch edge congestion and costs update.
3. Run `/api/optimize` -- the previously-shortest route may now be congested.
4. Run `/api/compare` to see QPSO vs Dijkstra/A*/PSO/GA on the current snapshot (they should match on cost -- see the honest finding above).
5. Switch to a truck vehicle profile and re-run; a route using a height- or weight-restricted edge is rejected with a specific reason.
6. Add 5-6 optional waypoints and re-run: this is the combinatorial case where QPSO's optimality gap and convergence speed genuinely differ from PSO/GA (`experiments/REPORT.md`, section 2).
7. Open `experiments/REPORT.md` for the full repeated-seed and scalability evidence.

## Important scientific boundaries

- QPSO runs on ordinary CPUs; "quantum" refers to the delta-potential-well update rule (Sun et al.), not quantum hardware.
- Traffic is a controlled, seeded simulation (`backend/traffic.py`), clearly not a live feed.
- No result claims a global optimum for the combinatorial (multi-stop) case -- only a measured gap against a brute-force ground truth on one small, explicitly stated instance.
- Point-to-point results are, honestly, tied with Dijkstra/A* by construction (see above) -- we do not claim otherwise.
- Real-world OSM import is implemented and unit-tested for correctness of the schema conversion, but the actual network download has not been exercised in this offline development environment; the demo ships with the deterministic synthetic city as the default, reproducible fallback.

## Research references

- Sun, J., Feng, B., Xu, W. -- Particle swarm optimization with particles having quantum behavior.
- Gen, M., Cheng, R. -- Genetic Algorithms and Engineering Design (priority-based encoding for shortest-path problems).
- Dijkstra, E. W. -- A note on two problems in connexion with graphs.
- Hart, P., Nilsson, N., Raphael, B. -- A formal basis for the heuristic determination of minimum cost paths.
- Boeing, G. -- OSMnx: New methods for acquiring, constructing, analyzing and visualizing complex street networks.
- Golden, B., Wong, R. -- Capacitated arc routing problems (context for the multi-stop / CVRP extension).
