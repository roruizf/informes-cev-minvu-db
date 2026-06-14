"""Unit tests for transform/normalize.py (pure functions, no DB)."""
from datetime import date

from informes_cev_minvu_db.transform import normalize as N


class TestParseChileanDate:
    def test_dash_format(self):
        assert N.parse_chilean_date("15-01-2019") == date(2019, 1, 15)

    def test_slash_format(self):
        assert N.parse_chilean_date("03/12/2020") == date(2020, 12, 3)

    def test_long_format(self):
        assert N.parse_chilean_date("10 de mayo de 2017") == date(2017, 5, 10)

    def test_already_date(self):
        d = date(2021, 6, 1)
        assert N.parse_chilean_date(d) is d

    def test_none_and_empty(self):
        assert N.parse_chilean_date(None) is None
        assert N.parse_chilean_date("") is None

    def test_invalid(self):
        assert N.parse_chilean_date("no-soy-fecha") is None

    def test_impossible_date(self):
        assert N.parse_chilean_date("32-13-2020") is None


class TestMesId:
    def test_spanish_name(self):
        assert N.mes_id("Enero") == 1
        assert N.mes_id("julio") == 7
        assert N.mes_id("Diciembre") == 12

    def test_int_passthrough(self):
        assert N.mes_id(4) == 4

    def test_out_of_range_int(self):
        assert N.mes_id(13) is None
        assert N.mes_id(0) is None

    def test_none_and_unknown(self):
        assert N.mes_id(None) is None
        assert N.mes_id("Foo") is None


class TestRenameMaps:
    def test_codigo_rename_in_every_page_map(self):
        for m in (N.PAGINA1_RENAME, N.PAGINA2_RENAME, N.PAGINA3C_RENAME,
                  N.PAGINA3E_RENAME, N.PAGINA4_RENAME, N.PAGINA5_RENAME,
                  N.PAGINA6_RENAME, N.PAGINA7_RENAME):
            assert m.get("codigo_evaluacion") == "codigo_evaluacion_energetica"

    def test_pagina1_free_text_dims(self):
        assert N.PAGINA1_RENAME["tipo_vivienda"] == "tipo_vivienda_nombre"
        assert N.PAGINA1_RENAME["region"] == "region_nombre"

    def test_pagina2_zona_termica_raw(self):
        assert N.PAGINA2_RENAME["zona_termica"] == "zona_termica_nombre"

    def test_envolvente_orientacion_raw(self):
        assert N.PAGINA3E_RENAME["orientacion"] == "orientacion_nombre"
        assert N.PAGINA3E_RENAME["ua_phil"] == "ua_mas_phi_l"

    def test_pagina6_temperatura_rename(self):
        assert N.PAGINA6_RENAME["temp_exterior"] == "temperatura_exterior"
        assert N.PAGINA6_RENAME["temp_interior"] == "temperatura_interior"

    def test_consumos_rename(self):
        out = N.rename_pagina3_consumos({
            "codigo_evaluacion": "X", "calefaccion_kwh_per": 0.9,
            "consumo_ep_iluminacion_kwh": 5.0, "calefaccion_consumo_proy_kwh": 10.0,
            "iluminacion_consumo_ref_kwh": 2.0,
        })
        assert out["codigo_evaluacion_energetica"] == "X"
        assert out["calefaccion_porcentaje"] == 0.9
        assert out["consumo_energia_primaria_iluminacion_kwh"] == 5.0
        assert out["calefaccion_consumo_proyectado_kwh"] == 10.0
        assert out["iluminacion_consumo_referencia_kwh"] == 2.0
