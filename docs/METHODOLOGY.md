# Revisión metodológica — `botcito-for-millions`

Revisión del pipeline cuantitativo en `src/botcito_core/` desde la perspectiva de un ML engineer con background de finanzas. Proyecto personal, no enterprise — la barra es **correcto y robusto**, no production-grade institucional.

> **TL;DR**: La arquitectura conceptual es estándar y razonable (correlación → cointegración → ADF → half-life → spread → z-score → señal). Hay **7 issues P0 de correctitud** que pueden invalidar resultados de backtest si se opera con dinero real, y al menos **7 mejoras P1** que valen el esfuerzo cuando los P0 estén resueltos. La metodología actual sirve para **daily** una vez arreglados los P0; para **1-min** requiere repensar microestructura, costos y latencia desde cero.

---

## 1. Inventario de la metodología actual

| Módulo | Técnica | Rol en el pipeline |
|---|---|---|
| `statistical_validation.compute_correlation_matrix` | Pearson sobre log-returns, ventana fija (`tail(window).corr()`) | Pre-filtro de pares candidatos |
| `statistical_validation.test_cointegration` | Engle-Granger (`statsmodels.tsa.stattools.coint`) | Screening |
| `statistical_validation.test_stationarity_adf` | ADF sobre el spread | Screening |
| `statistical_validation.compute_half_life` | OLS de Δspread sobre spread_lag (proxy de OU) | Screening |
| `statistical_validation.screen_pair` | Orquesta los 4 tests anteriores y emite veredicto | Screening end-to-end |
| `spread_calculator.compute_hedge_ratio` | OLS estático **o** Kalman filter (1D) | Hedge |
| `spread_calculator.compute_spread` | `A - β·B` | Spread |
| `spread_calculator.compute_zscore` | z-score con ventana **rodante** | Señal live |
| `model.train` | `PairModel` con `hedge_ratio`, `spread_mean`, `spread_std` **estáticos** del período de entrenamiento | Training |
| `model.optimize_thresholds` | Grid search 3×3 maximizando Sharpe en validación | Tuning |
| `backtest.run_backtest` | Simulación con `transaction_cost=0.001`, PnL = `pos·Δspread / spread_std − cost` | Evaluación |
| `alerts.generate_signal` | Reglas determinísticas sobre z-score (entry / exit / stop) | Señal |
| `news_agent.FinancialNewsAgent` | FinBERT → score [-1, 1] | **No conectado** al pipeline |
| `monitoring.py` | Loop de `schedule` que carga modelos y dispara alertas | Live (con imports rotos hoy) |

---

## 2. Hallazgos P0 — correctitud

> Estos pueden invalidar los resultados del backtest si quedan sin arreglar. Prioridad antes de cualquier mejora de metodología.

### P0.1 — `compute_correlation_matrix` no es rolling, es estático sobre los últimos N retornos

```python
# statistical_validation.py:11–17
def compute_correlation_matrix(prices: pd.DataFrame, window: int = 252) -> pd.DataFrame:
    returns = np.log(prices / prices.shift(1)).dropna()
    return returns.tail(window).corr()
```

`tail(window).corr()` calcula **una sola matriz** sobre los últimos `window` retornos. No es una rolling correlation. El nombre y el docstring sugieren lo contrario.

**Riesgos:**
- Si el caller pasa `prices` que incluye el período de validación/test → look-ahead inmediato.
- Si confía en que es rolling y lo usa para "ver evolución de la correlación", está leyendo data incorrecta.

**Fix:** renombrar a `compute_correlation_snapshot` y dejar explícito en el docstring que el caller es responsable de pasar solo precios del período de training. Si querían rolling, usar `returns.rolling(window).corr()` (caro: produce un panel 3D) o calcular sobre ventanas no-solapadas.

### P0.2 — Multiple testing sin corrección

`screen_pair` emite veredicto a α=0.05 por par. Con N tickers se generan `C(N,2)` pares; con N=30 son 435 pares; con N=100 son 4,950. A 5% de significancia, ~5% de los pares aparecen "cointegrados" **por puro azar**.

**Fix:** aplicar Benjamini-Hochberg (FDR control) sobre la lista completa de p-values:

```python
from statsmodels.stats.multitest import multipletests
pvals = [r["cointegracion"]["p_value"] for r in results]
reject, pvals_corrected, _, _ = multipletests(pvals, alpha=0.05, method="fdr_bh")
```

BH-FDR es preferible a Bonferroni para este tamaño (Bonferroni es demasiado conservador con miles de tests).

### P0.3 — Inconsistencia entre training, backtest y live

Tres usos distintos del z-score conviven en el código:

