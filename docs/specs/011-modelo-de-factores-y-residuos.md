# SPEC-011 — Modelo de factores PCA, residuos y s-score

- **Estado:** Verificada ✅ (2026-10-17) — §3 y §4 congelados
- **Aceptada por:** Leonel (dueño del modelado), 2026-10-15 — re-aceptada tras corregir AC2
- **Historial:** aceptada 2026-10-15 → devuelta a Borrador el mismo día porque AC2
  (`≥ 0.90` por ticker) no era cumplible con N = 20 aunque la implementación fuera
  correcta: una referencia de Avellaneda-Lee sobre `factor_panel(seed=0)` dio mediana
  0.96 y mínimo 0.877 (seeds 1–5: mínimo 0.84–0.90); el mínimo sube a 0.945 con N = 50
  y 0.975 con N = 100. AC2 pasó a mediana `≥ 0.90` + mínimo `≥ 0.80` y se re-aceptó.
  → Implementada 2026-10-17: los 11 ACs en verde (`seed=0`: EVR 0.587 + 0.139,
  corr. residuo mediana 0.961 / mínimo 0.877, mediana half-life acumulado 7.08 vs
  6.93 teórica, half-life crudo máx. 0.69; AC10 EVR[0] = 0.063 vs techo 0.078).
  → Verificada 2026-10-17 (`backtest-auditor`): causalidad bit a bit en 25 escenarios
  de `corrupt_after`; invarianza a escala, escala por ticker y permutación ≤ 1.8e-15;
  coincide con referencia SVD + statsmodels a 8.9e-17; sobre ruido puro ningún ticker
  con half-life en (5, 30). AC2 falla en 1 de 30 seeds (seed 26, mínimo 0.795) con
  código correcto — filtración de PCA con N = 20, no bug. Hallazgos P1 en `BACKLOG.md`.
- **Origen:** `docs/LITERATURE.md` §3.2 — Avellaneda & Lee (2010)
- **ADRs relacionados:** ADR-0005 (el pivote), ADR-0001 (z-score rolling causal), ADR-0002 (daily)
- **Timeframe objetivo:** daily
- **Archivos afectados:** `src/botcito_core/factor_model.py` (nuevo), `src/botcito_core/types.py`

## 1. Problema

El repo busca pares cointegrados y no encuentra ninguno: **0 de 465 pares** con 2,961
observaciones, con 22 hits crudos contra ~23 esperados por azar (ADR-0005). Y la
literatura reciente reporta que el modelo paramétrico OU-con-thresholds que
implementa `botcito_core` tiene **Sharpe neto negativo** después de costos
(`LITERATURE.md` §3.2).

El enfoque de factores ataca la causa: en vez de apostar a que existe **un** socio
para cada acción, construye el activo de comparación con **toda la sección cruzada**.
Un par cointegrado es el caso particular de 1 factor con 2 activos.

```
hoy:     spread_ij = precio_i − β · precio_j              (2 activos)
SPEC-011: residuo_i = retorno_i − αᵢ − Σₖ βᵏᵢ · Fₖ        (N activos, K factores)
```

## 2. Decisión metodológica

Definida en **ADR-0005**. Se implementa el pipeline de **Avellaneda & Lee (2010)**:
PCA sobre la matriz de correlación de retornos → eigenportafolios → regresión de cada
acción contra los K primeros → residuo idiosincrático → **residuo acumulado** →
s-score.

### El detalle que decide si esto funciona

> **El proceso que se modela como media-reverting es el residuo ACUMULADO
> `X(t) = Σ_{s≤t} ε(s)`, no el residuo `ε(t)`.**

Los residuos de un modelo de factores son aproximadamente ruido blanco: no tienen
nada que revertir. Lo que revierte es su suma acumulada. Implementar el s-score sobre
`ε(t)` directamente produce una estrategia que no funciona **y cuyo bug es
invisible** — el código corre, el z-score se calcula, las señales se emiten, y todo
es ruido. Por eso hay un AC dedicado a esta trampa (AC5).

