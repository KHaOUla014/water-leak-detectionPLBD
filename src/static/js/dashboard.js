let map, markersLayer;

// Initialiser la carte Leaflet
function initMap() {
  map = L.map('map').setView([6.8276, -5.2893], 12); // Yamoussoukro
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap',
    maxZoom: 19
  }).addTo(map);
  markersLayer = L.layerGroup().addTo(map);
}

// Charger et afficher les diagnostics
async function loadDiagnostics() {
  try {
    const res = await fetch('/api/diagnostics');
    const data = await res.json();
    
    updateStats(data);
    updateMap(data);
    updateSectorsList(data);
  } catch (e) {
    console.error("Erreur chargement :", e);
  }
}

function updateStats(data) {
  const green = data.filter(d => d.status === 'Normal').length;
  const orange = data.filter(d => d.status === 'Suspect').length;
  const red = data.filter(d => d.status === 'Fuite probable').length;
  const totalLoss = data.reduce((s,d) => s + d.loss, 0);
  
  document.getElementById('count-green').textContent = green;
  document.getElementById('count-orange').textContent = orange;
  document.getElementById('count-red').textContent = red;
  document.getElementById('total-loss').textContent = totalLoss.toFixed(1) + ' m³';
}

function updateMap(data) {
  markersLayer.clearLayers();
  const bounds = [];
  
  data.forEach(d => {
    const radius = d.status === 'Fuite probable' ? 14 : (d.status === 'Suspect' ? 11 : 8);
    
    const marker = L.circleMarker([d.lat, d.lon], {
      radius: radius,
      fillColor: d.color,
      color: '#fff',
      weight: 2,
      opacity: 1,
      fillOpacity: 0.85
    });
    
    marker.bindPopup(`
      <div style="font-family:sans-serif;min-width:200px">
        <h3 style="margin:0 0 8px 0;color:#0f172a">${d.sector_id}</h3>
        <span style="background:${d.color};color:white;padding:3px 10px;border-radius:10px;font-size:0.8rem">${d.status}</span>
        <p style="margin:8px 0 3px 0"><b>ILP :</b> ${d.ilp} m³/km/j</p>
        <p style="margin:3px 0"><b>Perte :</b> ${d.loss} m³</p>
        <p style="margin:3px 0"><b>Confiance :</b> ${(d.confidence*100).toFixed(0)}%</p>
        <p style="margin:8px 0 0 0;font-style:italic;color:#475569">${d.recommendation}</p>
      </div>
    `);
    
    // Pulse pour les fuites
    if (d.status === 'Fuite probable') {
      L.circleMarker([d.lat, d.lon], {
        radius: 22, fillColor: d.color, color: d.color,
        weight: 1, opacity: 0.4, fillOpacity: 0.15
      }).addTo(markersLayer);
    }
    
    marker.addTo(markersLayer);
    bounds.push([d.lat, d.lon]);
  });
  
  if (bounds.length) map.fitBounds(bounds, { padding: [40, 40] });
}

function updateSectorsList(data) {
  const list = document.getElementById('sectors-list');
  list.innerHTML = data.map(d => `
    <div class="sector-card" style="border-color:${d.color}" onclick="zoomTo(${d.lat},${d.lon})">
      <h3>${d.sector_id}</h3>
      <span class="badge" style="background:${d.color};color:white">${d.status}</span>
      <p><b>ILP :</b> ${d.ilp} m³/km/j</p>
      <p><b>Perte :</b> ${d.loss} m³</p>
      <p><b>Confiance :</b> ${(d.confidence*100).toFixed(0)}%</p>
    </div>
  `).join('');
}

function zoomTo(lat, lon) {
  map.setView([lat, lon], 15);
}

// === UPLOAD ===
const dropZone = document.getElementById('drop-zone');
const csvInput = document.getElementById('csv-input');

dropZone.addEventListener('click', () => csvInput.click());
dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('dragover'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('dragover');
  if (e.dataTransfer.files.length) uploadFile(e.dataTransfer.files[0]);
});
csvInput.addEventListener('change', e => {
  if (e.target.files.length) uploadFile(e.target.files[0]);
});

async function uploadFile(file) {
  const status = document.getElementById('upload-status');
  status.innerHTML = `⏳ Upload de <b>${file.name}</b>...`;
  
  const fd = new FormData();
  fd.append('file', file);
  
  try {
    const res = await fetch('/api/upload', { method: 'POST', body: fd });
    const data = await res.json();
    
    if (data.success) {
      status.innerHTML = `<span class="msg-success">✅ ${data.filename} chargé : ${data.rows} lignes, ${data.sectors} secteurs</span>`;
      document.getElementById('data-source').textContent = `📊 Données : ${data.filename}`;
    } else {
      status.innerHTML = `<span class="msg-error">❌ ${data.error}</span>`;
    }
  } catch (e) {
    status.innerHTML = `<span class="msg-error">❌ Erreur : ${e.message}</span>`;
  }
}

async function runAnalysis() {
  const status = document.getElementById('upload-status');
  status.innerHTML = '⏳ Analyse en cours...';
  await loadDiagnostics();
  status.innerHTML = '<span class="msg-success">✅ Analyse terminée !</span>';
}

async function resetData() {
  await fetch('/api/reset', { method: 'POST' });
  document.getElementById('data-source').textContent = '📊 Données : par défaut';
  document.getElementById('upload-status').innerHTML = '<span class="msg-success">↺ Données par défaut rechargées</span>';
  loadDiagnostics();
}

function exportResults() {
  window.location.href = '/api/export';
}

// === INIT ===
initMap();
loadDiagnostics();
setInterval(loadDiagnostics, 10000); // refresh toutes les 10s
