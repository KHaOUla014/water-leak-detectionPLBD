from flask import Flask, render_template, jsonify
from doom_engine import DoomAI
import pandas as pd

app = Flask(__name__)

# Initialisation et entraînement de Doom au démarrage
# ... code précédent ...
doom = DoomAI()
try:
    # On va chercher les données dans le dossier data/
    doom.train("data/historical_data.csv")
except FileNotFoundError:
    print("Veuillez d'abord exécuter src/data_generator.py")
# ... suite du code ...

@app.route('/')
def dashboard():
    return render_template('index.html')

@app.route('/api/diagnostic')
def get_diagnostic():
    # Simulation de la réception de données en temps réel pour aujourd'hui
    # Dans la réalité, ces données viendraient des capteurs/compteurs
    live_data = pd.DataFrame([
        {"secteur_id": "Secteur_1", "longueur_km": 10.5, "volume_injecte": 820, "volume_consomme": 800},
        {"secteur_id": "Secteur_2", "longueur_km": 8.2, "volume_injecte": 1200, "volume_consomme": 750}, # Fuite massive ici
        {"secteur_id": "Secteur_3", "longueur_km": 12.0, "volume_injecte": 650, "volume_consomme": 620},
        {"secteur_id": "Secteur_4", "longueur_km": 6.5, "volume_injecte": 480, "volume_consomme": 450},
        {"secteur_id": "Secteur_5", "longueur_km": 14.1, "volume_injecte": 950, "volume_consomme": 900}
    ])
    
    diagnostic = doom.predict(live_data)
    return jsonify(diagnostic)

if __name__ == '__main__':
    app.run(debug=True)