"""The phase-space page: spectrum, portraits, basins, bifurcation.

Three panels, because there are three different questions:

*Does this field run away?*  The eigenvalue disc.  Anything outside the unit
circle grows.  But an eigenvector with a negative component describes a state
Catharsis forbids, so the disc alone over-reports: the reachable growth, taken
over the non-negative cone, is the number that decides it.

*What shape is a relationship?*  The portrait: one tick's displacement sampled
over a slice, the invariant lines, and the basins found by settling every start.
The separatrix is not drawn — it appears as the boundary between basins, which
is a stronger claim than drawing a line.

*Where does behaviour switch?*  The sweep.  A jump is a border collision: the
start has crossed into another basin.

A trajectory from a real program can be laid over the portrait, which is the
point of the whole page -- the theory and the examples in one picture.
"""

from __future__ import annotations

import json
from html import escape

from .analysis import Spectrum, portrait, runtime_bifurcation, spectrum, trajectory
from .field import EMOTIONS

#: The default bifurcation: `coordination.feel` with its mutual doubt swept.
#: Below a critical doubt the group meets its shared goal; above it, nobody moves
#: first and it never leaves zero.  The `coordination.feel` /
#: `coordination_broken.feel` pair are two points either side of this line.
DEFAULT_SWEEP = """group team
agent alice bob charlie
join alice team
join bob team
join charlie team
goal team "rescue"
trust alice bob 0.6
trust bob charlie 0.6
trust charlie alice 0.6
doubt alice bob {}
doubt bob charlie {}
doubt charlie alice {}
hope alice 0.7
tick 25
"""

#: Slices worth offering by default: the antagonist pairs the language refuses
#: to collapse, plus the warm loop that turns out to be the one that runs away.
DEFAULT_PAIRS: tuple[tuple[str, str], ...] = (
    ("love", "trust"),
    ("trust", "doubt"),
    ("hope", "fear"),
    ("love", "anger"),
    ("gratitude", "resentment"),
    ("pride", "shame"),
    ("joy", "sadness"),
    ("grief", "sadness"),
)


def _spectrum_json(spec: Spectrum) -> dict:
    return {
        "axes": list(spec.axes),
        "values": [[z.real, z.imag] for z in spec.values],
        "radius": spec.radius,
        "reachable": spec.reachable,
        "runsAway": spec.runs_away,
        "kind": spec.kind,
        "verdict": spec.verdict,
        "mode": spec.dominant(8),
        "reachableMode": spec.reachable_dominant(8),
    }


def build_payload(
    pairs: tuple[tuple[str, str], ...] = DEFAULT_PAIRS,
    world=None,
    edge: tuple[str, str] | None = None,
    title: str = "field",
    sweep_source: str | None = None,
    sweep_label: str = "mutual doubt",
    resolution: int = 17,
    grid: int = 61,
    sweep_steps: int = 41,
) -> dict:
    """Everything the page draws, computed here so the page only renders.

    The last three arguments are the fidelity knobs -- how coarse the quiver
    grid is, how finely the basins are sampled, and how many times the sweep
    re-runs the whole program.  The defaults are what the page ships with; the
    tests turn them down, because a full-fidelity payload takes about half a
    minute and none of that time is spent on anything the tests are checking.
    """
    whole = spectrum(EMOTIONS)
    slices = []
    for axes in pairs:
        port = portrait(axes, resolution=resolution, grid=grid)
        slices.append(
            {
                "axes": list(axes),
                "spectrum": _spectrum_json(port.spectrum),
                "field": port.field,
                "manifolds": port.manifolds,
                "basins": port.basins,
                "corners": port.corners,
                "grid": port.grid,
                "path": (trajectory(world, edge[0], edge[1], axes) if world and edge else []),
            }
        )
    bifurcation = runtime_bifurcation(sweep_source or DEFAULT_SWEEP, steps=sweep_steps)
    collisions = [
        round((bifurcation[i - 1]["parameter"] + row["parameter"]) / 2, 4)
        for i, row in enumerate(bifurcation)
        if i and row["achieved"] != bifurcation[i - 1]["achieved"]
    ]
    return {
        "title": title,
        "whole": _spectrum_json(whole),
        "slices": slices,
        "edge": list(edge) if edge else None,
        "bifurcation": bifurcation,
        "collisions": collisions,
        "sweepLabel": sweep_label,
    }


