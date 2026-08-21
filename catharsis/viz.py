"""Replaying a run as a graph you can scrub through.

A Catharsis program is a field simulation, so a single end-state picture is a
photograph of a river: the reputation example is *about* doubt travelling from
one entity to another over ten ticks, and the final frame is precisely the view
that hides it.  So the output here is every frame of the run, with transport
controls.

The one real design decision is what an edge means.  Alice feels up to twenty
things about Bob at once and the language's whole claim is that a contradiction
is data, so any projection that paints that edge a single colour has thrown away
the thing the runtime exists to model.  What is drawn instead is **three arcs per
ordered pair**, in fixed lanes:

``bond``       what pulls toward   -- love, trust, hope, gratitude, joy, curiosity
``grievance``  what pushes away    -- anger, resentment, doubt, fear, jealousy, envy
``burden``     what simply weighs  -- grief, guilt, shame, sadness, loneliness, regret

An ambivalent relationship therefore *looks* ambivalent: two thick arcs running
alongside each other, which is a picture a net-sentiment score cannot draw.  The
lane each channel occupies never changes, so the graph stays readable without
colour at all, and the twenty individual axes live in the tooltip and the detail
panel, where identity belongs.
"""

from __future__ import annotations

import json
from html import escape

from .field import EMOTIONS

#: Which axes feed which arc.  Every emotion belongs to exactly one channel, and
#: ``surprise`` is deliberately absent -- it is a spike that lasts half a tick and
#: says nothing about the shape of a relationship.
#:
#: ``pride`` is the one genuine judgement call.  Functionally it distances: it is
#: in the inhibitor of nearly every repairing action.  But it lives almost
#: entirely on the self-loop, where it means self-regard and belongs beside
#: self-love and self-trust, so it is drawn as bond and the tooltip says which
#: axis it actually is.
CHANNELS: dict[str, tuple[str, ...]] = {
    "bond": ("love", "trust", "hope", "gratitude", "joy", "curiosity", "pride"),
    "grievance": ("anger", "resentment", "doubt", "fear", "jealousy", "envy"),
    "burden": ("grief", "guilt", "shame", "sadness", "loneliness", "regret"),
}

CHANNEL_LABELS = {
    "bond": "Bond — what pulls toward",
    "grievance": "Grievance — what pushes away",
    "burden": "Burden — what weighs",
}

#: Slots 1-3 of the reference categorical palette, which are the three that clear
#: the all-pairs colour-vision floors in both modes.  Colour is a convenience
#: here rather than the encoding: each channel also owns a fixed lane, so the
#: graph survives being read in greyscale.
PALETTE = {
    "bond": {"light": "#1baf7a", "dark": "#199e70"},
    "grievance": {"light": "#eb6834", "dark": "#d95926"},
    "burden": {"light": "#2a78d6", "dark": "#3987e5"},
}

#: A channel's arc is drawn at full weight once its axes sum to this.
CHANNEL_FULL = 2.0


def channel_totals(charge: dict[str, float]) -> dict[str, float]:
    """Collapse a charge vector onto the three drawable channels."""
    return {name: sum(charge.get(emotion, 0.0) for emotion in axes) for name, axes in CHANNELS.items()}


def build_payload(world, title: str, source: str) -> dict:
    """Everything the page needs, in one JSON-serialisable blob."""
    if not world.frames:
        raise ValueError("this world was not recorded; construct it with World(record=True)")
    return {
        "title": title,
        "source": source,
        "agents": list(world.agents),
        "emotions": list(EMOTIONS),
        "channels": {name: list(axes) for name, axes in CHANNELS.items()},
        "channelLabels": CHANNEL_LABELS,
        "palette": PALETTE,
        "channelFull": CHANNEL_FULL,
        "frames": world.frames,
    }


