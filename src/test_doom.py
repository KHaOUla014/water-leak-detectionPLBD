import pandas as pd
from pathlib import Path

df = pd.read_csv(Path("data/processed/temporal.csv"))
print("=== PRESSION par classe ===")
print(df.groupby('leak_label')['pressure_bar'].describe())
print("\n=== Distribution pression globale ===")
print(df['pressure_bar'].describe())
