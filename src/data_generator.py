import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def generate_synthetic_data(num_sectors=5, days=30):
    data = []
    start_date = datetime.now() - timedelta(days=days)
    
    for day in range(days):
        current_date = start_date + timedelta(days=day)
        for sector in range(1, num_sectors + 1):
            length_km = np.random.uniform(5.0, 15.0) # Longueur du réseau entre 5 et 15 km
            
            # Consommation normale (base)
            base_consumption = np.random.uniform(500, 1000)
            
            # Injection normale (légère perte inhérente de 5% max)
            injected = base_consumption * np.random.uniform(1.01, 1.05)
            
            # Simulation d'une fuite (anomalie) pour les 3 derniers jours sur le secteur 2
            if day > days - 4 and sector == 2:
                injected *= np.random.uniform(1.2, 1.4) # Hausse anormale de l'injection
                
            data.append({
                "date": current_date.strftime("%Y-%m-%d"),
                "secteur_id": f"Secteur_{sector}",
                "longueur_km": round(length_km, 2),
                "volume_injecte": round(injected, 2),
                "volume_consomme": round(base_consumption, 2)
            })
            
    return pd.DataFrame(data)

if __name__ == "__main__":
    df = generate_synthetic_data()
    # On sauvegarde dans le dossier data/ au lieu de la racine
    df.to_csv("data/historical_data.csv", index=False) 
    print("Données synthétiques générées avec succès dans 'data/historical_data.csv' !")