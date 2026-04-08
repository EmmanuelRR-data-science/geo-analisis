"""Pre-procesa el archivo AGEB de INEGI y genera un CSV ligero con indicadores clave.

Ejecutar una sola vez:
    python preprocess_ageb.py

Genera: ageb_data.csv
"""

import sys
import time

print("Preprocesando archivo AGEB (version extendida)...")
print("  (Esto puede tomar varios minutos para un archivo de 70 MB)")
start = time.time()

INPUT_FILE = "RESAGEBURB_09XLSX20.xlsx"
OUTPUT_FILE = "ageb_data.csv"

# Columns by index — extended set for richer analysis
NEEDED_COLS = {
    0: "ENTIDAD",
    2: "MUN",
    4: "LOC",
    6: "AGEB",
    7: "MZA",
    8: "POBTOT",         # Poblacion total
    9: "POBFEM",         # Poblacion femenina
    10: "POBMAS",        # Poblacion masculina
    20: "P_12YMAS",      # Poblacion 12 y mas
    23: "P_15YMAS",      # Poblacion 15 y mas
    26: "P_18YMAS",      # Poblacion 18 y mas
    48: "P_60YMAS",      # Poblacion 60 y mas
    52: "POB0_14",       # Poblacion 0-14
    53: "POB15_64",      # Poblacion 15-64
    54: "POB65_MAS",     # Poblacion 65 y mas
    139: "GRAPROES",     # Grado promedio de escolaridad
    142: "PEA",          # Poblacion economicamente activa
    145: "PE_INAC",      # Poblacion economicamente inactiva
    148: "POCUPADA",     # Poblacion ocupada
    151: "PDESOCUP",     # Poblacion desocupada
    154: "PSINDER",      # Poblacion sin derechohabiencia
    155: "PDER_SS",      # Poblacion derechohabiente servicios salud
    171: "TOTHOG",       # Total de hogares
    174: "POBHOG",       # Poblacion en hogares
    177: "VIVTOT",       # Total de viviendas
    180: "VIVPAR_HAB",   # Viviendas particulares habitadas
    185: "OCUPVIVPAR",   # Ocupantes en viviendas particulares
    186: "PROM_OCUP",    # Promedio de ocupantes por vivienda
    195: "VPH_C_ELEC",   # Viviendas con electricidad
    197: "VPH_AGUADV",   # Viviendas con agua entubada
    204: "VPH_DRENAJ",   # Viviendas con drenaje
    211: "VPH_REFRI",    # Viviendas con refrigerador
    212: "VPH_LAVAD",    # Viviendas con lavadora
    214: "VPH_AUTOM",    # Viviendas con automovil
    219: "VPH_PC",       # Viviendas con computadora
    221: "VPH_CEL",      # Viviendas con celular
    222: "VPH_INTER",    # Viviendas con internet
}

try:
    import pandas as pd
    print(f"  Leyendo {INPUT_FILE} con pandas (columnas extendidas)...")
    df = pd.read_excel(
        INPUT_FILE,
        usecols=list(NEEDED_COLS.keys()),
        dtype={0: str, 2: str, 4: str, 6: str, 7: str},
        engine="openpyxl",
    )
    df.columns = [NEEDED_COLS[i] for i in NEEDED_COLS.keys()]

    for col in ["ENTIDAD", "MUN", "LOC", "AGEB", "MZA"]:
        df[col] = df[col].astype(str).str.strip()

    df = df[
        (df["MZA"] == "000")
        & (df["LOC"] != "0000")
        & (df["AGEB"] != "0000")
    ]

    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8")

    elapsed = time.time() - start
    import os
    size_mb = os.path.getsize(OUTPUT_FILE) / 1024 / 1024
    print(f"  Generado {OUTPUT_FILE} ({size_mb:.1f} MB, {len(df)} registros, {len(NEEDED_COLS)} columnas)")
    print(f"  Tiempo: {elapsed:.1f}s")

except Exception as e:
    print(f"  Error: {e}")
    sys.exit(1)
