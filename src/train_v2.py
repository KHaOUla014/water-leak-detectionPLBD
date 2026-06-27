"""
Doom v2 - Entraînement modèles hybrides
"""
import pandas as pd
import numpy as np
import joblib
import pickle
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split, cross_val_predict, StratifiedKFold
from sklearn.metrics import classification_report, roc_auc_score, precision_recall_curve

PROCESSED_DIR = Path("data/processed")
MODELS_DIR = Path("models")
MODELS_DIR.mkdir(exist_ok=True)


def train_temporal():
    print("\n" + "=" * 60)
    print("  🧠 MODÈLE 1 — TEMPOREL (capteurs temps réel)")
    print("=" * 60)
    df = pd.read_csv(PROCESSED_DIR / "temporal.csv")

    features = ['pressure_bar', 'flow_rate_ls', 'temperature_c']
    X = df[features]
    y = df['leak_label']

    print(f"   {len(df)} lignes | Fuites : {y.sum()} ({y.mean()*100:.1f}%)")

    model = RandomForestClassifier(
        n_estimators=200, max_depth=12, class_weight='balanced',
        random_state=42, n_jobs=-1
    )

    # === VALIDATION CROISÉE 5-fold (chaque fuite testée 1 fois) ===
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    y_pred_cv  = cross_val_predict(model, X, y, cv=cv)
    y_proba_cv = cross_val_predict(model, X, y, cv=cv, method='predict_proba')[:, 1]

    print("\n📊 Performance (cross-validée, fiable) :")
    print(classification_report(y, y_pred_cv, target_names=['Normal', 'Fuite']))
    print(f"AUC-ROC : {roc_auc_score(y, y_proba_cv):.3f}")

    # === RECHERCHE DU MEILLEUR SEUIL (objectif : recall élevé) ===
    print("\n🎚️  Seuils (objectif : attraper un maximum de fuites) :")
    print(f"{'seuil':>7} {'precision':>10} {'recall':>8} {'f1':>6}")
    best_thr, best_f1 = 0.5, 0.0
    for t in [0.5, 0.4, 0.3, 0.25, 0.2, 0.15, 0.1]:
        yp = (y_proba_cv >= t).astype(int)
        tp = int(((yp == 1) & (y == 1)).sum())
        fp = int(((yp == 1) & (y == 0)).sum())
        fn = int(((yp == 0) & (y == 1)).sum())
        p = tp / (tp + fp) if tp + fp else 0
        r = tp / (tp + fn) if tp + fn else 0
        f = 2 * p * r / (p + r) if p + r else 0
        flag = ""
        # on garde le seuil avec recall>=0.90 ET meilleure precision
        if r >= 0.90 and f > best_f1:
            best_thr, best_f1, flag = t, f, "  ⭐"
        print(f"{t:>7.2f} {p:>10.2f} {r:>8.2f} {f:>6.2f}{flag}")

    print(f"\n✅ Seuil retenu : {best_thr:.2f} (recall ≥ 0.90)")

    # === Modèle final entraîné sur TOUTES les données ===
    model.fit(X, y)

    print("\n🔑 Importance features :")
    for f, imp in zip(features, model.feature_importances_):
        print(f"  {f:<20} {imp:.3f}")

    # On sauvegarde AUSSI le seuil pour que le moteur l'utilise
    joblib.dump(
        {'model': model, 'features': features, 'threshold': best_thr},
        MODELS_DIR / "doom_temporal.pkl"
    )
    print(f"\n💾 Sauvegardé : models/doom_temporal.pkl (seuil={best_thr:.2f})")


def train_static():
    print("\n" + "=" * 60)
    print("  🏗️  MODÈLE 2 — STATIQUE (infrastructure)")
    print("=" * 60)
    df = pd.read_csv(PROCESSED_DIR / "static.csv")

    # Encodage catégoriel
    df['material_enc'] = df['pipe_material'].astype('category').cat.codes
    df['corrosivity_enc'] = df['soil_corrosivity'].map({'Low': 0, 'Medium': 1, 'High': 2}).fillna(1)

    features = ['pressure_psi', 'flow_gpm', 'velocity_fps', 'temperature_f',
                'pipe_age_years', 'material_enc', 'corrosivity_enc']
    X = df[features]
    y = df['leak_class']

    print(f"   {len(df)} lignes | Fuites : {y.sum()} ({y.mean()*100:.1f}%)")

    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = GradientBoostingClassifier(
        n_estimators=200, max_depth=5, learning_rate=0.05, random_state=42
    )
    model.fit(X_tr, y_tr)

    y_pred = model.predict(X_te)
    print("\n📊 Performance :")
    print(classification_report(y_te, y_pred, target_names=['Normal', 'Fuite']))

    print("🔑 Importance features :")
    for f, imp in sorted(zip(features, model.feature_importances_), key=lambda x: -x[1]):
        print(f"  {f:<20} {imp:.3f}")

    out_path = MODELS_DIR / "doom_static.pkl"
    with open(out_path, 'wb') as f:
        pickle.dump({'model': model, 'features': features}, f)
    print(f"\n💾 Sauvegardé : {out_path}")


if __name__ == "__main__":
    train_temporal()
    train_static()
    print("\n🎉 Entraînement Doom v2 terminé !")