def render_html(payload: dict) -> str:
    """Wrap the payload in the player.  The result is a standalone file."""
    blob = json.dumps(payload, separators=(",", ":"), sort_keys=False)
    # A JSON island cannot be allowed to close the script element that holds it.
    blob = blob.replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    return TEMPLATE.replace("__TITLE__", escape(payload["title"])).replace("__PAYLOAD__", blob)


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__ — Catharsis</title>
<style>
  :root {
    color-scheme: light;
    --surface-0: #f4f4f2;
    --surface-1: #fcfcfb;
    --surface-2: #ebebe7;
    --border: #d8d8d2;
    --text-primary: #0b0b0b;
    --text-secondary: #52514e;
    --text-muted: #7a7973;
    --bond: #1baf7a;
    --grievance: #eb6834;
    --burden: #2a78d6;
    --node: #ffffff;
    --node-ring: #9a9a92;
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      color-scheme: dark;
      --surface-0: #121211;
      --surface-1: #1a1a19;
      --surface-2: #24241f;
      --border: #3a3a34;
      --text-primary: #ffffff;
      --text-secondary: #c3c2b7;
      --text-muted: #8f8e84;
      --bond: #199e70;
      --grievance: #d95926;
      --burden: #3987e5;
      --node: #2b2b27;
      --node-ring: #6e6d64;
    }
  }
  :root[data-theme="dark"] {
    color-scheme: dark;
    --surface-0: #121211;
    --surface-1: #1a1a19;
    --surface-2: #24241f;
    --border: #3a3a34;
    --text-primary: #ffffff;
    --text-secondary: #c3c2b7;
    --text-muted: #8f8e84;
    --bond: #199e70;
    --grievance: #d95926;
    --burden: #3987e5;
    --node: #2b2b27;
    --node-ring: #6e6d64;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    /* An app shell: the page never scrolls, the panels do.  Otherwise the graph
       drifts below the fold as soon as an entity has a lot of memories. */
    height: 100vh;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    background: var(--surface-0);
    color: var(--text-primary);
    font: 14px/1.5 ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  }
  header {
    display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap;
    padding: 14px 20px; border-bottom: 1px solid var(--border); background: var(--surface-1);
  }
  header h1 { font-size: 16px; margin: 0; font-weight: 650; }
  header .sub { color: var(--text-muted); font-size: 13px; }
  header .spacer { flex: 1; }
  button, select {
    font: inherit; color: var(--text-primary); background: var(--surface-2);
    border: 1px solid var(--border); border-radius: 7px; padding: 5px 10px; cursor: pointer;
  }
  button:hover { border-color: var(--text-muted); }
  button:disabled { opacity: .4; cursor: default; }
  button:focus-visible, select:focus-visible, input:focus-visible {
    outline: 2px solid var(--burden); outline-offset: 2px;
  }
  main { display: grid; grid-template-columns: minmax(0,1fr) 340px; gap: 0;
         align-items: stretch; flex: 1; min-height: 0; }
  @media (max-width: 900px) {
    main { grid-template-columns: minmax(0,1fr); }
    body { height: auto; overflow: auto; }
    #stage { min-height: 460px; }
  }
  #stage { position: relative; min-height: 320px; background: var(--surface-1); overflow: hidden; }
  #graph { display: block; width: 100%; height: 100%; touch-action: none; }
  aside {
    border-left: 1px solid var(--border); background: var(--surface-1);
    padding: 16px; overflow-y: auto; min-height: 0;
  }
  @media (max-width: 900px) { aside { border-left: 0; border-top: 1px solid var(--border); } }
  aside h2 { font-size: 13px; text-transform: uppercase; letter-spacing: .06em;
             color: var(--text-muted); margin: 0 0 8px; font-weight: 600; }
  aside h3 { font-size: 14px; margin: 16px 0 6px; font-weight: 650; }
  .transport {
    display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
    padding: 12px 20px; border-top: 1px solid var(--border); background: var(--surface-1);
  }
  .transport input[type=range] { flex: 1; min-width: 180px; accent-color: var(--burden); }
  .moment { padding: 0 20px 14px; background: var(--surface-1);
            display: grid; grid-template-columns: minmax(0,1fr) minmax(0,360px); gap: 20px; }
  @media (max-width: 760px) { .moment { grid-template-columns: minmax(0,1fr); } }
  #source {
    margin: 0; max-height: 132px; overflow-y: auto; border: 1px solid var(--border);
    border-radius: 7px; background: var(--surface-2); padding: 6px 0;
    font: 12px/1.55 ui-monospace, SFMono-Regular, Menlo, monospace;
  }
  #source div { padding: 0 10px; white-space: pre; color: var(--text-secondary); }
  #source div.on { background: var(--surface-1); color: var(--text-primary); font-weight: 650;
                   box-shadow: inset 3px 0 0 var(--burden); }
  #source div.blank { color: var(--text-muted); }
  .moment code {
    font: 13px/1.6 ui-monospace, SFMono-Regular, Menlo, monospace;
    background: var(--surface-2); padding: 2px 7px; border-radius: 5px;
    border: 1px solid var(--border); word-break: break-word;
  }
  .moment .events { margin: 8px 0 0; padding: 0; list-style: none;
                    color: var(--text-secondary); font-size: 13px; }
  .moment .events li { padding: 1px 0 1px 14px; text-indent: -14px; }
  .legend { display: flex; gap: 16px; flex-wrap: wrap; padding: 10px 20px 0; font-size: 13px; }
  .legend span { display: inline-flex; align-items: center; gap: 7px; color: var(--text-secondary); }
  .legend i { width: 20px; height: 3px; border-radius: 2px; display: inline-block; }
  .num { font-variant-numeric: tabular-nums; }
  .val { color: var(--text-primary); font-weight: 650; }
  .lbl { color: var(--text-secondary); }
  table { border-collapse: collapse; width: 100%; font-size: 13px; }
  th, td { text-align: left; padding: 3px 8px 3px 0; vertical-align: top; }
  th { color: var(--text-muted); font-weight: 600; }
  td.n, th.n { text-align: right; font-variant-numeric: tabular-nums; }
  .bar { height: 3px; border-radius: 2px; display: block; min-width: 2px; }
  #tip {
    position: fixed; pointer-events: none; z-index: 9; max-width: 320px;
    background: var(--surface-1); border: 1px solid var(--border); border-radius: 9px;
    padding: 9px 11px; font-size: 13px; box-shadow: 0 6px 24px rgba(0,0,0,.18);
    opacity: 0; transition: opacity .09s;
  }
  #tip.on { opacity: 1; }
  #tip .head { font-weight: 650; margin-bottom: 5px; }
  #tip .row { display: flex; align-items: center; gap: 7px; }
  #tip .key { width: 18px; height: 3px; border-radius: 2px; flex: none; }
  .muted { color: var(--text-muted); }
  .pill { display: inline-block; font-size: 11px; border: 1px solid var(--border);
          border-radius: 999px; padding: 0 7px; color: var(--text-secondary);
          background: var(--surface-2); margin-right: 4px; }
  .mem { border-left: 2px solid var(--border); padding-left: 9px; margin: 9px 0; }
  .mem .claim { font-style: italic; }
  #tableView { padding: 0 20px 20px; background: var(--surface-1); }
  #tableView[hidden] { display: none; }
  .hint { color: var(--text-muted); font-size: 12px; }
  .node-hit { cursor: pointer; }
  .node-label { paint-order: stroke fill; stroke-width: 3.5px; stroke-linejoin: round; }
  .edge-hit { cursor: pointer; }
  .selected-ring { fill: none; stroke: var(--text-primary); stroke-width: 2; }
