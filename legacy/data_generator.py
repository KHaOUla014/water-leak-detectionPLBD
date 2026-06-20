import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import json
import os

# ─────────────────────────────────────────
# PARAMÈTRES RÉSEAU CASABLANCA / LYDEC
# ─────────────────────────────────────────
NETWORK = {
    "city": "Casablanca",
    "operator": "Lydec",
    "pressure_nominal": 4.5,
    "pressure_min": 1.5,
    "pressure_max": 6.0,
    "center_lat": 33.5731,
    "center_lon": -7.5898,
    "radius_km": 15
}

# Seuils de détection
THRESHOLDS = {
    "delta_p_suspect": 0.5,
    "delta_p_leak":    1.5,
    "ilp_suspect":     3.0,
    "ilp_leak":        8.0
}

# ─────────────────────────────────────────
# 20 SECTEURS — VRAIS QUARTIERS
# ─────────────────────────────────────────
SECTORS_CONFIG = {
    # --- Ancien réseau (fonte grise) ---
    "Medina":         {"length_km": 18.5, "base_consumption": 420, "leak_proneness": 0.16, "network_age": "ancien"},
    "Hay_Mohammadi":  {"length_km": 22.0, "base_consumption": 480, "leak_proneness": 0.17, "network_age": "ancien"},
    "Ain_Sebaa":      {"length_km": 20.3, "base_consumption": 390, "leak_proneness": 0.15, "network_age": "ancien"},
    "Roches_Noires":  {"length_km": 14.7, "base_consumption": 310, "leak_proneness": 0.14, "network_age": "ancien"},
    "Derb_Sultan":    {"length_km": 16.2, "base_consumption": 350, "leak_proneness": 0.18, "network_age": "ancien"},
    "Ben_Msick":      {"length_km": 19.8, "base_consumption": 400, "leak_proneness": 0.15, "network_age": "ancien"},
    "Sbata":          {"length_km": 17.1, "base_consumption": 360, "leak_proneness": 0.13, "network_age": "ancien"},

    # --- Réseau mixte (fonte/PVC) ---
    "Maarif":         {"length_km": 12.4, "base_consumption": 280, "leak_proneness": 0.08, "network_age": "mixte"},
    "Bourgogne":      {"length_km": 10.8, "base_consumption": 250, "leak_proneness": 0.07, "network_age": "mixte"},
    "Gauthier":       {"length_km":  9.5, "base_consumption": 220, "leak_proneness": 0.06, "network_age": "mixte"},
    "Racine":         {"length_km": 11.2, "base_consumption": 260, "leak_proneness": 0.08, "network_age": "mixte"},
    "Val_Fleuri":     {"length_km": 13.0, "base_consumption": 290, "leak_proneness": 0.09, "network_age": "mixte"},
    "Beauséjour":     {"length_km": 10.1, "base_consumption": 230, "leak_proneness": 0.07, "network_age": "mixte"},

    # --- Réseau récent (PEHD) ---
    "Hay_Hassani":    {"length_km":  8.5, "base_consumption": 180, "leak_proneness": 0.03, "network_age": "recent"},
    "Lissasfa":       {"length_km":  7.2, "base_consumption": 160, "leak_proneness": 0.02, "network_age": "recent"},
    "Sidi_Maarouf":   {"length_km":  9.0, "base_consumption": 200, "leak_proneness": 0.04, "network_age": "recent"},
    "Bouskoura":      {"length_km":  6.8, "base_consumption": 150, "leak_proneness": 0.03, "network_age": "recent"},
    "Ain_Diab":       {"length_km": 11.5, "base_consumption": 260, "leak_proneness": 0.04, "network_age": "recent"},
    "Anfa":           {"length_km": 10.2, "base_consumption": 240, "leak_proneness": 0.03, "network_age": "recent"},
    "Sidi_Bernoussi": {"length_km": 15.3, "base_consumption": 320, "leak_proneness": 0.05, "network_age": "recent"},
}

# ─────────────────────────────────────────
# COORDONNÉES GPS RÉELLES PAR QUARTIER
# ─────────────────────────────────────────
SECTORS_GPS = {
    "Medina":         {"lat": 33.5950, "lon": -7.6190},
    "Hay_Mohammadi":  {"lat": 33.5830, "lon": -7.5700},
    "Ain_Sebaa":      {"lat": 33.6050, "lon": -7.5300},
    "Roches_Noires":  {"lat": 33.6100, "lon": -7.5550},
    "Derb_Sultan":    {"lat": 33.5750, "lon": -7.6100},
    "Ben_Msick":      {"lat": 33.5650, "lon": -7.5850},
    "Sbata":          {"lat": 33.5700, "lon": -7.5950},
    "Maarif":         {"lat": 33.5780, "lon": -7.6350},
    "Bourgogne":      {"lat": 33.5880, "lon": -7.6280},
    "Gauthier":       {"lat": 33.5920, "lon": -7.6200},
    "Racine":         {"lat": 33.5850, "lon": -7.6420},
    "Val_Fleuri":     {"lat": 33.5720, "lon": -7.6280},
    "Beauséjour":     {"lat": 33.5800, "lon": -7.6180},
    "Hay_Hassani":    {"lat": 33.5550, "lon": -7.6500},
    "Lissasfa":       {"lat": 33.5350, "lon": -7.6700},
    "Sidi_Maarouf":   {"lat": 33.5450, "lon": -7.6200},
    "Bouskoura":      {"lat": 33.5100, "lon": -7.6600},
    "Ain_Diab":       {"lat": 33.5950, "lon": -7.6900},
    "Anfa":           {"lat": 33.5900, "lon": -7.6600},
    "Sidi_Bernoussi": {"lat": 33.6200, "lon": -7.5100},
}

