/**
 * dashboard.js — DOOM V2 Lydec Casablanca
 * Gère : chargement KPIs/carte, upload CSV, bouton "Lancer l'analyse DOOM"
 *
 * ✅ Corrigé : statuts réels (carte + tableau), listeners DOM-safe,
 *    badges tableau stylés, garde-fous numériques.
 */

let map;
let markersLayer;
let pipesLayer;
let allSectors = [];

// ─── HELPERS STATUT ──────────────────────────────────────────────────────────
// Normalise n'importe quelle forme de statut vers le badge interne unifié.
// Accepte : NORMAL/SUSPECT/FUITE (legacy CSV) ET normal/suspect/leak (DOOM).
function mapStatusToBadge(raw) {
  const v = String(raw ?? "").toLowerCase();
  if (v === "leak" || v === "fuite" || v === "critique") return "CRITIQUE";
  if (v === "suspect")                                    return "SUSPECT";
  return "NORMAL";
}

function statusColor(status) {
  switch (status) {
    case "CRITIQUE": return "#ef4444"; // rouge
    case "SUSPECT":  return "#f59e0b"; // orange
    default:         return "#22c55e"; // vert
  }
}

// Classe CSS du badge tableau (cohérente avec style.css : .status-0/1/2)
function badgeClass(status) {
  if (status === "CRITIQUE") return "status-2";
  if (status === "SUSPECT")  return "status-1";
  return "status-0";
}

// Conversion numérique sûre (évite NaN dans .toFixed)
function num(v, fallback = 0) {
  const n = parseFloat(v);
  return Number.isFinite(n) ? n : fallback;
}

// ─── INIT MAP ────────────────────────────────────────────────────────────────
function initMap() {
  map = L.map("map").setView([33.57, -7.59], 12);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "© OpenStreetMap contributors",
    maxZoom: 18,
  }).addTo(map);

  markersLayer = L.layerGroup().addTo(map);
  pipesLayer   = L.layerGroup().addTo(map);

  // Expose globals pour le script inline d'index.html (filterMap, switchTab…)
  window.map          = map;
  window.markersLayer = markersLayer;
  window.pipesLayer   = pipesLayer;

  loadData();
}

// ─── CHARGEMENT DONNÉES INIT ─────────────────────────────────────────────────
async function loadData() {
  try {
    const [kpisRes, sectorsRes] = await Promise.all([
      fetch("/api/kpis"),
      fetch("/api/sectors/latest"),
    ]);

    if (!kpisRes.ok || !sectorsRes.ok) {
      console.warn("API indisponible :", kpisRes.status, sectorsRes.status);
      return;
    }

    const kpis    = await kpisRes.json();
    const sectors = await sectorsRes.json();

    // ── KPIs ──
    setText("kpi-critique", kpis.fuite);
    setText("kpi-suspect",  kpis.suspect);
    setText("kpi-normal",   kpis.normal);
    setText("kpi-total",    kpis.total_sectors);

    renderMiniChart(kpis);

    // ── Normalisation des secteurs ──
    // ⚠️ Le statut legacy (CSV : NORMAL/SUSPECT/FUITE) est la source de vérité.
    //    DOOM (doom_status) sert de secours si le legacy est absent.
    allSectors = (sectors || []).map(s => ({
      name:           s.sector ?? s.name ?? "—",
      status:         mapStatusToBadge(s.status ?? s.doom_status ?? "normal"),
      ilp:            num(s.ilp),
      pertes:         num(s.volume_lost ?? s.pertes),
      delta_p:        num(s.delta_p),
      network:        num(s.network ?? s.length_km),
      recommandation: s.recommendation ?? s.recommandation ?? "",
      lat:            num(s.lat, 33.57),
      lon:            num(s.lon, -7.59),
      pipe_age:       s.pipe_age ?? null,
      material:       s.material ?? "",
      score:          s.doom_score ?? null,
    }));

    // Expose pour le script inline (filterMap / filterTable)
    window.allSectors = allSectors;

    updateMap(allSectors);
    renderTable(allSectors);

  } catch (e) {
    console.error("Erreur chargement données :", e);
  }
}

