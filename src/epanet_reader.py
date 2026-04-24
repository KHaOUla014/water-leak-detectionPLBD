"""
epanet_reader.py
────────────────────────────────────────────────────────────────────────────────
Module de lecture EPANET et d'extraction des indicateurs hydrauliques.

Responsabilités :
  - Chargement du fichier réseau (.net / .inp)
  - Simulation hydraulique via wntr
  - Extraction des débits et des demandes par canalisation
  - Calcul des volumes injectés / consommés par secteur
  - Calcul de l'Indice Linéaire de Perte (ILP) [m³/km/jour]
  - Export CSV des résultats bruts
────────────────────────────────────────────────────────────────────────────────
"""

import os
import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Définition des secteurs : {nom: liste des IDs de canalisations} ────────────
SECTORS: dict[str, list[str]] = {
    "S1_Centre": ["P1", "P2", "P5", "P15"],
    "S2_Nord":   ["P3", "P4", "P11", "P12"],
    "S3_Est":    ["P8", "P9", "P10", "P14"],
    "S4_Ouest":  ["P6", "P7", "P13"],
}

# ── Longueurs réelles par canalisation (mètres) ───────────────────────────────
PIPE_LENGTHS_M: dict[str, float] = {
    "P1": 500, "P2": 400, "P3": 350, "P4": 300,
    "P5": 450, "P6": 380, "P7": 320, "P8": 400,
    "P9": 350, "P10": 300, "P11": 420, "P12": 380,
    "P13": 350, "P14": 280, "P15": 200,
}


