// ---- Data (loaded from graph-data.js) ----
// Expects: rawNodes, rawEdges

// ---- Deterministic colour from nick ----
const palette = [
  "#58a6ff","#3fb950","#d2a8ff","#ffa657","#ff7b72",
  "#79c0ff","#56d364","#bc8cff","#ffb86c","#f97583",
  "#a5d6ff","#7ee787","#e2c5ff","#ffc680","#ffa198",
];

function hashNick(nick) {
  let h = 0;
  for (let i = 0; i < nick.length; i++) {
    h = ((h << 5) - h + nick.charCodeAt(i)) | 0;
  }
  return Math.abs(h);
}

function nickColor(nick) {
  return palette[hashNick(nick) % palette.length];
}

// ---- Scale helpers ----
const msgCounts = rawNodes.map(n => n.message_count);
const maxMsg = Math.max(...msgCounts, 1);
const minSize = 10, maxSize = 25;

function nodeSize(count) {
  return minSize + (Math.sqrt(count) / Math.sqrt(maxMsg)) * (maxSize - minSize);
}

const weights = rawEdges.map(e => e.weight);
const maxW = Math.max(...weights, 1);
const minWidth = 1, maxWidth = 10;

function edgeWidth(w) {
  return minWidth + (w / maxW) * (maxWidth - minWidth);
}

// ---- Build vis datasets ----
function buildNodes(threshold) {
  const connected = new Set();
  rawEdges.forEach(e => {
    if (e.weight >= threshold) {
      connected.add(e.source);
      connected.add(e.target);
    }
  });

  return rawNodes
    // Filter out nodes with 0 messages (mentioned but never spoke).
    .filter(n => n.message_count > 0)
    .filter(n => threshold === 0 || connected.has(n.id))
    .map(n => {
      const aliases = n.aliases || {};
      const aliasEntries = Object.entries(aliases);
      const primary = aliasEntries.length > 0
        ? aliasEntries.reduce((a, b) => b[1] > a[1] ? b : a)[0]
        : n.id;
      const otherAliases = aliasEntries
        .filter(([name]) => name !== primary)
        .map(([name]) => name);
      let tooltip = `${primary}\nMessages: ${n.message_count}`;
      return {
        id: n.id,
        label: primary,
        title: tooltip,
        size: nodeSize(n.message_count),
        color: {
          background: nickColor(primary),
          border: "#0d1117",
          highlight: { background: nickColor(primary), border: "#ffffff" },
        },
        font: { color: "#e6edf3", size: 13, strokeWidth: 2, strokeColor: "#0d1117" },
        borderWidth: 2,
        message_count: n.message_count,
      };
    });
}

function buildEdges(threshold) {
  let id = 0;
  return rawEdges
    .filter(e => e.weight >= threshold)
    .map(e => ({
      id: id++,
      from: e.source,
      to: e.target,
      value: e.weight,
      width: edgeWidth(e.weight),
      title: `${e.source} \u2194 ${e.target}<br>Strength: ${e.weight.toFixed(2)}`,
      color: { color: "rgba(88,166,255,0.25)", highlight: "#58a6ff", opacity: 0.7 },
      smooth: { type: "continuous" },
      source: e.source,
      target: e.target,
      weight: e.weight,
    }));
}

const nodesDS = new vis.DataSet(buildNodes(0));
const edgesDS = new vis.DataSet(buildEdges(0));

const container = document.getElementById("network");
const network = new vis.Network(container, { nodes: nodesDS, edges: edgesDS }, {
  physics: {
    enabled: true,
    barnesHut: {
      gravitationalConstant: -8000,
      centralGravity: 0.3,
      springLength: 140,
      springConstant: 0.04,
      damping: 0.09,
    },
    stabilization: { iterations: 150 },
  },
  interaction: {
    hover: true,
    tooltipDelay: 150,
    multiselect: false,
  },
  edges: {
    arrows: { to: { enabled: false } },
    scaling: { min: 1, max: 10 },
  },
  nodes: {
    shape: "dot",
    scaling: { min: minSize, max: maxSize },
  },
});

// ---- Threshold slider ----
const slider = document.getElementById("threshold");
const thresholdVal = document.getElementById("threshold-val");

