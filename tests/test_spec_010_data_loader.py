"""
SPEC-010 — Loader de precios.

Ver `docs/specs/010-data-loader.md`.

Ningún test toca la red: `clean_prices` es puro y `load_yfinance` se verifica con
`yf.download` monkeypatcheado.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import synthetic as syn


def _panel(n: int = 100) -> pd.DataFrame:
    """Panel de 3 tickers con coberturas distintas: 100%, 96% y 50%."""
    indice = syn.business_index(n)
    completo = np.linspace(100, 120, n)

    casi_completo = completo.copy()
    casi_completo[10:14] = np.nan  # 4 de 100 → 96% de cobertura

    incompleto = completo.copy()
    incompleto[: n // 2] = np.nan  # 50% de cobertura

    return pd.DataFrame(
        {"COMPLETO": completo, "CASI": casi_completo, "ROTO": incompleto},
        index=indice,
    )


@pytest.mark.spec
def test_ac1_descarta_por_cobertura():
    from botcito_core.data_loader import clean_prices

    limpio = clean_prices(_panel(), min_coverage=0.95)

    assert list(limpio.columns) == ["COMPLETO", "CASI"]
    assert "ROTO" not in limpio.columns


@pytest.mark.spec
def test_ac2_sin_nan_en_el_resultado():
    from botcito_core.data_loader import clean_prices

    panel = _panel()
    panel.iloc[0, 1] = np.nan  # hueco inicial: el ffill no lo puede rellenar

    limpio = clean_prices(panel, min_coverage=0.95)

    assert not limpio.isna().any().any()
    assert len(limpio) < len(panel), "las filas iniciales incompletas se descartan"


@pytest.mark.spec
def test_ac3_no_muta_input():
    from botcito_core.data_loader import clean_prices

    panel = _panel()
    copia = panel.copy(deep=True)

    clean_prices(panel, min_coverage=0.95)

    pd.testing.assert_frame_equal(panel, copia)


@pytest.mark.spec
def test_ac4_indice_ordenado_sin_duplicados():
    from botcito_core.data_loader import clean_prices

    # n=100 para que CASI (4 NaN) mantenga 96% de cobertura y sobreviva el filtro
    panel = _panel(100)
    desordenado = pd.concat([panel.iloc[50:], panel.iloc[:50], panel.iloc[[30]]])

    limpio = clean_prices(desordenado, min_coverage=0.95)

    assert limpio.index.is_monotonic_increasing
    assert not limpio.index.has_duplicates
    assert len(limpio) <= len(panel)


@pytest.mark.spec
@pytest.mark.parametrize("cobertura", [0.0, 1.5, -0.1])
def test_ac5_errores_de_clean_prices(cobertura):
    from botcito_core.data_loader import clean_prices

    with pytest.raises(ValueError, match="min_coverage"):
        clean_prices(_panel(), min_coverage=cobertura)


@pytest.mark.spec
def test_ac5b_panel_vacio_y_una_sola_columna():
    from botcito_core.data_loader import clean_prices

    with pytest.raises(ValueError, match="vacío"):
        clean_prices(pd.DataFrame())

    # Con umbral exigente solo sobrevive COMPLETO → no hay par posible
    with pytest.raises(ValueError, match="no hay par posible"):
        clean_prices(_panel(), min_coverage=1.0)


@pytest.mark.spec
def test_ac6_aplana_multiindex_de_yfinance(monkeypatch):
    """I5: con varios tickers, yfinance devuelve columnas MultiIndex (campo, ticker)."""
    from botcito_core import data_loader

    indice = syn.business_index(100)
    columnas = pd.MultiIndex.from_product([["Close", "Volume"], ["AAPL", "MSFT"]])
    datos = pd.DataFrame(
        np.tile(np.linspace(100, 120, 100), (4, 1)).T, index=indice, columns=columnas
    )

    monkeypatch.setattr(data_loader.yf, "download", lambda **kwargs: datos)

    precios = data_loader.load_yfinance(["AAPL", "MSFT"], start="2020-01-01")

    assert list(precios.columns) == ["AAPL", "MSFT"]
    assert len(precios) == 100


@pytest.mark.spec
def test_ac7_pasa_auto_adjust_explicito(monkeypatch):
    """I6: el ajuste reescribe la historia; no puede venir de un default heredado."""
    from botcito_core import data_loader

    capturado: dict = {}
    indice = syn.business_index(50)
    columnas = pd.MultiIndex.from_product([["Close"], ["AAPL", "MSFT"]])
    datos = pd.DataFrame(
        np.tile(np.linspace(10, 20, 50), (2, 1)).T, index=indice, columns=columnas
    )

    def falso_download(**kwargs):
        capturado.update(kwargs)
        return datos

    monkeypatch.setattr(data_loader.yf, "download", falso_download)

    data_loader.load_yfinance(
        ["AAPL", "MSFT"], start="2023-01-01", end="2026-01-01", interval="1d"
    )

    assert "auto_adjust" in capturado, "auto_adjust debe pasarse explícitamente"
    assert capturado["tickers"] == ["AAPL", "MSFT"]
    assert capturado["start"] == "2023-01-01"
    assert capturado["end"] == "2026-01-01"
    assert capturado["interval"] == "1d"


@pytest.mark.spec
def test_ac8_errores_de_load_yfinance(monkeypatch):
    from botcito_core import data_loader

    with pytest.raises(ValueError, match="tickers"):
        data_loader.load_yfinance([], start="2020-01-01")

    monkeypatch.setattr(data_loader.yf, "download", lambda **kwargs: pd.DataFrame())
    with pytest.raises(ValueError, match="vacía"):
        data_loader.load_yfinance(["AAPL", "MSFT"], start="2020-01-01")
