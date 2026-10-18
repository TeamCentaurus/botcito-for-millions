"""
SPEC-006 — Hold-out test tras el tuning de umbrales.

Ver `docs/specs/006-holdout-test-thresholds.md`.

AC2 y AC3 pasan HOY (el grid search ya respeta el slice de validación y el guard
`exit < entry`): son guardas de regresión. El resto es el trabajo pendiente —
empezando por que `optimize_thresholds` muta el modelo y lo deja con la ÚLTIMA
combinación probada, no con la mejor.
"""

from __future__ import annotations

import dataclasses

import pytest

import synthetic as syn

PENDIENTE = "SPEC-006 no implementada"


@pytest.fixture
def fronteras(coint_prices):
    """train → val → test sobre las 500 barras del par sintético."""
    idx = coint_prices.index
    return {
        "train_end": str(idx[250].date()),
        "val_start": str(idx[251].date()),
        "val_end": str(idx[375].date()),
        "test_start": str(idx[376].date()),
        "test_end": str(idx[-1].date()),
    }


@pytest.mark.spec
@pytest.mark.xfail(reason=PENDIENTE, strict=True)
def test_ac1_optimize_no_muta_modelo(coint_prices, pair_model, fronteras):
    """I1: una función de búsqueda no puede dejar efectos en su entrada."""
    from botcito_core.model import optimize_thresholds

    antes = dataclasses.asdict(pair_model)
    optimize_thresholds(coint_prices, pair_model, fronteras["val_start"], fronteras["val_end"])
    despues = dataclasses.asdict(pair_model)

    assert antes == despues, (
        "optimize_thresholds mutó el modelo; además hoy lo deja con la última "
        "combinación del grid, no con la mejor"
    )


@pytest.mark.spec
def test_ac2_tuning_no_ve_datos_posteriores(coint_prices, pair_model, fronteras):
    """I2: corromper todo lo posterior a val_end no debe cambiar el resultado."""
    from botcito_core.model import optimize_thresholds

    corrompido = syn.corrupt_after(coint_prices, fronteras["val_end"])

    original = optimize_thresholds(
        coint_prices,
        dataclasses.replace(pair_model),
        fronteras["val_start"],
        fronteras["val_end"],
    )
    alterado = optimize_thresholds(
        corrompido,
        dataclasses.replace(pair_model),
        fronteras["val_start"],
        fronteras["val_end"],
    )

    assert original == alterado, "el tuning está leyendo datos posteriores a val_end"


@pytest.mark.spec
def test_ac3_exit_menor_que_entry(coint_prices, pair_model, fronteras):
    from botcito_core.model import optimize_thresholds

    mejor = optimize_thresholds(
        coint_prices,
        dataclasses.replace(pair_model),
        fronteras["val_start"],
        fronteras["val_end"],
    )
    assert mejor, "el grid search debe devolver alguna combinación"
    assert mejor["exit"] < mejor["entry"]


@pytest.mark.spec
@pytest.mark.xfail(reason=PENDIENTE, strict=True)
def test_ac4_evaluate_holdout_existe(coint_prices, pair_model, fronteras):
    from botcito_core.backtest import run_backtest
    from botcito_core.model import evaluate_holdout

    holdout = evaluate_holdout(
        coint_prices, pair_model, fronteras["test_start"], fronteras["test_end"]
    )
    referencia = run_backtest(
        coint_prices, pair_model, fronteras["test_start"], fronteras["test_end"]
    )

    assert set(holdout) == set(referencia)


@pytest.mark.spec
@pytest.mark.xfail(reason=PENDIENTE, strict=True)
def test_ac5_holdout_no_ve_validacion(coint_prices, pair_model, fronteras):
    """I5: el hold-out solo lee su propio rango."""
    from botcito_core.model import evaluate_holdout

    corrompido = syn.corrupt_between(
        coint_prices, fronteras["val_start"], fronteras["val_end"]
    )

    original = evaluate_holdout(
        coint_prices, pair_model, fronteras["test_start"], fronteras["test_end"]
    )
    alterado = evaluate_holdout(
        corrompido, pair_model, fronteras["test_start"], fronteras["test_end"]
    )

    assert original["total_trades"] == alterado["total_trades"]
    assert original["total_pnl"] == pytest.approx(alterado["total_pnl"], rel=1e-9)


@pytest.mark.spec
@pytest.mark.xfail(reason=PENDIENTE, strict=True)
def test_ac6_validate_split(fronteras):
    """I4: el solapamiento deja de ser responsabilidad del caller."""
    from botcito_core.model import Split, validate_split

    validate_split(Split(**fronteras))  # split válido: no lanza

    # test empieza antes de que termine validación
    with pytest.raises(ValueError):
        validate_split(Split(**{**fronteras, "test_start": fronteras["val_start"]}))

    # validación empieza antes de que termine training
    with pytest.raises(ValueError):
        validate_split(Split(**{**fronteras, "val_start": "2019-01-01"}))

    # rango invertido
    with pytest.raises(ValueError):
        validate_split(Split(**{**fronteras, "val_end": fronteras["val_start"],
                                "val_start": fronteras["val_end"]}))


@pytest.mark.spec
@pytest.mark.xfail(reason=PENDIENTE, strict=True)
def test_ac7_nombre_del_sharpe_de_validacion(coint_prices, pair_model, fronteras):
    """I6: el nombre tiene que impedir reportarlo como resultado out-of-sample."""
    from botcito_core.model import optimize_thresholds

    mejor = optimize_thresholds(
        coint_prices,
        dataclasses.replace(pair_model),
        fronteras["val_start"],
        fronteras["val_end"],
    )

    assert "sharpe_validacion" in mejor
    assert "sharpe" not in mejor


@pytest.mark.spec
@pytest.mark.xfail(reason=PENDIENTE, strict=True)
def test_ac8_grid_vacio_falla(coint_prices, pair_model, fronteras):
    from botcito_core.model import optimize_thresholds

    with pytest.raises(ValueError):
        optimize_thresholds(
            coint_prices,
            dataclasses.replace(pair_model),
            fronteras["val_start"],
            fronteras["val_end"],
            entry_range=(1.0,),
            exit_range=(2.0,),
        )


@pytest.mark.spec
@pytest.mark.xfail(reason=PENDIENTE, strict=True)
def test_ac9_cuenta_de_combinaciones(coint_prices, pair_model, fronteras):
    from botcito_core.model import optimize_thresholds

    mejor = optimize_thresholds(
        coint_prices,
        dataclasses.replace(pair_model),
        fronteras["val_start"],
        fronteras["val_end"],
        entry_range=(1.5, 2.0, 2.5),
        exit_range=(0.0, 0.5, 1.0),
    )

    # (entry, exit) con exit < entry: 3 * 3 = 9 combinaciones, todas válidas aquí.
    assert mejor["n_combinaciones"] == 9
