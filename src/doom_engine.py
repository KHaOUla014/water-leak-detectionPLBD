import pandas as pd
import numpy as np
import joblib
import os
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score


class DoomAI:
    """
    Doom : IA hybride pour la détection de fuites.
    - Niveau 1 : Seuils sur ILP (vert/orange/rouge)
    - Niveau 2 : Random Forest sur plusieurs features
    - Niveau 3 : Détection d'anomalie statistique (z-score historique)
    """

    LABELS = {0: "NORMAL", 1: "SUSPECT", 2: "FUITE_PROBABLE"}
    COLORS = {0: "#22c55e", 1: "#f59e0b", 2: "#ef4444"}

    THRESHOLDS = {"normal_max": 2.5, "suspect_max": 7.0}

    # Features utilisées par le modèle ML
    FEATURES = ["ilp", "volume_loss", "pressure_avg", "flow_night", "length_km"]

    def __init__(self, model_path="../models/doom_model.pkl"):
        self.model_path = model_path
        self.model = None
        self.history = {}

    # ---------- Préparation ----------
    def _prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcule volume_loss et ilp à partir du CSV brut."""
        df = df.copy()
        df["volume_loss"] = (df["volume_injected"] - df["volume_consumed"]).clip(lower=0)
        df["ilp"] = np.where(
            df["length_km"] > 0,
            df["volume_loss"] / df["length_km"],
            0
        )
        return df

    def threshold_classify(self, ilp):
        if ilp < self.THRESHOLDS["normal_max"]:
            return 0
        elif ilp < self.THRESHOLDS["suspect_max"]:
            return 1
        return 2

    # ---------- Entraînement ----------
    def train(self, csv_path="../data/synthetic_data.csv"):
        df = pd.read_csv(csv_path)
        df = self._prepare(df)

        X = df[self.FEATURES]
        y = df["label"]

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        self.model = RandomForestClassifier(
            n_estimators=200, max_depth=12, random_state=42, n_jobs=-1
        )
        self.model.fit(X_train, y_train)

        y_pred = self.model.predict(X_test)
        acc = accuracy_score(y_test, y_pred)
        print(f"\n🎯 Précision : {acc*100:.2f}%\n")
        print(classification_report(
            y_test, y_pred, target_names=list(self.LABELS.values())
        ))

        # Historique par secteur (pour z-score)
        self.history = (
            df.groupby("sector_id")["ilp"]
              .agg(["mean", "std"])
              .to_dict("index")
        )

        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        joblib.dump({"model": self.model, "history": self.history}, self.model_path)
        print(f"💾 Modèle sauvegardé → {self.model_path}")

    # ---------- Chargement ----------
    def load(self):
        data = joblib.load(self.model_path)
        self.model = data["model"]
        self.history = data["history"]

    # ---------- Anomalie ----------
    def anomaly_score(self, sector_id, ilp):
        if sector_id not in self.history:
            return 0.0
        stats = self.history[sector_id]
        std = stats["std"] if stats["std"] and stats["std"] > 0 else 1
        return abs((ilp - stats["mean"]) / std)

    # ---------- Diagnostic ----------
    def diagnose(self, sector_data: dict):
        """
        sector_data attendu :
        {
          sector_id, length_km,
          volume_injected, volume_consumed,
          pressure_avg, flow_night
        }
        """
        volume_loss = max(0, sector_data["volume_injected"] - sector_data["volume_consumed"])
        length = sector_data["length_km"]
        ilp = volume_loss / length if length > 0 else 0

        features = pd.DataFrame([{
            "ilp": ilp,
            "volume_loss": volume_loss,
            "pressure_avg": sector_data["pressure_avg"],
            "flow_night": sector_data["flow_night"],
            "length_km": length,
        }])

        ml_pred = int(self.model.predict(features)[0])
        proba = self.model.predict_proba(features)[0]
        confidence = float(proba.max())

        threshold_pred = self.threshold_classify(ilp)
        z = self.anomaly_score(sector_data["sector_id"], ilp)

        final = max(ml_pred, threshold_pred)
        if z > 3 and final == 0:
            final = 1

        return {
            "sector_id": sector_data["sector_id"],
            "ilp": round(ilp, 3),
            "volume_loss": round(volume_loss, 2),
            "ml_prediction": ml_pred,
            "threshold_prediction": threshold_pred,
            "anomaly_zscore": round(z, 2),
            "final_status": final,
            "status_label": self.LABELS[final],
            "color": self.COLORS[final],
            "confidence": round(confidence, 3),
            "recommendation": self._recommend(final, z)
        }

    def _recommend(self, status, z):
        if status == 2:
            return "🚨 Déployer Orby immédiatement pour localiser la fuite."
        elif status == 1:
            return "⚠️ Surveillance renforcée. Inspection Orby recommandée sous 48h."
        elif z > 2:
            return "🔎 Comportement inhabituel détecté, à surveiller."
        return "✅ Secteur en bon état."