| Lugar | Cómo se calcula z |
|---|---|
| `model.train` | `spread_mean = spread.mean()`, `spread_std = spread.std()` sobre el período de entrenamiento (estático) |
| `backtest.run_backtest:21` | `zscore = (spread - model.spread_mean) / model.spread_std` — usa los estáticos del training |
| `monitoring.py:25` | `compute_zscore(spread, window=model.zscore_window)` — z **rolling** |

**Lo que produce el backtest no es lo que pasa en producción.** El live usa stats rolling sobre los últimos `zscore_window` puntos; el backtest usa stats fijas del training. Son estrategias distintas con métricas distintas.

**Fix:** decidir UNA metodología y aplicarla en ambos:

- **Opción A (recomendada para daily)**: rolling en ambos. Backtest debe simular el cálculo rolling tal cual lo hace producción. Más realista, sin riesgo de drift.
- **Opción B**: estático en ambos, pero recalcular periódicamente (re-train mensual / trimestral). El live debe usar los mismos `spread_mean`/`spread_std` que el último training.

Cualquier divergencia entre live y backtest = bug.

### P0.4 — Sharpe ratio no anualizado

```python
# backtest.py:107
sharpe = returns_arr.mean() / returns_arr.std()
```

Esto es Sharpe **por trade**, no anualizado. Para hacer comparable con literatura/benchmarks:

```python
# Para backtest a daily con N trades en T años:
sharpe_anualizado = sharpe_per_trade * np.sqrt(N / T)
# O, si los retornos son por período (no por trade), usar:
# annual_factor = 252 (daily) | 252 * 6.5 * 60 (1-min) | etc.
sharpe_anualizado = (mean_returns_per_period / std_returns_per_period) * np.sqrt(annual_factor)
```

A timeframe minuto, el factor de anualización es ~98,280 (252 días × 6.5 h × 60 min) → diferencia de ×313 en el Sharpe reportado.

### P0.5 — PnL normalizado por `spread_std`, no por capital invertido

```python
# backtest.py:64
pnl = pnl / model.spread_std
```

Esto convierte el PnL a "unidades de desviación estándar del spread", no a unidades monetarias ni a retornos sobre capital invertido. Consecuencias:

- El "PnL total" que reporta el backtest no es interpretable en dólares.
- Los retornos no son comparables con otra estrategia ni con un benchmark.
- El cálculo de Sharpe está distorsionado (numerador y denominador en la misma unidad rara).

**Fix:** cambiar el denominador a notional invertido. Para un trade pair-trading dollar-neutral con $C de capital:

```python
notional_a = C / 2
notional_b = C / 2
shares_a = notional_a / price_a_at_entry
shares_b = notional_b / price_b_at_entry
pnl_dollars = position * (shares_a * (p_a_exit - p_a_entry) - hedge_ratio * shares_b * (p_b_exit - p_b_entry))
ret = pnl_dollars / C
```

### P0.6 — Engle-Granger asimétrico

`coint(price_a, price_b)` regresa A sobre B. Regresar B sobre A da p-value distinto. Algunas de las decisiones de "este par es cointegrado" cambian si invertimos el orden.

**Fix mínimo:** probar ambas direcciones y tomar el menor p-value (con corrección por multiple testing local). **Fix robusto:** reemplazar por test de Johansen, que no necesita elegir variable dependiente:

```python
from statsmodels.tsa.vector_ar.vecm import coint_johansen
res = coint_johansen(prices[[a, b]], det_order=0, k_ar_diff=1)
# res.lr1 (trace stat) y res.cvt (critical values) determinan rank de cointegración
```

### P0.7 — Validación insuficiente: tuning sobre el "test set"

`optimize_thresholds` hace grid search 3×3 sobre el período de validación maximizando Sharpe. **No hay un test hold-out posterior.** El Sharpe reportado puede sobre-ajustar a la grilla — especialmente con N pares × 9 combinaciones = N×9 evaluaciones.

**Fix:** dividir en `train → val → test`. Tunear thresholds en val, **reportar performance final solo en test**. Mejor aún: walk-forward (P1.4).

---

## 3. Hallazgos P1 — mejores metodologías

### P1.1 — Thresholds analíticos vs grid search heurístico

Si modelas el spread como Ornstein-Uhlenbeck:

$$dX_t = \theta(\mu - X_t)\,dt + \sigma\,dW_t$$

existen thresholds óptimos cerrados que maximizan retorno por unidad de tiempo (Bertram 2010). Con costos de transacción `c`:

$$z^*_{entry} \approx 1.0 \cdot (\text{función de } \theta, \sigma, c)$$

