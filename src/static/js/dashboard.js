// ═══════════════════════════════════════════════
// DASHBOARD — RÉSEAU EAU LYDEC CASABLANCA
// ═══════════════════════════════════════════════

let map, markersLayer, pipesLayer;
let allSectors = [];

// ─────────────────────────────────────────
// HELPERS
// ─────────────────────────────────────────
const STATUS_MAP = { NORMAL: "Normal", SUSPECT: "Suspect", FUITE: "Fuite" };
const COLOR_MAP  = { NORMAL: "#10b981", SUSPECT: "#f59e0b", FUITE: "#ef4444" };
const CODE_MAP   = { NORMAL: 0, SUSPECT: 1, FUITE: 2 };
const AGE_LABEL  = { ancien: "Ancien (fonte)", mixte: "Mixte (PVC)", recent: "Récent (PEHD)" };
const AGE_COLOR  = { ancien: "#e67e22", mixte: "#3498db", recent: "#27ae60" };

function normalize(d) {
  const status = d.status ?? "NORMAL";
  const code   = CODE_MAP[status] ?? 0;
  return {
    sector_id:      (d.sector ?? d.sector_id ?? "?").replace(/_/g, " "),
    sector_raw:     d.sector ?? d.sector_id ?? "?",
    status,
    status_code:    code,
    color:          COLOR_MAP[status],
    network_age:    d.network_age ?? "mixte",
    length_km:      Number(d.length_km    ?? 0),
    ilp:            Number(d.ilp          ?? 0),
    loss:           Number(d.volume_lost  ?? d.loss ?? 0),
    loss_rate_pct:  Number(d.loss_rate_pct ?? 0),
    pressure_in:    Number(d.pressure_in  ?? 0),
    pressure_out:   Number(d.pressure_out ?? 0),
    delta_p:        Number(d.delta_p      ?? 0),
    lat:            Number(d.lat ?? 33.5731 + (Math.random() - 0.5) * 0.1),
    lon:            Number(d.lon ?? -7.5898 + (Math.random() - 0.5) * 0.1),
    recommendation: d.recommendation ?? buildRecommendation(status, d),
  };
}

function buildRecommendation(status, d) {
  if (status === "FUITE")
    return `Intervention urgente — ILP ${Number(d.ilp ?? 0).toFixed(2)} m³/km/j, ΔP ${Number(d.delta_p ?? 0).toFixed(2)} bar`;
  if (status === "SUSPECT")
    return `Surveillance renforcée — contrôle pression recommandé`;
  return "Réseau en bon état — maintenance préventive standard";
}

// ─────────────────────────────────────────
// CARTE
// ─────────────────────────────────────────
function initMap() {
  const el = document.getElementById("map");
  if (!el) {
    console.warn("⚠️ #map introuvable");
    return;
  }
  map = L.map("map").setView([33.5731, -7.5898], 12);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "© OpenStreetMap"
  }).addTo(map);
  pipesLayer   = L.layerGroup().addTo(map);
  markersLayer = L.layerGroup().addTo(map);
  setTimeout(() => map.invalidateSize(), 200);
}