### Lo que se hereda gratis

El **s-score es el z-score rolling causal del residuo acumulado**, así que se calcula
con la misma `compute_zscore` que usa el live. **ADR-0001 se hereda tal cual**: la
consistencia backtest≡live que decidimos para pares vale sin cambios para residuos.

## 3. Contrato

```python
# types.py
@dataclass(frozen=True)
class FactorModel:
    """
    Modelo de factores estimado sobre UN período de entrenamiento.

    `loadings`, `intercepts`, `eigenvectors`, `return_means` y `return_stds` son
    parámetros del training y NO se re-estiman para evaluar: proyectar con ellos es
    lo que hace que el residuo fuera de muestra no tenga look-ahead.
    """
    tickers: tuple[str, ...]
    n_factors: int
    eigenvectors: np.ndarray             # (n_tickers, n_factors)
    loadings: np.ndarray                 # (n_tickers, n_factors) — betas de la regresión
    intercepts: np.ndarray               # (n_tickers,)
    return_means: np.ndarray             # (n_tickers,) del training
    return_stds: np.ndarray              # (n_tickers,) del training
    explained_variance_ratio: np.ndarray # (n_factors,)
    train_end: str
```

```python
# factor_model.py
def fit_factor_model(returns: pd.DataFrame, n_factors: int = 5,
                     train_end: str | None = None) -> FactorModel:
    """
    1. Estandariza los retornos con media y desviación del período recibido.
    2. PCA sobre la matriz de correlación → `n_factors` autovectores.
    3. Construye los eigenportafolios con pesos  Qᵏᵢ = vᵏᵢ / stdᵢ.
    4. Regresa cada acción contra los K retornos de eigenportafolio (OLS con
       intercepto) y guarda `loadings` e `intercepts`.

    El caller es responsable de pasar SOLO retornos del período de entrenamiento.
    """

def compute_factor_returns(model: FactorModel, returns: pd.DataFrame) -> pd.DataFrame:
    """Retornos de los K eigenportafolios: Fₖ(t) = Σᵢ Qᵏᵢ · Rᵢ(t).  (T, n_factors)"""

def compute_residuals(model: FactorModel, returns: pd.DataFrame) -> pd.DataFrame:
    """
    Residuo idiosincrático por acción, PROYECTANDO con los parámetros del modelo:
        εᵢ(t) = Rᵢ(t) − αᵢ − Σₖ βᵏᵢ · Fₖ(t)
    Nunca re-estima. (T, n_tickers)
    """

def cumulative_residual(residuals: pd.DataFrame) -> pd.DataFrame:
    """Suma acumulada de los residuos: el proceso que se modela como OU."""

def compute_sscore(cumulative: pd.DataFrame, window: int) -> pd.DataFrame:
    """
    s-score: z-score rolling causal del residuo acumulado, columna por columna,
    delegando en `botcito_core.spread_calculator.compute_zscore` para que el cálculo
    sea literalmente el mismo que usa el live (ADR-0001).
    """
```

**Invariantes:**

- **I1 (sin look-ahead)** — `compute_residuals` proyecta con los parámetros
  almacenados y **nunca re-estima**. El residuo en `t` depende solo de los retornos
  en `t` y del modelo.
- **I2 (causalidad)** — Modificar retornos posteriores a `t` no cambia el residuo ni
  el residuo acumulado en `t`. (El s-score hereda la causalidad de `compute_zscore`.)
- **I3 (ortogonalidad en muestra)** — Sobre el período de entrenamiento,
  `|corr(εᵢ, Fₖ)| < 1e-8` para todo `i, k`: es la condición de primer orden de OLS.
  Si falla, la regresión está mal.
- **I4 (varianza explicada)** — `explained_variance_ratio` es decreciente, todos sus
  elementos están en `[0, 1]` y su suma es `≤ 1`.