Mejor que grid `[1.5, 2.0, 2.5] × [0.0, 0.5, 1.0]` y mucho más robusto a cambios de costos. Implementación de referencia: [hudson-and-thames/arbitragelab](https://github.com/hudson-and-thames/arbitragelab) (open-source) o derivar con `scipy.optimize.minimize_scalar`.

### P1.2 — Kalman filter mal especificado

```python
# spread_calculator.py:29–37
kf = KalmanFilter(
    transition_matrices=[1],
    observation_matrices=price_b.values.reshape(-1, 1, 1),
    initial_state_mean=0,
    initial_state_covariance=1,
    observation_covariance=1,
    transition_covariance=0.01
)
```

Problemas:
1. El state vector es 1D (solo slope, sin intercept) → asume que la relación es `A_t = β_t · B_t + ruido`, sin término constante. En la práctica casi siempre hay intercept.
2. `transition_covariance=0.01` es arbitrario. Controla cuán rápido cambia β en el tiempo. Un valor mal calibrado da β o demasiado lento (efectivamente OLS) o demasiado ruidoso.
3. `observation_covariance=1` también arbitrario.

**Fix (referencia: Chan, *Algorithmic Trading*, cap. 3):**

```python
# State 2D: [intercept, slope]
obs_mat = np.vstack([np.ones(len(price_b)), price_b.values]).T[:, np.newaxis, :]
kf = KalmanFilter(
    n_dim_state=2,
    transition_matrices=np.eye(2),
    observation_matrices=obs_mat,
    initial_state_mean=[0, 0],
    initial_state_covariance=np.eye(2),
)
# Calibrar covarianzas con EM
kf = kf.em(price_a.values, n_iter=10, em_vars=["transition_covariance", "observation_covariance"])
state_means, _ = kf.filter(price_a.values)
intercept_t = state_means[:, 0]
beta_t = state_means[:, 1]
spread_t = price_a.values - intercept_t - beta_t * price_b.values
```

### P1.3 — Triple-barrier method (López de Prado) para backtest

En lugar de cerrar solo cuando `|z| < exit` o `|z| > stop`, define **tres barreras** sobre el PnL (no sobre z):

- **Profit-take**: cerrar si PnL > X% del capital.
- **Stop-loss**: cerrar si PnL < -Y%.
- **Time barrier**: cerrar si pasan T períodos sin tocar las anteriores.

Produce labels balanceados, evita posiciones que se quedan abiertas indefinidamente, y es la forma estándar moderna de evaluar mean-reversion. Ver *Advances in Financial Machine Learning*, cap. 3.

### P1.4 — Walk-forward con purging y embargoing

Reemplazar el split estático por walk-forward:

```
[train 1 año] → [val 3m] → [test 1m] → avanzar 1 mes →
[train 1 año] → [val 3m] → [test 1m] → ...
```

Y **purgar** observaciones cerca de la frontera entre train y test (cuando hay overlap por etiquetado/ventanas), **embargar** un período corto post-test antes de incluir esa data en el siguiente train. Detalle: López de Prado, cap. 7.

Para pairs trading sin etiquetas overlapping, purging puede ser suficiente con embargo = 0.

### P1.5 — Clustering antes del screening

Con N=100 tickers, screen 4,950 pares es caro y dispara multiple testing. Mejor:

1. Calcular distancia `d_ij = 1 - |corr_ij|` entre log-returns.
2. Aplicar DBSCAN o jerárquico → clusters de tickers similares.
3. Solo testear cointegración **dentro de clusters**.

Reduce O(N²) a `Σ |C_k|²` con `|C_k| << N`. Referencia: Krauss (2017), Sec. 4.

### P1.6 — Copulas para dependencias no-lineales

Si A y B no son linealmente comóvidos (típico cross-asset: una acción y un commodity), OLS subestima la relación y el spread parece errático. Modelar la cópula `C(u, v)` empírica → "spread copular" basado en cuantiles condicionales. Trade entry cuando `P(U_A < u | U_B = v) < α` o > 1-α.

Referencia: Liew & Wu (2013).

### P1.7 — GARCH para z-score adaptativo a volatilidad

Cuando la volatilidad del spread cambia con el tiempo (regímenes), z-score con std rolling subestima/sobreestima en transiciones. Estimar `σ_t` con GARCH(1,1):

```python
from arch import arch_model
am = arch_model(spread.diff().dropna(), vol="Garch", p=1, q=1)
res = am.fit(disp="off")
sigma_t = res.conditional_volatility
z_t = (spread - mu_t) / sigma_t  # mu_t puede ser EWMA o Kalman
```

Mejora marginal en daily, importante en intraday.

---

## 4. Decisión por timeframe

### 4.1 Daily / End-of-day

La metodología actual está **aceptablemente cerca** de la práctica estándar **una vez arreglados los P0**.

Recomendación:
- Resolver P0.1 a P0.7.
- Adoptar walk-forward (P1.4) — esfuerzo medio, impacto alto.
- Considerar OU + thresholds analíticos (P1.1) — esfuerzo medio, robustece la lógica de entry/exit.
- Ignorar microestructura: a daily, el bid-ask spread es noise irrelevante vs movimientos diarios.
- Costos de 0.1% por leg son razonables para retail con broker low-cost (IBKR, Schwab).
- Half-life esperada: 5–30 días. Filtro razonable: `1 < half_life < 60`.

### 4.2 Minute / 1-min

La metodología actual **no aplica directamente**. Razones:

#### Microestructura
A 1-min, la varianza del precio está dominada por **bid-ask bounce**: el "close" alterna entre bid y ask aunque el mid no se mueva. Resultado: se inflan estadísticos de varianza, ADF rechaza estacionariedad espuriamente, y los z-scores producen señales falsas.

Fix: usar mid-price o `(open + close) / 2` como proxy. Twelvedata 1-min OHLCV no da bid/ask — necesitas un feed L1 (Polygon, Alpaca, IEX) o aceptar la limitación y subir a 5-min/15-min.

#### Half-life en minutos ≠ half-life en días

Pares cointegrados a daily típicamente **no** lo están a minutos (la cointegración no se preserva bajo agregación temporal de forma trivial). Hay que re-screen específicamente con datos intraday. Filtro razonable: `30 < half_life_minutos < 240` (entre 30 min y 4 h).

#### Costos amplificados

Con turnover alto (varias entradas/salidas por día por par), 0.1% por leg destruye Sharpe rápido. Costo realista intraday:

- **Comisión**: 0.005% (broker low-cost, USD).
- **Bid-ask spread**: típicamente 0.01%–0.05% para large-caps líquidas, mucho más para small-caps. Es el costo dominante.
- **Slippage**: 0.005%–0.02% si tu orden es <5% del volumen.
- **Total round-trip**: 0.05%–0.20% típico para large-caps.

Si tu Sharpe pre-costos no excede ~3, los costos te lo bajan a algo no operable.

#### Latencia inherente

La Cloud Function ya marca `is_late` y `lateness_seconds`, pero `monitoring.py` no los usa. A 1-min, el dato llega 30–90s tarde por construcción (Twelvedata API + Pub/Sub + Cloud Function). El backtest debe simular esa latencia: la señal generada en `t` se ejecuta a `t + delay`.

#### Throughput

Cron `*/1 9-16 * * 1-5` (cada minuto 9–16 hora Lima, lun-vie) con timeout de 50s. Para 1 ticker AAPL es OK; para 100+ tickers vas a hacer una llamada batch a Twelvedata por minuto y excederás rate limits del plan gratuito.

#### Recomendación

Si quieres operar a 1-min:
1. **Re-derivar todo el screening con datos intraday**, no asumir que los pares daily-cointegrados sirven.
2. **Modelar costos de microestructura realistas** o pasar a 5-min / 15-min donde los costos son manejables.
3. **Simular latencia** en el backtest.
4. **Antes de invertir tiempo en 1-min, hacer la pregunta honesta**: ¿tu edge es realmente de microestructura o estás overfiteando ruido? La estadística sugiere que muy pocas estrategias retail funcionan a <5-min.

**Recomendación pragmática para proyecto personal**: empezar con daily, validar que la pipeline produce Sharpe positivo out-of-sample y P&L interpretable, **después** considerar mover a intraday. Tener el dato a 1-min en GCS no obliga a operar a 1-min — puedes resamplearlo a daily/hourly.

---

## 5. Brechas de integración (no estrictamente metodológicas)

### 5.1 `news_agent.py` (FinBERT) está desconectado del pipeline

Calcula sentimiento pero ningún módulo lo importa. Decidir:

- **(a) Filtro veto** (low-effort, alto upside conceptual): no entrar en una posición si el sentimiento sobre los tickers del par es fuertemente contrario a la dirección.
- **(b) Feature de un meta-modelo** (high-effort): entrenar un clasificador binario "esta señal de z-score cierra con PnL > 0" usando como features `z_score`, `half_life_actual`, `sentimiento_a`, `sentimiento_b`. Es el "secondary model" de López de Prado (cap. 3).
- **(c) Eliminar** si no se demuestra valor: tener código muerto que descarga FinBERT en cada inicialización (~400MB) sin uso es deuda técnica.

### 5.2 `monitoring.py` tiene imports rotos

`from src.data_loader import load_prices`, `from src.model import load_model`, `from src.alerts import ...` — esos paths no existen en el layout actual (`src/botcito_core/`). Ya documentado en `CLAUDE.md`. Es código por refactorizar antes de operar live.

### 5.3 `notifications_service` es un stub

`src/notifications_service/main.py` solo imprime "Hello". El plan del README menciona Telegram. Diseño pendiente.

---

## 6. Recomendaciones priorizadas

| Prioridad | Item | Archivo | Esfuerzo | Impacto |
|---|---|---|---|---|
| P0 | Renombrar `compute_correlation_matrix` → `compute_correlation_snapshot` y aclarar docstring | `statistical_validation.py` | 10 min | Alto |
| P0 | Aplicar BH-FDR sobre p-values de cointegración en screening | `statistical_validation.py` | 1 h | Alto |
| P0 | Decidir z-score estático vs rolling y aplicar consistente en backtest + live | `backtest.py`, `monitoring.py` | 2 h | Crítico |
| P0 | Anualizar Sharpe en `run_backtest` | `backtest.py` | 30 min | Medio |
| P0 | Cambiar denominador de PnL de `spread_std` a notional invertido | `backtest.py` | 1 h | Alto |
| P0 | Test hold-out post-`optimize_thresholds` | `model.py` | 2 h | Alto |
| P0 | Engle-Granger en ambas direcciones, o pasar a Johansen | `statistical_validation.py` | 2 h | Medio |
| P1 | Walk-forward con purging | `model.py`, `backtest.py` | 1 día | Alto |
| P1 | Reformular Kalman con state 2D `[α, β]` y EM | `spread_calculator.py` | 4 h | Medio |
| P1 | Triple-barrier method en backtest | `backtest.py` | 1 día | Medio |
| P1 | Clustering (DBSCAN) antes del screening | `statistical_validation.py` | 4 h | Medio (cuando N crezca) |
| P2 | OU + thresholds analíticos (Bertram 2010) | `model.py` | 1 día | Medio |
| P2 | GARCH-adjusted z-score | `spread_calculator.py` | 1 día | Bajo–Medio |
| P2 | Decidir destino de `news_agent` (veto / feature / eliminar) | `news_agent.py` | conversación | Bajo |
| — | Arreglar imports rotos en `monitoring.py` | `monitoring.py` | 30 min | Necesario antes de live |

---

## 7. Referencias

### Libros canónicos

- **Vidyamurthy** (2004), *Pairs Trading: Quantitative Methods and Analysis* — clásico del enfoque de cointegración.
- **Chan** (2013), *Algorithmic Trading: Winning Strategies and Their Rationale* — Kalman para hedge ratio dinámico (cap. 3), implementaciones MATLAB/Python.
- **López de Prado** (2018), *Advances in Financial Machine Learning* — walk-forward con purging/embargo (cap. 7), triple-barrier (cap. 3), fractional differentiation (cap. 5), backtesting honesto (cap. 11–14).

### Papers

- **Engle & Granger** (1987), *Co-integration and Error Correction*, Econometrica 55(2) — el paper original.
- **Johansen** (1991), *Estimation and Hypothesis Testing of Cointegration Vectors*, Econometrica 59(6) — test multivariado.
- **Bertram** (2010), *Analytic Solutions for Optimal Statistical Arbitrage Trading*, Physica A 389 — thresholds OU cerrados.
- **Leung & Li** (2015), *Optimal Mean Reversion Trading: Mathematical Analysis and Practical Applications* — extensiones modernas.
- **Liew & Wu** (2013), *Copula-based Pairs Trading Strategy*, Applied Financial Economics 23(20) — cópulas.
- **Krauss** (2017), *Statistical Arbitrage Pairs Trading Strategies: Review and Outlook*, *Journal of Economic Surveys* 31(2) — survey moderno y exhaustivo.
- **Benjamini & Hochberg** (1995), *Controlling the False Discovery Rate*, JRSS-B 57(1) — FDR para multiple testing.

### Software open-source de referencia

- [`statsmodels`](https://www.statsmodels.org/) — `coint`, `coint_johansen`, `adfuller`, `multipletests`.
- [`pykalman`](https://pykalman.github.io/) — Kalman filter con calibración EM (`KalmanFilter.em()`).
- [`arch`](https://arch.readthedocs.io/) — modelos GARCH.
- [`hudson-and-thames/arbitragelab`](https://github.com/hudson-and-thames/arbitragelab) — implementaciones de Bertram, copulas, Johansen, walk-forward para pairs trading.
