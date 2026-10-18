"""
Artefacto de resultados: el contrato entre el pipeline y cualquier consumidor.

ADR-0004: el pipeline escribe un artefacto versionado y todo consumidor de resultados
(dashboard, notificaciones) es un lector puro. Nadie recalcula. Un consumidor que
recalcula es una segunda implementación del pipeline que diverge, y además no deja
registro de qué se vio ni con qué parámetros.

Contrato completo en `docs/specs/009-artefacto-resultados-y-dashboard.md`.
"""

from __future__ import annotations

import dataclasses
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RUN_SCHEMA_VERSION = 1

CAMPOS_RUN = (
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

CAMPOS_BACKTEST = (
    "par",
    "periodo",
    "total_trades",
    "win_rate",
    "sharpe_ratio",
    "total_pnl",
    "max_drawdown",
    "total_return",
    "annualization_factor",
    "series",
    "trades",
)

CAMPOS_SERIES = ("fechas", "spread", "zscore", "equity_curve", "returns")

# Métricas que pueden ir en None mientras SPEC-004 y SPEC-005 estén abiertas.
METRICAS_DEGRADABLES = ("total_return", "annualization_factor")


def _to_native(valor: Any) -> Any:
    """
    Convierte a tipos nativos de Python, recursivamente.

    Hace falta porque los dicts que devuelve `botcito_core` están llenos de
    `np.float64`, `np.bool_` y arrays, y `json.dumps` no los serializa. Los flotantes
    no finitos (`inf` de un half-life sin reversión, `nan`) van a `None`: `Infinity`
    no es JSON válido.
    """
    if valor is None or isinstance(valor, (str, bool, int)):
        return valor

    if isinstance(valor, float):
        return valor if math.isfinite(valor) else None

    if dataclasses.is_dataclass(valor) and not isinstance(valor, type):
        return _to_native(dataclasses.asdict(valor))

    if isinstance(valor, dict):
        return {str(k): _to_native(v) for k, v in valor.items()}

    if isinstance(valor, (list, tuple, set)):
        return [_to_native(v) for v in valor]

    if isinstance(valor, datetime):
        return valor.isoformat()

    # numpy / pandas sin importarlos: todo lo que expone .item() o .tolist()
    if hasattr(valor, "tolist"):
        return _to_native(valor.tolist())
    if hasattr(valor, "item"):
        return _to_native(valor.item())
    if hasattr(valor, "isoformat"):
        return valor.isoformat()

    return str(valor)


def build_run(*,
              data_source: dict,
              split: dict,
              params: dict,
              screening: list[dict],
              models: list[Any],
              backtests: list[dict],
              advertencias: list[str] | None = None,
              run_id: str | None = None) -> dict:
    """
    Ensambla un artefacto de resultados y normaliza todo a tipos JSON nativos.

    No valida: para eso está `validate_run`, que corre dentro de `write_run`.
    """
    ahora = datetime.now(UTC)
    return {
        "schema_version": RUN_SCHEMA_VERSION,
        "run_id": run_id or ahora.strftime("%Y-%m-%dT%H-%M-%SZ"),
        "created_at": ahora.isoformat(),
        "data_source": _to_native(data_source),
        "split": _to_native(split),
        "params": _to_native(params),
        "screening": _to_native(screening),
        "models": _to_native(models),
        "backtests": _to_native(backtests),
        "advertencias": _to_native(advertencias or []),
    }


def validate_run(run: dict) -> None:
    """Lanza ValueError nombrando el primer problema que encuentre."""
    if not isinstance(run, dict):
        raise ValueError(f"el artefacto debe ser un dict, recibido: {type(run).__name__}")

    for campo in CAMPOS_RUN:
        if campo not in run:
            raise ValueError(f"falta el campo obligatorio '{campo}' en el artefacto")

    if not run["screening"]:
        raise ValueError("'screening' está vacío: un artefacto sin pares evaluados no dice nada")

    pares_screened = {entrada.get("par") for entrada in run["screening"]}
    degradado = False

    for backtest in run["backtests"]:
        for campo in CAMPOS_BACKTEST:
            if campo not in backtest:
                raise ValueError(
                    f"falta el campo '{campo}' en el backtest de {backtest.get('par', '?')}"
                )

        if backtest["par"] not in pares_screened:
            raise ValueError(
                f"el backtest de '{backtest['par']}' no tiene entrada en 'screening': "
                "no se puede reportar un par que no se screeneó"
            )

        series = backtest["series"]
        for campo in CAMPOS_SERIES:
            if campo not in series:
                raise ValueError(
                    f"falta la serie '{campo}' en el backtest de {backtest['par']}"
                )

        # I9: las series no vacías tienen que estar alineadas con las fechas
        n_fechas = len(series["fechas"])
        for campo in CAMPOS_SERIES:
            if campo == "fechas":
                continue
            if series[campo] and len(series[campo]) != n_fechas:
                raise ValueError(
                    f"serie desalineada en {backtest['par']}: '{campo}' tiene "
                    f"{len(series[campo])} puntos y 'fechas' tiene {n_fechas}"
                )
            if not series[campo]:
                degradado = True

        if any(backtest[m] is None for m in METRICAS_DEGRADABLES):
            degradado = True

    # I8: lo degradado se declara
    if degradado and not run["advertencias"]:
        raise ValueError(
            "el artefacto tiene métricas o series degradadas (None o vacías) y "
            "'advertencias' está vacío: la degradación tiene que declararse"
        )

    for par in {m.get("ticker_a", "") + "/" + m.get("ticker_b", "") for m in run["models"]}:
        if par and par not in pares_screened:
            raise ValueError(f"el modelo de '{par}' no tiene entrada en 'screening'")


def write_run(run: dict, path: str | Path) -> Path:
    """Valida y escribe el artefacto como JSON. Crea el directorio padre si falta."""
    validate_run(run)
    destino = Path(path)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        json.dumps(run, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    return destino


def read_run(path: str | Path) -> dict:
    """Lee y valida un artefacto. Falla si la versión del schema no es soportada."""
    origen = Path(path)
    if not origen.exists():
        raise FileNotFoundError(f"no existe el artefacto: {origen}")

    run = json.loads(origen.read_text(encoding="utf-8"))

    version = run.get("schema_version")
    if version != RUN_SCHEMA_VERSION:
        raise ValueError(
            f"schema_version {version} no soportada; esta versión de botcito_core "
            f"lee {RUN_SCHEMA_VERSION}"
        )

    validate_run(run)
    return run


def list_runs(directory: str | Path) -> list[Path]:
    """Artefactos .json de un directorio, del más reciente al más antiguo."""
    carpeta = Path(directory)
    if not carpeta.is_dir():
        return []
    return sorted(carpeta.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
