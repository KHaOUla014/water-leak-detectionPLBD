from data_generator import generate_synthetic_data
from doom_engine import DoomAI

if __name__ == "__main__":
    print("📊 Génération des données synthétiques...")
    generate_synthetic_data(n_sectors=20, n_days=365)
    
    print("\n🧠 Entraînement de Doom...")
    doom = DoomAI()
    doom.train(csv_path="../data/synthetic_data.csv")
    
    print("\n✨ Doom est prêt !")
