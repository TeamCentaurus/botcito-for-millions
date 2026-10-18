# SPEC-008 — Deduplicar `compute_hedge_ratio`

- **Estado:** Descartada — obsoleta por ADR-0005 (aceptado 2026-10-15, Opción A): el código sobre el que actúa se borra con el pivote
- **Origen:** hallazgo de sesión (no está en `METHODOLOGY.md`)
- **ADRs relacionados:** ninguno
- **Timeframe objetivo:** daily (agnóstico)
- **Archivos afectados:** `src/botcito_core/statistical_validation.py`, `src/botcito_core/spread_calculator.py`

## 1. Problema

`compute_hedge_ratio` y `_kalman_hedge_ratio` están definidas **dos veces**, con
cuerpos idénticos:

| Copia | Ubicación |
|---|---|
| A | `src/botcito_core/spread_calculator.py:6-38` |
| B | `src/botcito_core/statistical_validation.py:96-128` |

Y los consumidores están repartidos entre ambas:

- `model.py:4` → `from botcito_core.statistical_validation import compute_hedge_ratio` (copia **B**)
- `statistical_validation.py:148` (dentro de `screen_pair`) → copia **B**
- La copia **A** no tiene consumidores hoy, pero es la que vive en el módulo cuyo
  nombre corresponde (`spread_calculator`).

Esto es un prerrequisito de otros trabajos, no cosmética: **P1.2 de METHODOLOGY pide
reespecificar el Kalman con state 2D `[α, β]` y calibración EM.** Aplicado a una sola
copia, la otra queda viva y divergente, y `screen_pair` seguiría usando la versión
vieja mientras `model.train` usa la nueva — produciendo hedge ratios distintos para el
mismo par según quién pregunte.

Hallazgo menor en el mismo archivo: `statistical_validation.py:5-8` importa `OLS` y
`add_constant` dos veces.

## 2. Decisión metodológica

Una sola definición, en `spread_calculator.py` — es su lugar semántico: el hedge ratio
es un insumo del cálculo del spread, no un test estadístico.
`statistical_validation.py` la importa.

No se cambia el comportamiento de ninguna de las dos copias en este spec. Es una
deduplicación **sin cambio funcional**, verificable como tal: el hedge ratio de
cualquier entrada debe ser idéntico antes y después.

Nota sobre un bug latente que este spec **no** arregla: `compute_hedge_ratio` declara
`-> float` pero con `method="kalman"` devuelve una `pd.Series`, y con un `method`
desconocido cae por el final de la función y devuelve `None` sin error. Se documenta
aquí y se arregla en el spec de P1.2.

## 3. Contrato

```python
# spread_calculator.py — ÚNICA definición
def compute_hedge_ratio(price_a: pd.Series, price_b: pd.Series,
                        method: str = "ols") -> float | pd.Series: ...

def _kalman_hedge_ratio(price_a: pd.Series, price_b: pd.Series) -> pd.Series: ...
```

```python
# statistical_validation.py — importa, no redefine
from botcito_core.spread_calculator import compute_hedge_ratio
```

**Invariantes:**

- **I1** — Existe exactamente **una** definición de `compute_hedge_ratio` y una de
  `_kalman_hedge_ratio` en todo `src/botcito_core/`.
- **I2** — Sin cambio funcional: para la misma entrada, el valor devuelto es idéntico
  (bit a bit para OLS) al de la copia B antes del cambio.
- **I3** — `botcito_core.statistical_validation.compute_hedge_ratio` y
  `botcito_core.spread_calculator.compute_hedge_ratio` son **el mismo objeto**
  (`is`), no dos funciones equivalentes.
- **I4** — No hay import circular: `spread_calculator` no importa
  `statistical_validation`.

**Errores:** sin cambios en este spec.

## 4. Criterios de aceptación

- **AC1** — I3: `statistical_validation.compute_hedge_ratio is spread_calculator.compute_hedge_ratio`.
- **AC2** — I1: el conteo de `def compute_hedge_ratio` en `src/botcito_core/**/*.py` es
  exactamente 1; igual para `def _kalman_hedge_ratio`.
- **AC3** — I2: para un `cointegrated_pair(beta=2.0)` sintético, el hedge ratio OLS
  devuelto coincide con el valor de referencia (≈ 2.0, tolerancia `0.05`) y es
  reproducible entre llamadas.
- **AC4** — I4: `import botcito_core.spread_calculator` y
  `import botcito_core.statistical_validation` funcionan en cualquier orden, en
  procesos limpios.
- **AC5** — `screen_pair` y `model.train` siguen funcionando end-to-end sobre datos
  sintéticos tras el cambio (test de humo que recorre ambos).
- **AC6** — `statistical_validation.py` no tiene imports duplicados de `OLS` ni de
  `add_constant`.

## 5. Verificación

- **Archivo:** `tests/test_spec_008_dedup.py`
- **Comando:** `uv run pytest tests/test_spec_008_dedup.py -v`

| AC | Test |
|---|---|
| AC1 | `test_ac1_misma_funcion` |
| AC2 | `test_ac2_una_sola_definicion` |
| AC3 | `test_ac3_sin_cambio_funcional` |
| AC4 | `test_ac4_sin_import_circular` |
| AC5 | `test_ac5_humo_screen_pair_y_train` |
| AC6 | `test_ac6_sin_imports_duplicados` |

## 6. Fuera de alcance

- Reespecificar el Kalman (state 2D + EM) → P1.2, `BACKLOG.md`.
- Arreglar el tipo de retorno inconsistente (`float` vs `pd.Series`) y el `None`
  silencioso con `method` desconocido → `BACKLOG.md`, junto con P1.2.
- Validar estabilidad temporal del hedge ratio → `BACKLOG.md`.

## 7. Referencias

Ninguna metodológica: es deuda estructural. El motivo de prioridad es habilitar
P1.2 (Chan, *Algorithmic Trading*, cap. 3) sin dejar una copia divergente.
