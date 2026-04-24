"""
main.py
────────────────────────────────────────────────────────────────────────────────
DOOM — Point d'entrée principal

Pipeline complet :
  1. Chargement du réseau EPANET
  2. Simulation hydraulique
  3. Calcul des indicateurs (ILP)
  4. Analyse IA (seuils + anomalies + scoring)
  5. Génération des sorties (tableau, graphique, carte, résumé)

Usage :
  python main.py
  python main.py --network path/to/network.inp
  python main.py --mock          ← simulation synthétique sans wntr
────────────────────────────────────────────────────────────────────────────────
"""

import argparse
import logging
import os
import sys

# ── Ajout du dossier src au PYTHONPATH ────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("DOOM")


# ═══════════════════════════════════════════════════════════════════════════════
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="DOOM — Détection de Fuites en Réseau d'Eau")
    p.add_argument(
        "--network",
        default=os.path.join(os.path.dirname(__file__), "..", "network", "orby_doom_v1.inp"),
        help="Chemin vers le fichier EPANET (.inp ou .net)",
    )
    p.add_argument(
        "--mock", action="store_true",
        help="Forcer le mode simulation synthétique (ne nécessite pas wntr)",
    )
    p.add_argument(
        "--output-dir",
        default=os.path.join(os.path.dirname(__file__), "..", "output"),
        help="Répertoire de sortie pour les graphiques",
    )
    p.add_argument(
        "--data-dir",
        default=os.path.join(os.path.dirname(__file__), "..", "data"),
        help="Répertoire des données (CSV résultats et historique)",
    )
    return p.parse_args()


# ═══════════════════════════════════════════════════════════════════════════════
def main():
    args = parse_args()

    logger.info("╔══════════════════════════════════════════════════╗")
    logger.info("║   DOOM  —  Démarrage du pipeline d'analyse       ║")
    logger.info("╚══════════════════════════════════════════════════╝")

    # ── Imports locaux ───────────────────────────────────────────────────────
    from epanet_reader import EpanetReader, SECTORS
    from doom_engine   import DoomEngine
    from ui_dashboard  import UiDashboard

    network_path = os.path.abspath(args.network)
    output_dir   = os.path.abspath(args.output_dir)
    data_dir     = os.path.abspath(args.data_dir)

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(data_dir,   exist_ok=True)

    # ────────────────────────────────────────────────────────────────────────
    # ÉTAPE 1 — Chargement et simulation EPANET
    # ────────────────────────────────────────────────────────────────────────
    logger.info("▶ Étape 1/4 — Chargement du réseau EPANET")
    reader = EpanetReader(network_path)

    if args.mock:
        reader._use_mock = True
        logger.info("   Mode mock forcé par l'utilisateur.")
    else:
        reader.load_network()

    reader.run_simulation()

    # Export résultats bruts
    sim_csv = os.path.join(data_dir, "simulation_results.csv")
    reader.save_simulation_csv(sim_csv)

    # ────────────────────────────────────────────────────────────────────────
    # ÉTAPE 2 — Calcul des ILP par secteur
    # ────────────────────────────────────────────────────────────────────────
    logger.info("▶ Étape 2/4 — Calcul des Indices Linéaires de Perte (ILP)")
    sector_ilp = reader.compute_sector_ilp()

    logger.info("   ILP calculés :")
    for sector, row in sector_ilp.iterrows():
        logger.info(f"     {sector:<20}  ILP = {row['ILP']:.4f}  "
                    f"(perdu={row['vol_perdu']:.2f} m³/j, "
                    f"longueur={row['longueur_km']:.2f} km)")

    # ────────────────────────────────────────────────────────────────────────
    # ÉTAPE 3 — Moteur DOOM (classification + anomalies + score)
    # ────────────────────────────────────────────────────────────────────────
    logger.info("▶ Étape 3/4 — Analyse DOOM (IA de détection de fuites)")

    history_csv = os.path.join(data_dir, "ilp_history.csv")
    alerts_csv  = os.path.join(data_dir, "alerts.csv")

    engine = DoomEngine(
        sector_ilp=sector_ilp,
        sectors_pipes=SECTORS,
        history_csv=history_csv,
    )
    alerts = engine.run()

    alerts_df = engine.get_alerts_dataframe()
    summary   = engine.get_summary()

    logger.info(f"   Résumé : {summary['normaux']} normaux | "
                f"{summary['suspects']} suspects | "
                f"{summary['fuites_probables']} fuites probables | "
                f"score moyen = {summary['score_moyen']}")

    # ────────────────────────────────────────────────────────────────────────
    # ÉTAPE 4 — Interface de présentation
    # ────────────────────────────────────────────────────────────────────────
    logger.info("▶ Étape 4/4 — Génération des sorties visuelles")

    dashboard = UiDashboard(
        alerts_df=alerts_df,
        sector_ilp=sector_ilp,
        sectors_pipes=SECTORS,
        output_dir=output_dir,
    )
    chart_path, map_path, summary_path = dashboard.render_all()

    # ────────────────────────────────────────────────────────────────────────
    # FIN
    # ────────────────────────────────────────────────────────────────────────
    logger.info("╔══════════════════════════════════════════════════╗")
    logger.info("║   DOOM  —  Pipeline terminé avec succès          ║")
    logger.info("╠══════════════════════════════════════════════════╣")
    logger.info(f"║  Graphique   : {os.path.basename(chart_path):<32}║")
    logger.info(f"║  Carte       : {os.path.basename(map_path):<32}║")
    logger.info(f"║  Résumé      : {os.path.basename(summary_path):<32}║")
    logger.info("╚══════════════════════════════════════════════════╝")

    return alerts_df


# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    main()