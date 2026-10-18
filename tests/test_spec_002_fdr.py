"""
SPEC-002 — Corrección BH-FDR en el screening.

Ver `docs/specs/002-fdr-multiple-testing.md`. Todos los ACs están pendientes:
`screen_universe` no existe todavía y `screen_pair` sigue emitiendo veredicto propio.
"""

from __future__ import annotations

import itertools

import pytest
from statsmodels.stats.multitest import multipletests


def _todos_los_pares(prices):
    return list(itertools.combinations(prices.columns, 2))


@pytest.mark.spec
def test_ac1_screen_universe_existe_y_ordena(indep_universe):
    from botcito_core.statistical_validation import screen_universe

    pares = _todos_los_pares(indep_universe)
    resultados = screen_universe(indep_universe, pares, alpha=0.05)

    assert len(resultados) == len(pares) == 190
    for (ticker_a, ticker_b), resultado in zip(pares, resultados, strict=True):
        assert resultado["par"] == f"{ticker_a}/{ticker_b}"


@pytest.mark.spec
def test_ac2_claves_del_resultado(coint_prices):
    from botcito_core.statistical_validation import screen_universe

    resultados = screen_universe(coint_prices, [("A", "B")], alpha=0.05)
    resultado = resultados[0]

    for clave in (
        "p_value_corregido",
        "rechaza_h0_fdr",
        "valido",
        "n_pares_probados",
        "cumple_filtros_locales",
        "cointegracion",
        "estacionariedad",
        "half_life_dias",
        "hedge_ratio",
    ):
        assert clave in resultado, f"falta la clave {clave}"
    assert resultado["n_pares_probados"] == 1


@pytest.mark.spec
def test_ac3_coincide_con_statsmodels(mixed_universe):
    """Caso numérico cerrado contra la implementación de referencia de BH."""
    from botcito_core.statistical_validation import screen_universe

    pares = _todos_los_pares(mixed_universe)
    resultados = screen_universe(mixed_universe, pares, alpha=0.05)

    crudos = [r["cointegracion"]["p_value"] for r in resultados]
    rechaza_ref, corregidos_ref, _, _ = multipletests(crudos, alpha=0.05, method="fdr_bh")

    for resultado, corregido, rechaza in zip(resultados, corregidos_ref, rechaza_ref, strict=True):
        assert resultado["p_value_corregido"] == pytest.approx(corregido, abs=1e-12)
        assert bool(resultado["rechaza_h0_fdr"]) == bool(rechaza)


@pytest.mark.spec
def test_ac4_corregido_mayor_o_igual(mixed_universe):
    """I2: BH nunca hace el veredicto más permisivo."""
    from botcito_core.statistical_validation import screen_universe

    resultados = screen_universe(mixed_universe, _todos_los_pares(mixed_universe), alpha=0.05)

    for resultado in resultados:
        assert resultado["p_value_corregido"] >= resultado["cointegracion"]["p_value"] - 1e-12


@pytest.mark.spec
def test_ac5_pares_independientes_no_pasan(indep_universe):
    """
    190 pares de random walks independientes. Sin corrección pasarían 4 a alpha=0.05
    (p mínimo 0.0182); con BH el corregido mínimo es 0.7313 y no pasa ninguno.
    """
    from botcito_core.statistical_validation import screen_universe

    pares = _todos_los_pares(indep_universe)
    resultados = screen_universe(indep_universe, pares, alpha=0.05)

    validos = [r for r in resultados if r["valido"]]
    assert validos == [], f"falsos positivos tras BH: {[r['par'] for r in validos]}"

    # Y que el test sea informativo: sin corregir sí habría falsos positivos.
    crudos = [r["cointegracion"]["p_value"] for r in resultados]
    assert sum(p < 0.05 for p in crudos) > 0, (
        "si ni los p-values crudos pasan, el test no demuestra que BH sirva de algo"
    )


@pytest.mark.spec
def test_ac6_no_mata_senal_verdadera(mixed_universe, true_pairs):
    """231 pares: 11 rechazos sin corregir, exactamente los 2 construidos con BH."""
    from botcito_core.statistical_validation import screen_universe

    pares = _todos_los_pares(mixed_universe)
    resultados = screen_universe(mixed_universe, pares, alpha=0.05)

    validos = {
        tuple(r["par"].split("/")) for r in resultados if r["valido"]
    }
    assert validos == true_pairs, f"esperados {true_pairs}, obtenidos {validos}"


@pytest.mark.spec
def test_ac7_screen_pair_no_decide(coint_prices):
    """I4: un par aislado no puede emitir veredicto de validez."""
    from botcito_core.statistical_validation import screen_pair

    resultado = screen_pair(coint_prices, "A", "B")

    assert "valido" not in resultado, (
        "la validez requiere conocer el tamaño del universo: debe decidirla screen_universe"
    )
    assert "cumple_filtros_locales" in resultado


@pytest.mark.spec
def test_ac8_monotonia_en_alpha(mixed_universe):
    """I5: los válidos con alpha=0.01 son subconjunto de los de alpha=0.05."""
    from botcito_core.statistical_validation import screen_universe

    pares = _todos_los_pares(mixed_universe)

    def validos(alpha):
        resultados = screen_universe(mixed_universe, pares, alpha=alpha)
        return {r["par"] for r in resultados if r["valido"]}

    assert validos(0.01) <= validos(0.05)


@pytest.mark.spec
def test_ac9_errores_de_entrada(coint_prices):
    from botcito_core.statistical_validation import screen_universe

    with pytest.raises(ValueError):
        screen_universe(coint_prices, [("A", "NO_EXISTE")], alpha=0.05)

    with pytest.raises(ValueError):
        screen_universe(coint_prices, [], alpha=0.05)

    with pytest.raises(ValueError):
        screen_universe(coint_prices, [("A", "B")], alpha=1.5)
