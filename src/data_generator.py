import numpy as np
import pandas as pd
from datetime import datetime, timedelta


def generate_synthetic_data(n_sectors=20, n_days=365, output_file="../data/synthetic_data.csv"):
    """
    Génère des données synthétiques réalistes pour entraîner Doom.
    Simule un réseau d'eau avec différents secteurs hydrauliques.
    Inclut les coordonnées GPS pour la cartographie.
    """
    np.random.seed(42)
    rows = []

    # 🌍 Centre de la carte : Yamoussoukro (Côte d'Ivoire)
    # Change ces valeurs selon ta zone géographique
    CENTER_LAT, CENTER_LON = 6.8276, -5.2893

    # Caractéristiques de chaque secteur
    sectors = {
        f"SECT_{i:03d}": {
            "length_km": np.random.uniform(2, 25),
            "base_consumption": np.random.uniform(50, 500),     # m³/jour
            "leak_proneness": np.random.uniform(0.02, 0.15),    # tendance aux fuites
            "lat": CENTER_LAT + np.random.uniform(-0.05, 0.05), # 🆕 latitude GPS
            "lon": CENTER_LON + np.random.uniform(-0.05, 0.05), # 🆕 longitude GPS
        }
        for i in range(1, n_sectors + 1)
    }

    start_date = datetime.now() - timedelta(days=n_days)

    for sector_id, props in sectors.items():
        # État du secteur dans le temps (peut développer une fuite)
        leak_state = 0       # 0 = normal, 1 = suspect, 2 = fuite
        leak_intensity = 0

        for day in range(n_days):
            date = start_date + timedelta(days=day)

            # Variation saisonnière + bruit
            season_factor = 1 + 0.2 * np.sin(2 * np.pi * day / 365)
            consumption = props["base_consumption"] * season_factor * np.random.uniform(0.9, 1.1)

            # Probabilité d'apparition d'une fuite
            if leak_state == 0 and np.random.random() < props["leak_proneness"] / 365:
                leak_state = 1
                leak_intensity = np.random.uniform(5, 20)  # m³/jour de perte
            elif leak_state == 1 and np.random.random() < 0.05:
                leak_state = 2
                leak_intensity *= np.random.uniform(1.5, 3)  # aggravation
            elif leak_state >= 1 and np.random.random() < 0.01:
                # Réparation
                leak_state = 0
                leak_intensity = 0

            # Volumes
            volume_consumed = consumption
            volume_injected = consumption + leak_intensity + np.random.normal(0, 2)
            volume_injected = max(volume_injected, volume_consumed)

            # Pression moyenne (baisse si fuite)
            pressure_avg = 3.0 - (leak_intensity * 0.05) + np.random.normal(0, 0.1)
            pressure_avg = max(1.0, pressure_avg)

            # Débit nocturne (augmente si fuite)
            flow_night = 1.0 + (leak_intensity * 0.3) + np.random.normal(0, 0.3)
            flow_night = max(0.1, flow_night)

            # Label : 0 = normal, 1 = suspect, 2 = fuite
            label = leak_state

            rows.append({
                "date": date.strftime("%Y-%m-%d"),
                "sector_id": sector_id,
                "length_km": props["length_km"],
                "lat": props["lat"],                # 🆕 GPS
                "lon": props["lon"],                # 🆕 GPS
                "volume_injected": round(volume_injected, 2),
                "volume_consumed": round(volume_consumed, 2),
                "pressure_avg": round(pressure_avg, 2),
                "flow_night": round(flow_night, 2),
                "label": label
            })

    df = pd.DataFrame(rows)

    # Création du dossier si nécessaire
    import os
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    df.to_csv(output_file, index=False)
    print(f"✅ Données générées : {len(df)} lignes")
    print(f"📂 Fichier : {output_file}")
    print(f"📊 Distribution des labels :")
    print(df['label'].value_counts().sort_index())
    print(f"🌍 Zone GPS : lat [{df['lat'].min():.4f}, {df['lat'].max():.4f}], "
          f"lon [{df['lon'].min():.4f}, {df['lon'].max():.4f}]")

    return df


if __name__ == "__main__":
    generate_synthetic_data()
