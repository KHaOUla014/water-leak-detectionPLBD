from flask import Flask, jsonify, render_template, request, send_file, send_from_directory
import pandas as pd
import json
import os
from datetime import datetime

from pathlib import Path

BASE_DIR   = Path(__file__).resolve().parent      # src/
DATA_DIR   = BASE_DIR / "data"                    # src/data
MODELS_DIR = BASE_DIR / "models"                  # src/models


# ─── DOOM v2 ─────────────────────────────────────────
try:
    from doom_engine_v2 import DoomEngineV2   # ✅ même dossier
    doom = DoomEngineV2()
    DOOM_READY = True
    print("✅ Doom v2 chargé")
except Exception as e:
    print(f"⚠️  Doom v2 indisponible : {e}")
    doom = None
    DOOM_READY = False

app = Flask(__name__)

# ─────────────────────────────────────────
# ROUTE STATIQUE ASSETS  ← après app = Flask() ✓
# ─────────────────────────────────────────
@app.route("/assets/<path:filename>")
def assets(filename):
    return send_from_directory("assets", filename)

# ─────────────────────────────────────────
# CHARGEMENT DES DONNÉES
# ─────────────────────────────────────────
def load_data():
    csv_path = DATA_DIR / "network_data.csv"
    if not csv_path.exists():
        return None
    df = pd.read_csv(csv_path)
    df["date"] = pd.to_datetime(df["date"])
    return df

def load_json():
    json_path = DATA_DIR / "dashboard_data.json"
    if not json_path.exists():
        return []
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


LEGACY_TO_BADGE = {"NORMAL": "normal", "SUSPECT": "suspect", "FUITE": "leak"}

def enrich_with_doom(sector_dict):
    """Ajoute le diagnostic DOOM SANS jamais écraser le statut legacy fiable."""
    if not DOOM_READY:
        return sector_dict
    try:
        sector_id    = sector_dict.get("sector", "Inconnu")
        pressure_out = float(sector_dict.get("pressure_out", 3.0))
        daily_conso  = float(sector_dict.get("daily_consumption", 8000))
        flow_ls      = daily_conso * 1000 / 86400
        temperature  = float(sector_dict.get("temperature_c", 20.0))  # ✅ bon 4e arg

        diag = doom.diagnose(sector_id, pressure_out, flow_ls, temperature)
        sector_dict['doom_score']  = diag.get('score')
        sector_dict['doom_status'] = diag.get('status')
        sector_dict['doom_label']  = diag.get('label')
    except Exception as e:
        # En cas d'échec DOOM : on retombe proprement sur le legacy
        sector_dict['doom_error'] = str(e)
    return sector_dict



# ─────────────────────────────────────────
# ROUTES PRINCIPALES
# ─────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/sectors/latest")
def sectors_latest():
    """Source de vérité = CSV (statut legacy + géo réelle), enrichi DOOM."""
    df = load_data()
    if df is None:
        # fallback JSON si CSV absent
        data = load_json()
        return jsonify([enrich_with_doom(dict(s)) for s in data])

    latest_date = df["date"].max()
    df_latest = df[df["date"] == latest_date].copy()

    enriched = []
    for _, row in df_latest.iterrows():
        item = {
            "sector":            row["sector"],
            "status":            row["status"],          # ✅ NORMAL/SUSPECT/FUITE garanti
            "lat":               float(row["lat"]),
            "lon":               float(row["lon"]),
            "ilp":               float(row.get("ilp", 0)),
            "volume_lost":       float(row.get("volume_lost", 0)),
            "delta_p":           float(row.get("delta_p", 0)),
            "network":           float(row.get("length_km", 0)),
            "pressure_out":      float(row.get("pressure_out", 3.0)),
            "daily_consumption": float(row.get("daily_consumption", 8000)),
        }
        enriched.append(enrich_with_doom(item))
    return jsonify(enriched)