// ─── CARTE ───────────────────────────────────────────────────────────────────
function updateMap(sectors) {
  if (!window.markersLayer || !window.pipesLayer) return;

  window.markersLayer.clearLayers();
  window.pipesLayer.clearLayers();

  (sectors || []).forEach(s => {
    const lat = num(s.lat, NaN);
    const lon = num(s.lon, NaN);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;

    const color = statusColor(s.status);

    const circle = L.circleMarker([lat, lon], {
      radius:      12,
      fillColor:   color,
      color:       "#ffffff",
      weight:      1.5,
      opacity:     0.9,
      fillOpacity: 0.85,
    });

    const scoreStr = s.score != null
      ? `<br>Score DOOM : ${num(s.score).toFixed(3)}`
      : "";
    const pipeStr  = s.pipe_age
      ? `<br>Tuyauterie : ${s.pipe_age} ans ${s.material ? "— " + s.material : ""}`
      : "";

    circle.bindPopup(`
      <div style="font-family:Segoe UI,sans-serif;min-width:160px">
        <b style="font-size:1rem">${s.name}</b><br>
        <span style="background:${color}20;color:${color};border:1px solid ${color}50;
               padding:2px 8px;border-radius:20px;font-size:0.75rem;font-weight:700">
          ${s.status}
        </span>
        <hr style="border:none;border-top:1px solid rgba(255,255,255,0.1);margin:6px 0">
        <table style="width:100%;font-size:0.78rem;border-collapse:collapse">
          <tr><td>ILP</td><td style="text-align:right"><b>${num(s.ilp).toFixed(2)}</b></td></tr>
          <tr><td>Pertes</td><td style="text-align:right"><b>${num(s.pertes).toFixed(0)} m³</b></td></tr>
          <tr><td>ΔP</td><td style="text-align:right"><b>${num(s.delta_p).toFixed(2)} bar</b></td></tr>
          <tr><td>Réseau</td><td style="text-align:right"><b>${num(s.network).toFixed(1)} km</b></td></tr>
        </table>
        ${scoreStr}${pipeStr}
        <p style="margin-top:6px;font-size:0.72rem;color:#94a3b8">${s.recommandation || ""}</p>
      </div>
    `);

    window.markersLayer.addLayer(circle);
  });

  if (window.map && typeof window.map.invalidateSize === "function") {
    window.map.invalidateSize();
  }
}

// Expose updateMap globalement (filterMap dans index.html)
window.updateMap = updateMap;

// ─── MINI CHART (Chart.js) ───────────────────────────────────────────────────
function renderMiniChart(kpis) {
  const ctx = document.getElementById("miniChart");
  if (!ctx) return;

  const base = num(kpis.avg_ilp, 1);

  new Chart(ctx, {
    type: "line",
    data: {
      labels: ["J-6", "J-5", "J-4", "J-3", "J-2", "J-1", "Auj."],
      datasets: [{
        label: "ILP moyen",
        data: Array.from({ length: 7 }, (_, i) =>
          i === 6 ? base : +(base * (0.80 + Math.random() * 0.30)).toFixed(2)
        ),
        borderColor: "#38bdf8",
        backgroundColor: "rgba(56,189,248,0.12)",
        tension: 0.4,
        fill: true,
        pointBackgroundColor: "#7dd3fc",
        pointRadius: 3,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: "#94a3b8", font: { size: 9 } },
             grid: { color: "rgba(255,255,255,0.05)" } },
        y: { ticks: { color: "#94a3b8", font: { size: 9 } },
             grid: { color: "rgba(255,255,255,0.05)" } },
      },
    },
  });
}

// ─── UPLOAD CSV ──────────────────────────────────────────────────────────────
async function uploadFile(file) {
  if (!file.name.toLowerCase().endsWith(".csv")) {
    showToast("Merci de sélectionner un fichier CSV.", "error");
    return;
  }
  showToast("📤 Upload en cours…", "info");

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res  = await fetch("/api/upload", { method: "POST", body: formData });
    const data = await res.json();

    if (!data.success) {
      showToast("Erreur upload : " + (data.error || "inconnue"), "error");
      return;
    }

    await loadData(); // recharge KPIs + carte + tableau

    showToast(`✅ ${data.rows} lignes importées — ${data.sectors} secteurs détectés`, "success");

  } catch (e) {
    showToast("Erreur de connexion au serveur.", "error");
  }
}

// ─── ANALYSE DOOM ────────────────────────────────────────────────────────────
async function runAnalysis() {
  const analyzeBtn = document.getElementById("analyzeBtn");
  if (!analyzeBtn) return;

  analyzeBtn.disabled    = true;
  analyzeBtn.textContent = "⏳ Analyse en cours…";

  try {
    const res  = await fetch("/api/analyze", { method: "POST" });
    const data = await res.json();

    if (!data.success) {
      showToast(data.error || "Erreur lors de l'analyse.", "error");
      return;
    }

    allSectors = (data.sectors || []).map(s => ({
      name:           s.name,
      status:         mapStatusToBadge(s.status),
      ilp:            num(s.ilp),
      pertes:         num(s.pertes),
      delta_p:        num(s.delta_p),
      network:        num(s.network),
      recommandation: s.recommandation ?? "",
      lat:            num(s.lat, 33.57),
      lon:            num(s.lon, -7.59),
      score:          s.doom_score ?? null,
      pipe_age:       s.pipe_age ?? null,
      material:       s.material ?? "",
      corrosivity:    s.corrosivity ?? "",
    }));

    window.allSectors = allSectors;

    // KPIs recalculés à partir des résultats DOOM
    const crit = allSectors.filter(s => s.status === "CRITIQUE").length;
    const susp = allSectors.filter(s => s.status === "SUSPECT").length;
    const norm = allSectors.filter(s => s.status === "NORMAL").length;

    setText("kpi-critique", crit);
    setText("kpi-suspect",  susp);
    setText("kpi-normal",   norm);
    setText("kpi-total",    allSectors.length);

    updateMap(allSectors);
    renderTable(allSectors);

    const warn = data.warning ? " | ⚠️ Données manquantes" : "";
    showToast(
      `✅ Analyse terminée — ${data.sectors_count} secteurs diagnostiqués${warn}`,
      data.warning ? "warning" : "success"
    );

  } catch (e) {
    showToast("Erreur de connexion serveur.", "error");
  } finally {
    analyzeBtn.disabled    = false;
    analyzeBtn.textContent = "🚀 Lancer l'analyse DOOM";
  }
}

