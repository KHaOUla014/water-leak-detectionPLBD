import pandas as pd
import numpy as np

class DoomAI:
    def __init__(self):
        self.baselines = {} # Stocke la moyenne et l'écart-type par secteur

    def train(self, historical_csv):
        """Entraîne Doom à comprendre la normalité de chaque secteur."""
        df = pd.read_csv(historical_csv)
        df['v_fuite'] = df['volume_injecte'] - df['volume_consomme']
        df['ilp'] = df['v_fuite'] / df['longueur_km']
        
        # Calcul de la moyenne et de l'écart-type de l'ILP par secteur
        for sector in df['secteur_id'].unique():
            sector_data = df[df['secteur_id'] == sector]['ilp']
            self.baselines[sector] = {
                'mean': sector_data.mean(),
                'std': sector_data.std()
            }
            
    def predict(self, current_data):
        """Fournit un diagnostic (Vert, Orange, Rouge) pour de nouvelles données."""
        results = []
        for index, row in current_data.iterrows():
            sector = row['secteur_id']
            v_fuite = row['volume_injecte'] - row['volume_consomme']
            ilp = v_fuite / row['longueur_km']
            
            if sector in self.baselines:
                mean = self.baselines[sector]['mean']
                std = self.baselines[sector]['std']
                
                # Z-score: à combien d'écarts-types sommes-nous de la moyenne ?
                z_score = (ilp - mean) / std if std > 0 else 0
                
                # Classification par seuils
                if z_score < 1.5:
                    status = "Normal"
                    color = "#2ecc71" # Vert
                elif 1.5 <= z_score < 2.5:
                    status = "Suspect"
                    color = "#f39c12" # Orange
                else:
                    status = "Fuite Probable"
                    color = "#e74c3c" # Rouge
            else:
                status = "Inconnu"
                color = "#95a5a6" # Gris
                
            results.append({
                "secteur": sector,
                "ilp_actuel": round(ilp, 2),
                "statut": status,
                "couleur": color
            })
        return results