"""Migration script: load ageb_data.csv into PostgreSQL."""

import sys
import pandas as pd
from sqlalchemy import text
from app.db import get_engine
from app.models.db_models import Base


# Columns that should be stored as Float
FLOAT_COLUMNS = {"graproes", "prom_ocup"}

# All demographic columns in the model
DEMOGRAPHIC_COLUMNS = [
    "pobtot", "pobfem", "pobmas", "p_12ymas", "p_15ymas", "p_18ymas",
    "p_60ymas", "pob0_14", "pob15_64", "pob65_mas", "graproes", "pea",
    "pe_inac", "pocupada", "pdesocup", "psinder", "pder_ss", "tothog",
    "pobhog", "vivtot", "vivpar_hab", "ocupvivpar", "prom_ocup",
    "vph_c_elec", "vph_aguadv", "vph_drenaj", "vph_refri", "vph_lavad",
    "vph_autom", "vph_pc", "vph_cel", "vph_inter",
]


def clean_value(val, as_float=False):
    """Clean non-numeric values from CSV data."""
    if val is None or str(val).strip() in ("*", "N/D", ""):
        return None if as_float else 0
    try:
        return float(val) if as_float else int(float(val))
    except (ValueError, TypeError):
        return None if as_float else 0


def build_ageb_id(entidad, mun, loc, ageb):
    """Generate padded AGEB composite key."""
    return (
        str(entidad).zfill(2)
        + str(mun).zfill(3)
        + str(loc).zfill(4)
        + str(ageb).zfill(4)
    )


def migrate():
    csv_path = "ageb_data.csv"
    print(f"📖 Loading {csv_path}...")

    try:
        df = pd.read_csv(csv_path, dtype=str)
    except FileNotFoundError:
        print(f"❌ File not found: {csv_path}")
        sys.exit(1)

    print(f"📊 Total rows in CSV: {len(df)}")

    try:
        engine = get_engine()
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        sys.exit(1)

    # Create tables (without drop)
    Base.metadata.create_all(engine)

    # Build upsert SQL
    col_names = ["id", "entidad", "municipio", "localidad", "ageb_id", "mza"] + DEMOGRAPHIC_COLUMNS
    placeholders = ", ".join(f":{c}" for c in col_names)
    update_set = ", ".join(f"{c} = EXCLUDED.{c}" for c in col_names if c != "id")

    upsert_sql = text(
        f"INSERT INTO ageb_demographics ({', '.join(col_names)}) "
        f"VALUES ({placeholders}) "
        f"ON CONFLICT (id) DO UPDATE SET {update_set}"
    )

    count = 0
    with engine.begin() as conn:
        for _, row in df.iterrows():
            ent = str(row.get("ENTIDAD", "")).strip()
            mun = str(row.get("MUN", "")).strip()
            loc = str(row.get("LOC", "")).strip()
            ageb = str(row.get("AGEB", "")).strip()
            mza = str(row.get("MZA", "")).strip().zfill(3) if row.get("MZA") else "000"

            ageb_id_val = build_ageb_id(ent, mun, loc, ageb)

            params = {
                "id": ageb_id_val,
                "entidad": ent.zfill(2),
                "municipio": mun.zfill(3),
                "localidad": loc.zfill(4),
                "ageb_id": ageb.zfill(4),
                "mza": mza,
            }

            for col in DEMOGRAPHIC_COLUMNS:
                csv_col = col.upper()
                raw = row.get(csv_col, None)
                is_float = col in FLOAT_COLUMNS
                params[col] = clean_value(raw, as_float=is_float)

            conn.execute(upsert_sql, params)
            count += 1

    print(f"✅ Migration complete: {count} records inserted/updated.")


if __name__ == "__main__":
    migrate()
