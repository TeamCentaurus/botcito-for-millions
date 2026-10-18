# Backlog — pendientes sin spec

Nada de aquí tiene contrato ni criterios de aceptación todavía. Para promover un item,
usar `/spec-new <item>` y escribirlo con `TEMPLATE.md`.

## P1 — mejores metodologías (de `docs/METHODOLOGY.md` §3)

| Item | Archivo | Esfuerzo | Nota |
|---|---|---|---|
| **P1.4** Walk-forward con purging y embargo | `model.py`, `backtest.py` | 1 día | La evolución de SPEC-006. Mayor impacto de los P1 |
| **P1.2** Kalman con state 2D `[α, β]` + calibración EM | `spread_calculator.py` | 4 h | **Requiere SPEC-008 cerrada** o se arregla solo una de las dos copias |
| **P1.3** Triple-barrier method | `backtest.py` | 1 día | Requiere SPEC-005 (necesita PnL en dólares para definir las barreras) |
| **P1.5** Clustering (DBSCAN/jerárquico) antes del screening | `statistical_validation.py` | 4 h | Rinde cuando el universo crezca; reduce `C(N,2)` y alivia SPEC-002 |
| **P1.1** OU + thresholds analíticos (Bertram 2010) | `model.py` | 1 día | Reemplaza el grid search de SPEC-006 por solución cerrada |
| **P1.7** z-score ajustado por GARCH | `spread_calculator.py` | 1 día | Marginal en daily, importante en intraday |
| **P1.6** Cópulas para dependencias no-lineales | nuevo módulo | — | Solo si se amplía a cross-asset |

## Derivados del pivote a factores (ADR-0005, aceptado 2026-10-15)

Vigentes tras aceptar ADR-0005:

- **Elegir `n_factors`** como hiperparámetro validado, no a ojo (SPEC-011 §6).
- **Ampliar el universo (N ≥ 50, idealmente cientos).** Con N ≈ 20–30, PCA filtra
  parte del residuo de las acciones con peso grande en un autovector al
  eigenportafolio: en sintético, corr(residuo estimado, verdadero) mínima 0.84–0.88
  con N = 20, contra 0.945 con N = 50 y 0.975 con N = 100 (SPEC-011, historial de AC2).
  Avellaneda-Lee usan ~1000 acciones. Acompañarlo de higiene de universo (liquidez,
  sobrevivencia) para no meter sesgo de selección.
- **Factores por ETF sectorial** en vez de PCA — la otra variante de Avellaneda-Lee.
- **Factores latentes condicionales / deep learning** (Management Science, Sharpe > 4).
  Requiere características a nivel firma: `openassetpricing.com` da 209 gratis.
- **Re-estimación periódica del modelo de factores.** La literatura reporta que la
  vida útil out-of-sample de un par es ≤ 2 años (`LITERATURE.md` §1); el PCA tiene el
  mismo problema y hoy no hay política de re-ajuste.
- **KPSS junto al ADF** sobre los residuos (hipótesis nulas opuestas; acuerdo entre
  ambos = más confianza).
- **Límites de concentración entre posiciones simultáneas.** Con factores se agudiza:
  varias acciones pueden pedir la misma cobertura.
- **Costo de financiamiento del short.** Con K=5 las piernas cortas se multiplican y
  deja de ser despreciable.
- **Trend following como alternativa** (Hurst-Ooi-Pedersen, 1880–2016, Sharpe 0.76).
  Es otro proyecto, pero tiene la evidencia más fuerte que existe.
- **Validar la pipeline con un par de vínculo estructural** (GOOGL/GOOG o similar):
  hoy no existe en el repo ningún dato real con media-reversión verdadera contra el
  cual verificar SPEC-003/004/005. No sería operable por costos, pero sirve de banco
  de pruebas.

- **Diagnóstico de SPEC-011 sobre datos reales** antes de 012/013 (STATUS §1): EVR
  por factor y distribución de half-life de los residuos acumulados.
