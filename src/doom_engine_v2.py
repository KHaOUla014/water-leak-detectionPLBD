import pandas as pd
import joblib
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "models"
PROCESSED_DIR = BASE_DIR / "data" / "processed"

ALPHA_TEMPORAL = 0.7
BETA_STATIC = 0.3
THRESHOLD_SUSPECT = 0.35
THRESHOLD_LEAK = 0.65

BAR_TO_PSI = 14.5038
LS_TO_GPM = 15.8503
def c_to_f(c): return c * 9/5 + 32

# Encodages (doivent matcher train_v2.py — ajuste si besoin)
MATERIAL_MAP = {'Cast Iron': 0, 'HDPE': 1, 'PVC': 2, 'Steel': 3}
CORROSIVITY_MAP = {'Low': 0, 'Medium': 1, 'High': 2}  # celle-ci est explicite dans train_v2.py, OK


class DoomEngineV2:
    def __init__(self):
        print("🤖 Chargement Doom v2...")
        temp = joblib.load(MODELS_DIR / "doom_temporal.pkl")
        stat = joblib.load(MODELS_DIR / "doom_static.pkl")
        self.temporal_model = temp['model']
        self.temporal_features = temp['features']
        self.static_model = stat['model']
        self.static_features = stat['features']

        df = pd.read_csv(PROCESSED_DIR / "static.csv")
        agg = df.groupby('sector_id').agg({
            'velocity_fps': 'mean',
            'pipe_age_years': 'mean',
            'pipe_material': lambda s: s.mode().iat[0],
            'soil_corrosivity': lambda s: s.mode().iat[0],
        })
        self.profiles = agg
        print(f"✅ {len(self.profiles)} profils secteurs : {list(self.profiles.index[:5])}...")

    def get_profile(self, sector_id):
        if sector_id not in self.profiles.index:
            print(f"⚠️  '{sector_id}' inconnu, fallback sur {self.profiles.index[0]}")
            return self.profiles.iloc[0].to_dict()
        return self.profiles.loc[sector_id].to_dict()

    def diagnose(self, sector_id, pressure_bar, flow_rate_ls, temperature_c):
        # Temporel (unités métriques)
        X_temp = pd.DataFrame([{
            'pressure_bar': pressure_bar,
            'flow_rate_ls': flow_rate_ls,
            'temperature_c': temperature_c
        }])[self.temporal_features]
        p_temporal = float(self.temporal_model.predict_proba(X_temp)[0, 1])

        # Static (unités impériales + encodages)
        prof = self.get_profile(sector_id)
        mat_enc = MATERIAL_MAP.get(prof['pipe_material'], 0)
        cor_enc = CORROSIVITY_MAP.get(prof['soil_corrosivity'], 0)

        X_stat = pd.DataFrame([{
            'pressure_psi': pressure_bar * BAR_TO_PSI,
            'flow_gpm': flow_rate_ls * LS_TO_GPM,
            'velocity_fps': prof['velocity_fps'],
            'temperature_f': c_to_f(temperature_c),
            'pipe_age_years': prof['pipe_age_years'],
            'material_enc': mat_enc,
            'corrosivity_enc': cor_enc,
        }])[self.static_features]
        p_static = float(self.static_model.predict_proba(X_stat)[0, 1])

        score = ALPHA_TEMPORAL * p_temporal + BETA_STATIC * p_static
        if score >= THRESHOLD_LEAK:
            status, label = "leak", "Fuite"
        elif score >= THRESHOLD_SUSPECT:
            status, label = "suspect", "Suspect"
        else:
            status, label = "normal", "Normal"

        return {
            'sector_id': sector_id,
            'status': status, 'label': label,
            'score': round(score, 3),
            'p_temporal': round(p_temporal, 3),
            'p_static': round(p_static, 3),
            'pipe_age': round(prof['pipe_age_years'], 1),
            'material': prof['pipe_material'],
            'corrosivity': prof['soil_corrosivity'],
            'recommendation': self._recommend(status, prof),
        }

    def _recommend(self, status, prof):
        age = prof['pipe_age_years']
        if status == "leak":
            base = "🚨 Intervention urgente — équipe terrain sous 2h."
            if age > 20: base += f" Réseau ancien ({age:.0f} ans)."
            if prof['soil_corrosivity'] == "High": base += " Sol corrosif."
            return base
        elif status == "suspect":
            return f"⚠️ Surveillance renforcée — {prof['pipe_material']}, {age:.0f} ans."
        return "✅ Réseau nominal."

if __name__ == "__main__":
    engine = DoomEngineV2()
    print("\n--- Test diagnostic ---")
    for case in [
        ("Ain_Diab", 2.5, 180, 22),
        ("Maarif", 3.5, 100, 18),
        ("Medina", 1.8, 250, 20),
    ]:
        res = engine.diagnose(*case)
        print(f"\n{res['sector_id']} → {res['label']} (score={res['score']})")
        print(f"  Temporel: {res['p_temporal']} | Infra: {res['p_static']}")
        print(f"  Infra: {res['material']}, {res['pipe_age']} ans, sol {res['corrosivity']}")
        print(f"  💡 {res['recommendation']}")