def render_html(payload: dict) -> str:
    # allow_nan=False turns an inf or a NaN into an error here rather than
    # into a page that silently fails to parse itself.
    blob = json.dumps(payload, separators=(",", ":"), allow_nan=False)
    blob = blob.replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    return TEMPLATE.replace("__TITLE__", escape(payload["title"])).replace("__PAYLOAD__", blob)


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Phase space — __TITLE__</title>
<style>
  :root {
    color-scheme: light;
    --surface-0:#f4f4f2; --surface-1:#fcfcfb; --surface-2:#ebebe7; --border:#d8d8d2;
    --text-primary:#0b0b0b; --text-secondary:#52514e; --text-muted:#7a7973;
    --stable:#2a78d6; --unstable:#eb6834; --neutral:#1baf7a; --grid:#e2e2dd;
  }
  @media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
    color-scheme: dark;
    --surface-0:#121211; --surface-1:#1a1a19; --surface-2:#24241f; --border:#3a3a34;
    --text-primary:#fff; --text-secondary:#c3c2b7; --text-muted:#8f8e84;
    --stable:#3987e5; --unstable:#d95926; --neutral:#199e70; --grid:#2c2c27;
  } }
  :root[data-theme="dark"] {
    color-scheme: dark;
    --surface-0:#121211; --surface-1:#1a1a19; --surface-2:#24241f; --border:#3a3a34;
    --text-primary:#fff; --text-secondary:#c3c2b7; --text-muted:#8f8e84;
    --stable:#3987e5; --unstable:#d95926; --neutral:#199e70; --grid:#2c2c27;
  }
  * { box-sizing:border-box }
  body { margin:0; background:var(--surface-0); color:var(--text-primary);
         font:14px/1.55 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif }
  header { display:flex; align-items:baseline; gap:12px; flex-wrap:wrap; padding:14px 20px;
           border-bottom:1px solid var(--border); background:var(--surface-1) }
  header h1 { font-size:16px; margin:0; font-weight:650 }
  header .sub { color:var(--text-muted); font-size:13px }
  header .spacer { flex:1 }
  button, select { font:inherit; color:var(--text-primary); background:var(--surface-2);
    border:1px solid var(--border); border-radius:7px; padding:5px 10px; cursor:pointer }
  button:focus-visible, select:focus-visible { outline:2px solid var(--stable); outline-offset:2px }
  .verdict { padding:14px 20px; background:var(--surface-1); border-bottom:1px solid var(--border) }
  .verdict b { font-weight:650 }
  .verdict .runs { color:var(--unstable) }
  .verdict .held { color:var(--neutral) }
  .wrap { display:grid; grid-template-columns:repeat(auto-fit,minmax(330px,1fr)); gap:16px; padding:20px }
  .panel { background:var(--surface-1); border:1px solid var(--border); border-radius:11px; padding:14px }
  .panel h2 { font-size:13px; margin:0 0 2px; text-transform:uppercase; letter-spacing:.06em;
              color:var(--text-muted); font-weight:600 }
  .panel p.note { margin:2px 0 10px; color:var(--text-secondary); font-size:13px }
  svg { display:block; width:100%; height:auto; overflow:visible }
  .legend { display:flex; gap:14px; flex-wrap:wrap; font-size:12px; color:var(--text-secondary);
            margin-top:8px }
  .legend span { display:inline-flex; align-items:center; gap:6px }
  .legend i { width:14px; height:3px; border-radius:2px }
  table { border-collapse:collapse; width:100%; font-size:13px; margin-top:6px }
  td, th { padding:2px 8px 2px 0; text-align:left }
  td.n, th.n { text-align:right; font-variant-numeric:tabular-nums }
  th { color:var(--text-muted); font-weight:600 }
  .pick { display:flex; gap:8px; align-items:center; flex-wrap:wrap; padding:0 20px }
  #tip { position:fixed; pointer-events:none; z-index:9; background:var(--surface-1);
         border:1px solid var(--border); border-radius:8px; padding:7px 10px; font-size:12.5px;
         box-shadow:0 6px 22px rgba(0,0,0,.18); opacity:0; transition:opacity .09s }
  #tip.on { opacity:1 }
  code { font:12.5px ui-monospace,SFMono-Regular,Menlo,monospace; background:var(--surface-2);
         border:1px solid var(--border); border-radius:4px; padding:1px 5px }
