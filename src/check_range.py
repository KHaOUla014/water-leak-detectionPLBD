import pandas as pd
from pathlib import Path

df = pd.read_csv(Path("..") / "data" / "processed" / "temporal.csv")
print(df[['pressure_bar', 'flow_rate_ls', 'temperature_c']].describe())

# Bonus : voir les plages selon le label fuite
if 'is_leak' in df.columns:
    LABEL = "int64"   # ← remplace
    print(df.groupby(LABEL)[['pressure_bar','flow_rate_ls','temperature_c']].mean())
    print("\nRépartition :\n", df[LABEL].value_counts())

    print("\n=== Moyennes par classe ===")
    print(df.groupby('is_leak')[['pressure_bar', 'flow_rate_ls', 'temperature_c']].mean())

import pandas as pd
from pathlib import Path

df = pd.read_csv(Path("..") / "data" / "processed" / "temporal.csv")

print("=== Répartition leak_label ===")
print(df['leak_label'].value_counts())

print("\n=== Moyennes par classe ===")
print(df.groupby('leak_label')[['pressure_bar','flow_rate_ls','temperature_c']].mean())

print("\n=== Profil des FUITES (leak_label=1) ===")
print(df[df['leak_label']==1][['pressure_bar','flow_rate_ls','temperature_c']].describe())