- **I5 (el OU es el acumulado)** — `compute_half_life` sobre el residuo acumulado
  recupera la half-life diseñada; sobre el residuo crudo **no**: los incrementos de un
  OU tienen autocorrelación ≈ −θ/2, así que la half-life estimada cae por debajo de
  1 día (≈ 0.66 con θ = 0.1), fuera del rango tradeable `5 < hl < 30` de ADR-0002.
  Es la trampa de §2.
- **I6 (función pura)** — Ninguna de las cuatro funciones muta su entrada.
- **I7 (una sola fuente del z-score)** — `compute_sscore` resuelve `compute_zscore`
  al mismo objeto que usa `monitoring.py`.
- **I8 (alineación)** — Las columnas de `returns` tienen que coincidir con
  `model.tickers`, en el mismo orden.

**Errores:**

- `ValueError` si `n_factors < 1` o `n_factors >= n_tickers` (con K = N el residuo es
  idénticamente cero).
- `ValueError` si hay menos de `10 * n_factors` observaciones (la regresión no es
  informativa).
- `ValueError` si `returns` tiene `NaN` (el loader de SPEC-010 ya garantiza que no).
- `ValueError` si las columnas de `returns` no coinciden con `model.tickers` (I8),
  nombrando la diferencia.

## 4. Criterios de aceptación

Requieren un generador nuevo en `tests/synthetic.py`:

```python
def factor_panel(n_tickers=20, n_factors=2, n=1000, varianza_factores=0.7,
                 theta=0.1, seed=0) -> tuple[pd.DataFrame, dict]:
    """Retornos de N acciones generados por K factores + OU idiosincrático.
    Devuelve el panel y el ground truth: factores, betas, residuos verdaderos."""
```

- **AC1 (I4)** — Con un panel de `n_factors=2` y 70 % de varianza en los factores,
  `fit_factor_model(..., n_factors=2)` devuelve `explained_variance_ratio`
  decreciente, en `[0,1]`, con suma `≤ 1`, y los dos primeros capturan ≥ 60 % de la
  varianza total.
- **AC2 (ground truth)** — Sobre el panel de AC1, la correlación entre el residuo
  estimado y el residuo verdadero del generador tiene **mediana `≥ 0.90`** entre
  tickers y **mínimo `≥ 0.80`**. No se exige `≥ 0.90` por ticker: con N = 20, una
  acción con peso grande en un autovector filtra su propio residuo al
  eigenportafolio y la regresión se lo quita (propiedad de PCA con N chico, ver nota
  de devolución). El test mide el régimen de universo que el proyecto usa de verdad.
- **AC3 (I3)** — En el período de entrenamiento,
  `max |corr(residuo_i, factor_k)| < 1e-8`.
- **AC4 (I1 e I2)** — Ajustando el modelo hasta `t` y corrompiendo los retornos
  posteriores a `s` con `corrupt_after`, el residuo y el residuo acumulado en `s`
  son **idénticos** a los de los datos originales.
- **AC5 (I5 — la trampa)** — Sobre el panel de AC1 (`n_tickers=20`, `n=1000`,
  `theta=0.1`, `seed=0`):
  - (a) la **mediana entre tickers** de `compute_half_life` sobre el **residuo
    acumulado** está dentro de ±20 % de `ln(2)/theta`;
  - (b) para **todo** ticker, `compute_half_life` sobre el **residuo crudo** queda
    **fuera** del rango tradeable de ADR-0002 (`5 < hl < 30` días; `inf` también
    cuenta como fuera).

  El test afirma **ambas** cosas: sin (b), nada impide implementar el s-score sobre
  la serie equivocada. Se usa la mediana y no cada ticker porque el estimador AR(1)
  tiene ≈ ±14 % de error a 1σ con n = 1000: sobre 20 OU *verdaderos* (sin error de
  estimación de factores), 3 de 20 caen fuera de ±20 %, mientras la mediana queda a
  1.2 % (simulación del 2026-10-15). Un AC por ticker fallaría con código correcto.