</style>
</head>
<body>
<header>
  <h1>__TITLE__</h1>
  <span class="sub">Catharsis — programs with feelings</span>
  <span class="spacer"></span>
  <button id="tableToggle" aria-expanded="false">Table view</button>
  <button id="themeToggle" title="Switch theme">◐ Theme</button>
</header>

<div class="legend" id="legend"></div>

<main>
  <div id="stage"><svg id="graph" role="img" aria-label="Relationship graph"></svg></div>
  <aside id="panel"><h2>Details</h2><p class="hint">Hover an arc or a node. Click to pin it here.</p></aside>
</main>

<div class="transport">
  <button id="toStart" title="Rewind to the start (Home)">⏮</button>
  <button id="stepBack" title="Step back (←)">◀</button>
  <button id="play" title="Play / pause (Space)">▶ Play</button>
  <button id="stop" title="Stop and rewind">⏹ Stop</button>
  <button id="stepFwd" title="Step forward (→)">▶</button>
  <button id="toEnd" title="Jump to the end (End)">⏭</button>
  <input type="range" id="scrub" min="0" value="0" step="1" aria-label="Moment">
  <span class="num muted" id="counter"></span>
  <select id="speed" aria-label="Playback speed">
    <option value="1200">0.5×</option>
    <option value="600" selected>1×</option>
    <option value="300">2×</option>
    <option value="120">5×</option>
  </select>
</div>

<div class="moment">
  <div>
    <code id="momentLabel"></code>
    <ul class="events" id="events"></ul>
  </div>
  <pre id="source" aria-label="Program source"></pre>
