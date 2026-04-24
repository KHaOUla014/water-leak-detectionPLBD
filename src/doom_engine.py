"""
doom_engine.py
────────────────────────────────────────────────────────────────────────────────
Moteur DOOM — Détection d'Opérations anOmales sur les réseaux d'eau Municipaux

Responsabilités :
  - Définition et application des seuils ILP (vert / orange / rouge)
  - Détection d'anomalies statistique (Z-score sur historique)
  - Calcul du score de fuite composite [0 – 100]
  - Localisation probable de la fuite (canalisation la plus suspecte)
  - Génération des alertes structurées
────────────────────────────────────────────────────────────────────────────────
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
#  Configuration des seuils ILP  [m³/km/jour]
# ═══════════════════════════════════════════════════════════════════════════════
ILP_THRESHOLDS = {
    "green":  (0.0,  2.5),   # Normal
    "orange": (2.5,  5.0),   # Suspect
    "red":    (5.0, float("inf")),  # Fuite probable
}

# Z-score au-delà duquel une valeur ILP est considérée anomalie statistique
ZSCORE_ALERT_THRESHOLD = 2.0

# Poids du score composite
SCORE_WEIGHTS = {
    "ilp_norm":    0.45,   # ILP normalisé par seuil rouge
    "zscore_norm": 0.35,   # Z-score normalisé
    "trend_norm":  0.20,   # Tendance haussière récente
}

# Mapping couleur → label lisible
COLOR_LABEL = {
    "green":  "Normal",
    "orange": "Suspect",
    "red":    "Fuite probable",
}

# Emojis pour les exports textuels
COLOR_EMOJI = {"green": "🟢", "orange": "🟠", "red": "🔴"}


# ═══════════════════════════════════════════════════════════════════════════════
@dataclass
class SectorAlert:
    """
    Résultat d'analyse DOOM pour un secteur hydraulique.
    """
    secteur:              str
    ilp:                  float
    couleur:              str                    # green | orange | red
    label:                str
    score_fuite:          float                  # 0–100
    zscore:               float
    is_anomalie:          bool
    localisation_probable: Optional[str] = None  # ID canalisation suspecte
    pipes_suspects:       list[str] = field(default_factory=list)
    message:              str = ""

    @property
    def emoji(self) -> str:
        return COLOR_EMOJI.get(self.couleur, "⚪")

    def to_dict(self) -> dict:
        return {
            "secteur":              self.secteur,
            "ILP":                  round(self.ilp, 4),
            "couleur":              self.couleur,
            "statut":               self.label,
            "score_fuite":          round(self.score_fuite, 1),
            "zscore":               round(self.zscore, 2),
            "anomalie_statistique": self.is_anomalie,
            "localisation_probable": self.localisation_probable or "—",
            "pipes_suspects":       ", ".join(self.pipes_suspects) or "—",
            "message":              self.message,
        }


# ═══════════════════════════════════════════════════════════════════════════════
class DoomEngine:
    """
    Moteur d'analyse des pertes hydrauliques.

    Entrées :
      - sector_ilp  : DataFrame produit par EpanetReader.compute_sector_ilp()
      - history_csv : chemin vers un CSV d'historique ILP (optionnel)
    """

    def __init__(
        self,
        sector_ilp: pd.DataFrame,
        sectors_pipes: dict[str, list[str]] | None = None,
        history_csv: str = "data/ilp_history.csv",
    ):
        self.sector_ilp    = sector_ilp
        self.sectors_pipes = sectors_pipes or {}
        self.history_csv   = history_csv
        self.history: pd.DataFrame = self._load_or_create_history()
        self.alerts: list[SectorAlert] = []

    # ──────────────────────────────────────────────────────────────────────────
    def run(self) -> list[SectorAlert]:
        """
        Point d'entrée principal : analyse complète de tous les secteurs.
        Retourne la liste des alertes.
        """
        logger.info("═" * 60)
        logger.info("  DOOM ENGINE — Démarrage de l'analyse")
        logger.info("═" * 60)

        self.alerts = []

        for secteur, row in self.sector_ilp.iterrows():
            alert = self._analyse_sector(str(secteur), row)
            self.alerts.append(alert)
            logger.info(f"  {alert.emoji}  {secteur:<20} ILP={alert.ilp:.4f}  "
                        f"Score={alert.score_fuite:.1f}  [{alert.label}]")

        # Mettre à jour l'historique
        self._update_history()

        # Sauvegarder les alertes
        self._save_alerts()

        logger.info("─" * 60)
        logger.info(f"  {len([a for a in self.alerts if a.couleur == 'red'])} fuite(s) probable(s) | "
                    f"{len([a for a in self.alerts if a.couleur == 'orange'])} suspect(s)")
        logger.info("═" * 60)

        return self.alerts

    # ──────────────────────────────────────────────────────────────────────────
    def _analyse_sector(self, secteur: str, row: pd.Series) -> SectorAlert:
        ilp = float(row["ILP"])

        # 1. Classification par seuils
        couleur = self._classify_ilp(ilp)
        label   = COLOR_LABEL[couleur]

        # 2. Détection d'anomalie statistique (Z-score)
        zscore, is_anomalie = self._zscore_anomaly(secteur, ilp)

        # 3. Score composite de fuite [0–100]
        score = self._compute_leak_score(secteur, ilp, zscore)

        # Renforcement : si le Z-score confirme l'anomalie, on monte d'un cran
        if is_anomalie and couleur == "green":
            couleur = "orange"
            label   = COLOR_LABEL[couleur]

        # 4. Localisation probable
        pipes_suspects, localisation = self._localize_leak(secteur, ilp, score)

        # 5. Message explicatif
        message = self._build_message(secteur, ilp, couleur, zscore, is_anomalie, score)

        return SectorAlert(
            secteur=secteur,
            ilp=ilp,
            couleur=couleur,
            label=label,
            score_fuite=score,
            zscore=zscore,
            is_anomalie=is_anomalie,
            localisation_probable=localisation,
            pipes_suspects=pipes_suspects,
            message=message,
        )

    # ──────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _classify_ilp(ilp: float) -> str:
        """Applique les seuils ILP → 'green' | 'orange' | 'red'."""
        if ilp < ILP_THRESHOLDS["green"][1]:
            return "green"
        elif ilp < ILP_THRESHOLDS["orange"][1]:
            return "orange"
        else:
            return "red"

    # ──────────────────────────────────────────────────────────────────────────
    def _zscore_anomaly(self, secteur: str, ilp: float) -> tuple[float, bool]:
        """
        Compare l'ILP courant à l'historique du secteur.
        Retourne (z_score, is_anomalie).
        """
        if secteur not in self.history.columns or len(self.history) < 3:
            return 0.0, False

        hist = self.history[secteur].dropna().values
        mu, sigma = hist.mean(), hist.std()

        if sigma < 1e-6:        # pas de variance → pas d'anomalie détectable
            return 0.0, False

        z = (ilp - mu) / sigma
        return round(float(z), 3), abs(z) >= ZSCORE_ALERT_THRESHOLD

    # ──────────────────────────────────────────────────────────────────────────
    def _compute_leak_score(self, secteur: str, ilp: float, zscore: float) -> float:
        """
        Score de fuite composite [0 – 100].

        Composantes :
          - ILP normalisé par rapport au seuil rouge (5.0)
          - Z-score normalisé [0; 1] (plafonné à z=4)
          - Tendance haussière sur l'historique récent
        """
        # Composante ILP
        ilp_norm = min(ilp / ILP_THRESHOLDS["red"][0], 1.0)

        # Composante Z-score
        zscore_norm = min(abs(zscore) / 4.0, 1.0)

        # Composante tendance (pente sur les 7 derniers jours)
        trend_norm = self._trend_score(secteur)

        score = (
            SCORE_WEIGHTS["ilp_norm"]    * ilp_norm +
            SCORE_WEIGHTS["zscore_norm"] * zscore_norm +
            SCORE_WEIGHTS["trend_norm"]  * trend_norm
        ) * 100

        return round(min(score, 100.0), 2)

    # ──────────────────────────────────────────────────────────────────────────
    def _trend_score(self, secteur: str) -> float:
        """
        Tendance récente : pente normalisée des 7 derniers jours ILP.
        Retourne 0–1 (0 = stable/baissier, 1 = fortement haussier).
        """
        if secteur not in self.history.columns or len(self.history) < 3:
            return 0.0

        recent = self.history[secteur].dropna().tail(7).values
        if len(recent) < 2:
            return 0.0

        x = np.arange(len(recent))
        slope = np.polyfit(x, recent, 1)[0]
        return float(np.clip(slope / 2.0, 0.0, 1.0))   # normalise sur ~2 m³/km/j·jour

    # ──────────────────────────────────────────────────────────────────────────
    def _localize_leak(
        self, secteur: str, ilp: float, score: float
    ) -> tuple[list[str], Optional[str]]:
        """
        Identifie les canalisations suspectes dans le secteur en croisant
        la longueur (écrêtée) et le score global.

        Retourne (liste_pipes_suspects, pipe_principal).
        """
        if score < 20.0 or secteur not in self.sectors_pipes:
            return [], None

        from epanet_reader import PIPE_LENGTHS_M

        pipes = self.sectors_pipes[secteur]
        if not pipes:
            return [], None

        # Heuristique : les canalisations les plus longues sont plus exposées
        scored_pipes = sorted(
            pipes,
            key=lambda p: PIPE_LENGTHS_M.get(p, 300),
            reverse=True,
        )

        n_suspects = max(1, int(len(scored_pipes) * 0.5))
        suspects   = scored_pipes[:n_suspects]

        return suspects, suspects[0]

    # ──────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _build_message(
        secteur: str, ilp: float, couleur: str,
        zscore: float, is_anomalie: bool, score: float
    ) -> str:
        base = {
            "green":  f"ILP={ilp:.2f} m³/km/j — fonctionnement normal.",
            "orange": f"ILP={ilp:.2f} m³/km/j — pertes suspectes, surveillance recommandée.",
            "red":    f"ILP={ilp:.2f} m³/km/j — FUITE PROBABLE, intervention prioritaire.",
        }[couleur]

        anomaly_txt = (
            f" Anomalie statistique détectée (Z={zscore:+.1f})."
            if is_anomalie else ""
        )
        return f"{base}{anomaly_txt} Score DOOM : {score:.0f}/100."

    # ──────────────────────────────────────────────────────────────────────────
    #  Historique
    # ──────────────────────────────────────────────────────────────────────────
    def _load_or_create_history(self) -> pd.DataFrame:
        """
        Charge le CSV historique ou génère un historique synthétique
        de 30 jours si le fichier n'existe pas.
        """
        if os.path.exists(self.history_csv):
            try:
                df = pd.read_csv(self.history_csv, index_col=0, parse_dates=True)
                logger.info(f"Historique ILP chargé : {len(df)} entrées.")
                return df
            except Exception as exc:
                logger.warning(f"Impossible de lire l'historique ({exc}) → génération.")

        return self._generate_synthetic_history()

    def _generate_synthetic_history(self) -> pd.DataFrame:
        """
        30 jours d'historique ILP par secteur (sans anomalie majeure)
        pour initialiser la détection statistique.
        """
        np.random.seed(0)
        dates = pd.date_range(end=pd.Timestamp.today().normalize(), periods=30, freq="D")
        base  = {"S1_Centre": 1.8, "S2_Nord": 2.2, "S3_Est": 1.5, "S4_Ouest": 1.2}

        data = {
            sector: base_ilp + np.random.normal(0, 0.3, 30)
            for sector, base_ilp in base.items()
        }
        df = pd.DataFrame(data, index=dates)
        df.index.name = "date"

        os.makedirs(os.path.dirname(self.history_csv) or ".", exist_ok=True)
        df.to_csv(self.history_csv)
        logger.info(f"Historique synthétique créé → {self.history_csv}")
        return df

    def _update_history(self):
        """Ajoute la session courante à l'historique."""
        today   = pd.Timestamp.today().normalize()
        new_row = pd.Series(
            {row["secteur"]: row["ILP"] for row in [a.to_dict() for a in self.alerts]},
            name=today,
        )
        self.history = pd.concat([self.history, new_row.to_frame().T])
        self.history.index.name = "date"

        try:
            os.makedirs(os.path.dirname(self.history_csv) or ".", exist_ok=True)
            self.history.to_csv(self.history_csv)
        except Exception as exc:
            logger.warning(f"Historique non sauvegardé : {exc}")

    # ──────────────────────────────────────────────────────────────────────────
    def _save_alerts(self, path: str = "data/alerts.csv"):
        """Sauvegarde les alertes courantes au format CSV."""
        rows = [a.to_dict() for a in self.alerts]
        df   = pd.DataFrame(rows)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        df.to_csv(path, index=False)
        logger.info(f"Alertes sauvegardées → {path}")

    # ──────────────────────────────────────────────────────────────────────────
    def get_alerts_dataframe(self) -> pd.DataFrame:
        """Retourne les alertes sous forme de DataFrame."""
        return pd.DataFrame([a.to_dict() for a in self.alerts])

    def get_summary(self) -> dict:
        """Résumé global de la session d'analyse."""
        counts = {"green": 0, "orange": 0, "red": 0}
        for a in self.alerts:
            counts[a.couleur] += 1
        return {
            "total_secteurs": len(self.alerts),
            "normaux":        counts["green"],
            "suspects":       counts["orange"],
            "fuites_probables": counts["red"],
            "score_moyen":    round(
                np.mean([a.score_fuite for a in self.alerts]) if self.alerts else 0, 1
            ),
        }