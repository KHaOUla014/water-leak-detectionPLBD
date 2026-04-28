"""
Doom v2 - Préparation des données réelles
Fusionne 2 datasets : temporel (capteurs) + statique (infrastructure)
"""
import pandas as pd
import numpy as np
from pathlib import Path


RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# Au lieu de : CASA_SECTORS = [f"SEC_{i:02d}" for i in range(1, 21)]

def get_casa_sectors():
    """Récupère les vrais noms de secteurs depuis network_data.csv"""
    csv_path = Path("data/network_data.csv")
    if csv_path.exists():
        df = pd.read_csv(csv_path)
        return sorted(df['sector'].unique().tolist())
    # Fallback
    return [f"SEC_{i:02d}" for i in range(1, 21)]

CASA_SECTORS = get_casa_sectors()

np.random.seed(42)


def prepare_temporal():
    """Dataset 1 : séries temporelles capteurs."""
    print("📥 Chargement dataset temporel...")
    df = pd.read_csv(RAW_DIR / "water_leak_detection_1000_rows.csv")
    
    # Normalisation des noms de colonnes
    df.columns = [c.strip() for c in df.columns]
    
    # Renommage standardisé
    rename_map = {
        'Timestamp': 'timestamp',
        'Sensor_ID': 'sensor_id',
        'Pressure (bar)': 'pressure_bar',
        'Flow Rate (L/s)': 'flow_rate_ls',
        'Temperature (°C)': 'temperature_c',
        'Leak Status': 'leak_label',
        'Burst Status': 'burst_label'
    }
    df = df.rename(columns=rename_map)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Mapping 10 capteurs → 20 secteurs Casa (chaque secteur hérite d'un profil)
    sensors = df['sensor_id'].unique()
    sector_to_sensor = {sec: np.random.choice(sensors) for sec in CASA_SECTORS}
    
    rows = []
    for sector, sensor in sector_to_sensor.items():
        sub = df[df['sensor_id'] == sensor].copy()
        sub['sector_id'] = sector
        rows.append(sub)
    
    out = pd.concat(rows, ignore_index=True)
    out = out[['timestamp', 'sector_id', 'pressure_bar', 'flow_rate_ls',
               'temperature_c', 'leak_label', 'burst_label']]
    
    out.to_csv(PROCESSED_DIR / "temporal.csv", index=False)
    print(f"✅ temporal.csv : {len(out)} lignes / {out['sector_id'].nunique()} secteurs")
    print(f"   Taux fuites : {out['leak_label'].mean()*100:.1f}%")
    return out


def prepare_static():
    print("\n📥 Chargement dataset statique...")
    df = pd.read_csv(RAW_DIR / "water_network_leak_dataset.csv", sep=";")
    df.columns = [c.strip().lower().replace(' ', '_') for c in df.columns]
    
    # Conversion virgule décimale → point
    num_cols = ['pressure_psi', 'flow_gpm', 'velocity_fps', 'temperature_f', 'pipe_age_years']
    for c in num_cols:
        if df[c].dtype == 'object':
            df[c] = df[c].astype(str).str.replace(',', '.').astype(float)
    
    sectors = CASA_SECTORS
    sampled = df.sample(n=2000, random_state=42, replace=True).reset_index(drop=True)
    sampled['sector_id'] = [CASA_SECTORS[i % len(CASA_SECTORS)] for i in range(len(sampled))]

    cols = ['sector_id'] + [c for c in sampled.columns if c != 'sector_id']
    sampled = sampled[cols]
    
    sampled.to_csv(PROCESSED_DIR / "static.csv", index=False)
    print(f"✅ static.csv : {len(sampled)} secteurs")
    return sampled



if __name__ == "__main__":
    print("=" * 60)
    print("  DOOM v2 - Préparation données réelles")
    print("=" * 60)
    prepare_temporal()
    prepare_static()
    print("\n🎉 Préparation terminée ! → data/processed/")