function updateMap(data) {
  if (!map) return;
  markersLayer.clearLayers();
  pipesLayer.clearLayers();

  const bounds = [];

  // ── Pipes (liens entre secteurs proches) ──
  data.forEach((a, i) => {
    data.slice(i + 1).forEach(b => {
      const dist = Math.hypot(a.lat - b.lat, a.lon - b.lon);
      if (dist > 0.025) return;
      const worstKey = a.status_code >= b.status_code ? a.status : b.status;
      const lineColor = COLOR_MAP[worstKey];
      const isDashed  = worstKey !== "NORMAL";
      L.polyline([[a.lat, a.lon], [b.lat, b.lon]], {
        color:     lineColor,
        weight:    isDashed ? 3 : 1.8,
        opacity:   isDashed ? 0.85 : 0.45,
        dashArray: isDashed ? "8,6" : null,
      })
      .bindTooltip(
        `🔗 ${a.sector_id} → ${b.sector_id}<br>Risque : ${STATUS_MAP[worstKey] ?? "?"}`,
        { sticky: true }
      )
      .addTo(pipesLayer);
    });
  });

  // ── Marqueurs ──
  data.forEach(d => {
    const radius = d.status_code === 2 ? 14 : d.status_code === 1 ? 11 : 8;

    if (d.status_code === 2) {
      L.circleMarker([d.lat, d.lon], {
        radius: 22, fillColor: d.color, color: d.color,
        weight: 1, opacity: 0.4, fillOpacity: 0.15
      }).addTo(markersLayer);
    }

    const marker = L.circleMarker([d.lat, d.lon], {
      radius, fillColor: d.color, color: "#fff",
      weight: 2, opacity: 1, fillOpacity: 0.88
    });

    marker.bindPopup(`
      <div style="min-width:220px">
        <h4 style="margin:0 0 8px;color:${d.color}">${d.sector_id}</h4>
        <p style="margin:2px 0"><b>Statut :</b> ${STATUS_MAP[d.status]}</p>
        <p style="margin:2px 0"><b>Réseau :</b> ${AGE_LABEL[d.network_age]}</p>
        <p style="margin:2px 0"><b>ILP :</b> ${d.ilp.toFixed(3)} m³/km/j</p>
        <p style="margin:2px 0"><b>ΔP :</b> ${d.delta_p.toFixed(2)} bar</p>
        <p style="margin:2px 0"><b>Pertes :</b> ${d.loss.toFixed(1)} m³ (${d.loss_rate_pct}%)</p>
        <button onclick="showHistory('${d.sector_raw}')" style="margin-top:8px;
          padding:6px 12px;background:${d.color};color:white;border:none;
          border-radius:8px;cursor:pointer;font-size:0.85rem">
          📈 Historique 30 jours
        </button>
      </div>
    `);

    marker.addTo(markersLayer);
    bounds.push([d.lat, d.lon]);
  });

  if (bounds.length) map.fitBounds(bounds, { padding: [40, 40] });
}

function zoomTo(lat, lon) { if (map) map.setView([lat, lon], 15); }

// ─────────────────────────────────────────
// STATS GLOBALES
// ─────────────────────────────────────────
function updateStats(data) {
  const normal  = data.filter(d => d.status_code === 0).length;
  const suspect = data.filter(d => d.status_code === 1).length;
  const fuite   = data.filter(d => d.status_code === 2).length;
  const totalLoss = data.reduce((s, d) => s + d.loss, 0);

  setEl("count-green",  normal);
  setEl("count-orange", suspect);
  setEl("count-red",    fuite);
  setEl("total-loss",   totalLoss.toFixed(1) + " m³");
}

// ─────────────────────────────────────────
// KPIs LYDEC
// ─────────────────────────────────────────
async function loadKPIs() {
  try {
    const res  = await fetch("/api/kpis");
    const data = await res.json();
    if (data.error) return;

    setEl("kpi-date",     data.date           ?? "—");
    setEl("kpi-yield",    (data.network_yield ?? 0) + " %");
    setEl("kpi-ilp",      data.avg_ilp        ?? 0);
    setEl("kpi-loss-pct", (data.avg_loss_rate ?? 0) + " %");
    setEl("kpi-lost-m3",  (data.total_lost_m3 ?? 0) + " m³");
    setEl("kpi-delta-p",  (data.avg_delta_p   ?? 0) + " bar");
  } catch (e) {
    console.warn("KPIs non disponibles :", e.message);
  }
}

