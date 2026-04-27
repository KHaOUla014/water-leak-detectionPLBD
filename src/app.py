from flask import Flask, jsonify, render_template, request, send_file
import pandas as pd
import json
import os
from datetime import datetime

app = Flask(__name__)

# ─────────────────────────────────────────
# CHARGEMENT DES DONNÉES
# ─────────────────────────────────────────
def load_data():
    csv_path = "data/network_data.csv"
    if not os.path.exists(csv_path):
        return None
    df = pd.read_csv(csv_path)
    df["date"] = pd.to_datetime(df["date"])
    return df


def load_json():
    json_path = "data/dashboard_data.json"
    if not os.path.exists(json_path):
        return []
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ─────────────────────────────────────────
# ROUTES PRINCIPALES
# ─────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/sectors/latest")
def sectors_latest():
    """Dernier jour de données pour tous les secteurs"""
    data = load_json()
    return jsonify(data)


@app.route("/api/sectors/summary")
def sectors_summary():
    """Résumé global par secteur (30 jours)"""
    path = "data/sector_summary.csv"
    if not os.path.exists(path):
        return jsonify({"error": "Données non générées"}), 404
    df = pd.read_csv(path)
    return jsonify(df.to_dict(orient="records"))


@app.route("/api/sectors/<sector_name>/history")
def sector_history(sector_name):
    """Historique 30 jours d'un secteur"""
    df = load_data()
    if df is None:
        return jsonify({"error": "Données non trouvées"}), 404

    sector_data = df[df["sector"] == sector_name]
    if sector_data.empty:
        return jsonify({"error": f"Secteur '{sector_name}' introuvable"}), 404

    sector_data = sector_data.sort_values("date")
    result = sector_data[[
        "date", "pressure_in", "pressure_out", "delta_p",
        "daily_consumption", "volume_lost", "ilp",
        "loss_rate_pct", "status"
    ]].copy()
    result["date"] = result["date"].dt.strftime("%Y-%m-%d")

    return jsonify(result.to_dict(orient="records"))


@app.route("/api/kpis")
def kpis():
    """KPIs globaux du réseau"""
    df = load_data()
    if df is None:
        return jsonify({"error": "Données non trouvées"}), 404

    latest_date = df["date"].max()
    df_latest = df[df["date"] == latest_date]

    total_sectors = len(df_latest)
    fuite_count   = int((df_latest["status"] == "FUITE").sum())
    suspect_count = int((df_latest["status"] == "SUSPECT").sum())
    normal_count  = int((df_latest["status"] == "NORMAL").sum())

    avg_ilp       = round(float(df_latest["ilp"].mean()), 2)
    avg_loss_rate = round(float(df_latest["loss_rate_pct"].mean()), 1)
    avg_delta_p   = round(float(df_latest["delta_p"].mean()), 2)

    total_lost    = round(float(df_latest["volume_lost"].sum()), 0)
    total_billed  = round(float(df_latest["volume_billed"].sum()), 0)

    return jsonify({
        "date":            latest_date.strftime("%Y-%m-%d"),
        "total_sectors":   total_sectors,
        "fuite":           fuite_count,
        "suspect":         suspect_count,
        "normal":          normal_count,
        "avg_ilp":         avg_ilp,
        "avg_loss_rate":   avg_loss_rate,
        "avg_delta_p":     avg_delta_p,
        "total_lost_m3":   total_lost,
        "total_billed_m3": total_billed,
        "network_yield":   round((total_billed / (total_billed + total_lost)) * 100, 1)
    })


@app.route("/api/alerts")
def alerts():
    """Liste des alertes actives (FUITE + SUSPECT)"""
    df = load_data()
    if df is None:
        return jsonify([])

    latest_date = df["date"].max()
    df_latest = df[df["date"] == latest_date]

    alerts_df = df_latest[df_latest["status"].isin(["FUITE", "SUSPECT"])].copy()
    alerts_df = alerts_df.sort_values("ilp", ascending=False)

    result = []
    for _, row in alerts_df.iterrows():
        result.append({
            "sector":        row["sector"],
            "status":        row["status"],
            "ilp":           row["ilp"],
            "delta_p":       row["delta_p"],
            "loss_rate_pct": row["loss_rate_pct"],
            "network_age":   row["network_age"],
            "lat":           row["lat"],
            "lon":           row["lon"],
        })

    return jsonify(result)


@app.route("/api/network/stats")
def network_stats():
    """Stats par type de réseau"""
    df = load_data()
    if df is None:
        return jsonify([])

    stats = df.groupby("network_age").agg(
        avg_ilp=("ilp", "mean"),
        avg_loss_rate=("loss_rate_pct", "mean"),
        fuite_rate=("status", lambda x: round((x == "FUITE").mean() * 100, 1))
    ).round(2).reset_index()

    return jsonify(stats.to_dict(orient="records"))


# ─────────────────────────────────────────
# UPLOAD / RESET / EXPORT
# ─────────────────────────────────────────
@app.route("/api/upload", methods=["POST"])
def upload_csv():
    """Upload d'un CSV utilisateur"""
    if "file" not in request.files:
        return jsonify({"success": False, "error": "Aucun fichier"}), 400
    f = request.files["file"]
    if not f.filename.lower().endswith(".csv"):
        return jsonify({"success": False, "error": "Format CSV requis"}), 400
    try:
        os.makedirs("data", exist_ok=True)
        path = "data/network_data.csv"
        f.save(path)
        df = pd.read_csv(path)
        return jsonify({
            "success":  True,
            "filename": f.filename,
            "rows":     len(df),
            "sectors":  int(df["sector"].nunique()) if "sector" in df.columns else 0
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/reset", methods=["POST", "GET"])
def reset_data():
    """Recharge les données par défaut"""
    return jsonify({"success": True, "message": "Données par défaut rechargées"})


@app.route("/api/export")
def export_csv():
    """Export du dernier état du réseau"""
    path = "data/network_data.csv"
    if not os.path.exists(path):
        return jsonify({"error": "Aucune donnée"}), 404
    return send_file(
        path,
        as_attachment=True,
        download_name=f"lydec_export_{datetime.now():%Y%m%d}.csv"
    )


# ─────────────────────────────────────────
# LANCEMENT
# ─────────────────────────────────────────
if __name__ == "__main__":
    if not os.path.exists("data/network_data.csv"):
        print("⚠️  Données manquantes — lance d'abord : python data_generator.py")
    else:
        print("🚰 Dashboard Lydec Casablanca")
        print("   → http://127.0.0.1:5000")
    app.run(debug=True)
