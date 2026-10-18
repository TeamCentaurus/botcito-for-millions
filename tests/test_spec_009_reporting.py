"""
SPEC-009 — Artefacto de resultados + dashboard Streamlit.

Ver `docs/specs/009-artefacto-resultados-y-dashboard.md` y ADR-0004.

Lo que se verifica es el **contrato** (serialización, validación, versión, degradación
declarada) y las **fronteras** del dashboard (lector puro, sin efectos al importar).
Que un gráfico se vea bien no es automatizable y no se pretende.

AC11 sigue bloqueado por SPEC-004 y SPEC-005: hasta que `run_backtest` produzca
`returns`, `equity_curve`, `total_return` y `annualization_factor`, la integración
end-to-end no puede llenar el schema sin degradar.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[1]
DASHBOARD = RAIZ / "app" / "dashboard.py"

CAMPOS_OBLIGATORIOS = (
    "schema_version",
    "run_id",
    "created_at",
    "data_source",
    "split",
    "params",
    "screening",
    "models",
    "backtests",
    "advertencias",
)

# Nombres de cómputo que un lector puro no puede importar (ADR-0004, I6).
COMPUTO_PROHIBIDO = {
    "run_backtest",
    "screen_universe",
    "screen_pair",
    "train",
    "optimize_thresholds",
    "evaluate_holdout",
}
MODULOS_PROHIBIDOS = {
    "botcito_core.backtest",
    "botcito_core.model",
    "botcito_core.statistical_validation",
    "botcito_core.spread_calculator",
}


def _run_minimo() -> dict:
    """Artefacto válido mínimo, construido a mano (no depende del pipeline)."""
    return {
        "schema_version": 1,
        "run_id": "2026-10-12T16-30-00Z",
        "created_at": "2026-10-12T16:30:00+00:00",
        "data_source": {
            "provider": "yfinance",
            "interval": "1d",
            "tickers": ["AAPL", "MSFT"],
            "start": "2023-01-01",
            "end": "2026-03-01",
        },
        "split": {
            "train_end": "2024-12-31",
            "val_start": "2025-01-01",
            "val_end": "2025-09-30",
            "test_start": "2025-10-01",
            "test_end": "2026-03-01",
        },
        "params": {
            "alpha": 0.05,
            "capital": 10_000.0,
            "transaction_cost": 0.001,
            "annualization_factor": 252,
            "zscore_window": 30,
        },
        "screening": [
            {
                "par": "AAPL/MSFT",
                "cointegracion": {"p_value": 0.0026},
                "p_value_corregido": 0.771,
                "rechaza_h0_fdr": False,
                "cumple_filtros_locales": True,
                "valido": False,
                "n_pares_probados": 1,
                "half_life_dias": 12.5,
                "hedge_ratio": 1.87,
            }
        ],
        "models": [
            {
                "ticker_a": "AAPL",
                "ticker_b": "MSFT",
                "hedge_ratio": 1.87,
                "spread_mean": 74.16,
                "spread_std": 19.36,
                "half_life": 12.5,
                "zscore_window": 30,
                "entry_threshold": 2.0,
                "exit_threshold": 0.5,
                "stop_loss_threshold": 3.5,
            }
        ],
        "backtests": [
            {
                "par": "AAPL/MSFT",
                "periodo": "test",
                "total_trades": 5,
                "win_rate": 0.6,
                "sharpe_ratio": 0.82,
                "total_pnl": 310.0,
                "max_drawdown": 0.047,
                "total_return": 0.031,
                "annualization_factor": 252,
                "series": {
                    "fechas": ["2025-10-01", "2025-10-02"],
                    "spread": [74.0, 74.5],
                    "zscore": [-0.1, 0.02],
                    "equity_curve": [1.0, 1.004],
                    "returns": [0.0, 0.004],
                },
                "trades": [],
            }
        ],
        "advertencias": [
            "SPEC-004 no implementada: el Sharpe no está anualizado.",
            "SPEC-005 no implementada: el PnL está en unidades de spread_std.",
        ],
    }


@pytest.mark.spec
def test_ac1_round_trip(tmp_path):
    """I1: escribir y leer no pierde ni reordena nada."""
    from botcito_core.reporting import read_run, write_run

    original = _run_minimo()
    destino = write_run(original, tmp_path / "runs" / "run.json")

    assert destino.exists(), "write_run debe crear el directorio padre si falta"
    assert read_run(destino) == original


@pytest.mark.spec
@pytest.mark.parametrize("campo", CAMPOS_OBLIGATORIOS)
def test_ac2_campos_obligatorios(campo):
    """I2: falta un campo → ValueError que lo nombra."""
    from botcito_core.reporting import validate_run

    run = _run_minimo()
    del run[campo]

    with pytest.raises(ValueError) as exc:
        validate_run(run)

    assert campo in str(exc.value), (
        f"el error debe nombrar el campo que falta; dijo: {exc.value!r}"
    )


@pytest.mark.spec
def test_ac3_version_no_soportada(tmp_path):
    """I3: una versión desconocida falla en vez de interpretarse a medias."""
    from botcito_core.reporting import RUN_SCHEMA_VERSION, read_run

    run = _run_minimo()
    run["schema_version"] = 999
    ruta = tmp_path / "futuro.json"
    ruta.write_text(json.dumps(run), encoding="utf-8")

    with pytest.raises(ValueError) as exc:
        read_run(ruta)

    mensaje = str(exc.value)
    assert "999" in mensaje and str(RUN_SCHEMA_VERSION) in mensaje


@pytest.mark.spec
def test_ac4_dashboard_es_lector_puro():
    """
    I6 (ADR-0004): el dashboard no importa cómputo. Verificado sobre el AST, no
    importando el módulo — un import podría pasar por casualidad.
    """
    assert DASHBOARD.exists(), f"falta {DASHBOARD.relative_to(RAIZ)}"

    arbol = ast.parse(DASHBOARD.read_text(encoding="utf-8"))
    modulos: set[str] = set()
    nombres: set[str] = set()

    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            modulos.update(alias.name for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom):
            if nodo.module:
                modulos.add(nodo.module)
            nombres.update(alias.name for alias in nodo.names)

    assert not (nombres & COMPUTO_PROHIBIDO), (
        f"el dashboard importa funciones de cómputo: {sorted(nombres & COMPUTO_PROHIBIDO)}"
    )
    assert not (modulos & MODULOS_PROHIBIDOS), (
        f"el dashboard importa módulos de cómputo: {sorted(modulos & MODULOS_PROHIBIDOS)}"
    )

    de_core = {m for m in modulos if m.startswith("botcito_core")}
    assert de_core <= {"botcito_core.reporting", "botcito_core"}, (
        f"el único módulo de botcito_core permitido es reporting; importa {sorted(de_core)}"
    )


@pytest.mark.spec
def test_ac5_dashboard_sin_efectos_al_importar(capsys, monkeypatch):
    """
    I7: importar el módulo no renderiza ni abre archivos. Es el error de
    monitoring.py, que ejecuta un while True en el cuerpo y no es importable.
    """
    import importlib
    import sys

    assert DASHBOARD.exists(), f"falta {DASHBOARD.relative_to(RAIZ)}"

    monkeypatch.syspath_prepend(str(DASHBOARD.parent))
    sys.modules.pop("dashboard", None)

    modulo = importlib.import_module("dashboard")

    capturado = capsys.readouterr()
    assert capturado.out == "" and capturado.err == "", (
        f"importar el dashboard produjo salida: {capturado.out!r} {capturado.err!r}"
    )
    assert hasattr(modulo, "main"), "todo el render debe estar dentro de main()"


@pytest.mark.spec
def test_ac6_json_puro_sin_tipos_numpy():
    """
    I4: los dicts de botcito_core vienen llenos de np.float64 / np.bool_ (ver la
    salida de la celda 7 del notebook viejo). build_run tiene que normalizarlos.
    """
    from botcito_core.reporting import build_run
    from botcito_core.types import PairModel

    modelo = PairModel(
        ticker_a="AAPL",
        ticker_b="MSFT",
        hedge_ratio=np.float64(1.87),
        spread_mean=np.float64(74.16),
        spread_std=np.float64(19.36),
        half_life=np.float64(12.5),
        zscore_window=30,
        entry_threshold=2.0,
        exit_threshold=0.5,
        stop_loss_threshold=3.5,
    )
    base = _run_minimo()
    screening = [
        {
            **base["screening"][0],
            "cointegracion": {
                "p_value": np.float64(0.0026),
                "valores_criticos": np.array([-3.91, -3.34, -3.05]),
            },
            "valido": np.bool_(False),
            "half_life_dias": float("inf"),  # half-life sin reversión
        }
    ]
    backtests = [
        {
            **base["backtests"][0],
            "sharpe_ratio": np.float64(0.82),
            "series": {
                "fechas": [pd.Timestamp("2025-10-01"), pd.Timestamp("2025-10-02")],
                "spread": np.array([74.0, 74.5]),
                "zscore": np.array([-0.1, 0.02]),
                "equity_curve": np.array([1.0, 1.004]),
                "returns": np.array([0.0, 0.004]),
            },
        }
    ]

    run = build_run(
        data_source=base["data_source"],
        split=base["split"],
        params=base["params"],
        screening=screening,
        models=[modelo],
        backtests=backtests,
        advertencias=base["advertencias"],
    )

    # Sin default= ni allow_nan: si queda un tipo numpy, un Timestamp o un inf, revienta.
    json.dumps(run, allow_nan=False)
    assert run["screening"][0]["half_life_dias"] is None, "inf no es JSON válido"


@pytest.mark.spec
def test_ac7_consistencia_screening_backtests():
    """I5: un backtest de un par que no se screenéo es incoherente."""
    from botcito_core.reporting import validate_run

    run = _run_minimo()
    run["backtests"][0]["par"] = "NVDA/BAC"  # no está en screening

    with pytest.raises(ValueError) as exc:
        validate_run(run)

    assert "NVDA/BAC" in str(exc.value)


@pytest.mark.spec
def test_ac8_list_runs_ordena_por_fecha(tmp_path):
    import os
    import time

    from botcito_core.reporting import list_runs, write_run

    primero = write_run({**_run_minimo(), "run_id": "viejo"}, tmp_path / "viejo.json")
    time.sleep(0.01)
    segundo = write_run({**_run_minimo(), "run_id": "nuevo"}, tmp_path / "nuevo.json")
    os.utime(primero, (1, 1))  # fuerza que el primero sea claramente más antiguo

    (tmp_path / "notas.txt").write_text("no es un artefacto", encoding="utf-8")

    rutas = list_runs(tmp_path)
    assert rutas == [segundo, primero], "del más reciente al más antiguo"
    assert all(r.suffix == ".json" for r in rutas)


@pytest.mark.spec
def test_ac9_ruta_inexistente(tmp_path):
    from botcito_core.reporting import read_run

    with pytest.raises(FileNotFoundError):
        read_run(tmp_path / "no_existe.json")


@pytest.mark.spec
def test_ac10_advertencias_sobreviven_y_se_muestran(tmp_path):
    """
    Sin el banner, el dashboard muestra sharpe=1179.75 como si fuera un resultado.
    """
    from botcito_core.reporting import read_run, write_run

    run = _run_minimo()
    leido = read_run(write_run(run, tmp_path / "run.json"))
    assert leido["advertencias"] == run["advertencias"]

    assert DASHBOARD.exists(), f"falta {DASHBOARD.relative_to(RAIZ)}"
    assert "advertencias" in DASHBOARD.read_text(encoding="utf-8"), (
        "el dashboard tiene que renderizar el campo advertencias"
    )


@pytest.mark.spec
def test_ac12_degradacion_exige_advertencia():
    """I8: un resultado degradado sin declararlo es peor que no tenerlo."""
    from botcito_core.reporting import validate_run

    run = _run_minimo()
    run["backtests"][0]["total_return"] = None
    run["advertencias"] = []

    with pytest.raises(ValueError) as exc:
        validate_run(run)
    assert "advertencias" in str(exc.value)

    run["advertencias"] = ["SPEC-005 pendiente: total_return no disponible."]
    validate_run(run)  # con la degradación declarada, pasa

    # Una serie vacía también cuenta como degradación
    run["backtests"][0]["series"]["zscore"] = []
    run["advertencias"] = []
    with pytest.raises(ValueError):
        validate_run(run)


@pytest.mark.spec
def test_ac13_series_alineadas():
    """I9: una serie desalineada con las fechas haría mentir a cualquier gráfico."""
    from botcito_core.reporting import validate_run

    run = _run_minimo()
    run["backtests"][0]["series"]["zscore"] = [0.1]  # fechas tiene 2

    with pytest.raises(ValueError) as exc:
        validate_run(run)

    mensaje = str(exc.value)
    assert "zscore" in mensaje and "AAPL/MSFT" in mensaje


@pytest.mark.spec
@pytest.mark.xfail(
    reason="SPEC-009 AC11 bloqueado: depende de SPEC-004 y SPEC-005",
    strict=True,
)
def test_ac11_integracion_pipeline_a_artefacto(tmp_path, coint_prices, pair_model):
    """
    Pipeline completo → artefacto SIN degradar, sobre datos sintéticos.

    Hoy falla porque `run_backtest` no produce `returns`, `equity_curve`,
    `total_return` ni `annualization_factor`.
    """
    from botcito_core.backtest import run_backtest
    from botcito_core.model import train
    from botcito_core.reporting import build_run, read_run, write_run
    from botcito_core.statistical_validation import screen_universe

    fin = str(coint_prices.index[-1].date())
    train_end = str(coint_prices.index[300].date())

    screening = screen_universe(coint_prices, [("A", "B")], alpha=0.05)
    modelo = train(coint_prices, "A", "B", train_end=train_end)
    backtest = run_backtest(coint_prices, modelo, train_end, fin)

    run = build_run(
        data_source={"provider": "synthetic", "interval": "1d", "tickers": ["A", "B"],
                     "start": str(coint_prices.index[0].date()), "end": fin},
        split={"train_end": train_end, "val_start": train_end, "val_end": fin,
               "test_start": train_end, "test_end": fin},
        params={"alpha": 0.05, "capital": 10_000.0, "transaction_cost": 0.001,
                "annualization_factor": 252, "zscore_window": modelo.zscore_window},
        screening=screening,
        models=[modelo],
        backtests=[{
            **backtest,
            "par": "A/B",
            "periodo": "test",
            "total_return": backtest["total_return"],
            "annualization_factor": backtest["annualization_factor"],
            "series": {
                "fechas": [str(d.date()) for d in coint_prices.loc[train_end:].index],
                "spread": [], "zscore": [],
                "equity_curve": backtest["equity_curve"],
                "returns": backtest["returns"],
            },
        }],
        advertencias=[],  # sin degradación: el artefacto tiene que ser completo
    )

    assert read_run(write_run(run, tmp_path / "run.json")) == run