function setEl(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

// ─────────────────────────────────────────
// TABLEAU
// ─────────────────────────────────────────
function updateSectorsList(data) {
  allSectors = data;
  renderTable();
  updateCount(data.length);
}

function renderTable() {
  const search  = (document.getElementById("searchInput")?.value ?? "").toLowerCase();
  const filter  = document.getElementById("filterStatus")?.value ?? "all";
  const sortKey = document.getElementById("sortBy")?.value       ?? "status_code";

  let rows = [...allSectors];

  if (filter !== "all") {
    const code = parseInt(filter);
    rows = rows.filter(d => d.status_code === code);
  }

  if (search) {
    rows = rows.filter(d =>
      d.sector_id.toLowerCase().includes(search)   ||
      d.status.toLowerCase().includes(search)      ||
      d.network_age.toLowerCase().includes(search) ||
      d.recommendation.toLowerCase().includes(search)
    );
  }

  rows.sort((a, b) => {
    if (sortKey === "sector_id")   return a.sector_id.localeCompare(b.sector_id);
    if (sortKey === "status_code") return b.status_code - a.status_code;
    return b[sortKey] - a[sortKey];
  });

  updateCount(rows.length);

  const maxIlp  = Math.max(...allSectors.map(d => d.ilp),  1);
  const maxLoss = Math.max(...allSectors.map(d => d.loss), 1);

  const tbody = document.getElementById("sectorsTableBody");
  if (!tbody) return;

  if (rows.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" class="empty-row">Aucun secteur trouvé</td></tr>`;
    return;
  }

  tbody.innerHTML = rows.map(d => {
    const ilpPct  = Math.min((d.ilp  / maxIlp)  * 100, 100).toFixed(1);
    const lossPct = Math.min((d.loss / maxLoss) * 100, 100).toFixed(1);
    const dpPct   = Math.min((d.delta_p / 3.0)  * 100, 100).toFixed(1);
    const barColor = d.color;

    return `
    <tr>
      <td><b>${d.sector_id}</b></td>
      <td><span class="status-badge status-${d.status_code}">${STATUS_MAP[d.status]}</span></td>
      <td><span style="color:${AGE_COLOR[d.network_age]}">${AGE_LABEL[d.network_age]}</span></td>
      <td>
        <div class="bar-cell">
          <div class="bar"><div class="bar-fill" style="width:${ilpPct}%;background:${barColor}"></div></div>
          <span>${d.ilp.toFixed(3)}</span>
        </div>
      </td>
      <td>
        <div class="bar-cell">
          <div class="bar"><div class="bar-fill" style="width:${lossPct}%;background:${barColor}"></div></div>
          <span>${d.loss.toFixed(1)} m³ (${d.loss_rate_pct}%)</span>
        </div>
      </td>
      <td>
        <div class="bar-cell">
          <div class="bar"><div class="bar-fill" style="width:${dpPct}%;background:${barColor}"></div></div>
          <span>${d.delta_p.toFixed(2)} bar</span>
        </div>
      </td>
      <td style="font-size:0.85rem;opacity:0.85">${d.recommendation}</td>
      <td>
        <button class="btn-sm" onclick="showHistory('${d.sector_raw}')">
          📈 Détails
        </button>
      </td>
    </tr>`;
  }).join("");
}

function updateCount(n) {
  setEl("tableCount", `${n} secteur(s)`);
}

// ─────────────────────────────────────────
// MODAL HISTORIQUE
// ─────────────────────────────────────────
let historyChart = null;

async function showHistory(sectorRaw) {
  const d = allSectors.find(s => s.sector_raw === sectorRaw);
  if (!d) return;

  setEl("historyTitle", `📈 ${d.sector_id} — Détails & Historique 30 jours`);

  document.getElementById("historyBody").innerHTML = `
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:12px;margin-bottom:18px">
      ${metaBox("Statut",    `<span class="status-badge status-${d.status_code}">${d.status}</span>`)}
      ${metaBox("Réseau",    `<span style="color:${AGE_COLOR[d.network_age]}">${AGE_LABEL[d.network_age]}</span>`)}
      ${metaBox("ILP",       d.ilp.toFixed(3) + " m³/km/j")}
      ${metaBox("Pertes",    d.loss.toFixed(1) + " m³ (" + d.loss_rate_pct + " %)")}
      ${metaBox("ΔP",        d.delta_p.toFixed(2) + " bar")}
      ${metaBox("P. entrée", d.pressure_in.toFixed(2) + " bar")}
      ${metaBox("P. sortie", d.pressure_out.toFixed(2) + " bar")}
      ${metaBox("Longueur",  d.length_km + " km")}
    </div>
    <div style="background:rgba(255,255,255,0.05);border-radius:10px;padding:14px;margin-bottom:18px">
      <p style="font-size:0.82rem;opacity:0.6;margin-bottom:5px">💡 Recommandation</p>
      <p style="line-height:1.6">${d.recommendation}</p>
    </div>
    <canvas id="historyCanvas" height="100"></canvas>
    <div style="margin-top:14px;display:flex;gap:10px">
      <button class="btn btn-outline" onclick="zoomTo(${d.lat},${d.lon});closeHistory()">
        🗺️ Voir sur la carte
      </button>
    </div>
  `;

  document.getElementById("historyModal").style.display = "flex";

  try {
    const res  = await fetch(`/api/sectors/${sectorRaw}/history`);
    const hist = await res.json();
    if (!Array.isArray(hist) || hist.length === 0) return;

    if (historyChart) historyChart.destroy();
    const ctx = document.getElementById("historyCanvas").getContext("2d");
    historyChart = new Chart(ctx, {
      type: "line",
      data: {
        labels: hist.map(h => h.date),
        datasets: [
          { label: "ILP (m³/km/j)", data: hist.map(h => h.ilp),
            borderColor: "#ef4444", backgroundColor: "rgba(239,68,68,0.1)",
            tension: 0.4, yAxisID: "y" },
          { label: "ΔP (bar)", data: hist.map(h => h.delta_p),
            borderColor: "#3b82f6", backgroundColor: "rgba(59,130,246,0.1)",
            tension: 0.4, yAxisID: "y" },
          { label: "Pertes (%)", data: hist.map(h => h.loss_rate_pct),
            borderColor: "#f59e0b", backgroundColor: "rgba(245,158,11,0.1)",
            tension: 0.4, yAxisID: "y1" }
        ]
      },
      options: {
        responsive: true,
        interaction: { mode: "index", intersect: false },
        plugins: { legend: { position: "top" } },
        scales: {
          y:  { type: "linear", position: "left",  title: { display: true, text: "ILP / ΔP" } },
          y1: { type: "linear", position: "right", title: { display: true, text: "Pertes (%)" },
                grid: { drawOnChartArea: false } }
        }
      }
    });
  } catch (e) {
    console.warn("Historique non disponible :", e.message);
  }
}

function metaBox(label, value) {
  return `
    <div style="background:rgba(255,255,255,0.05);border-radius:10px;padding:12px">
      <p style="font-size:0.75rem;opacity:0.6;margin-bottom:4px">${label}</p>
      <p style="font-size:1rem;font-weight:600">${value}</p>
    </div>`;
}

function closeHistory(e) {
  if (!e || e.target === document.getElementById("historyModal")) {
    document.getElementById("historyModal").style.display = "none";
  }
}

// ─────────────────────────────────────────
// CHARGEMENT API
// ─────────────────────────────────────────
async function loadDiagnostics() {
  try {
    const res  = await fetch("/api/sectors/latest");
    const json = await res.json();
    const raw  = Array.isArray(json) ? json : (json.sectors ?? []);
    const data = raw.map(normalize);

    updateStats(data);
    updateMap(data);
    updateSectorsList(data);
    loadKPIs();
  } catch (e) {
    console.error("Erreur chargement :", e);
  }
}

// ─────────────────────────────────────────
// UPLOAD
// ─────────────────────────────────────────
function setupUpload() {
  const dropZone = document.getElementById("drop-zone");
  const csvInput = document.getElementById("csv-input");
  if (!dropZone || !csvInput) return;

  dropZone.addEventListener("dragover", e => {
    e.preventDefault(); dropZone.classList.add("dragover");
  });
  dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));
  dropZone.addEventListener("drop", e => {
    e.preventDefault(); dropZone.classList.remove("dragover");
    if (e.dataTransfer.files.length) uploadFile(e.dataTransfer.files[0]);
  });
  csvInput.addEventListener("change", e => {
    if (e.target.files.length) uploadFile(e.target.files[0]);
  });
}

