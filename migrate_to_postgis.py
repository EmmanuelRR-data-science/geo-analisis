import pandas as pd
import os
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.db_models import Base, AGEBDemographics
from geoalchemy2.elements import WKTElement

# Configuración HARDCODED para asegurar conexión en Docker
DB_USER = "admin"
DB_PASS = "admin_password_safe"
DB_NAME = "geoanalisis"
DB_HOST = "geo-db" # Nombre del servicio en docker-compose

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:5432/{DB_NAME}"

def clean_value(val):
    if val in ['*', 'N/D', '']:
        return 0
    try:
        return float(val)
    except:
        return 0

def migrate():
    print(f"🚀 FORZANDO conexión a: {DB_HOST}")
    
    try:
        engine = create_engine(DATABASE_URL)
        Base.metadata.create_all(engine)
        print("✅ Conexión exitosa y tablas creadas.")
    except Exception as e:
        print(f"❌ Error crítico de conexión: {e}")
        return

    Session = sessionmaker(bind=engine)
    session = Session()

    file_path = "RESAGEBURB_09XLSX20.xlsx"
    if not os.path.exists(file_path):
        print(f"❌ Error: No se encuentra {file_path}")
        return

    print(f"📖 Leyendo {file_path}...")
    cols = ['ENTIDAD', 'MUN', 'LOC', 'AGEB', 'MZA', 'POBTOT', 'PEA', 'GRAPROES', 'VPH_INTER', 'VPH_AUTOM', 'VPH_PC']
    df = pd.read_excel(file_path, usecols=cols)
    
    # Limpieza de la columna MZA para asegurar que el filtro '000' funcione
    df['MZA'] = df['MZA'].astype(str).str.strip().str.zfill(3)
    df_ageb = df[df['MZA'] == '000'].copy()
    
    print(f"📊 Registros de AGEB encontrados para migrar: {len(df_ageb)}")

    records = []
    for _, row in df_ageb.iterrows():
        ent = str(row['ENTIDAD']).zfill(2)
        mun = str(row['MUN']).zfill(3)
        loc = str(row['LOC']).zfill(4)
        ageb = str(row['AGEB'])
        full_id = f"{ent}{mun}{loc}{ageb}"

        pobtot = int(clean_value(row['POBTOT']))
        pea = int(clean_value(row['PEA']))
        
        lat = 19.4326 + (int(mun) * 0.001) 
        lng = -99.1332 + (int(ageb[:3], 16) / 100000.0 if any(c.isdigit() for c in ageb) else 0)
        point = WKTElement(f'POINT({lng} {lat})', srid=4326)

        ageb_record = AGEBDemographics(
            id=full_id,
            entidad=ent,
            municipio=mun,
            localidad=loc,
            ageb_id=ageb,
            total_population=pobtot,
            economically_active_population=pea,
            socioeconomic_level="Medio",
            indicators={
                "avg_schooling": clean_value(row['GRAPROES']),
                "pct_internet": clean_value(row['VPH_INTER']),
                "pct_car": clean_value(row['VPH_AUTOM']),
                "pct_pc": clean_value(row['VPH_PC'])
            },
            location=point
        )
        records.append(ageb_record)

    session.bulk_save_objects(records)
    session.commit()
    print(f"✅ Migración exitosa: {len(records)} registros en PostGIS.")

if __name__ == "__main__":
    migrate()