</style>
</head>
<body>
<header>
  <h1>Phase space</h1>
  <span class="sub">__TITLE__ — Catharsis as a dynamical system</span>
  <span class="spacer"></span>
  <button id="themeToggle">◐ Theme</button>
</header>

<div class="verdict" id="verdict"></div>
<div class="pick">
  <label for="slice">Slice:</label>
  <select id="slice"></select>
  <span class="sub" id="sliceVerdict"></span>
</div>

<div class="wrap">
  <div class="panel">
    <h2>Eigenvalues <span id="discAxes" style="text-transform:none;letter-spacing:0"></span></h2>
    <p class="note">Anything outside the circle grows. The dashed ring is the reachable growth —
       what the non-negative cone actually permits.</p>
    <svg id="disc" viewBox="0 0 320 320"></svg>
    <div class="legend">
      <span><i style="background:var(--stable)"></i>decays</span>
      <span><i style="background:var(--unstable)"></i>grows</span>
    </div>
  </div>

  <div class="panel">
    <h2>Phase portrait</h2>
    <p class="note" id="portraitNote"></p>
    <svg id="portrait" viewBox="0 0 320 320"></svg>
    <div class="legend">
      <span id="legUnstable"><i style="background:var(--unstable)"></i>unstable manifold</span>
      <span id="legStable"><i style="background:var(--stable)"></i>stable manifold</span>
      <span><i style="background:var(--text-primary)"></i>a real run</span>
    </div>
  </div>

  <div class="panel">
    <h2>Bifurcation — the whole runtime</h2>
    <p class="note" id="sweepNote"></p>
    <svg id="sweepPlot" viewBox="0 0 320 250"></svg>
    <div class="legend">
      <span><i style="background:var(--neutral)"></i>shared goal met</span>
      <span><i style="background:var(--unstable)"></i>actions taken</span>
      <span><i style="background:var(--text-primary)"></i>border collision</span>
    </div>
  </div>

  <div class="panel">
    <h2>What grows</h2>
    <p class="note">The direction with the largest reachable growth, by axis.</p>
    <div id="modeTable"></div>
  </div>
</div>

