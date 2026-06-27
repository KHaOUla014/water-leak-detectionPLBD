"""
Génère water_network_leak_dataset.csv au format réaliste.
Format CALQUÉ sur l'existant : séparateur ';', virgules décimales.
À placer dans : data/raw/water_network_leak_dataset.csv
"""
import numpy as np
import pandas as pd
from pathlib import Path

np.random.seed(42)
N = 2000

# ─────────────────────────────────────────────────────────
# 1. CARACTÉRISTIQUES BRUTES
# ─────────────────────────────────────────────────────────
pipe_age = np.random.randint(1, 30, N)
materials = np.random.choice(['PVC', 'HDPE', 'Steel', 'Cast Iron'],
                             N, p=[0.35, 0.30, 0.20, 0.15])
soil = np.random.choice(['Low', 'Medium', 'High'],
                        N, p=[0.45, 0.35, 0.20])
temperature_f = np.random.randint(50, 85, N)

# ─────────────────────────────────────────────────────────
# 2. RISQUE DE FUITE (probabiliste)
# ─────────────────────────────────────────────────────────
risk_age = pipe_age / 29.0
mat_risk = {'PVC': 0.15, 'HDPE': 0.10, 'Steel': 0.30, 'Cast Iron': 0.45}
risk_material = np.array([mat_risk[m] for m in materials])
soil_risk = {'Low': 0.10, 'Medium': 0.25, 'High': 0.45}
risk_soil = np.array([soil_risk[s] for s in soil])

risk_score = 0.35 * risk_age + 0.35 * risk_material + 0.30 * risk_soil
risk_score += np.random.normal(0, 0.10, N)

risk_score = np.clip(risk_score, 0, 1)

# ─────────────────────────────────────────────────────────
# 3. TIRAGE DE LA FUITE
# ─────────────────────────────────────────────────────────
leak = (np.random.random(N) < risk_score).astype(int)

# ─────────────────────────────────────────────────────────
# 4. SIGNATURE HYDRAULIQUE (avec chevauchement)
# ─────────────────────────────────────────────────────────
pressure = np.random.normal(65, 4, N)
flow = np.random.normal(110, 12, N)

# Intensité de fuite variable (micro → grosses)
leak_intensity = np.where(leak == 1, np.random.uniform(0.02, 0.22, N), 0)
pressure -= pressure * leak_intensity          # la fuite fait CHUTER la pression
flow += flow * leak_intensity * 0.6            # et MONTER le débit

# ─────────────────────────────────────────────────────────
# 5. FAUX SIGNAUX (pression basse SANS fuite)
# ─────────────────────────────────────────────────────────
false_signal = (np.random.random(N) < 0.08) & (leak == 0)
pressure[false_signal] -= pressure[false_signal] * np.random.uniform(0.05, 0.15, false_signal.sum())

# ─────────────────────────────────────────────────────────
# 6. BRUIT DE CAPTEUR
# ─────────────────────────────────────────────────────────
pressure += np.random.normal(0, 1.5, N)
flow += np.random.normal(0, 4, N)
velocity = flow / 27.0 + np.random.normal(0, 0.3, N)

pressure = np.clip(pressure, 15, 85).round(1)
flow = np.clip(flow, 60, 290).round(1)
velocity = np.clip(velocity, 2.5, 10).round(1)

# ─────────────────────────────────────────────────────────
# 7. ASSEMBLAGE — noms de colonnes AVANT nettoyage
#    (ton prepare_static fait .lower().replace(' ','_'))
# ─────────────────────────────────────────────────────────
df = pd.DataFrame({
    'Pressure PSI': pressure,
    'Flow GPM': flow,
    'Velocity FPS': velocity,
    'Temperature F': temperature_f,
    'Pipe Age Years': pipe_age,
    'Pipe Material': materials,
    'Soil Corrosivity': soil,
    'Leak Class': leak
})

# ─────────────────────────────────────────────────────────
# 8. EXPORT au format EXACT attendu : sep=';', virgule décimale
# ─────────────────────────────────────────────────────────
out_path = Path("data/raw/water_network_leak_dataset.csv")
out_path.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(out_path, sep=';', index=False, decimal=',')

# ─────────────────────────────────────────────────────────
# 9. CONTRÔLE QUALITÉ
# ─────────────────────────────────────────────────────────
print("=" * 55)
print(f"✅ Généré : {out_path}")
print(f"   {N} lignes | Taux de fuite : {leak.mean():.1%}")
print("=" * 55)
print(f"\n📊 Pression — sains : {pressure[leak==0].mean():.1f} | fuites : {pressure[leak==1].mean():.1f}")
print(f"📊 Débit    — sains : {flow[leak==0].mean():.1f} | fuites : {flow[leak==1].mean():.1f}")
print(f"\n🔍 CHEVAUCHEMENT pression (le test clé) :")
print(f"   sains  : [{np.percentile(pressure[leak==0],5):.0f} – {np.percentile(pressure[leak==0],95):.0f}]")
print(f"   fuites : [{np.percentile(pressure[leak==1],5):.0f} – {np.percentile(pressure[leak==1],95):.0f}]")
print(f"\n🎯 Vérifie : les plages doivent SE CHEVAUCHER partiellement.")