@app.route("/api/sectors/summary")
def sectors_summary():
    path = "data/sector_summary.csv"
    if not os.path.exists(path):
        return jsonify({"error": "Données non générées"}), 404
    df = pd.read_csv(path)
    return jsonify(df.to_dict(orient="records"))

@app.route("/api/sectors/<sector_name>/history")
def sector_history(sector_name):
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
        "network_yield":   round((total_billed / (total_billed + total_lost)) * 100, 1),
        "doom_ready":      DOOM_READY
    })

@app.route("/api/alerts")
def alerts():
    df = load_data()
    if df is None:
        return jsonify([])
    latest_date = df["date"].max()
    df_latest = df[df["date"] == latest_date]
    alerts_df = df_latest[df_latest["status"].isin(["FUITE", "SUSPECT"])].copy()
    alerts_df = alerts_df.sort_values("ilp", ascending=False)
    result = []
    for _, row in alerts_df.iterrows():
        item = {
            "sector":        row["sector"],
            "status":        row["status"],
            "ilp":           row["ilp"],
            "delta_p":       row["delta_p"],
            "loss_rate_pct": row["loss_rate_pct"],
            "network_age":   row["network_age"],
            "lat":           row["lat"],
            "lon":           row["lon"],
            "pressure_out":  row.get("pressure_out", 3.0),
            "daily_consumption": row.get("daily_consumption", 8000),
        }
        result.append(enrich_with_doom(item))
    return jsonify(result)

@app.route("/api/network/stats")
def network_stats():
    df = load_data()
    if df is None:
        return jsonify([])
    stats = df.groupby("network_age").agg(
        avg_ilp=("ilp", "mean"),
        avg_loss_rate=("loss_rate_pct", "mean"),
        fuite_rate=("status", lambda x: round((x == "FUITE").mean() * 100, 1))
    ).round(2).reset_index()
    return jsonify(stats.to_dict(orient="records"))

@app.route("/favicon.ico")
def favicon():
    return ("", 204)  # No Content, plus de 404


# ─────────────────────────────────────────
# ROUTES DOOM v2
# ─────────────────────────────────────────
@app.route("/api/doom/status")
def doom_status():
    if not DOOM_READY:
        return jsonify({"ready": False, "reason": "Modèles non chargés"})
    return jsonify({
        "ready": True,
        "version": "v2-hybrid",
        "models": ["temporal", "static"],
        "fusion": "0.7 × P_temporel + 0.3 × Score_infra",
        "n_profiles": len(doom.profiles)
    })

@app.route("/api/doom/diagnose/<sector_name>")
def doom_diagnose(sector_name):
    if not DOOM_READY:
        return jsonify({"error": "Doom v2 non disponible"}), 503
    df = load_data()
    if df is None:
        return jsonify({"error": "Données indisponibles"}), 404
    sub = df[df["sector"] == sector_name]
    if sub.empty:
        return jsonify({"error": f"Secteur '{sector_name}' introuvable"}), 404
    last = sub.sort_values("date").iloc[-1]
    pressure = float(last.get("pressure_out", 3.0))
    flow_ls = float(last.get("daily_consumption", 8000)) * 1000 / 86400
    diag = doom.diagnose(sector_name, pressure, flow_ls, 20.0)
    diag['date'] = last['date'].strftime("%Y-%m-%d")
    diag['legacy_status'] = last['status']
    return jsonify(diag)

@app.route("/api/doom/all")
def doom_all():
    if not DOOM_READY:
        return jsonify({"error": "Doom v2 non disponible"}), 503
    df = load_data()
    if df is None:
        return jsonify([])
    latest_date = df["date"].max()
    df_latest = df[df["date"] == latest_date]
    results = []
    for _, row in df_latest.iterrows():
        pressure = float(row.get("pressure_out", 3.0))
        flow_ls = float(row.get("daily_consumption", 8000)) * 1000 / 86400
        diag = doom.diagnose(row["sector"], pressure, flow_ls, 20.0)
        diag['lat'] = row.get("lat")
        diag['lon'] = row.get("lon")
        diag['legacy_status'] = row["status"]
        results.append(diag)
    return jsonify(results)

