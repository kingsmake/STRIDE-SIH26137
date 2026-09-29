import React, { useEffect, useMemo, useState } from "react";
import L from "leaflet";
import { MapContainer, TileLayer, CircleMarker, Polyline, Popup, useMap } from "react-leaflet";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

function FitRoute({ points }) {
  const map = useMap();
  useEffect(() => {
    if (!points?.length) return;
    const bounds=L.latLngBounds(points.map(p=>[p.lat,p.lon]));
    map.fitBounds(bounds,{padding:[30,30],maxZoom:15});
  }, [points,map]);
  return null;
}

function App() {
  const [network,setNetwork]=useState(null);
  const [source,setSource]=useState(0);
  const [destination,setDestination]=useState(17);
  const [waypoints,setWaypoints]=useState([2,5,12]);
  const [objective,setObjective]=useState("balanced");
  const [vehicle,setVehicle]=useState("car");
  const [particles,setParticles]=useState(28);
  const [iterations,setIterations]=useState(60);
  const [scenario,setScenario]=useState("normal");
  const [severity,setSeverity]=useState(0.65);
  const [result,setResult]=useState(null);
  const [comparison,setComparison]=useState(null);
  const [loading,setLoading]=useState(false);
  const [error,setError]=useState("");

  useEffect(()=>{ fetch(`${API}/api/network`).then(r=>r.json()).then(setNetwork).catch(()=>setError("Backend not running. Start FastAPI on port 8000.")); },[]);
  const nodes=network?.nodes||[];
  const edges=network?.edges||[];
  const nodeById=useMemo(()=>Object.fromEntries(nodes.map(n=>[n.id,n])),[nodes]);

  const pathPoints=result?.path?.map(id=>nodeById[id]).filter(Boolean)||[];
  const routeEdges= result?.edges || [];

  async function setTraffic(mode=scenario) {
    setError("");
    await fetch(`${API}/api/scenario`,{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({mode,severity,seed:42})});
    const n=await fetch(`${API}/api/network`).then(r=>r.json());
    setNetwork(n);
    setResult(null);
    setComparison(null);
  }

  async function runOptimize() {
    setLoading(true); setError("");
    try {
      const r=await fetch(`${API}/api/optimize`,{method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({source,destination,waypoints,objective,vehicle,particles,iterations,seed:42})});
      const data=await r.json(); if(!r.ok) throw new Error(data.detail||"Optimization failed");
      setResult(data);
    } catch(e){setError(e.message)} finally{setLoading(false)}
  }

  async function runCompare() {
    setLoading(true); setError("");
    try {
      const r=await fetch(`${API}/api/compare`,{method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({source,destination,waypoints,objective,particles,iterations,seed:42})});
      const data=await r.json(); if(!r.ok) throw new Error(data.detail||"Benchmark failed");
      setComparison(data);
      const q=data.results.find(x=>x.algorithm==="QPSO"); if(q) setResult(q);
    } catch(e){setError(e.message)} finally{setLoading(false)}
  }

  const chart=result?.convergence?.map((cost,i)=>({iteration:i+1,cost}))||[];

  return <div className="app">
    <header className="topbar">
      <div>
        <div className="eyebrow">SMART INDIA HACKATHON 2026 • SIH26137</div>
        <h1>S.T.R.I.D.E.</h1>
        <p>Swarm-based Traffic Routing and Intelligent Density Engine</p>
      </div>
      <div className="status"><span className="dot"/> OFFLINE RESEARCH DEMO</div>
    </header>

    <main className="layout">
      <aside className="panel controls">
        <h2>Route Experiment</h2>
        <label>Source</label>
        <select value={source} onChange={e=>setSource(+e.target.value)}>{nodes.map(n=><option key={n.id} value={n.id}>{n.id} — {n.name}</option>)}</select>
        <label>Destination</label>
        <select value={destination} onChange={e=>setDestination(+e.target.value)}>{nodes.map(n=><option key={n.id} value={n.id}>{n.id} — {n.name}</option>)}</select>
        <label>Optional waypoints</label>
        <div className="checks">{nodes.filter(n=>n.id!==source&&n.id!==destination).map(n=>
          <label className="check" key={n.id}><input type="checkbox" checked={waypoints.includes(n.id)}
            onChange={e=>setWaypoints(w=>e.target.checked?[...w,n.id]:w.filter(x=>x!==n.id))}/>{n.id}</label>)}</div>
        <label>Objective</label>
        <select value={objective} onChange={e=>setObjective(e.target.value)}>
          <option value="fastest">Fastest</option><option value="shortest">Shortest</option>
          <option value="balanced">Balanced</option><option value="low_congestion">Low congestion</option>
        </select>
        <label>Vehicle</label>
        <select value={vehicle} onChange={e=>setVehicle(e.target.value)}>
          <option value="car">Car</option><option value="van">Delivery van</option><option value="truck">Delivery truck</option>
        </select>

        <div className="row"><div><label>Particles</label><input type="number" min="8" max="100" value={particles} onChange={e=>setParticles(+e.target.value)}/></div>
        <div><label>Iterations</label><input type="number" min="10" max="300" value={iterations} onChange={e=>setIterations(+e.target.value)}/></div></div>

        <h3>Traffic Scenario</h3>
        <select value={scenario} onChange={e=>setScenario(e.target.value)}>
          <option value="normal">Normal</option><option value="rush_hour">Rush hour</option><option value="incident">Incident</option>
        </select>
        <input type="range" min="0" max="1" step="0.05" value={severity} onChange={e=>setSeverity(+e.target.value)}/>
        <div className="range-label"><span>Severity</span><strong>{Math.round(severity*100)}%</strong></div>
        <button className="secondary" onClick={()=>setTraffic(scenario)}>Apply traffic change</button>

        <button className="primary" disabled={loading||!network} onClick={runOptimize}>{loading?"Optimizing…":"Run QPSO Optimization"}</button>
        <button className="secondary" disabled={loading||!network} onClick={runCompare}>Benchmark QPSO vs Baselines</button>

        {error&&<div className="error">{error}</div>}
        <div className="method-note">
          <b>How the route is built</b>
          <span>{waypoints.length>0
            ? "Continuous random-key particle → waypoint visiting order → shortest-path stitching → feasible road path → objective cost."
            : "Continuous per-node priority vector → priority-guided spanning-tree decode (always loop-free & feasible) → objective cost. See backend/priority_encoding.py."}</span>
        </div>
      </aside>

      <section className="map-panel">
        <MapContainer center={[20.002,73.79]} zoom={13} scrollWheelZoom className="map">
          <TileLayer attribution='&copy; OpenStreetMap contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"/>
          {edges.map((e,i)=>{const a=nodeById[e.source],b=nodeById[e.target]; if(!a||!b)return null;
            const c=e.congestion??0.2; return <Polyline key={i} positions={[[a.lat,a.lon],[b.lat,b.lon]]}
              pathOptions={{color:c>.7?"#e24a4a":c>.45?"#f59e0b":"#4f8cff",weight:4,opacity:.55}}/>})}
          {pathPoints.length>1&&<Polyline positions={pathPoints.map(p=>[p.lat,p.lon])} pathOptions={{color:"#19d3ae",weight:8,opacity:.95}}/>}
          {nodes.map(n=><CircleMarker key={n.id} center={[n.lat,n.lon]} radius={n.id===source||n.id===destination?9:6}
             pathOptions={{color:n.id===source?"#27c46b":n.id===destination?"#ff5d73":"#ffffff",fillColor:n.id===source?"#27c46b":n.id===destination?"#ff5d73":"#26364a",fillOpacity:1,weight:2}}>
             <Popup><b>{n.id} — {n.name}</b><br/>Traffic node</Popup>
          </CircleMarker>)}
          <FitRoute points={pathPoints}/>
        </MapContainer>
        <div className="legend"><span><i className="green"/>Optimized route</span><span><i className="blue"/>Low traffic</span><span><i className="orange"/>Elevated</span><span><i className="red"/>Congested</span></div>
      </section>

      <aside className="panel results">
        <h2>Optimization Trace</h2>
        {result ? <>
          <div className="hero-metric"><span>Selected route cost</span><strong>{result.metrics.cost.toFixed(2)}</strong><small>{result.algorithm}</small></div>
          <div className="metric-grid">
            <div><span>Travel time</span><b>{result.metrics.travel_time_min.toFixed(1)} min</b></div>
            <div><span>Distance</span><b>{result.metrics.distance_km.toFixed(2)} km</b></div>
            <div><span>Avg congestion</span><b>{(result.metrics.congestion*100).toFixed(0)}%</b></div>
            <div><span>Iterations</span><b>{result.iterations}</b></div>
          </div>
          <div className="route-sequence"><span>Route sequence</span><strong>{result.path.join(" → ")}</strong></div>
          {result.constraint_check&&<div className={`constraint-check ${result.constraint_check.feasible?"ok":"bad"}`}>
            <span>{result.constraint_check.feasible?"✔":"✖"} {result.constraint_check.vehicle} constraint check</span>
            {!result.constraint_check.feasible&&<ul>{result.constraint_check.violations.map((v,i)=><li key={i}>{v.reason}</li>)}</ul>}
          </div>}
          <h3>Convergence</h3>
          <div className="chart"><ResponsiveContainer width="100%" height={190}>
            <LineChart data={chart}><CartesianGrid strokeDasharray="3 3" stroke="#26364a"/><XAxis dataKey="iteration" stroke="#8291a8"/><YAxis stroke="#8291a8"/><Tooltip/>
              <Line type="monotone" dataKey="cost" stroke="#19d3ae" dot={false} strokeWidth={2}/></LineChart>
          </ResponsiveContainer></div>
          <h3>Edge explanation</h3>
          <div className="edge-list">{routeEdges.map((e,i)=><div key={i}><span>{e.source} → {e.target}</span><small>{e.time_min} min · {(e.congestion*100).toFixed(0)}% congestion</small></div>)}</div>
        </>:<div className="empty">Run an experiment to see route quality, convergence and edge-level explanation.</div>}

        {comparison&&<div className="benchmark">
          <h3>Baseline comparison</h3>
          <table><thead><tr><th>Method</th><th>Cost</th><th>Time</th><th>Distance</th></tr></thead><tbody>
          {comparison.results.map((r,i)=><tr key={i}><td>{r.algorithm}</td><td>{r.metrics.cost.toFixed(2)}</td><td>{r.metrics.travel_time_min.toFixed(1)}</td><td>{r.metrics.distance_km.toFixed(2)}</td></tr>)}
          </tbody></table>
        </div>}
      </aside>
    </main>
    <footer>Research prototype • Controlled traffic scenarios • CPU-based QPSO • No claim of guaranteed global optimum</footer>
  </div>
}
export default App;
