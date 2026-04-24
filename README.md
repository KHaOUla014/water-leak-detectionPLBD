# Learning-By-Doing – Orby & Doom

Projet de détection intelligente des fuites d’eau dans un réseau de distribution, avec un robot sphérique **Orby** et une intelligence artificielle **Doom** pour l’analyse prédictive des pertes.

Ce projet s’inscrit dans la thématique de la robotique et de l’intelligence artificielle au service des enjeux africains, plus particulièrement la gestion durable de l’eau potable.

---

## Objectif du projet

L’objectif est de proposer une **solution technologique innovante et adaptée aux réalités africaines** pour réduire les pertes d’eau dans les réseaux de distribution, en combinant :

- Un **robot sphérique Orby** capable de se déplacer à l’intérieur des canalisations et d’identifier précisément les zones de fuite.
- Une **intelligence artificielle Doom** chargée de fournir une analyse prédictive sur le risque de fuite, à partir de données de débit et de pression.

---

## Architecture globale

Le système se compose de trois grands blocs :

1. **EPANET**  
   - Modélisation d’un réseau de distribution d’eau sous forme de .net / .inp.  
   - Simulation hydraulique (débit, pression, temps).  
   - Repérage des pertes sur un tronçon entre la station de distribution et l’entrée de la ville.

2. **Python – Doom**  
   - Lecture des résultats de simulation EPANET.  
   - Calcul de la différence entre débit amont et aval.  
   - Classement du risque de fuite (vert / orange / rouge).  
   - Sortie au format tableaux et graphiques.

3. **Orby (prototype physique)**  
   - Robot sphérique de détection de fuites, capable de circuler dans une canalisation.  
   - Capteurs acoustiques, IMU, éventuellement capteur de pression.  
   - Microcontrôleur (ESP32) pour l’acquisition, le stockage ou la transmission des données.

---

## Installation du projet (environnement Doom)

### Prérequis

- Python 3.8 ou supérieur
- EPANET (Desktop ou Toolkit via Python)
- Un package Python pour interagir avec EPANET (par exemple `EPyT` ou équivalent)

### Étapes rapides

1. Cloner le dépôt :
   ```bash
   git clone https://github.com/ton_pseudo/Orby-Doom.git
   cd Orby-Doom
   ```

2. Créer un environnement virtuel :
   ```bash
   python -m venv venv
   source venv/bin/activate   # Linux/Mac
   venv\Scripts\activate       # Windows
   ```

3. Installer les dépendances :
   ```bash
   pip install -r requirements.txt
   ```

4. Lancer le script de simulation + analyse :
   ```bash
   python main.py
   ```

---

## Structure du dépôt

```text
Orby-Doom/
├── network/
│   └── orby_doom_v1.net        # Réseau EPANET simplifié (transfert amont → entrée de ville)
├── src/
│   ├── epanet_reader.py        # Lecture des résultats EPANET
│   ├── doom_engine.py          # Analyse de risque de fuite
│   ├── ui_dashboard.py         # Interface simple d'affichage des résultats
│   └── main.py                 # Point d'entrée principal
├── data/
│   ├── simulation_results.csv  # Débits amont/aval, pertes, etc.
│   └── alerts.csv              # Alerte de type "vert / orange / rouge"
├── output/
│   └── risk_chart.png          # Graphique de suivi du risque
└── README.md                   # Ce fichier
```

---

## Comment Doom fonctionne ?

1. **Lecture EPANET**  
   - Récupération du débit amont (début de la conduite).
   - Récupération du débit aval (entrée de la ville).

2. **Calcul de la perte**
   - \( Q_{perte} = Q_{amont} - Q_{aval} \)
   - \( \text{taux\_perte} = \frac{Q_{perte}}{Q_{amont}} \times 100 \) (si \( Q_{amont} > 0 \)).

3. **Classement du risque**

   | Taux de perte       | État  | Score de risque (0–100) |
   |---------------------|-------|-------------------------|
   | < 5 %               | Vert  | 0–39                    |
   | 5 % ≤ taux < 10 %   | Orange| 40–69                   |
   | ≥ 10 %              | Rouge | 70–100                  |

4. **Sortie**  
   - Affichage de l’heure, des débits, du taux de perte, de l’état et du score.  
   - Enregistrement dans `alerts.csv` pour suivi historique.

---

## Contribution

Les contributions sont les bienvenues, notamment sur :
- L’amélioration du moteur de décision Doom (seuils, statistiques, détection d’anomalies).
- L’intégration de capteurs réels et de données expérimentales (Orby).
- La création d’une interface Web plus avancée.

---

## Licence

Ce projet est fourni à titre d’exemple académique et de démonstration de concept.  
Veillez à respecter les licences de EPANET, de ses wrappers Python et de toute dépendance utilisée.

---

## Auteurs

- [Nom de l’équipe ou de chaque membre]  
- Projet de [Année] – [Nom de l’établissement], Learning-By-Doing.