@app.route("/api/doom/compare")
def doom_compare():
    if not DOOM_READY:
        return jsonify({"error": "Doom v2 non disponible"}), 503
    df = load_data()
    if df is None:
        return jsonify([])
    latest_date = df["date"].max()
    df_latest = df[df["date"] == latest_date]
    agree, disagree = 0, 0
    details = []
    status_map = {"NORMAL": "normal", "SUSPECT": "suspect", "FUITE": "leak"}
    for _, row in df_latest.iterrows():
        pressure = float(row.get("pressure_out", 3.0))
        flow_ls = float(row.get("daily_consumption", 8000)) * 1000 / 86400
        diag = doom.diagnose(row["sector"], pressure, flow_ls, 20.0)
        legacy = status_map.get(row["status"], "normal")
        match = (legacy == diag['status'])
        if match: agree += 1
        else: disagree += 1
        details.append({
            "sector": row["sector"],
            "legacy": row["status"],
            "doom": diag['label'],
            "score": diag['score'],
            "match": match
        })
    return jsonify({
        "agree": agree,
        "disagree": disagree,
        "agreement_rate": round(agree / (agree + disagree) * 100, 1),
        "details": details
    })

# ─────────────────────────────────────────
# UPLOAD / RESET / EXPORT
# ─────────────────────────────────────────
@app.route("/api/upload", methods=["POST"])
def upload_csv():
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
        try:
            df_uploaded = pd.read_csv(path)
            latest = df_uploaded.groupby("sector").last().reset_index()
            latest.to_json(DATA_DIR / "dashboard_data.json", orient="records", date_format="iso")
        except Exception:
            pass

        return jsonify({
            "success":  True,
            "filename": f.filename,
            "rows":     len(df),
            "sectors":  int(df["sector"].nunique()) if "sector" in df.columns else 0
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/analyze", methods=["POST"])
def analyze():
    if not DOOM_READY:
        return jsonify({"success": False, "error": "Modèle DOOM v2 non disponible"}), 503

    df = load_data()
    if df is None:
        return jsonify({"success": False,
                        "error": "Aucune donnée. Importez d'abord un fichier CSV."}), 404

    try:
        latest_date = df["date"].max()
        df_latest = df[df["date"] == latest_date].copy()

        results = []
        for _, row in df_latest.iterrows():
            flow_ls = float(row.get("daily_consumption", 8000)) * 1000 / 86400
            diag = doom.diagnose(
                row.get("sector", "Inconnu"),                       # ✅ sector_id
                float(row.get("pressure_out", 3.0)),
                flow_ls,                                            # ✅ flow cohérent
                float(row.get("temperature_c", 20.0)),
            )
            results.append({
                "name":           row.get("sector", "Inconnu"),
                "status":         diag.get("status", "NORMAL"),
                "ilp":            float(row.get("ilp", 0)),
                "pertes":         float(row.get("volume_lost", 0)),
                "delta_p":        float(row.get("delta_p", 0)),
                "network":        float(row.get("length_km", 0)),   # ✅ ajouté (le JS l'attend)
                "recommandation": diag.get("recommendation", diag.get("label", "—")),
                "lat":            float(row.get("lat", 33.57)),
                "lon":            float(row.get("lon", -7.59)),
                "doom_score":     diag.get("score", 0),
                "pipe_age":       diag.get("pipe_age"),
                "material":       diag.get("material", ""),
                "corrosivity":    diag.get("corrosivity", ""),
            })


        return jsonify({"success": True, "sectors_count": len(results), "sectors": results})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/reset", methods=["POST", "GET"])
def reset_data():
    return jsonify({"success": True, "message": "Données par défaut rechargées"})

@app.route("/api/export")
def export_csv():
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
        print(f"   Doom v2 : {'✅ ACTIF' if DOOM_READY else '❌ INACTIF'}")
        print("   → http://127.0.0.1:5000")
    app.run(debug=True)