- **Decisiones de implementación de SPEC-011 no fijadas por el contrato** (2026-10-17),
  a revisar en `/spec-verify 011`: (1) `fit_factor_model` lanza además `ValueError` si
  algún ticker tiene desviación cero (el contrato no lo pide; dividir por std = 0
  rompería la estandarización); (2) el signo de cada autovector se normaliza para que
  la suma de sus componentes sea ≥ 0 (determinismo; no afecta residuos); (3) std con
  `ddof=1` y EVR = λₖ / traza (traza = N); (4) `compute_factor_returns` y
  `compute_residuals` también rechazan `NaN`.
- **I7 contra `monitoring.py` solo se verifica por identidad con
  `botcito_core.spread_calculator.compute_zscore`**: `monitoring.py` importa
  `from src.spread_calculator import compute_zscore`, que no resuelve. Al refactorizar
  `monitoring.py` debe importar desde `botcito_core.spread_calculator`, o I7 se rompe.
- **Margen de AC2 con N = 20 es chico en el mínimo** (0.84–0.90 sobre seeds 0–5 vs.
  umbral 0.80): refuerza el ítem de ampliar el universo.
- **Hallazgos P1 de `/spec-verify 011`** (2026-10-17, ninguno invalida resultados):
  - `factor_model.py:79` compara `std == 0` exacto: un retorno constante ≠ 0 da std
    ~1e-17 por redondeo, pasa el filtro y su peso en el eigenportafolio es basura
    (−24.8 a +49.6). Usar tolerancia relativa.
  - Se rechaza `NaN` pero no `inf`: `compute_residuals` lo propaga en silencio.
  - `cumulative_residual` trata `NaN` como 0 (cumsum con skipna); `compute_sscore` lo
    propaga.
  - `train_end` no se valida contra el índice: metadata que puede mentir en el artefacto.
  - `FactorModel` es frozen solo en superficie: sus arrays son `writeable=True`.
  - `n_factors=True` se acepta como 1; `n_factors=1.5` lanza `TypeError`, no `ValueError`.
  - I8 coacciona columnas con `str()`: columnas int 0..19 y str "0".."19" pasan como iguales.
  - Columnas duplicadas dan el mensaje "en otro orden".
- **Huecos de cobertura de SPEC-011** (verificados a mano, sin test): I2 para
  `compute_sscore`, I6 (AC7 no llama `compute_sscore`), invarianzas de escala y
  permutación, calidad fuera de muestra, robustez entre seeds (AC2 falla 1/30 con
  código correcto; AC5a llega a +18.7 % en seed 6), casos degenerados.
- **Para SPEC-012: medir half-life fuera de muestra.** Dentro de muestra el residuo
  acumulado está anclado en 0 en ambos extremos (los residuos OLS suman cero), lo que
  sesga la half-life a la baja.

## Decisiones de modelado pendientes

- **Endurecer el rango de half-life** de `1 < hl < 60` (`statistical_validation.py:163`)
  a `5 < hl < 30` según ADR-0002. Cambia qué pares son válidos: es modelado, no
  correctitud. Requiere revalidar el universo.
- **`filter_by_correlation` ignora anti-correlación.** `statistical_validation.py:30`
  filtra `corr >= min_corr` sin valor absoluto, así que descarta pares fuertemente
  negativos que podrían ser tradeables con hedge ratio negativo. Decidir si es
  intencional.
- **Johansen como método por defecto** en `test_cointegration` (SPEC-007 lo deja como
  opción).
- **¿Corregir por FDR también los p-values del ADF?** SPEC-002 corrige solo
  cointegración. Pregunta abierta.
- **Destino de `news_agent.py`** (METHODOLOGY §5.1): filtro veto, feature de un
  meta-modelo, o eliminar. Hoy es código muerto que descarga FinBERT (~400MB) sin
  consumidor.
- **`zscore_window` como hiperparámetro.** SPEC-003 garantiza que backtest y live usan
  la misma ventana, no que la ventana sea la correcta.
- **Tasa libre de riesgo** en el numerador del Sharpe (excess returns).
- **Sharpe con retornos autocorrelacionados.** El spread de un par mean-reverting está
  autocorrelacionado por construcción, así que `√252` es optimista (Lo 2002).
- **Métricas adicionales**: Sortino, Calmar, profit factor, skew/kurtosis, peor trade.
- **Position sizing** distinto de equal-dollar: vol-targeting, Kelly fraccionado.
- **Slippage, market impact y borrow fee del short** en el modelo de costos.
- **Circuit breaker por drawdown** y monitoreo de correlación entre posiciones abiertas.