np.random.seed(42)

def generate_sector_data(sector_name, config, n_days=30):
    records = []
    base_date = datetime(2024, 1, 1)
    proneness = config["leak_proneness"]

    for day in range(n_days):
        current_date = base_date + timedelta(days=day)

        # Probabilité de fuite selon proneness
        rand = np.random.random()
        if rand < proneness * 0.6:
            status = "FUITE"
        elif rand < proneness * 1.4:
            status = "SUSPECT"
        else:
            status = "NORMAL"

        # Pression d'entrée (légèrement variable)
        pressure_in = np.random.uniform(4.0, 6.0)

        # Delta pression selon statut
        if status == "FUITE":
            delta_p = np.random.uniform(1.5, 3.0)
        elif status == "SUSPECT":
            delta_p = np.random.uniform(0.5, 1.5)
        else:
            delta_p = np.random.uniform(0.05, 0.5)

        pressure_out = max(NETWORK["pressure_min"], pressure_in - delta_p)

        # Consommation journalière
        daily_consumption = config["base_consumption"] * np.random.uniform(0.85, 1.15)

        # Volume perdu selon statut
        if status == "FUITE":
            loss_rate = np.random.uniform(0.18, 0.30)
        elif status == "SUSPECT":
            loss_rate = np.random.uniform(0.08, 0.18)
        else:
            loss_rate = np.random.uniform(0.02, 0.08)

        volume_lost = daily_consumption * loss_rate
        volume_billed = daily_consumption - volume_lost

        # ILP (Indice Linéaire de Pertes) en m³/km/j
        ilp = volume_lost / config["length_km"]

        # Vérification cohérence seuils
        if ilp > THRESHOLDS["ilp_leak"] or delta_p > THRESHOLDS["delta_p_leak"]:
            status = "FUITE"
        elif ilp > THRESHOLDS["ilp_suspect"] or delta_p > THRESHOLDS["delta_p_suspect"]:
            if status == "NORMAL":
                status = "SUSPECT"

        # Coordonnées GPS
        gps = SECTORS_GPS[sector_name]

        records.append({
            "date":              current_date.strftime("%Y-%m-%d"),
            "sector":            sector_name,
            "network_age":       config["network_age"],
            "lat":               gps["lat"],
            "lon":               gps["lon"],
            "length_km":         round(config["length_km"], 1),
            "pressure_in":       round(pressure_in, 2),
            "pressure_out":      round(pressure_out, 2),
            "delta_p":           round(delta_p, 2),
            "daily_consumption": round(daily_consumption, 1),
            "volume_lost":       round(volume_lost, 1),
            "volume_billed":     round(volume_billed, 1),
            "ilp":               round(ilp, 2),
            "loss_rate_pct":     round(loss_rate * 100, 1),
            "status":            status,
        })

    return records


def generate_all_data(n_days=30):
    all_records = []
    for sector_name, config in SECTORS_CONFIG.items():
        records = generate_sector_data(sector_name, config, n_days)
        all_records.extend(records)

    df = pd.DataFrame(all_records)
    df = df.sort_values(["date", "sector"]).reset_index(drop=True)
    return df


def export_data(df):
    os.makedirs("data", exist_ok=True)

    # CSV complet
    df.to_csv("data/network_data.csv", index=False)
    print(f"✅ CSV exporté : {len(df)} lignes")

    # JSON pour le dashboard
    latest_date = df["date"].max()
    df_latest = df[df["date"] == latest_date]

    dashboard_data = []
    for _, row in df_latest.iterrows():
        dashboard_data.append(row.to_dict())

    with open("data/dashboard_data.json", "w", encoding="utf-8") as f:
        json.dump(dashboard_data, f, ensure_ascii=False, indent=2)
    print(f"✅ JSON exporté : {len(dashboard_data)} secteurs (date: {latest_date})")

    # Résumé par secteur
    summary = df.groupby("sector").agg(
        network_age=("network_age", "first"),
        avg_ilp=("ilp", "mean"),
        avg_delta_p=("delta_p", "mean"),
        avg_loss_rate=("loss_rate_pct", "mean"),
        fuite_days=("status", lambda x: (x == "FUITE").sum()),
        suspect_days=("status", lambda x: (x == "SUSPECT").sum()),
        normal_days=("status", lambda x: (x == "NORMAL").sum()),
    ).round(2).reset_index()

    summary.to_csv("data/sector_summary.csv", index=False)
    print(f"✅ Résumé exporté : {len(summary)} secteurs")

    return df_latest


if __name__ == "__main__":
    print("🚰 Génération des données — Réseau Lydec Casablanca")
    print("=" * 55)
    df = generate_all_data(n_days=30)
    export_data(df)
    print("\n📊 Aperçu statuts :")
    print(df["status"].value_counts())
    print("\n📊 Aperçu par type de réseau :")
    print(df.groupby("network_age")["ilp"].mean().round(2))
