import pandas as pd
import os
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.db_models import Base, AGEBDemographics
from geoalchemy2.elements import WKTElement
from dotenv import load_dotenv

load_dotenv()

# Configuración de la base de datos (conectar al contenedor db)
DB_USER = os.getenv("POSTGRES_USER", "admin")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "admin_password_safe")
DB_NAME = os.getenv("POSTGRES_DB", "geoanalisis")
DB_HOST = os.getenv("DB_HOST", "localhost")  # Localhost para correr desde afuera si hay tunel, o IP
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:5432/{DB_NAME}"

def clean_value(val):
    if val in ['*', 'N/D', '']:
        return 0
    try:
        return float(val)
    except:
        return 0

def migrate():
    print("🚀 Iniciando migración de datos a PostGIS...")
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    file_path = "RESAGEBURB_09XLSX20.xlsx"
    if not os.path.exists(file_path):
        print(f"❌ Error: No se encuentra el archivo {file_path}")
        return

    # Leer Excel (solo las columnas necesarias para ahorrar memoria)
    cols = ['ENTIDAD', 'MUN', 'LOC', 'AGEB', 'MZA', 'POBTOT', 'PEA', 'GRAPROES', 'VPH_INTER', 'VPH_AUTOM', 'VPH_PC']
    df = pd.read_excel(file_path, usecols=cols)

    # Filtrar solo registros de AGEB (INEGI pone el total del AGEB cuando MZA es '000')
    df_ageb = df[df['MZA'] == '000'].copy()

    records = []
    for _, row in df_ageb.iterrows():
        # Crear ID único
        ent = str(row['ENTIDAD']).zfill(2)
        mun = str(row['MUN']).zfill(3)
        loc = str(row['LOC']).zfill(4)
        ageb = str(row['AGEB'])
        full_id = f"{ent}{mun}{loc}{ageb}"

        # Limpiar valores
        pobtot = int(clean_value(row['POBTOT']))
        pea = int(clean_value(row['PEA']))
        
        # Simular una ubicación (Para el MVP, usaremos el centro de CDMX 19.4326, -99.1332 con un pequeño offset)
        # TODO: Integrar shapes reales de INEGI para centroides exactos
        lat = 19.4326 + (int(mun) * 0.01) 
        lng = -99.1332 + (int(ageb[:3], 16) / 10000.0 if any(c.isdigit() for c in ageb) else 0)
        point = WKTElement(f'POINT({lng} {lat})', srid=4326)

        ageb_record = AGEBDemographics(
            id=full_id,
            entidad=ent,
            municipio=mun,
            localidad=loc,
            ageb_id=ageb,
            total_population=pobtot,
            economically_active_population=pea,
            socioeconomic_level="Medio",  # Placeholder
            indicators={
                "avg_schooling": clean_value(row['GRAPROES']),
                "pct_internet": clean_value(row['VPH_INTER']),
                "pct_car": clean_value(row['VPH_AUTOM']),
                "pct_pc": clean_value(row['VPH_PC'])
            },
            location=point
        )
        records.append(ageb_record)

    # Insertar en lotes
    session.bulk_save_objects(records)
    session.commit()
    print(f"✅ Migración completada: {len(records)} AGEBs insertados en PostGIS.")

if __name__ == "__main__":
    migrate()
