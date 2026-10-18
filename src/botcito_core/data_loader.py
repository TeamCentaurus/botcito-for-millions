"""
Carga de precios para el laboratorio.

Separa **descarga** de **higiene** porque tienen testabilidad opuesta:
`clean_prices` es una función pura que se verifica por completo con datos armados a
mano, y `load_yfinance` es un wrapper delgado que se verifica con la descarga
monkeypatcheada. Un loader monolítico solo se puede testear con red, y un test con
red no es un test.

Contrato en `docs/specs/010-data-loader.md`.
"""

from __future__ import annotations

import pandas as pd
import yfinance as yf


def clean_prices(raw: pd.DataFrame, min_coverage: float = 0.95) -> pd.DataFrame:
    """
    Higiene de un panel de precios.

    1. Descarta columnas con cobertura (fracción de valores no nulos) menor a
       `min_coverage`. Es el filtro que decide qué tickers entran al universo.
    2. Ordena el índice y descarta fechas duplicadas (se queda con la última).
    3. Forward-fill de huecos internos.
    4. Descarta las filas iniciales que sigan incompletas después del ffill.

    Función pura: no muta `raw`.
    """
    if not 0 < min_coverage <= 1:
        raise ValueError(f"min_coverage debe estar en (0, 1], recibido: {min_coverage}")

    if raw.empty:
        raise ValueError("el panel de precios está vacío")

    panel = raw.copy()

    cobertura = panel.notna().mean()
    sobreviven = cobertura[cobertura >= min_coverage].index.tolist()
    descartadas = [c for c in panel.columns if c not in sobreviven]
    panel = panel[sobreviven]

    if len(panel.columns) < 2:
        raise ValueError(
            f"tras filtrar por cobertura >= {min_coverage} quedan "
            f"{len(panel.columns)} columnas; no hay par posible "
            f"(descartadas: {descartadas})"
        )

    panel = panel[~panel.index.duplicated(keep="last")].sort_index()
    panel = panel.ffill().dropna()

    if panel.empty:
        raise ValueError("no quedó ninguna fila completa después del forward-fill")

    return panel


def load_yfinance(tickers: list[str],
                  start: str,
                  end: str | None = None,
                  interval: str = "1d",
                  min_coverage: float = 0.95,
                  auto_adjust: bool = True) -> pd.DataFrame:
    """
    Descarga precios de cierre con yfinance y aplica `clean_prices`.

    `auto_adjust` va explícito a propósito: el default de yfinance cambió a True y el
    ajuste reescribe la historia hacia atrás, lo cual afecta la cointegración sobre
    niveles. Tiene que ser una decisión visible, no un default heredado.

    Ojo con el survivorship bias: yfinance solo devuelve tickers que siguen listados.
    No se puede resolver desde acá; declararlo en las `advertencias` de la corrida.
    """
    if not tickers:
        raise ValueError("tickers está vacío")

    raw = yf.download(
        tickers=tickers,
        start=start,
        end=end,
        interval=interval,
        auto_adjust=auto_adjust,
        progress=False,
    )

    if raw is None or raw.empty:
        raise ValueError(
            f"la descarga de {len(tickers)} tickers volvió vacía "
            f"({start} → {end}, interval={interval})"
        )

    return clean_prices(_extraer_close(raw, tickers), min_coverage=min_coverage)


def _extraer_close(raw: pd.DataFrame, tickers: list[str]) -> pd.DataFrame:
    """
    Aplana la respuesta de yfinance a un DataFrame de cierres, una columna por ticker.

    Con varios tickers yfinance devuelve columnas MultiIndex; el nivel que lleva
    "Close" puede ser el 0 o el 1 según cómo se agrupe.
    """
    if isinstance(raw.columns, pd.MultiIndex):
        for nivel in range(raw.columns.nlevels):
            if "Close" in raw.columns.get_level_values(nivel):
                return raw.xs("Close", axis=1, level=nivel)
        raise ValueError(f"la descarga no trae 'Close': columnas {raw.columns.tolist()}")

    if "Close" in raw.columns:
        close = raw[["Close"]]
        if len(tickers) == 1:
            close = close.rename(columns={"Close": tickers[0]})
        return close

    return raw
