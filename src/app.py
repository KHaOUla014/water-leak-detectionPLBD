from flask import Flask, render_template, jsonify, request
import pandas as pd
import numpy as np
from doom_engine import DoomAI
from datetime import datetime

app = Flask(__name__)
doom = DoomAI()
doom.load()

# Charger les données pour la simulation temps réel
df_full = pd.read_csv("../data/synthetic_data.csv")

# Calculer ilp et volume_loss une fois pour toutes (pour l'historique)
df_full["volume_loss"] = (df_full["volume_injected"] - df_full["volume_consumed"]).clip(lower=0)
df_full["ilp"] = np.where(
    df_full["length_km"] > 0,
    df_full["volume_loss"] / df_full["length_km"],
    0
)

SECTORS = df_full["sector_id"].unique().tolist()


def get_latest_sector_data():
    """Récupère la dernière mesure pour chaque secteur (simulation live)."""
    latest = df_full.sort_values("date").groupby("sector_id").tail(1)

    results = []
    for _, row in latest.iterrows():
        data = {
            "sector_id": row["sector_id"],
            "length_km": row["length_km"],
            "volume_injected": row["volume_injected"] * np.random.uniform(0.95, 1.05),
            "volume_consumed": row["volume_consumed"] * np.random.uniform(0.95, 1.05),
            "pressure_avg": row["pressure_avg"] + np.random.normal(0, 0.1),
            "flow_night": max(0, row["flow_night"] + np.random.normal(0, 0.5)),
        }
        diag = doom.diagnose(data)
        diag["timestamp"] = datetime.now().strftime("%H:%M:%S")
        results.append(diag)
    return results


@app.route("/")
def dashboard():
    return render_template("dashboard.html")


@app.route("/api/diagnostics")
def api_diagnostics():
    results = get_latest_sector_data()
    summary = {
        "total": len(results),
        "normal": sum(1 for r in results if r["final_status"] == 0),
        "suspect": sum(1 for r in results if r["final_status"] == 1),
        "leak": sum(1 for r in results if r["final_status"] == 2),
    }
    return jsonify({"sectors": results, "summary": summary})


@app.route("/api/diagnose", methods=["POST"])
def api_diagnose():
    data = request.json
    return jsonify(doom.diagnose(data))


@app.route("/api/history/<sector_id>")
def api_history(sector_id):
    hist = df_full[df_full["sector_id"] == sector_id].tail(60)
    return jsonify({
        "dates": hist["date"].tolist(),
        "ilp": hist["ilp"].round(3).tolist(),
        "pressure": hist["pressure_avg"].round(2).tolist(),
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
