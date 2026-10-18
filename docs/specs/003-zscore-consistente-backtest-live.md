# SPEC-003 — z-score consistente: backtest ≡ live

- **Estado:** Borrador (desbloqueado: ADR-0001 aceptado con Opción A)
- **Origen:** `docs/METHODOLOGY.md` §P0.3 (marcado **crítico**)
- **ADRs relacionados:** ADR-0001 (decide rolling vs estático)
- **Timeframe objetivo:** daily
- **Archivos afectados:** `src/botcito_core/backtest.py`, `src/botcito_core/spread_calculator.py`, `src/botcito_core/types.py`, `src/botcito_core/monitoring.py`

## 1. Problema

Tres cálculos de z-score distintos conviven en el repo:

```python
# model.py:40-41  — guarda estadísticos ESTÁTICOS del training
spread_mean=spread.mean(), spread_std=spread.std(),

# backtest.py:21  — usa los estáticos
zscore = (spread - model.spread_mean) / model.spread_std

# monitoring.py:25  — usa z ROLLING
zscore = compute_zscore(spread, window=model.zscore_window)
```

**El backtest mide una estrategia y producción ejecuta otra.** No es una diferencia de
implementación: son distribuciones de señal distintas, umbrales con significado
distinto y métricas no transferibles. Cualquier Sharpe que reporte `run_backtest` hoy
no describe lo que hará `monitoring.py`.

El `PairModel` (`types.py`) sostiene la ambigüedad: lleva `spread_mean`, `spread_std`
**y** `zscore_window` al mismo tiempo, sin que nada indique cuál manda.

## 2. Decisión metodológica

Definida en **ADR-0001**, aceptado el 2026-10-12 con la **Opción A: rolling en
ambos** — el backtest simula el cálculo rolling causal tal como lo hace el live.

El contrato de abajo implementa esa decisión. `spread_mean` y `spread_std` dejan de ser
insumo de la señal y pasan a ser diagnóstico del training.

## 3. Contrato

```python
# spread_calculator.py — ÚNICA fuente de verdad del z-score
def compute_zscore(spread: pd.Series, window: int) -> pd.Series:
    """
    z-score rolling CAUSAL: en la barra t usa solo las últimas `window`
    observaciones hasta t inclusive. Las primeras (window - 1) barras son NaN.
    `window` pasa a ser obligatorio: no hay default que invite a usar uno distinto
    en backtest y en live.
    """
```

```python
# backtest.py — consume la misma función, no recalcula nada
zscore = compute_zscore(spread, model.zscore_window)
```

`run_backtest` **añade la clave `zscore`** (la `pd.Series` efectivamente usada) al dict
que devuelve. Sin eso, la equivalencia backtest ≡ live no es auditable desde fuera: hay
que poder comparar la serie que usó el backtest contra la que produce el live.

**Invariantes:**

- **I1 (live ≡ backtest)** — Para la misma serie de precios y el mismo `PairModel`, el
  z-score que el backtest usa en la barra `t` es **idéntico** al que el live calcularía
  teniendo datos solo hasta `t`.
- **I2 (causalidad)** — `z_t` no depende de ninguna observación posterior a `t`.
  Modificar precios en `t+1..T` no cambia `z_t`.
- **I3 (warmup)** — Las primeras `window - 1` barras tienen `z = NaN` y **no generan
  señales ni posiciones**. Hoy `run_backtest` no contempla `NaN` porque usa estáticos;
  `generate_signal(NaN, model)` devolvería `NEUTRAL` por cómo encadenan las
  comparaciones, lo cual funciona por accidente, no por diseño.
- **I4** — `backtest.py` no lee `model.spread_mean` ni `model.spread_std` para calcular
  la señal.
- **I5** — `monitoring.py` y `backtest.py` importan `compute_zscore` del mismo módulo.

**Errores:**

- `ValueError` si `window < 2` (la desviación estándar no está definida).
- `ValueError` si `len(spread) < window` (no hay warmup suficiente para una sola señal).

`spread_mean` y `spread_std` **permanecen** en el `PairModel` pero su docstring debe
decir explícitamente que son **diagnóstico del training** (para detectar drift
comparándolos contra los rolling actuales), **no insumo de la señal**. Sin esa nota,
se volverán a usar por error.

## 4. Criterios de aceptación

- **AC1 (I1)** — Simulación live: recorrer la serie barra por barra, llamando
  `compute_zscore` sobre el prefijo `[0..t]` y tomando el último valor. La serie
  resultante es idéntica (`pd.testing.assert_series_equal`) a la que el backtest usa.
- **AC2 (I2)** — Dado un spread sintético, `z_t` calculado sobre la serie completa es
  igual a `z_t` calculado sobre la serie truncada en `t`, para varios `t`.
- **AC3 (I2, destructivo)** — Reemplazar los valores posteriores a `t` por `1e6` no
  cambia `z_t`.
- **AC4 (I3)** — `run_backtest` no abre ninguna posición en las primeras
  `window - 1` barras.
- **AC5 (I4)** — Mutar `model.spread_mean` y `model.spread_std` a valores absurdos
  (`1e9`) **no cambia** ningún resultado de `run_backtest`. Test de comportamiento, no
  de grep: demuestra que la señal ya no depende de ellos.
- **AC6 (I5)** — `monitoring` y `backtest` resuelven `compute_zscore` al mismo objeto.
- **AC7** — `window=1` y `len(spread) < window` lanzan `ValueError`.
- **AC8** — El docstring de `PairModel` documenta `spread_mean`/`spread_std` como
  diagnóstico, no como insumo de señal.

## 5. Verificación

- **Archivo:** `tests/test_spec_003_zscore_consistency.py`
- **Comando:** `uv run pytest tests/test_spec_003_zscore_consistency.py -v`

| AC | Test |
|---|---|
| AC1 | `test_ac1_live_equivale_a_backtest` |
| AC2 | `test_ac2_causalidad_por_truncamiento` |
| AC3 | `test_ac3_futuro_no_afecta_pasado` |
| AC4 | `test_ac4_sin_trades_en_warmup` |
| AC5 | `test_ac5_backtest_ignora_stats_estaticos` |
| AC6 | `test_ac6_misma_funcion_en_live_y_backtest` |
| AC7 | `test_ac7_errores_de_ventana` |
| AC8 | `test_ac8_pairmodel_documenta_diagnostico` |

## 6. Fuera de alcance

- Arreglar los imports rotos de `monitoring.py:4-7` (`from src.data_loader`, etc.).
  Necesario antes de operar live, pero es refactor de módulo, no metodología →
  `BACKLOG.md`.
- Validar `zscore_window` como hiperparámetro (qué ventana es la correcta) →
  `BACKLOG.md`. Este spec solo garantiza que backtest y live usan **la misma**.
- z-score ajustado por GARCH → P1.7, `BACKLOG.md`.

## 7. Referencias

- López de Prado (2018), cap. 11–14 — la divergencia entre el entorno de backtest y el
  de producción como causa principal de backtests no reproducibles en vivo.
- `docs/METHODOLOGY.md` §P0.3 — el hallazgo original, con la tabla de los tres cálculos.
