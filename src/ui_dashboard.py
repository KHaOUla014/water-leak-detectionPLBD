"""
ui_dashboard.py
────────────────────────────────────────────────────────────────────────────────
Interface de présentation DOOM — Tableau · Graphiques · Carte réseau

Produit trois sorties :
  1. Tableau récapitulatif en console (rich / fallback texte)
  2. Graphique risk_chart.png  (barres ILP + score, couleur coded)
  3. Carte/schéma du réseau en PNG  (nœuds + canalisations, code couleur secteur)
────────────────────────────────────────────────────────────────────────────────
"""

import logging
import os
from typing import Optional

import matplotlib
matplotlib.use("Agg")                          # rendu sans display X11
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Palette couleurs DOOM ───────────────────────────────────────────────────
DOOM_PALETTE = {
    "green":      "#2ECC71",
    "orange":     "#E67E22",
    "red":        "#E74C3C",
    "bg":         "#0D1117",
    "bg_panel":   "#161B22",
    "text":       "#E6EDF3",
    "text_muted": "#8B949E",
    "grid":       "#21262D",
    "accent":     "#58A6FF",
}

# ── Coordonnées des nœuds du réseau de test (issues du fichier .inp) ─────────
NODE_COORDS = {
    "R1":  (0.0,  50.0),
    "T1":  (20.0, 70.0),
    "J1":  (20.0, 50.0),
    "J2":  (40.0, 60.0),
    "J3":  (60.0, 65.0),
    "J4":  (75.0, 55.0),
    "J5":  (35.0, 35.0),
    "J6":  (50.0, 25.0),
    "J7":  (65.0, 20.0),
    "J8":  (55.0, 50.0),
    "J9":  (70.0, 40.0),
    "J10": (80.0, 35.0),
    "J11": (80.0, 50.0),
    "J12": (75.0, 30.0),
}

PIPE_CONNECTIONS = {
    "P1":  ("R1",  "J1"),  "P2":  ("J1",  "J2"),
    "P3":  ("J2",  "J3"),  "P4":  ("J3",  "J4"),
    "P5":  ("J1",  "J5"),  "P6":  ("J5",  "J6"),
    "P7":  ("J6",  "J7"),  "P8":  ("J2",  "J8"),
    "P9":  ("J8",  "J9"),  "P10": ("J9",  "J10"),
    "P11": ("J4",  "J11"), "P12": ("J11", "J12"),
    "P13": ("J7",  "J12"), "P14": ("J10", "J11"),
    "P15": ("T1",  "J5"),
}

SECTOR_COLORS_HEX = {
    "S1_Centre": "#58A6FF",
    "S2_Nord":   "#E67E22",
    "S3_Est":    "#E74C3C",
    "S4_Ouest":  "#2ECC71",
}


