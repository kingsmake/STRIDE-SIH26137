from __future__ import annotations
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .graph_data import build_graph, serialise_graph
from .traffic import apply_scenario
from .models import OptimizeRequest, ScenarioRequest, RouteCheckRequest
from .qpso import QPSO
from .route_qpso import RouteQPSO
from .metrics import compare, serialise_result
from .routing import k_shortest_paths
from .constraints import check_route, first_feasible

app=FastAPI(title="S.T.R.I.D.E. API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173","http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GRAPH=build_graph()
apply_scenario(GRAPH)

@app.get("/api/health")
def health():
    return {"status":"ok","project":"S.T.R.I.D.E.","version":"1.0.0"}

@app.get("/api/network")
def network():
    return serialise_graph(GRAPH)

@app.get("/api/scenario")
def scenario():
    values=[float(d["congestion"]) for _,_,d in GRAPH.edges(data=True)]
    return {"mode":CURRENT_SCENARIO["mode"],"severity":CURRENT_SCENARIO["severity"],
            "avg_congestion":sum(values)/len(values)}

CURRENT_SCENARIO={"mode":"normal","severity":0.65,"seed":42}

@app.post("/api/scenario")
def set_scenario(req: ScenarioRequest):
    global GRAPH, CURRENT_SCENARIO
    GRAPH=build_graph()
    apply_scenario(GRAPH,req.mode,req.severity,req.seed)
    CURRENT_SCENARIO=req.model_dump()
    return {"ok":True,**CURRENT_SCENARIO}

@app.get("/api/alternatives")
def alternatives(source: int, destination: int, objective: str = "balanced", k: int = 3, vehicle: str = "car"):
    """2-3 static shortest-path alternatives with distance/time/congestion,
    each annotated with a vehicle-feasibility check. Backs the demo's
    "show 2-3 possible routes" + "reject an invalid route" steps."""
    if source not in GRAPH or destination not in GRAPH:
        raise HTTPException(400,"Source or destination node does not exist")
    candidates=k_shortest_paths(GRAPH,source,destination,objective,k)
    out=[]
    for path, m in candidates:
        chk=check_route(GRAPH,path,vehicle)
        out.append({"path":path,"metrics":m,"edges":serialise_result(GRAPH,{"path":path})["edges"],
                    "feasible":chk["feasible"],"violations":chk["violations"]})
    return {"alternatives":out,"vehicle":chk["vehicle"] if candidates else vehicle}

@app.post("/api/check_route")
def api_check_route(req: RouteCheckRequest):
    for a,b in zip(req.path[:-1],req.path[1:]):
        if not GRAPH.has_edge(a,b):
            raise HTTPException(400,f"No such road segment {a}->{b}")
    return check_route(GRAPH,req.path,req.vehicle)

@app.post("/api/optimize")
def optimize(req: OptimizeRequest):
    if req.source not in GRAPH or req.destination not in GRAPH:
        raise HTTPException(400,"Source or destination node does not exist")
    if req.source==req.destination:
        raise HTTPException(400,"Source and destination must differ")
    valid=[x for x in req.waypoints if x in GRAPH and x not in (req.source,req.destination)]
    req.waypoints=list(dict.fromkeys(valid))

    if req.waypoints:
        result=QPSO(GRAPH,req.source,req.destination,req.objective,req.waypoints,req.particles,req.iterations,req.seed).run()
    else:
        # No waypoints = the actual SIH26137 problem: point-to-point
        # traffic-aware route optimization over the whole graph.
        result=RouteQPSO(GRAPH,req.source,req.destination,req.objective,req.particles,req.iterations,req.seed).run()

    result["constraint_check"]=check_route(GRAPH,result["path"],req.vehicle)
    result["scenario"]=CURRENT_SCENARIO
    return serialise_result(GRAPH,result)

@app.post("/api/compare")
def compare_api(req: OptimizeRequest):
    if req.source not in GRAPH or req.destination not in GRAPH:
        raise HTTPException(400,"Source or destination node does not exist")
    req.waypoints=list(dict.fromkeys([x for x in req.waypoints if x in GRAPH and x not in (req.source,req.destination)]))
    data=compare(GRAPH,req)
    data["results"]=[serialise_result(GRAPH,r) for r in data["results"]]
    data["scenario"]=CURRENT_SCENARIO
    return data