# ═══════════════════════════════════════════════════════════════════════════════
class EpanetReader:
    """
    Lit un fichier EPANET (.inp/.net) et produit les indicateurs
    hydrauliques nécessaires au moteur DOOM.
    """

    def __init__(self, network_file: str):
        self.network_file = network_file
        self.wn = None                 # WaterNetworkModel wntr
        self.results = None            # SimulationResults wntr
        self._use_mock = False         # True si wntr absent ou simulation échouée

    # ──────────────────────────────────────────────────────────────────────────
    def load_network(self):
        """
        Charge le modèle réseau EPANET.
        Bascule en mode mock si wntr n'est pas installé.
        """
        try:
            import wntr
            logger.info(f"Chargement du réseau : {self.network_file}")
            self.wn = wntr.network.WaterNetworkModel(self.network_file)
            logger.info(
                f"  → {len(self.wn.pipe_name_list)} canalisations  |  "
                f"{len(self.wn.junction_name_list)} nœuds"
            )
        except ImportError:
            logger.warning("wntr non installé → mode simulation synthétique activé.")
            self._use_mock = True
        except Exception as exc:
            logger.error(f"Erreur de lecture EPANET : {exc}")
            self._use_mock = True
        return self

    # ──────────────────────────────────────────────────────────────────────────
    def run_simulation(self):
        """
        Exécute la simulation hydraulique sur 24 h (pas horaire).
        """
        if self._use_mock:
            logger.info("Mode mock : génération de données synthétiques.")
            self._generate_mock_results()
            return self

        try:
            import wntr
            self.wn.options.time.duration = 24 * 3600
            self.wn.options.time.hydraulic_timestep = 3600
            sim = wntr.sim.EpanetSimulator(self.wn)
            self.results = sim.run_sim()
            logger.info("Simulation hydraulique terminée (24 h).")
        except Exception as exc:
            logger.error(f"Simulation échouée ({exc}) → mode mock.")
            self._use_mock = True
            self._generate_mock_results()
        return self

    # ──────────────────────────────────────────────────────────────────────────
    def extract_flows(self) -> pd.DataFrame:
        """
        Retourne un DataFrame des débits [L/s] pour chaque canalisation,
        indexé par horodatage (index = heure 0 à 23).
        """
        if self._use_mock:
            return self._mock_flows

        flowrate = self.results.link["flowrate"]  # m³/s → LPS ×1000
        df = flowrate * 1000
        df.index = pd.RangeIndex(len(df), name="heure")
        return df

    # ──────────────────────────────────────────────────────────────────────────
    def extract_demands(self) -> pd.DataFrame:
        """
        Retourne un DataFrame des demandes [L/s] pour chaque nœud.
        """
        if self._use_mock:
            return self._mock_demands

        demand = self.results.node["demand"]      # m³/s → LPS ×1000
        df = demand * 1000
        df.index = pd.RangeIndex(len(df), name="heure")
        return df

    # ──────────────────────────────────────────────────────────────────────────
    def compute_sector_ilp(self) -> pd.DataFrame:
        """
        Calcule pour chaque secteur :
          - Vol_injecté   [m³/jour]
          - Vol_consommé  [m³/jour]
          - Vol_perdu     [m³/jour]
          - Longueur_km   [km]
          - ILP           [m³/km/jour]

        Retourne un DataFrame avec un secteur par ligne.
        """
        flows   = self.extract_flows()   # [L/s] → 24 lignes × N colonnes
        demands = self.extract_demands() # idem nœuds

        records = []
        for sector, pipe_ids in SECTORS.items():

            # ── Volume injecté : débit entrant dans le secteur ──────────────
            sector_cols   = [p for p in pipe_ids if p in flows.columns]
            vol_injected  = self._flow_lps_to_m3_day(flows[sector_cols].abs().mean(axis=1))

            # ── Volume consommé : somme des demandes des nœuds du secteur ───
            # Approximation : on prend la moitié des nœuds disponibles
            node_cols  = demands.columns.tolist()
            n_take     = max(1, len(node_cols) // len(SECTORS))
            idx        = list(SECTORS.keys()).index(sector)
            sel_nodes  = node_cols[idx * n_take: (idx + 1) * n_take]
            vol_consumed = self._flow_lps_to_m3_day(demands[sel_nodes].sum(axis=1)) if sel_nodes else 0.0

            # ── Longueur totale du secteur ──────────────────────────────────
            length_m  = sum(PIPE_LENGTHS_M.get(p, 300) for p in pipe_ids)
            length_km = length_m / 1000

            # ── ILP ────────────────────────────────────────────────────────
            v_inj   = float(np.mean(vol_injected))
            v_cons  = float(np.mean(vol_consumed)) if not isinstance(vol_consumed, float) else vol_consumed
            v_lost  = max(v_inj - v_cons, 0.0)
            ilp     = v_lost / length_km if length_km > 0 else 0.0

            records.append({
                "secteur":      sector,
                "vol_injecte":  round(v_inj,   3),
                "vol_consomme": round(v_cons,  3),
                "vol_perdu":    round(v_lost,  3),
                "longueur_km":  round(length_km, 3),
                "ILP":          round(ilp,     4),
            })

        df = pd.DataFrame(records).set_index("secteur")
        logger.info("ILP calculé pour tous les secteurs.")
        return df

    # ──────────────────────────────────────────────────────────────────────────
    #  Helpers privés
    # ──────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _flow_lps_to_m3_day(series: pd.Series) -> pd.Series:
        """Convertit un débit moyen [L/s] en volume journalier [m³/jour]."""
        return series * 3.6  # L/s → m³/h  (×3600/1000)  × 24 h

    # ──────────────────────────────────────────────────────────────────────────
    def _generate_mock_results(self):
        """
        Génère des données hydrauliques réalistes pour 24 heures
        quand wntr n'est pas disponible (démo / CI).
        """
        np.random.seed(42)
        n_hours = 24
        hour_pattern = 0.6 + 0.4 * np.sin(np.linspace(0, 2 * np.pi, n_hours))

        all_pipes = list(PIPE_LENGTHS_M.keys())

        # Débits de base [L/s] + modulation temporelle
        base_flows = {p: np.random.uniform(0.5, 5.0) for p in all_pipes}
        flow_data  = {
            p: base_flows[p] * hour_pattern + np.random.normal(0, 0.05, n_hours)
            for p in all_pipes
        }

        # Simulation de fuite sur S2_Nord et S3_Est
        for p in SECTORS["S2_Nord"]:
            flow_data[p] *= 1.35          # sur-débit = perte
        for p in SECTORS["S3_Est"][:2]:
            flow_data[p] *= 1.15

        self._mock_flows = pd.DataFrame(flow_data, index=pd.RangeIndex(n_hours, name="heure"))

        # Demandes aux nœuds [L/s]
        all_nodes  = [f"J{i}" for i in range(1, 13)]
        base_dem   = {n: np.random.uniform(0.1, 0.8) for n in all_nodes}
        demand_data = {
            n: base_dem[n] * hour_pattern + np.random.normal(0, 0.02, n_hours)
            for n in all_nodes
        }
        self._mock_demands = pd.DataFrame(demand_data, index=pd.RangeIndex(n_hours, name="heure"))

    # ──────────────────────────────────────────────────────────────────────────
    def save_simulation_csv(self, output_path: str = "data/simulation_results.csv"):
        """Sauvegarde les résultats bruts de simulation au format CSV."""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        flows = self.extract_flows()
        flows.to_csv(output_path)
        logger.info(f"Résultats de simulation sauvegardés → {output_path}")