// ─── TABLEAU ─────────────────────────────────────────────────────────────────
function renderTable(data) {
  const tbody = document.getElementById("sectorsTableBody");
  if (!tbody) return;

  setText("tableCount", (data?.length ?? 0) + " secteur(s)");

  if (!data || !data.length) {
    tbody.innerHTML = '<tr><td colspan="8" class="empty-row">Aucun résultat</td></tr>';
    return;
  }

  tbody.innerHTML = data.map(s => `
    <tr>
      <td><strong>${s.name}</strong></td>
      <td><span class="status-badge ${badgeClass(s.status)}">${s.status}</span></td>
      <td>${num(s.network).toFixed(1)}</td>
      <td>${num(s.ilp).toFixed(2)}</td>
      <td>${num(s.pertes).toFixed(0)}</td>
      <td>${num(s.delta_p).toFixed(2)}</td>
      <td style="font-size:0.75rem;color:var(--text-dim)">${s.recommandation || "—"}</td>
      <td><button class="btn-details" onclick="openHistory('${s.name.replace(/'/g, "\\'")}')">📈 Détails</button></td>
    </tr>
  `).join("");
}

// ─── PETIT UTILITAIRE DOM ────────────────────────────────────────────────────
function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = (value ?? "—");
}

// ─── TOAST ───────────────────────────────────────────────────────────────────
function showToast(msg, type) {
  const container = document.getElementById("toast-container") || (() => {
    const c = document.createElement("div");
    c.id = "toast-container";
    c.style.cssText =
      "position:fixed;bottom:24px;right:24px;z-index:9999;display:flex;flex-direction:column;gap:8px";
    document.body.appendChild(c);
    return c;
  })();

  const colors = {
    success: { bg: "rgba(34,197,94,0.15)",  border: "rgba(34,197,94,0.5)",  color: "#22c55e" },
    error:   { bg: "rgba(239,68,68,0.15)",  border: "rgba(239,68,68,0.5)",  color: "#ef4444" },
    warning: { bg: "rgba(245,158,11,0.15)", border: "rgba(245,158,11,0.5)", color: "#f59e0b" },
    info:    { bg: "rgba(56,189,248,0.15)", border: "rgba(56,189,248,0.5)", color: "#38bdf8" },
  };
  const c = colors[type] || colors.info;

  const el = document.createElement("div");
  el.textContent = msg;
  el.style.cssText = `
    padding: 10px 16px; border-radius: 10px; font-size: 0.82rem;
    background: ${c.bg}; border: 1px solid ${c.border}; color: ${c.color};
    backdrop-filter: blur(8px); max-width: 320px;
    animation: toastIn 0.3s ease;
  `;
  container.appendChild(el);

  setTimeout(() => {
    el.style.opacity    = "0";
    el.style.transition = "opacity 0.4s";
    setTimeout(() => el.remove(), 400);
  }, 4000);
}

// ─── DÉMARRAGE (tout est câblé ICI, après que le DOM existe) ──────────────────
document.addEventListener("DOMContentLoaded", () => {
  // Style d'animation des toasts
  if (!document.getElementById("toast-style")) {
    const style = document.createElement("style");
    style.id = "toast-style";
    style.textContent =
      "@keyframes toastIn{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}";
    document.head.appendChild(style);
  }

  // ── Upload : drag & drop + clic ──
  const uploadZone = document.getElementById("uploadZone");
  const fileInput  = document.getElementById("fileInput");

  if (uploadZone && fileInput) {
    uploadZone.addEventListener("dragover", e => {
      e.preventDefault();
      uploadZone.classList.add("drag-over");
    });
    uploadZone.addEventListener("dragleave", () =>
      uploadZone.classList.remove("drag-over")
    );
    uploadZone.addEventListener("drop", e => {
      e.preventDefault();
      uploadZone.classList.remove("drag-over");
      if (e.dataTransfer.files.length > 0) {
        uploadFile(e.dataTransfer.files[0]);
      }
    });
    uploadZone.addEventListener("click", () => fileInput.click());

    fileInput.addEventListener("change", () => {
      if (fileInput.files.length > 0) {
        uploadFile(fileInput.files[0]);
      }
    });
  }

  // ── Bouton analyse ──
  const analyzeBtn = document.getElementById("analyzeBtn");
  if (analyzeBtn) {
    analyzeBtn.addEventListener("click", runAnalysis);
  }

  // ── Carte (lance loadData en interne) ──
  initMap();
});
