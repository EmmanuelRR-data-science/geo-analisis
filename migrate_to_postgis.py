import pandas as pd
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.db_models import Base, AGEBDemographics
from geoalchemy2.elements import WKTElement

# Configuración HARDCODED para Docker
DB_USER = "admin"
DB_PASS = "admin_password_safe"
DB_NAME = "geoanalisis"
DB_HOST = "geo-db"

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:5432/{DB_NAME}"

def clean_value(val):
    if val in ['*', 'N/D', '', None]:
        return 0
    try:
        return float(val)
    except:
        return 0

def migrate():
    print(f"🚀 Iniciando migración a {DB_HOST}...")
    engine = create_engine(DATABASE_URL)
    Base.metadata.drop_all(engine) # Limpiar para asegurar datos frescos
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    file_path = "RESAGEBURB_09XLSX20.xlsx"
    print(f"📖 Cargando {file_path}...")
    
    # Leer columnas necesarias
    cols = ['ENTIDAD', 'MUN', 'LOC', 'AGEB', 'MZA', 'POBTOT', 'PEA', 'GRAPROES', 
            'VPH_INTER', 'VPH_AUTOM', 'VPH_PC', 'POBFEM', 'POBMAS', 'POB0_14', 
            'POB15_64', 'POB65_MAS', 'POCUPADA', 'PDESOCUP', 'PE_INAC', 
            'TOTHOG', 'VIVTOT', 'VIVPAR_HAB', 'PDER_SS', 'PSINDER']
    
    df = pd.read_excel(file_path, usecols=cols)

    # FILTRO CRÍTICO: MZA == 0 (Total de AGEB), pero excluyendo totales de MUN/LOC
    # En INEGI, los totales de AGEB tienen MZA=0 y AGEB != '0000' (o 0)
    df_ageb = df[
        (df['MZA'].astype(int) == 0) & 
        (df['AGEB'].astype(str) != '0000') & 
        (df['AGEB'].astype(str) != '0')
    ].copy()

    print(f"📊 Registros de AGEB detectados: {len(df_ageb)}")

    records = []
    for _, row in df_ageb.iterrows():
        ent = str(row['ENTIDAD']).zfill(2)
        mun = str(row['MUN']).zfill(3)
        loc = str(row['LOC']).zfill(4)
        ageb = str(row['AGEB']).zfill(4)
        full_id = f"{ent}{mun}{loc}{ageb}"

        # Geometría simulada (Centro de CDMX con offset por municipio/ageb)
        lat = 19.4326 + (int(mun) * 0.002) 
        lng = -99.1332 + (len(ageb) * 0.0001)
        point = WKTElement(f'POINT({lng} {lat})', srid=4326)

        ageb_record = AGEBDemographics(
            id=full_id,
            entidad=ent,
            municipio=mun,
            localidad=loc,
            ageb_id=ageb,
            total_population=int(clean_value(row['POBTOT'])),
            economically_active_population=int(clean_value(row['PEA'])),
            socioeconomic_level="Calculado",
            indicators={
                "avg_schooling": clean_value(row['GRAPROES']),
                "pct_internet": clean_value(row['VPH_INTER']),
                "pct_car": clean_value(row['VPH_AUTOM']),
                "pct_pc": clean_value(row['VPH_PC']),
                "pobfem": int(clean_value(row['POBFEM'])),
                "pobmas": int(clean_value(row['POBMAS'])),
                "pob0_14": int(clean_value(row['POB0_14'])),
                "pob15_64": int(clean_value(row['POB15_64'])),
                "pob65_mas": int(clean_value(row['POB65_MAS'])),
                "pocupada": int(clean_value(row['POCUPADA'])),
                "pdesocup": int(clean_value(row['PDESOCUP'])),
                "pe_inac": int(clean_value(row['PE_INAC'])),
                "tothog": int(clean_value(row['TOTHOG'])),
                "vivtot": int(clean_value(row['VIVTOT'])),
                "vivpar_hab": int(clean_value(row['VIVPAR_HAB'])),
                "pder_ss": int(clean_value(row['PDER_SS'])),
                "psinder": int(clean_value(row['PSINDER']))
            },
            location=point
        )
        records.append(ageb_record)

    session.bulk_save_objects(records)
    session.commit()
    print(f"✅ Migración COMPLETADA: {len(records)} AGEBs en PostGIS.")

if __name__ == "__main__":
    migrate()