async function uploadFile(file) {
  const status = document.getElementById("upload-status");
  if (status) status.innerHTML = `⏳ Upload de <b>${file.name}</b>...`;
  const fd = new FormData();
  fd.append("file", file);
  try {
    const res  = await fetch("/api/upload", { method: "POST", body: fd });
    const data = await res.json();
    if (data.success) {
      if (status) status.innerHTML = `<span class="msg-success">
        ✅ ${data.filename} — ${data.rows} lignes, ${data.sectors} secteurs
      </span>`;
      setEl("data-source", `📊 Données : ${data.filename}`);
      loadDiagnostics();
    } else if (status) {
      status.innerHTML = `<span class="msg-error">❌ ${data.error}</span>`;
    }
  } catch (e) {
    if (status) status.innerHTML = `<span class="msg-error">❌ Erreur : ${e.message}</span>`;
  }
}

async function runAnalysis() {
  const status = document.getElementById("upload-status");
  if (status) status.innerHTML = "⏳ Analyse en cours...";
  await loadDiagnostics();
  if (status) status.innerHTML = `<span class="msg-success">✅ Analyse terminée !</span>`;
}

async function resetData() {
  try { await fetch("/api/reset", { method: "POST" }); } catch (e) {}
  setEl("data-source", "📊 Données : Lydec Casablanca (défaut)");
  const status = document.getElementById("upload-status");
  if (status) status.innerHTML = `<span class="msg-success">↺ Données Casablanca rechargées</span>`;
  loadDiagnostics();
}

function exportResults() { window.location.href = "/api/export"; }

// ─────────────────────────────────────────
// INIT (DOM prêt)
// ─────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  // Toolbar
  ["searchInput", "filterStatus", "sortBy"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener("input", renderTable);
  });

  // Upload
  setupUpload();

  // Carte + données
  initMap();
  loadDiagnostics();
  setInterval(loadDiagnostics, 30000);
});