# ═══════════════════════════════════════════════════════════════════════════════
class UiDashboard:
    """
    Interface de présentation des résultats DOOM.
    """

    def __init__(
        self,
        alerts_df: pd.DataFrame,
        sector_ilp: pd.DataFrame,
        sectors_pipes: dict[str, list[str]],
        output_dir: str = "output",
    ):
        self.alerts_df     = alerts_df
        self.sector_ilp    = sector_ilp
        self.sectors_pipes = sectors_pipes
        self.output_dir    = output_dir
        os.makedirs(output_dir, exist_ok=True)

    # ──────────────────────────────────────────────────────────────────────────
    def render_all(self):
        """Génère toutes les sorties visuelles."""
        self.print_console_table()
        chart_path = self.render_risk_chart()
        map_path   = self.render_network_map()
        summary    = self.write_summary()
        return chart_path, map_path, summary

    # ══════════════════════════════════════════════════════════════════════════
    # 1. TABLEAU CONSOLE
    # ══════════════════════════════════════════════════════════════════════════
    def print_console_table(self):
        """Affiche un tableau formaté en console."""
        print("\n")
        print("╔══════════════════════════════════════════════════════════════════════════╗")
        print("║         DOOM — Détection de Fuites — Rapport d'Analyse                 ║")
        print("╠══════════════╦═══════════╦══════════╦══════════╦═══════════╦══════════╣")
        print("║ Secteur      ║ ILP       ║ Statut   ║ Score    ║ Anomalie  ║ Localisation ║")
        print("╠══════════════╬═══════════╬══════════╬══════════╬═══════════╬══════════╣")

        emoji_map = {"green": "🟢", "orange": "🟠", "red": "🔴"}

        for _, row in self.alerts_df.iterrows():
            e        = emoji_map.get(row["couleur"], "⚪")
            secteur  = str(row["secteur"])[:12].ljust(12)
            ilp_str  = f"{row['ILP']:.3f}".ljust(9)
            stat_str = str(row["statut"])[:8].ljust(8)
            score_str= f"{row['score_fuite']:.0f}/100".ljust(8)
            anom_str = ("OUI ⚠" if row["anomalie_statistique"] else "Non  ").ljust(9)
            loc_str  = str(row["localisation_probable"])[:8].ljust(8)
            print(f"║ {e} {secteur} ║ {ilp_str} ║ {stat_str} ║ {score_str} ║ {anom_str} ║ {loc_str} ║")

        print("╚══════════════╩═══════════╩══════════╩══════════╩═══════════╩══════════╝\n")

    # ══════════════════════════════════════════════════════════════════════════
    # 2. GRAPHIQUE RISK CHART
    # ══════════════════════════════════════════════════════════════════════════
    def render_risk_chart(self) -> str:
        """
        Graphique à deux panneaux :
          - Panneau gauche  : barres ILP avec zones seuils
          - Panneau droit   : jauge du score de fuite par secteur
        """
        fig, (ax_ilp, ax_score) = plt.subplots(
            1, 2, figsize=(14, 6),
            facecolor=DOOM_PALETTE["bg"],
        )
        fig.suptitle(
            "DOOM — Tableau de Bord de Risque",
            color=DOOM_PALETTE["text"], fontsize=15, fontweight="bold", y=1.02,
        )

        secteurs = self.alerts_df["secteur"].tolist()
        ilps     = self.alerts_df["ILP"].tolist()
        scores   = self.alerts_df["score_fuite"].tolist()
        couleurs = [DOOM_PALETTE[c] for c in self.alerts_df["couleur"].tolist()]

        x = np.arange(len(secteurs))
        bar_w = 0.55

        # ── Panneau ILP ──────────────────────────────────────────────────────
        ax_ilp.set_facecolor(DOOM_PALETTE["bg_panel"])
        ax_ilp.set_title("Indice Linéaire de Perte [m³/km/j]",
                         color=DOOM_PALETTE["text"], fontsize=11, pad=10)

        # Zones seuils (fond)
        max_ylim = max(max(ilps) * 1.3, 7.0)
        ax_ilp.axhspan(0,   2.5, alpha=0.06, color=DOOM_PALETTE["green"])
        ax_ilp.axhspan(2.5, 5.0, alpha=0.06, color=DOOM_PALETTE["orange"])
        ax_ilp.axhspan(5.0, max_ylim, alpha=0.06, color=DOOM_PALETTE["red"])

        # Lignes de seuil
        for yval, color, label in [
            (2.5, DOOM_PALETTE["orange"], "Seuil Orange (2.5)"),
            (5.0, DOOM_PALETTE["red"],    "Seuil Rouge (5.0)"),
        ]:
            ax_ilp.axhline(yval, color=color, lw=1.2, ls="--", alpha=0.7)
            ax_ilp.text(len(secteurs) - 0.1, yval + 0.08, label,
                        color=color, fontsize=7.5, ha="right")

        bars = ax_ilp.bar(x, ilps, color=couleurs, width=bar_w,
                          edgecolor=DOOM_PALETTE["bg"], linewidth=0.8, zorder=3)

        # Valeurs sur les barres
        for bar, val in zip(bars, ilps):
            ax_ilp.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.08,
                f"{val:.2f}", color=DOOM_PALETTE["text"],
                ha="center", va="bottom", fontsize=9.5, fontweight="bold",
            )

        ax_ilp.set_xticks(x)
        ax_ilp.set_xticklabels(
            [s.replace("_", "\n") for s in secteurs],
            color=DOOM_PALETTE["text"], fontsize=9,
        )
        ax_ilp.set_ylim(0, max_ylim)
        ax_ilp.tick_params(colors=DOOM_PALETTE["text_muted"], axis="y")
        ax_ilp.grid(axis="y", color=DOOM_PALETTE["grid"], linewidth=0.5)
        for spine in ax_ilp.spines.values():
            spine.set_edgecolor(DOOM_PALETTE["grid"])

        # ── Panneau Score ────────────────────────────────────────────────────
        ax_score.set_facecolor(DOOM_PALETTE["bg_panel"])
        ax_score.set_title("Score de Fuite DOOM [0 – 100]",
                           color=DOOM_PALETTE["text"], fontsize=11, pad=10)

        score_bars = ax_score.barh(
            secteurs, scores,
            color=couleurs, height=0.5,
            edgecolor=DOOM_PALETTE["bg"], linewidth=0.8,
        )

        # Fond de référence 100
        ax_score.barh(
            secteurs, [100] * len(secteurs),
            color=DOOM_PALETTE["bg"], height=0.5, zorder=0, alpha=0.5,
        )

        for bar, score in zip(score_bars, scores):
            ax_score.text(
                score + 1.5, bar.get_y() + bar.get_height() / 2,
                f"{score:.0f}", color=DOOM_PALETTE["text"],
                va="center", fontsize=9.5, fontweight="bold",
            )

        ax_score.set_xlim(0, 110)
        ax_score.set_xlabel("Score", color=DOOM_PALETTE["text_muted"], fontsize=9)
        ax_score.tick_params(colors=DOOM_PALETTE["text_muted"])
        ax_score.grid(axis="x", color=DOOM_PALETTE["grid"], linewidth=0.5)
        for spine in ax_score.spines.values():
            spine.set_edgecolor(DOOM_PALETTE["grid"])
        ax_score.tick_params(axis="y", colors=DOOM_PALETTE["text"])

        # Légende commune
        legend_patches = [
            mpatches.Patch(color=DOOM_PALETTE["green"],  label="Normal (ILP < 2.5)"),
            mpatches.Patch(color=DOOM_PALETTE["orange"], label="Suspect (2.5–5.0)"),
            mpatches.Patch(color=DOOM_PALETTE["red"],    label="Fuite probable (> 5.0)"),
        ]
        fig.legend(
            handles=legend_patches, loc="lower center",
            ncol=3, framealpha=0.15,
            labelcolor=DOOM_PALETTE["text"], fontsize=9,
            facecolor=DOOM_PALETTE["bg_panel"],
        )

        plt.tight_layout(rect=[0, 0.06, 1, 1])
        out_path = os.path.join(self.output_dir, "risk_chart.png")
        fig.savefig(out_path, dpi=150, bbox_inches="tight",
                    facecolor=DOOM_PALETTE["bg"])
        plt.close(fig)
        logger.info(f"Graphique sauvegardé → {out_path}")
        return out_path

    # ══════════════════════════════════════════════════════════════════════════
    # 3. CARTE / SCHÉMA DU RÉSEAU
    # ══════════════════════════════════════════════════════════════════════════
    def render_network_map(self) -> str:
        """
        Génère une carte schématique du réseau :
          - Canalisations colorées selon leur secteur + statut (épaisseur ∝ risque)
          - Nœuds avec label
          - Légende secteurs + statut
        """
        # Mapping pipe → couleur de statut du secteur
        pipe_alert_color: dict[str, str] = {}
        for _, row in self.alerts_df.iterrows():
            s = str(row["secteur"])
            c = DOOM_PALETTE[row["couleur"]]
            for p in self.sectors_pipes.get(s, []):
                pipe_alert_color[p] = c

        fig, ax = plt.subplots(figsize=(12, 9), facecolor=DOOM_PALETTE["bg"])
        ax.set_facecolor(DOOM_PALETTE["bg"])
        ax.set_title("DOOM — Schéma du Réseau Hydraulique",
                     color=DOOM_PALETTE["text"], fontsize=13, fontweight="bold", pad=12)

        # ── Canalisations ────────────────────────────────────────────────────
        for pipe_id, (n1, n2) in PIPE_CONNECTIONS.items():
            x1, y1 = NODE_COORDS.get(n1, (0, 0))
            x2, y2 = NODE_COORDS.get(n2, (0, 0))
            color  = pipe_alert_color.get(pipe_id, DOOM_PALETTE["text_muted"])
            # Épaisseur selon la couleur de risque
            lw_map = {
                DOOM_PALETTE["red"]:    4.5,
                DOOM_PALETTE["orange"]: 3.0,
                DOOM_PALETTE["green"]:  2.0,
            }
            lw = lw_map.get(color, 1.5)

            ax.plot([x1, x2], [y1, y2], color=color, lw=lw, alpha=0.9,
                    solid_capstyle="round", zorder=2)

            # Label ID canalisation (milieu du tronçon)
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            ax.text(mx, my, pipe_id, fontsize=6.5,
                    color=DOOM_PALETTE["text_muted"], ha="center", va="center",
                    bbox=dict(boxstyle="round,pad=0.15", fc=DOOM_PALETTE["bg"],
                              ec="none", alpha=0.7),
                    zorder=4)

        # ── Nœuds ────────────────────────────────────────────────────────────
        for node_id, (nx, ny) in NODE_COORDS.items():
            is_source = node_id in ("R1", "T1")
            marker  = "*" if is_source else "o"
            msize   = 14 if is_source else 9
            mcolor  = DOOM_PALETTE["accent"] if is_source else "#ADBAC7"

            ax.plot(nx, ny, marker=marker, markersize=msize,
                    color=mcolor, zorder=5,
                    markeredgecolor=DOOM_PALETTE["bg"], markeredgewidth=0.8)
            ax.text(nx + 1.5, ny + 1.5, node_id, fontsize=7.5,
                    color=DOOM_PALETTE["text"], zorder=6,
                    path_effects=[pe.withStroke(linewidth=2, foreground=DOOM_PALETTE["bg"])])

        # ── Zones secteurs (fond transparent) ────────────────────────────────
        sector_nodes = {
            "S1_Centre": ["J1", "J2", "J5", "T1", "R1"],
            "S2_Nord":   ["J3", "J4", "J11", "J12"],
            "S3_Est":    ["J8", "J9", "J10"],
            "S4_Ouest":  ["J6", "J7"],
        }
        for s, nodes in sector_nodes.items():
            coords = [NODE_COORDS[n] for n in nodes if n in NODE_COORDS]
            if len(coords) < 3:
                continue
            xs = [c[0] for c in coords]
            ys = [c[1] for c in coords]
            # Bounding box légèrement élargie
            x_min, x_max = min(xs) - 5, max(xs) + 5
            y_min, y_max = min(ys) - 5, max(ys) + 5
            row = self.alerts_df[self.alerts_df["secteur"] == s]
            c   = DOOM_PALETTE[row["couleur"].values[0]] if len(row) else "#888"
            rect = mpatches.FancyBboxPatch(
                (x_min, y_min), x_max - x_min, y_max - y_min,
                boxstyle="round,pad=1", linewidth=1.2,
                edgecolor=c, facecolor=c, alpha=0.08, zorder=1,
            )
            ax.add_patch(rect)
            ax.text(
                (x_min + x_max) / 2, y_max + 0.8, s.replace("_", "\n"),
                fontsize=7.5, color=c, ha="center", va="bottom",
                fontweight="bold", alpha=0.9, zorder=7,
            )

        # ── Légende ──────────────────────────────────────────────────────────
        legend_items = [
            mpatches.Patch(color=DOOM_PALETTE["green"],  label="Normal"),
            mpatches.Patch(color=DOOM_PALETTE["orange"], label="Suspect"),
            mpatches.Patch(color=DOOM_PALETTE["red"],    label="Fuite probable"),
            mpatches.Patch(color=DOOM_PALETTE["accent"], label="Source / Réservoir"),
        ]
        ax.legend(
            handles=legend_items, loc="lower left",
            framealpha=0.25, labelcolor=DOOM_PALETTE["text"],
            facecolor=DOOM_PALETTE["bg_panel"], fontsize=8.5,
            edgecolor=DOOM_PALETTE["grid"],
        )

        ax.set_xlim(-8, 95)
        ax.set_ylim(8, 82)
        ax.axis("off")

        plt.tight_layout()
        out_path = os.path.join(self.output_dir, "network_map.png")
        fig.savefig(out_path, dpi=150, bbox_inches="tight",
                    facecolor=DOOM_PALETTE["bg"])
        plt.close(fig)
        logger.info(f"Carte réseau sauvegardée → {out_path}")
        return out_path

    # ══════════════════════════════════════════════════════════════════════════
    # 4. RÉSUMÉ TEXTE
    # ══════════════════════════════════════════════════════════════════════════
    def write_summary(self) -> str:
        """Génère summary.txt dans le dossier output."""
        lines = [
            "DOOM — Rapport de Synthèse",
            "=" * 50,
            f"Date d'analyse : {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "RÉSULTATS PAR SECTEUR",
            "-" * 50,
        ]

        emoji_map = {"green": "[OK]", "orange": "[!!]", "red": "[ALERTE]"}

        for _, row in self.alerts_df.iterrows():
            e = emoji_map.get(row["couleur"], "[?]")
            lines.append(
                f"  {e} {row['secteur']:<20} "
                f"ILP={row['ILP']:.3f}  Score={row['score_fuite']:.0f}/100"
            )
            lines.append(f"      Statut : {row['statut']}")
            if row["anomalie_statistique"]:
                lines.append(f"      ⚠ Anomalie statistique (Z={row['zscore']:.2f})")
            if row["localisation_probable"] != "—":
                lines.append(f"      → Localisation probable : {row['localisation_probable']}")
            lines.append(f"      Message : {row['message']}")
            lines.append("")

        lines.append("=" * 50)

        # ILP moyen
        mean_ilp = self.alerts_df["ILP"].mean()
        n_red    = (self.alerts_df["couleur"] == "red").sum()
        n_orange = (self.alerts_df["couleur"] == "orange").sum()

        lines += [
            f"ILP moyen réseau : {mean_ilp:.3f} m³/km/jour",
            f"Secteurs en alerte rouge  : {n_red}",
            f"Secteurs en alerte orange : {n_orange}",
            "",
            "Fichiers générés :",
            "  - output/risk_chart.png",
            "  - output/network_map.png",
            "  - output/summary.txt",
            "  - data/alerts.csv",
            "  - data/simulation_results.csv",
        ]

        out_path = os.path.join(self.output_dir, "summary.txt")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        logger.info(f"Résumé sauvegardé → {out_path}")
        return out_path