## Deuda técnica

- **`monitoring.py:4-7` sigue con imports rotos** aunque SPEC-010 ya creó
  `botcito_core/data_loader.py`: el import dice `from src.data_loader`, que no resuelve
  contra el layout actual.
- **`monitoring.py` original:** `from src.data_loader import load_prices`,
  `from src.model import load_model`, `from src.alerts import ... send_alert` — ninguno
  resuelve contra el layout actual (`src/botcito_core/`), y `send_alert` no existe en
  `alerts.py`. Además el módulo ejecuta código al importarse (`schedule.every(...)` y un
  `while True` en el cuerpo), así que no es importable desde un test. Necesario antes de
  operar live.
- **Deps importadas y no declaradas en `pyproject.toml`**: `schedule` (`monitoring.py:2`)
  y `transformers` (`news_agent.py:1`). Ojo: declarar `transformers` arrastra torch
  (~400MB) y el destino de `news_agent` está sin decidir — resolver eso primero.
- **Tipo de retorno inconsistente en `compute_hedge_ratio`**: declara `-> float` pero
  con `method="kalman"` devuelve `pd.Series`, y con un `method` desconocido cae al final
  de la función y devuelve `None` sin error. Va junto con P1.2.
- **`compute_spread` tiene una rama muerta**: `spread_calculator.py:44-46` ramifica por
  `isinstance(hedge_ratio, pd.Series)` y las dos ramas son idénticas.
- **`import` duplicado de `OLS`/`add_constant`** en `statistical_validation.py:5-8`
  (lo limpia SPEC-008, AC6).
- **`README.md` describe una estructura que no existe**: `src/bot_core/`,
  `connectors.py`, `strategies.py`, `utils.py`, `notification_service/` (el real es
  `notifications_service/`), `telegram_bot.py`. También tiene un `# dsdsd` al final.
- **`notifications_service/main.py` es un stub** que imprime "Hello" (METHODOLOGY §5.3).
- **`src/botcito_core/__init__.py` está vacío**: no reexporta nada, así que todos los
  consumidores importan submódulos directamente.
- **`test/` (singular) vacío y sin trackear** — se usa `tests/`. Borrarlo es cosmético.
- **`PairModel` sin `frozen=True`** ni versionado; `save_model` escribe un `.pkl` sin
  metadata de fecha ni de período de entrenamiento.

## Reporting y visualización

Derivados de SPEC-009 y ADR-0004. El contrato del artefacto ya existe, así que cada uno
de estos es trabajo chico:

- **Export a HTML estático** como segundo renderer del artefacto: autocontenido,
  interactivo, sin servidor, compartible como archivo. Es la alternativa a Streamlit
  cuando hay que mandarle un resultado a alguien.
- **Desplegar el dashboard en la VM**: servicio en `docker-compose.yml` + puerto 8501
  en las reglas de IAP (`infra/`), y verlo con `gcloud compute start-iap-tunnel`.
  SPEC-009 es deliberadamente solo-local.
- **`notifications_service` como lector del artefacto**: hoy es un stub que imprime
  "Hello". Con ADR-0004 no recalcula señales: lee la corrida y manda lo que dice.
  Necesita su propio spec.
- **Retención de artefactos**: `runs/` va a crecer. Decidir si se archivan en GCS o se
  rotan.

## Infraestructura

- **Añadir `.github/workflows/tests.yml`** (`uv sync` + `uv run pytest` + `ruff check`)
  cuando se decida commitear `tests/`. Hoy todo el andamiaje SDD es local por decisión
  explícita, y un workflow sin commitear nunca se ejecuta.
- **Correr `ruff` sobre `src/`.** Esta iteración solo lintea `tests/`; `src/` tiene
  hallazgos preexistentes que son material de este backlog.
- **Correlación rodante real** (`returns.rolling(window).corr()`, panel 3D) si alguna
  vez hay un consumidor — SPEC-001 deliberadamente no la implementa.
- **DAGs pendientes**: `dags/data_ingestion.py` y `dags/strategy_inference.py` (hoy solo
  existe `airflow_healthcheck_dag.py`).