slider.addEventListener("input", () => {
  const t = parseFloat(slider.value);
  thresholdVal.textContent = t.toFixed(2);
  nodesDS.clear();
  edgesDS.clear();
  nodesDS.add(buildNodes(t));
  edgesDS.add(buildEdges(t));
});

// ---- Nick search ----
const searchInput = document.getElementById("nick-search");

searchInput.addEventListener("input", () => {
  const q = searchInput.value.trim().toLowerCase();
  if (!q) {
    nodesDS.forEach(n => {
      nodesDS.update({ id: n.id, opacity: 1.0, font: { ...n.font, color: "#e6edf3" } });
    });
    return;
  }
  const match = rawNodes.find(n => {
    if (n.id.toLowerCase().includes(q)) return true;
    const aliases = n.aliases || {};
    return Object.keys(aliases).some(a => a.toLowerCase().includes(q));
  });
  if (match) {
    network.selectNodes([match.id]);
    network.focus(match.id, { scale: 1.2, animation: { duration: 400, easingFunction: "easeInOutQuad" } });
    showNodeInfo(match.id);
  }
});

searchInput.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    searchInput.value = "";
    searchInput.dispatchEvent(new Event("input"));
    network.unselectAll();
  }
});

// ---- Physics toggle ----
let physicsOn = true;
const toggleBtn = document.getElementById("toggle-physics");
toggleBtn.addEventListener("click", () => {
  physicsOn = !physicsOn;
  network.setOptions({ physics: { enabled: physicsOn } });
  toggleBtn.textContent = physicsOn ? "Disable Physics" : "Enable Physics";
});

document.getElementById("fit-btn").addEventListener("click", () => {
  network.fit({ animation: { duration: 500, easingFunction: "easeInOutQuad" } });
});

// ---- Selection info ----
const selInfo = document.getElementById("selection-info");

function showNodeInfo(nodeId) {
  const nodeData = rawNodes.find(n => n.id === nodeId);
  if (!nodeData) return;

  const aliases = nodeData.aliases || {};
  const aliasEntries = Object.entries(aliases);
  const primary = aliasEntries.length > 0
    ? aliasEntries.reduce((a, b) => b[1] > a[1] ? b : a)[0]
    : nodeId;
  const otherAliases = aliasEntries
    .filter(([name]) => name !== primary)
    .map(([name]) => name);

  const connections = rawEdges
    .filter(e => e.source === nodeId || e.target === nodeId)
    .map(e => ({
      nick: e.source === nodeId ? e.target : e.source,
      weight: e.weight,
    }))
    .sort((a, b) => b.weight - a.weight)
    .slice(0, 8);

  let html = `<b>${primary}</b><br>Messages: ${nodeData.message_count}`;
  if (otherAliases.length > 0) {
    html += `<br><span class="alias-label">AKA: ${otherAliases.join(", ")}</span>`;
  }
  if (connections.length > 0) {
    html += `<br><br><b>Top connections:</b>`;
    connections.forEach(c => {
      html += `<br>&nbsp;&nbsp;${c.nick}: ${c.weight.toFixed(2)}`;
    });
  }
  selInfo.innerHTML = html;
}

network.on("selectNode", (params) => {
  if (params.nodes.length === 0) return;
  showNodeInfo(params.nodes[0]);
});

network.on("selectEdge", (params) => {
  // Skip when a node is also selected — selectNode already handled the display
  if (params.nodes && params.nodes.length > 0) return;
  if (params.edges.length === 0) return;
  const edgeId = params.edges[0];
  const edgeData = edgesDS.get(edgeId);
  if (!edgeData) return;
  selInfo.innerHTML = `<b>${edgeData.source}</b> \u2194 <b>${edgeData.target}</b><br>Strength: ${edgeData.weight.toFixed(3)}`;
});

network.on("deselectNode", () => { selInfo.textContent = "Click a node or edge to inspect."; });
network.on("deselectEdge", () => { selInfo.textContent = "Click a node or edge to inspect."; });

// ---- Keyboard shortcuts ----
document.addEventListener("keydown", (e) => {
  if (e.key === "/" && document.activeElement !== searchInput) {
    e.preventDefault();
    searchInput.focus();
  }
});
