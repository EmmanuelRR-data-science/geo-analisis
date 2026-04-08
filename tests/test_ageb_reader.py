"""Unit tests for AGEBReader."""

import pandas as pd
import pytest

from app.services.ageb_reader import AGEBReader, _safe_int, _safe_float, _classify_socioeconomic


class TestSafeConversions:
    """Tests for _safe_int and _safe_float helpers."""

    def test_safe_int_normal(self):
        assert _safe_int(1234) == 1234

    def test_safe_int_string(self):
        assert _safe_int("567") == 567

    def test_safe_int_float_string(self):
        assert _safe_int("11.52") == 11

    def test_safe_int_confidential(self):
        assert _safe_int("*") == 0

    def test_safe_int_none(self):
        assert _safe_int(None) == 0

    def test_safe_float_normal(self):
        assert _safe_float(3.14) == pytest.approx(3.14)

    def test_safe_float_confidential(self):
        assert _safe_float("*") == 0.0

    def test_safe_float_string(self):
        assert _safe_float("11.52") == pytest.approx(11.52)


class TestClassifySocioeconomic:
    """Tests for NSE classification from GRAPROES."""

    def test_alto(self):
        assert _classify_socioeconomic(15.0) == "Alto"

    def test_medio_alto(self):
        assert _classify_socioeconomic(13.0) == "Medio-Alto"

    def test_medio(self):
        assert _classify_socioeconomic(11.0) == "Medio"

    def test_medio_bajo(self):
        assert _classify_socioeconomic(8.0) == "Medio-Bajo"

    def test_bajo(self):
        assert _classify_socioeconomic(5.0) == "Bajo"


class TestAGEBReaderLoad:
    """Tests for AGEBReader.load()."""

    def test_file_not_found(self):
        reader = AGEBReader()
        with pytest.raises(FileNotFoundError, match="no encontrado"):
            reader.load("nonexistent_file.xlsx")

    def test_corrupt_file(self, tmp_path):
        bad_file = tmp_path / "bad.xlsx"
        bad_file.write_text("this is not an excel file")
        reader = AGEBReader()
        with pytest.raises(ValueError, match="No se pudo leer"):
            reader.load(str(bad_file))

    def test_missing_columns(self, tmp_path):
        # Create a valid Excel file but with wrong columns
        df = pd.DataFrame({"A": [1], "B": [2]})
        path = tmp_path / "missing_cols.xlsx"
        df.to_excel(str(path), index=False)
        reader = AGEBReader()
        with pytest.raises(ValueError, match="columnas faltantes"):
            reader.load(str(path))

    def test_load_valid_file(self, tmp_path):
        df = pd.DataFrame({
            "ENTIDAD": ["09", "09"],
            "NOM_ENT": ["CDMX", "CDMX"],
            "MUN": ["015", "015"],
            "LOC": ["0001", "0001"],
            "AGEB": ["0010", "0025"],
            "MZA": ["000", "000"],
            "POBTOT": [3000, 5000],
            "PEA": ["1500", "2500"],
            "GRAPROES": ["12.5", "10.0"],
            "POCUPADA": ["1400", "2300"],
            "VIVPAR_HAB": ["800", "1200"],
        })
        path = tmp_path / "test_ageb.xlsx"
        df.to_excel(str(path), index=False)

        reader = AGEBReader()
        result = reader.load(str(path))
        assert len(result) == 2
        assert "ageb_id" in result.columns
        assert result.iloc[0]["ageb_id"] == "0901500010010"
        assert result.iloc[1]["ageb_id"] == "0901500010025"

    def test_load_filters_non_ageb_rows(self, tmp_path):
        df = pd.DataFrame({
            "ENTIDAD": ["09", "09", "09"],
            "MUN": ["015", "015", "015"],
            "LOC": ["0000", "0001", "0001"],
            "AGEB": ["0000", "0000", "0010"],
            "MZA": ["000", "000", "000"],
            "POBTOT": [100000, 50000, 3000],
            "PEA": ["50000", "25000", "1500"],
            "GRAPROES": ["11.0", "11.0", "12.5"],
        })
        path = tmp_path / "test_filter.xlsx"
        df.to_excel(str(path), index=False)

        reader = AGEBReader()
        result = reader.load(str(path))
        # Only the third row is a real AGEB-level row
        assert len(result) == 1
        assert result.iloc[0]["ageb_id"] == "0901500010010"


class TestAGEBReaderGetZoneData:
    """Tests for AGEBReader.get_zone_data()."""

    @pytest.fixture()
    def loaded_reader(self, tmp_path):
        df = pd.DataFrame({
            "ENTIDAD": ["09", "09", "09"],
            "MUN": ["015", "015", "015"],
            "LOC": ["0001", "0001", "0001"],
            "AGEB": ["0010", "0025", "0030"],
            "MZA": ["000", "000", "000"],
            "POBTOT": [3000, 5000, 2000],
            "PEA": ["1500", "2500", "*"],
            "GRAPROES": ["12.5", "10.0", "8.0"],
            "POCUPADA": ["1400", "2300", "*"],
            "VIVPAR_HAB": ["800", "1200", "500"],
        })
        path = tmp_path / "test_zone.xlsx"
        df.to_excel(str(path), index=False)
        reader = AGEBReader()
        reader.load(str(path))
        return reader

    def test_runtime_error_without_load(self):
        reader = AGEBReader()
        with pytest.raises(RuntimeError, match="load"):
            reader.get_zone_data(["0901500010010"])

    def test_no_matching_agebs(self, loaded_reader):
        result = loaded_reader.get_zone_data(["9999999999999"])
        assert result.ageb_count == 0
        assert result.total_population == 0
        assert result.socioeconomic_level == "Desconocido"

    def test_single_ageb(self, loaded_reader):
        result = loaded_reader.get_zone_data(["0901500010010"])
        assert result.ageb_count == 1
        assert result.total_population == 3000
        assert result.economically_active_population == 1500
        assert result.socioeconomic_level == "Medio-Alto"
        assert result.population_density > 0

    def test_multiple_agebs(self, loaded_reader):
        result = loaded_reader.get_zone_data(["0901500010010", "0901500010025"])
        assert result.ageb_count == 2
        assert result.total_population == 8000
        assert result.economically_active_population == 4000

    def test_confidential_pea_treated_as_zero(self, loaded_reader):
        result = loaded_reader.get_zone_data(["0901500010030"])
        assert result.ageb_count == 1
        assert result.total_population == 2000
        assert result.economically_active_population == 0

    def test_raw_indicators_present(self, loaded_reader):
        result = loaded_reader.get_zone_data(["0901500010010"])
        assert "0901500010010" in result.raw_indicators
        raw = result.raw_indicators["0901500010010"]
        assert raw["pobtot"] == 3000
        assert raw["pea"] == 1500