<div id="tip" role="tooltip"></div>
<script type="application/json" id="payload">__PAYLOAD__</script>
<script>
(function(){
"use strict";
const DATA = JSON.parse(document.getElementById("payload").textContent);
const tip = document.getElementById("tip");
const NS = "http://www.w3.org/2000/svg";
const el=(n,a)=>{const e=document.createElementNS(NS,n);for(const k in a)e.setAttribute(k,a[k]);return e;};
const css=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const txt=(t,c)=>{const e=document.createElement(t);if(c!==undefined)e.textContent=c;return e;};
let current = 0;

function hover(node, text){
  node.addEventListener("pointerenter", e=>{ tip.textContent=text; tip.classList.add("on"); move(e); });
  node.addEventListener("pointermove", move);
  node.addEventListener("pointerleave", ()=>tip.classList.remove("on"));
  function move(e){
    const b=tip.getBoundingClientRect();
    let x=e.clientX+14, y=e.clientY+14;
    if(x+b.width>innerWidth-8) x=e.clientX-b.width-14;
    if(y+b.height>innerHeight-8) y=e.clientY-b.height-14;
    tip.style.left=Math.max(8,x)+"px"; tip.style.top=Math.max(8,y)+"px";
  }
}

/* ---------------- eigenvalue disc ---------------- */
function drawDisc(spec){
  const svg=document.getElementById("disc");
  while(svg.firstChild) svg.removeChild(svg.firstChild);
  const cx=160, cy=160, R=118;
  const lim=Math.max(1.15, spec.radius*1.08);
  const map=(re,im)=>[cx+R*re/lim, cy-R*im/lim];
  svg.appendChild(el("line",{x1:cx-R*1.05,y1:cy,x2:cx+R*1.05,y2:cy,stroke:css("--grid"),"stroke-width":1}));
  svg.appendChild(el("line",{x1:cx,y1:cy-R*1.05,x2:cx,y2:cy+R*1.05,stroke:css("--grid"),"stroke-width":1}));
  svg.appendChild(el("circle",{cx,cy,r:R/lim,fill:"none",stroke:css("--text-muted"),"stroke-width":1.5}));
  if(spec.reachable>0){
    svg.appendChild(el("circle",{cx,cy,r:R*spec.reachable/lim,fill:"none",
      stroke:css("--neutral"),"stroke-width":1.5,"stroke-dasharray":"4 4"}));
  }
  spec.values.forEach(([re,im])=>{
    const [x,y]=map(re,im);
    const grows=Math.hypot(re,im)>1.001;
    const dot=el("circle",{cx:x,cy:y,r:4.5,fill:grows?css("--unstable"):css("--stable"),
      stroke:css("--surface-1"),"stroke-width":1.5});
    hover(dot, `λ = ${re.toFixed(4)}${im>=0?"+":"−"}${Math.abs(im).toFixed(4)}i   |λ| = ${Math.hypot(re,im).toFixed(4)}`);
    svg.appendChild(dot);
  });
  const lab=el("text",{x:cx+R/lim+6,y:cy-6,"font-size":11,fill:css("--text-muted")});
  lab.textContent="|λ|=1"; svg.appendChild(lab);
}

/* ---------------- phase portrait ---------------- */
function drawPortrait(slice){
  const svg=document.getElementById("portrait");
  while(svg.firstChild) svg.removeChild(svg.firstChild);
  const P=28, S=264;                       // padding, plot size
  const X=v=>P+v*S, Y=v=>P+S-v*S;

  // basins as a coarse raster; the separatrix is wherever the label changes
  const g=slice.grid, cell=S/(g-1);
  const hues=[css("--stable"),css("--unstable"),css("--neutral"),css("--text-muted")];
  if(slice.corners.length>1){
    for(let r=0;r<g;r++) for(let c=0;c<g;c++){
      svg.appendChild(el("rect",{x:X(c/(g-1))-cell/2,y:Y(r/(g-1))-cell/2,width:cell,height:cell,
        fill:hues[slice.basins[r][c]%hues.length],opacity:0.16,stroke:"none"}));
    }
    // the separatrix: every cell edge where the destination changes.  Drawn
    // rather than shaded, because the boundary is the whole finding.
    for(let r=0;r<g;r++) for(let c=0;c<g;c++){
      const here=slice.basins[r][c];
      if(c+1<g && slice.basins[r][c+1]!==here){
        const x=X((c+0.5)/(g-1));
        svg.appendChild(el("line",{x1:x,y1:Y(r/(g-1))-cell/2,x2:x,y2:Y(r/(g-1))+cell/2,
          stroke:css("--text-primary"),"stroke-width":1.6,opacity:.55}));
      }
      if(r+1<g && slice.basins[r+1][c]!==here){
        const y=Y((r+0.5)/(g-1));
        svg.appendChild(el("line",{x1:X(c/(g-1))-cell/2,y1:y,x2:X(c/(g-1))+cell/2,y2:y,
          stroke:css("--text-primary"),"stroke-width":1.6,opacity:.55}));
      }
    }
  }
  svg.appendChild(el("rect",{x:P,y:P,width:S,height:S,fill:"none",stroke:css("--border")}));

  // one tick's displacement, drawn in pixels: length scaled against the largest
  // displacement on the slice, so a slow field is still legible
  const biggest=Math.max(1e-9,...slice.field.map(v=>Math.hypot(v.dx,v.dy)));
  const step=S/(Math.sqrt(slice.field.length)-1);
  slice.field.forEach(v=>{
    const m=Math.hypot(v.dx,v.dy);
    if(m<1e-6) return;
    const len=(0.2+0.8*Math.min(1,m/biggest))*step*0.82;
    const x1=X(v.x), y1=Y(v.y);
    const x2=x1+(v.dx/m)*len, y2=y1-(v.dy/m)*len;   // Y is inverted
    const arrow=el("line",{x1,y1,x2,y2,stroke:css("--text-muted"),"stroke-width":1.1,
      opacity:0.6,"marker-end":"url(#tipArrow)"});
    hover(arrow, `at ${slice.axes[0]} ${v.x.toFixed(2)}, ${slice.axes[1]} ${v.y.toFixed(2)}: `
      + `one tick moves it ${v.dx>=0?"+":""}${v.dx.toFixed(3)}, ${v.dy>=0?"+":""}${v.dy.toFixed(3)}`);
    svg.appendChild(arrow);
  });
  const defs=el("defs");
  const mk=el("marker",{id:"tipArrow",viewBox:"0 0 8 8",refX:6,refY:4,markerWidth:4,markerHeight:4,
    orient:"auto-start-reverse"});
  mk.appendChild(el("path",{d:"M0,1 L6,4 L0,7 z",fill:css("--text-muted"),opacity:0.7}));
  defs.appendChild(mk); svg.insertBefore(defs, svg.firstChild);

  // invariant lines through the origin, clipped to the unit square.  A slice can
  // have a manifold whose only clipped segment lies outside the non-negative
  // square, so the legend follows what was drawn rather than what exists.
  const drawn={stable:false, unstable:false};
  slice.manifolds.forEach(m=>{
    if(m.slope===null || !isFinite(m.slope)) return;
    const pts=[];
    for(const t of [0,1]){ const y=m.slope*t; if(y>=0&&y<=1) pts.push([t,y]); }
    for(const y of [0,1]){ const t=y/m.slope; if(isFinite(t)&&t>=0&&t<=1) pts.push([t,y]); }
    const uniq=[];
    pts.forEach(pt=>{ if(!uniq.some(u=>Math.abs(u[0]-pt[0])<1e-9 && Math.abs(u[1]-pt[1])<1e-9)) uniq.push(pt); });
    if(uniq.length<2) return;
    pts.length=0; pts.push(uniq[0], uniq[1]);
    const line=el("line",{x1:X(pts[0][0]),y1:Y(pts[0][1]),x2:X(pts[1][0]),y2:Y(pts[1][1]),
      stroke:m.kind==="unstable"?css("--unstable"):css("--stable"),"stroke-width":2,
      "stroke-dasharray":m.kind==="stable"?"6 4":""});
    hover(line, `${m.kind} manifold — λ ${m.eigenvalue.toFixed(3)}, slope ${m.slope.toFixed(3)}`);
    svg.appendChild(line);
    drawn[m.kind]=true;
  });
  document.getElementById("legUnstable").style.display=drawn.unstable?"":"none";
  document.getElementById("legStable").style.display=drawn.stable?"":"none";

  // a real run laid over the theory
  if(slice.path && slice.path.length>1){
    let d="";
    slice.path.forEach((p,i)=>{ d += (i?" L":"M")+X(p.x)+","+Y(p.y); });
    svg.appendChild(el("path",{d,fill:"none",stroke:css("--text-primary"),"stroke-width":2,opacity:.85}));
    slice.path.forEach((p,i)=>{
      if(i%3 && i!==slice.path.length-1) return;
      const dot=el("circle",{cx:X(p.x),cy:Y(p.y),r:2.6,fill:css("--text-primary")});
      hover(dot, `${p.label} — tick ${p.tick}: ${slice.axes[0]} ${p.x.toFixed(2)}, ${slice.axes[1]} ${p.y.toFixed(2)}`);
      svg.appendChild(dot);
    });
  }

  [0,0.5,1].forEach(t=>{
    const tx=el("text",{x:X(t),y:P+S+13,"text-anchor":"middle","font-size":10,fill:css("--text-muted")});
    tx.textContent=t.toFixed(t===0.5?1:0); svg.appendChild(tx);
    const ty=el("text",{x:P-6,y:Y(t)+3,"text-anchor":"end","font-size":10,fill:css("--text-muted")});
    ty.textContent=t.toFixed(t===0.5?1:0); svg.appendChild(ty);
  });
  const xl=el("text",{x:P+S/2,y:P+S+28,"text-anchor":"middle","font-size":12,fill:css("--text-secondary")});
  xl.textContent=slice.axes[0]; svg.appendChild(xl);
  const yl=el("text",{x:P-16,y:P+S/2,"text-anchor":"middle","font-size":12,fill:css("--text-secondary"),
    transform:`rotate(-90 ${P-16} ${P+S/2})`});
  yl.textContent=slice.axes[1]; svg.appendChild(yl);
}

/* ---------------- sweep ---------------- */
function drawSweep(){
  const svg=document.getElementById("sweepPlot");
  while(svg.firstChild) svg.removeChild(svg.firstChild);
  const rows=DATA.bifurcation;
  if(!rows.length) return;
  const P=34, W=258, H=170;
  const lo=rows[0].parameter, hi=rows[rows.length-1].parameter;
  const maxActs=Math.max(1,...rows.map(r=>r.actions));
  const X=v=>P+(v-lo)/(hi-lo||1)*W, Y=v=>P+H-v*H;
  svg.appendChild(el("rect",{x:P,y:P,width:W,height:H,fill:"none",stroke:css("--border")}));
  [0,0.5,1].forEach(t=>{
    svg.appendChild(el("line",{x1:P,y1:Y(t),x2:P+W,y2:Y(t),stroke:css("--grid"),"stroke-width":1}));
    const ty=el("text",{x:P-6,y:Y(t)+3,"text-anchor":"end","font-size":10,fill:css("--text-muted")});
    ty.textContent=t.toFixed(t===0.5?1:0); svg.appendChild(ty);
    const tx=el("text",{x:X(lo+(hi-lo)*t),y:P+H+13,"text-anchor":"middle","font-size":10,fill:css("--text-muted")});
    tx.textContent=(lo+(hi-lo)*t).toFixed(1); svg.appendChild(tx);
  });
  // the collision, drawn first so the curves sit on top of it
  DATA.collisions.forEach(c=>{
    svg.appendChild(el("line",{x1:X(c),y1:P,x2:X(c),y2:P+H,stroke:css("--text-primary"),
      "stroke-width":1.6,"stroke-dasharray":"4 3",opacity:.8}));
    const lab=el("text",{x:X(c)+5,y:P+13,"font-size":11,fill:css("--text-primary")});
    lab.textContent=c.toFixed(2); svg.appendChild(lab);
  });
  const series=[
    ["progress", css("--neutral"), r=>Math.min(1,r.progress)],
    ["actions",  css("--unstable"), r=>r.actions/maxActs],
  ];
  series.forEach(([name,colour,get])=>{
    let d="";
    rows.forEach((r,i)=>{ d += (i?" L":"M")+X(r.parameter)+","+Y(get(r)); });
    svg.appendChild(el("path",{d,fill:"none",stroke:css("--surface-1"),"stroke-width":5,opacity:.9}));
    svg.appendChild(el("path",{d,fill:"none",stroke:colour,"stroke-width":2}));
  });
  rows.forEach(r=>{
    const dot=el("circle",{cx:X(r.parameter),cy:Y(Math.min(1,r.progress)),r:6,fill:"transparent"});
    hover(dot, `${DATA.sweepLabel} ${r.parameter.toFixed(3)} — progress ${(r.progress*100).toFixed(0)}%, `
      + `${r.actions} actions, goal ${r.achieved?"met":"not met"}`);
    svg.appendChild(dot);
  });
  const xl=el("text",{x:P+W/2,y:P+H+28,"text-anchor":"middle","font-size":12,fill:css("--text-secondary")});
  xl.textContent=DATA.sweepLabel; svg.appendChild(xl);
}

/* ---------------- text ---------------- */
function drawVerdict(){
  const host=document.getElementById("verdict");
  host.replaceChildren();
  const w=DATA.whole;
  const b=txt("b","The whole field: ");
  host.appendChild(b);
  const v=txt("span", w.verdict);
  v.className = w.runsAway ? "runs" : "held";
  host.appendChild(v);
  host.appendChild(txt("div",
    "Spectral radius is what the linear map does; reachable growth is what the non-negative cone allows. "
    + "When they disagree, the cone wins — an eigenvector needing a negative emotion names a state Catharsis has no way to be in."));
}

function drawMode(slice){
  const host=document.getElementById("modeTable");
  host.replaceChildren();
  const rows=[["whole field", DATA.whole.reachableMode], [slice.axes.join(" / "), slice.spectrum.reachableMode]];
  rows.forEach(([label, mode])=>{
    host.appendChild(txt("h3", label)).style.cssText="font-size:13px;margin:10px 0 2px;font-weight:650";
    const table=document.createElement("table");
    if(!mode.length){ host.appendChild(txt("p","nothing grows here")).className="note"; return; }
    mode.forEach(([name,value])=>{
      const tr=document.createElement("tr");
      tr.appendChild(txt("td",name));
      tr.appendChild(txt("td",value.toFixed(3))).className="n";
      table.appendChild(tr);
    });
    host.appendChild(table);
  });
}

function show(i){
  current=i;
  const slice=DATA.slices[i];
  drawDisc(slice.spectrum);
  document.getElementById("discAxes").textContent = "— " + slice.axes.join(" / ");
  drawPortrait(slice);
  drawSweep();
  drawMode(slice);
  document.getElementById("sliceVerdict").textContent = slice.spectrum.verdict;
  document.getElementById("portraitNote").textContent =
    "Arrows are one tick's displacement. " +
    (slice.corners.length>1 ? "Shading is the basin each start falls into. " : "Every start settles in one place. ")
    + (slice.path.length ? "The dark line is " + (DATA.edge? DATA.edge.join(" → ") : "a real run") + "." : "");
  document.getElementById("sweepNote").textContent = DATA.collisions.length
    ? "The same program run 41 times, varying " + DATA.sweepLabel + ". Behaviour switches at "
      + DATA.collisions.map(c=>c.toFixed(2)).join(", ")
      + " — a border collision, which is what a bifurcation looks like in a piecewise system."
    : "The same program run 41 times, varying " + DATA.sweepLabel + ". No switch in this range.";
}

const picker=document.getElementById("slice");
DATA.slices.forEach((s,i)=>{
  const o=document.createElement("option"); o.value=String(i); o.textContent=s.axes.join(" / ");
  picker.appendChild(o);
});
picker.onchange=e=>show(Number(e.target.value));
document.getElementById("themeToggle").onclick=()=>{
  const root=document.documentElement;
  const dark=css("--surface-0")==="#121211";
  root.setAttribute("data-theme", dark?"light":"dark");
  show(current);
};
drawVerdict();
show(0);
})();
</script>
</body>
</html>
"""