- **AC6 (I7)** — `factor_model.compute_zscore is spread_calculator.compute_zscore`,
  y `compute_sscore` sobre una columna coincide con `compute_zscore` aplicado a esa
  columna.
- **AC7 (I6)** — `returns` queda idéntico tras las cuatro llamadas.
- **AC8** — `n_factors=0`, `n_factors=n_tickers`, y un panel con 15 observaciones y
  `n_factors=5` lanzan `ValueError`.
- **AC9 (I8)** — `returns` con columnas en otro orden o con un ticker distinto lanza
  `ValueError` nombrando la diferencia.
- **AC10 (robustez)** — Con un panel de retornos **independientes** (sin estructura
  de factores; `n_tickers=20`, `n=1000`, `seed=0`),
  `explained_variance_ratio[0] < 1.2 · (1 + √(N/T))² / N`: el modelo no inventa
  factores donde no hay. El techo es el borde superior de Marchenko-Pastur para el
  autovalor de una matriz de correlación de ruido puro, con 20 % de margen. No se
  compara contra `1/N` a secas porque con N=20, T=1000 el ruido solo ya da ≈ 0.064
  contra 0.05 (simulación del 2026-10-15); el umbral resultante es ≈ 0.078, y un
  panel con un factor real del 70 % lo supera holgadamente.
- **AC11** — `FactorModel` es `frozen` y `dataclasses.asdict` sobre él es
  serializable por `reporting._to_native` (lo necesita el artefacto v2).

## 5. Verificación

- **Archivo:** `tests/test_spec_011_factor_model.py`
- **Comando:** `uv run pytest tests/test_spec_011_factor_model.py -v`

| AC | Test |
|---|---|
| AC1 | `test_ac1_varianza_explicada` |
| AC2 | `test_ac2_recupera_residuo_verdadero` |
| AC3 | `test_ac3_ortogonalidad_en_muestra` |
| AC4 | `test_ac4_sin_look_ahead` |
| AC5 | `test_ac5_el_ou_es_el_acumulado` |
| AC6 | `test_ac6_sscore_usa_compute_zscore` |
| AC7 | `test_ac7_no_muta_input` |
| AC8 | `test_ac8_errores_de_dimension` |
| AC9 | `test_ac9_tickers_desalineados` |
| AC10 | `test_ac10_no_inventa_factores` |
| AC11 | `test_ac11_serializable` |

## 6. Fuera de alcance

- **Cuántos factores usar.** `n_factors` es hiperparámetro; validarlo es trabajo de
  SPEC-012 y del hold-out de SPEC-006. Avellaneda-Lee usan ~15 sobre un universo
  amplio; con 30 tickers, 3–5 es el orden razonable.
- **Factores por ETF sectorial** (la otra variante de Avellaneda-Lee) →
  `BACKLOG.md`.
- **Factores latentes condicionales / deep learning** → `BACKLOG.md`. Necesitan
  características a nivel firma (`openassetpricing.com`) y están fuera del alcance de
  un proyecto personal por ahora.
- **Screening de residuos** → SPEC-012.
- **Backtest multi-pierna** → SPEC-013.
- **Re-estimación periódica del modelo** (cada cuánto re-ajustar el PCA) →
  `BACKLOG.md`. Relacionado con el hallazgo de que la vida útil de un par es ≤ 2 años
  (`LITERATURE.md` §1).

## 7. Referencias

- **Avellaneda & Lee (2010)**, *Statistical Arbitrage in the US Equities Market*,
  Quantitative Finance 10(7) — el pipeline que implementa este spec: PCA,
  eigenportafolios, residuo acumulado, s-score.
- **Guijarro-Ordóñez, Pelger & Zanotti**, *Deep Learning Statistical Arbitrage*,
  Management Science — la versión moderna del mismo esquema, con factores latentes
  condicionales en vez de PCA.
- `docs/LITERATURE.md` §3.2 — por qué este enfoque y no el de pares.