</div>

<div id="tableView" hidden></div>
<div id="tip" role="tooltip"></div>

<script type="application/json" id="payload">__PAYLOAD__</script>
<script>
(function () {
  "use strict";
  const DATA = JSON.parse(document.getElementById("payload").textContent);
  const FRAMES = DATA.frames;
  const CHANNELS = DATA.channels;
  const CHANNEL_KEYS = Object.keys(CHANNELS);
  const FULL = DATA.channelFull;

  const svg = document.getElementById("graph");
  const NS = "http://www.w3.org/2000/svg";
  const tip = document.getElementById("tip");
  const panel = document.getElementById("panel");

  let index = 0, timer = null, pinned = null, hovered = null;

  /* ---------- helpers ---------- */
  const el = (name, attrs) => {
    const node = document.createElementNS(NS, name);
    for (const k in attrs) node.setAttribute(k, attrs[k]);
    return node;
  };
  const h = (name, cls, text) => {
    const node = document.createElement(name);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;   // labels are program data
    return node;
  };
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const fmt = (v) => v.toFixed(2);

  function totals(charge) {
    const out = {};
    for (const key of CHANNEL_KEYS) {
      let sum = 0;
      for (const emotion of CHANNELS[key]) sum += charge[emotion] || 0;
      out[key] = sum;
    }
    return out;
  }
  const weight = (sum) => Math.min(1, sum / FULL);

  /* ---------- layout: fixed circle, so only the edges move ---------- */
  let positions = {}, radius = 0, centre = { x: 0, y: 0 };
  function layout() {
    const box = svg.getBoundingClientRect();
    const w = Math.max(320, box.width), ht = Math.max(380, box.height);
    svg.setAttribute("viewBox", `0 0 ${w} ${ht}`);
    centre = { x: w / 2, y: ht / 2 };
    const names = DATA.agents;
    radius = Math.max(84, Math.min(w, ht) / 2 - 76);
    positions = {};
    if (names.length === 1) { positions[names[0]] = { ...centre }; return; }
    names.forEach((name, i) => {
      const angle = -Math.PI / 2 + (2 * Math.PI * i) / names.length;
      positions[name] = { x: centre.x + radius * Math.cos(angle), y: centre.y + radius * Math.sin(angle) };
    });
  }

  /* ---------- drawing ---------- */
  function arcPath(from, to, offset) {
    const dx = to.x - from.x, dy = to.y - from.y;
    const len = Math.hypot(dx, dy) || 1;
    const nx = -dy / len, ny = dx / len;                 // unit normal
    const trim = 40;                                     // clear the node and its self-rings
    const sx = from.x + (dx / len) * trim, sy = from.y + (dy / len) * trim;
    const ex = to.x - (dx / len) * trim, ey = to.y - (dy / len) * trim;
    const bow = Math.min(70, len * 0.20) + offset;
    const cx = (sx + ex) / 2 + nx * bow, cy = (sy + ey) / 2 + ny * bow;
    return { d: `M${sx},${sy} Q${cx},${cy} ${ex},${ey}`, mid: { x: (sx + 2 * cx + ex) / 4, y: (sy + 2 * cy + ey) / 4 } };
  }

  function render() {
    const frame = FRAMES[index];
    const state = frame.state;
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    layout();

    const defs = el("defs");
    for (const key of CHANNEL_KEYS) {
      const marker = el("marker", { id: "ah-" + key, viewBox: "0 0 8 8", refX: "7", refY: "4",
        markerWidth: "5", markerHeight: "5", orient: "auto-start-reverse" });
      marker.appendChild(el("path", { d: "M0,1 L7,4 L0,7 z", fill: css("--" + key) }));
      defs.appendChild(marker);
    }
    svg.appendChild(defs);

    const edgeLayer = el("g"), nodeLayer = el("g");
    svg.appendChild(edgeLayer); svg.appendChild(nodeLayer);

    // Ordered pairs bow to one side so a -> b never hides b -> a.
    for (const source of DATA.agents) {
      const agent = state.agents[source];
      if (!agent) continue;
      for (const target in agent.bonds) {
        if (!positions[target]) continue;
        const bond = agent.bonds[target];
        const sums = totals(bond.charge);
        const side = source < target ? 1 : -1;
        CHANNEL_KEYS.forEach((key, lane) => {
          const value = sums[key];
          if (value < 0.04) return;
          const w = weight(value);
          const { d, mid } = arcPath(positions[source], positions[target], side * (14 + lane * 15));
          const path = el("path", { d, fill: "none", stroke: css("--" + key),
            "stroke-width": (1.2 + 6 * w).toFixed(2), "stroke-linecap": "round",
            opacity: (0.32 + 0.58 * w).toFixed(2), "marker-end": `url(#ah-${key})` });
          edgeLayer.appendChild(path);
          const hit = el("path", { d, fill: "none", stroke: "transparent",
            "stroke-width": 22, class: "edge-hit" });
          const ref = { kind: "edge", source, target, channel: key };
          bindHover(hit, ref, () => edgeTip(source, target, bond, sums));
          edgeLayer.appendChild(hit);
          if (key === "bond" && sums.bond > 0.25 && sums.grievance > 0.25) {
            const badge = el("circle", { cx: mid.x, cy: mid.y, r: 4.5,
              fill: css("--surface-1"), stroke: css("--text-secondary"), "stroke-width": 1.5 });
            edgeLayer.appendChild(badge);
          }
        });
      }
    }

    for (const name of DATA.agents) {
      const agent = state.agents[name];
      const at = positions[name];
      if (!agent || !at) continue;
      const sums = totals(agent.self);
      const group = el("g");
      // self-regard: the same three channels, as a ring around the node
      CHANNEL_KEYS.forEach((key, lane) => {
        const w = weight(sums[key]);
        if (w < 0.02) return;
        const r = 24 + lane * 3.6;
        const circumference = 2 * Math.PI * r;
        group.appendChild(el("circle", { cx: at.x, cy: at.y, r,
          fill: "none", stroke: css("--" + key), "stroke-width": 2.6,
          "stroke-dasharray": `${(circumference * w).toFixed(1)} ${circumference.toFixed(1)}`,
          transform: `rotate(-90 ${at.x} ${at.y})`, "stroke-linecap": "round", opacity: 0.9 }));
      });
      group.appendChild(el("circle", { cx: at.x, cy: at.y, r: 20,
        fill: css("--node"), stroke: css("--node-ring"), "stroke-width": 1.5 }));
      if (pinned && pinned.kind === "node" && pinned.name === name) {
        group.appendChild(el("circle", { cx: at.x, cy: at.y, r: 39, class: "selected-ring" }));
      }
      // The name sits under the node rather than inside it: entity names come
      // from the program and are any length at all.
      const label = el("text", { x: at.x, y: at.y + 48, "text-anchor": "middle",
        "font-size": "13", "font-weight": "650", class: "node-label",
        fill: css("--text-primary"), stroke: css("--surface-1") });
      label.textContent = name;
      group.appendChild(label);
      const hit = el("circle", { cx: at.x, cy: at.y, r: 36, fill: "transparent", class: "node-hit" });
      bindHover(hit, { kind: "node", name }, () => nodeTip(name, agent, sums));
      group.appendChild(hit);
      nodeLayer.appendChild(group);
    }

    document.getElementById("momentLabel").textContent = frame.label;
    highlightSource(frame.line);
    const events = document.getElementById("events");
    events.replaceChildren();
    frame.events.forEach((text) => events.appendChild(h("li", null, "· " + text)));
    document.getElementById("counter").textContent = `${index + 1} / ${FRAMES.length}  ·  tick ${frame.tick}`;
    document.getElementById("scrub").value = String(index);
    if (pinned) showDetail(pinned);
    if (!document.getElementById("tableView").hidden) renderTable();
  }

  /* ---------- the program, following along ---------- */
  const SOURCE_LINES = (DATA.source || "").split("\n");
  const sourceHost = document.getElementById("source");
  SOURCE_LINES.forEach((text, i) => {
    const row = h("div", null, String(i + 1).padStart(3, " ") + "  " + text);
    row.dataset.line = String(i + 1);
    sourceHost.appendChild(row);
  });
  function highlightSource(line) {
    const rows = sourceHost.children;
    for (const row of rows) row.classList.toggle("on", Number(row.dataset.line) === line);
    const active = sourceHost.querySelector(".on");
    if (active) {
      const top = active.offsetTop - sourceHost.offsetTop;
      if (top < sourceHost.scrollTop || top > sourceHost.scrollTop + sourceHost.clientHeight - 24) {
        sourceHost.scrollTop = Math.max(0, top - sourceHost.clientHeight / 2);
      }
    }
  }

  /* ---------- tooltips ---------- */
  function bindHover(node, ref, build) {
    const enter = (event) => {
      hovered = ref;
      tip.replaceChildren(build());
      tip.classList.add("on");
      move(event);
    };
    const move = (event) => {
      const point = event.touches ? event.touches[0] : event;
      const box = tip.getBoundingClientRect();
      let x = (point.clientX || 0) + 16, y = (point.clientY || 0) + 16;
      if (x + box.width > innerWidth - 8) x = (point.clientX || 0) - box.width - 16;
      if (y + box.height > innerHeight - 8) y = (point.clientY || 0) - box.height - 16;
      tip.style.left = Math.max(8, x) + "px";
      tip.style.top = Math.max(8, y) + "px";
    };
    const leave = () => { hovered = null; tip.classList.remove("on"); };
    node.addEventListener("pointerenter", enter);
    node.addEventListener("pointermove", move);
    node.addEventListener("pointerleave", leave);
    node.addEventListener("click", () => { pinned = ref; showDetail(ref); render(); });
  }

  function channelRows(sums) {
    const wrap = h("div");
    for (const key of CHANNEL_KEYS) {
      const row = h("div", "row");
      const key_ = h("i", "key"); key_.style.background = css("--" + key);
      row.appendChild(key_);
      row.appendChild(h("span", "val num", fmt(sums[key])));
      row.appendChild(h("span", "lbl", key));
      wrap.appendChild(row);
    }
    return wrap;
  }

  function edgeTip(source, target, bond, sums) {
    const wrap = h("div");
    wrap.appendChild(h("div", "head", `${source} → ${target}`));
    wrap.appendChild(channelRows(sums));
    const strong = Object.entries(bond.charge).filter(([, v]) => v >= 0.05)
      .sort((a, b) => b[1] - a[1]).slice(0, 6);
    if (strong.length) {
      const list = h("div", "muted");
      list.style.marginTop = "6px";
      list.textContent = strong.map(([k, v]) => `${k} ${fmt(v)}`).join("   ");
      wrap.appendChild(list);
    }
    const notes = [];
    if (bond.tension > 0.05) notes.push(`tension ${fmt(bond.tension)}`);
    if (bond.trust_ceiling < 0.999) notes.push(`trust ceiling ${fmt(bond.trust_ceiling)}`);
    if (notes.length) {
      const line = h("div", "muted"); line.style.marginTop = "4px";
      line.textContent = notes.join("   ");
      wrap.appendChild(line);
    }
    return wrap;
  }

  function nodeTip(name, agent, sums) {
    const wrap = h("div");
    wrap.appendChild(h("div", "head", name + " — about itself"));
    wrap.appendChild(channelRows(sums));
    const line = h("div", "muted"); line.style.marginTop = "6px";
    line.textContent = `wellbeing ${fmt(agent.wellbeing)}   unresolved ${fmt(agent.unresolved)}   ` +
      `${agent.memories.length} memories`;
    wrap.appendChild(line);
    return wrap;
  }

  /* ---------- detail panel ---------- */
  function chargeTable(charge) {
    const table = h("table");
    const entries = Object.entries(charge).filter(([, v]) => v >= 0.005).sort((a, b) => b[1] - a[1]);
    if (!entries.length) { const p = h("p", "hint", "nothing"); return p; }
    for (const [name, value] of entries) {
      const tr = h("tr");
      tr.appendChild(h("td", null, name));
      tr.appendChild(h("td", "n num", fmt(value)));
      const cell = h("td");
      cell.style.width = "70px";
      const bar = h("span", "bar");
      let channel = "burden";
      for (const key of CHANNEL_KEYS) if (CHANNELS[key].includes(name)) channel = key;
      bar.style.background = css("--" + channel);
      bar.style.width = Math.max(2, value * 60) + "px";
      cell.appendChild(bar);
      tr.appendChild(cell);
      table.appendChild(tr);
    }
    return table;
  }

  function showDetail(ref) {
    const state = FRAMES[index].state;
    panel.replaceChildren();
    panel.appendChild(h("h2", null, "Details"));
    if (ref.kind === "edge") {
      const agent = state.agents[ref.source];
      const bond = agent && agent.bonds[ref.target];
      panel.appendChild(h("h3", null, `${ref.source} → ${ref.target}`));
      if (!bond) { panel.appendChild(h("p", "hint", "no bond at this moment")); return; }
      panel.appendChild(chargeTable(bond.charge));
      const meta = h("p", "hint");
      meta.textContent = `tension ${fmt(bond.tension)}   ·   trust ceiling ${fmt(bond.trust_ceiling)}`;
      panel.appendChild(meta);
      const about = (state.agents[ref.source].memories || []).filter((m) => m.about === ref.target);
      if (about.length) {
        panel.appendChild(h("h3", null, "Memories of " + ref.target));
        about.forEach((m) => panel.appendChild(memoryCard(m)));
      }
      return;
    }
    const agent = state.agents[ref.name];
    if (!agent) { panel.appendChild(h("p", "hint", "not born yet")); return; }
    panel.appendChild(h("h3", null, ref.name + " — about itself"));
    panel.appendChild(chargeTable(agent.self));
    const meta = h("p", "hint");
    meta.textContent = `wellbeing ${fmt(agent.wellbeing)}   ·   unresolved ${fmt(agent.unresolved)}`;
    panel.appendChild(meta);

    const bonds = Object.keys(agent.bonds);
    if (bonds.length) {
      panel.appendChild(h("h3", null, "Bonds"));
      const table = h("table");
      const head = h("tr");
      ["", ...CHANNEL_KEYS].forEach((key, i) => {
        const th = h("th", i ? "n" : null, key);
        head.appendChild(th);
      });
      table.appendChild(head);
      bonds.forEach((target) => {
        const sums = totals(agent.bonds[target].charge);
        const tr = h("tr");
        tr.appendChild(h("td", null, "→ " + target));
        CHANNEL_KEYS.forEach((key) => tr.appendChild(h("td", "n num", fmt(sums[key]))));
        table.appendChild(tr);
      });
      panel.appendChild(table);
    }
    if (agent.resources && Object.keys(agent.resources).length) {
      panel.appendChild(h("h3", null, "Resources"));
      const table = h("table");
      Object.entries(agent.resources).forEach(([name, value]) => {
        const tr = h("tr");
        tr.appendChild(h("td", null, name));
        tr.appendChild(h("td", "n num", String(value)));
        const need = agent.needs && agent.needs[name];
        tr.appendChild(h("td", "hint", need ? `needs ${need}` : ""));
        table.appendChild(tr);
      });
      panel.appendChild(table);
    }
    if (agent.memories.length) {
      panel.appendChild(h("h3", null, `Memories (${agent.memories.length})`));
      agent.memories.forEach((m) => panel.appendChild(memoryCard(m)));
    }
    (agent.alternate_histories || []).forEach((branch) => {
      panel.appendChild(h("h3", null, "Alternate history"));
      const p = h("p");
      p.appendChild(h("span", "claim", `“${branch.untaken}” instead of “${branch.taken}”`));
      panel.appendChild(p);
      const meta2 = h("p", "hint");
      meta2.textContent = `regret ${fmt(branch.regret)}   ·   ${branch.open ? "open" : "closed"}` +
        `   ·   ${branch.visits} visit(s)`;
      panel.appendChild(meta2);
    });
  }

  function memoryCard(m) {
    const card = h("div", "mem");
    card.appendChild(h("div", "claim", "“" + m.claim + "”"));
    const line = h("div", "hint");
    line.textContent = `${m.confidence_label} (${fmt(m.confidence)})   ·   weight ${m.emotional_weight}` +
      `   ·   ${m.contradictions} contradiction(s)`;
    card.appendChild(line);
    const pills = h("div");
    pills.style.marginTop = "3px";
    const tags = [m.kind];
    if (m.source) tags.push("from " + m.source);
    if (m.reconciled) tags.push("forgiven");
    if (m.suppressed) tags.push("denied, still ruminating");
    tags.forEach((t) => pills.appendChild(h("span", "pill", t)));
    card.appendChild(pills);
    return card;
  }

  /* ---------- table view (so no value is hover-only) ---------- */
  function renderTable() {
    const host = document.getElementById("tableView");
    host.replaceChildren();
    const state = FRAMES[index].state;
    host.appendChild(h("h3", null, "Every bond at this moment"));
    const table = h("table");
    const head = h("tr");
    ["from", "to", ...CHANNEL_KEYS, "tension", "trust ceiling"].forEach((key, i) => {
      head.appendChild(h("th", i > 1 ? "n" : null, key));
    });
    table.appendChild(head);
    for (const source of DATA.agents) {
      const agent = state.agents[source];
      if (!agent) continue;
      const rows = [["(self)", agent.self, null], ...Object.entries(agent.bonds).map(
        ([target, bond]) => [target, bond.charge, bond])];
      rows.forEach(([target, charge, bond]) => {
        const sums = totals(charge);
        const tr = h("tr");
        tr.appendChild(h("td", null, source));
        tr.appendChild(h("td", null, target));
        CHANNEL_KEYS.forEach((key) => tr.appendChild(h("td", "n num", fmt(sums[key]))));
        tr.appendChild(h("td", "n num", bond ? fmt(bond.tension) : "—"));
        tr.appendChild(h("td", "n num", bond ? fmt(bond.trust_ceiling) : "—"));
        table.appendChild(tr);
      });
    }
    host.appendChild(table);
  }

  /* ---------- transport ---------- */
  function go(next) {
    index = Math.max(0, Math.min(FRAMES.length - 1, next));
    render();
    if (index === FRAMES.length - 1) pause();
  }
  function play() {
    if (timer) return;
    if (index === FRAMES.length - 1) index = 0;
    document.getElementById("play").textContent = "⏸ Pause";
    const tick = () => { if (index >= FRAMES.length - 1) { pause(); return; } go(index + 1); };
    timer = setInterval(tick, Number(document.getElementById("speed").value));
  }
  function pause() {
    if (timer) clearInterval(timer);
    timer = null;
    document.getElementById("play").textContent = "▶ Play";
  }
  document.getElementById("play").onclick = () => (timer ? pause() : play());
  document.getElementById("stop").onclick = () => { pause(); go(0); };
  document.getElementById("toStart").onclick = () => { pause(); go(0); };
  document.getElementById("toEnd").onclick = () => { pause(); go(FRAMES.length - 1); };
  document.getElementById("stepBack").onclick = () => { pause(); go(index - 1); };
  document.getElementById("stepFwd").onclick = () => { pause(); go(index + 1); };
  document.getElementById("scrub").oninput = (e) => { pause(); go(Number(e.target.value)); };
  document.getElementById("speed").onchange = () => { if (timer) { pause(); play(); } };
  document.getElementById("tableToggle").onclick = (e) => {
    const host = document.getElementById("tableView");
    host.hidden = !host.hidden;
    e.target.setAttribute("aria-expanded", String(!host.hidden));
    if (!host.hidden) renderTable();
  };
  document.getElementById("themeToggle").onclick = () => {
    const root = document.documentElement;
    const dark = getComputedStyle(root).getPropertyValue("--surface-0").trim() === "#121211";
    root.setAttribute("data-theme", dark ? "light" : "dark");
    render();
  };
  addEventListener("keydown", (e) => {
    if (e.target.tagName === "SELECT" || e.target.tagName === "INPUT") return;
    if (e.key === " ") { e.preventDefault(); timer ? pause() : play(); }
    else if (e.key === "ArrowLeft") { pause(); go(index - 1); }
    else if (e.key === "ArrowRight") { pause(); go(index + 1); }
    else if (e.key === "Home") { pause(); go(0); }
    else if (e.key === "End") { pause(); go(FRAMES.length - 1); }
    else if (e.key === "Escape") { pinned = null; panel.replaceChildren(
      h("h2", null, "Details"), h("p", "hint", "Hover an arc or a node. Click to pin it here.")); render(); }
  });
  addEventListener("resize", () => render());

  /* ---------- legend ---------- */
  const legend = document.getElementById("legend");
  CHANNEL_KEYS.forEach((key) => {
    const span = h("span");
    const swatch = h("i");
    swatch.style.background = css("--" + key);
    span.appendChild(swatch);
    span.appendChild(document.createTextNode(DATA.channelLabels[key]));
    legend.appendChild(span);
  });
  const note = h("span", "hint", "· inner→outer lanes are fixed, so the graph reads without colour");
  legend.appendChild(note);

  document.getElementById("scrub").max = String(FRAMES.length - 1);
  render();
})();
</script>
</body>
</html>
"""
