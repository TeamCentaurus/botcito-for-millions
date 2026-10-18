# Estado del proyecto

Documento de retomada. Si volvés a esto en una semana o un mes, **leé solo este
archivo** y vas a saber dónde estás y qué sigue.

- **Última sesión:** 2026-10-18 (walk-forward de SPEC-011 sobre datos reales, ver §1)
- **Próximo paso:** **compuerta de la fase 1** de [`PLAN_TECNICAS.md`](PLAN_TECNICAS.md): el dueño del modelado revisa y acepta (o corrige) `docs/tecnicas/A-trend-following/PREREGISTRO.md` + ADR-0006 y `docs/tecnicas/B-residuos-ml/PREREGISTRO.md` + ADR-0007. Cada pre-registro termina con su lista de decisiones abiertas. Después: SPEC-005/004 como piezas reutilizables y fase 2 de A
- **Estado de la suite:** `90 passed, 44 xfailed` · `uv run ruff check tests/` limpio
- **Versionado:** todo el andamiaje está commiteado en `main` desde el 2026-10-18
  (push con `[skip ci]` para no disparar el deploy de Airflow). Push a `main` = deploy a
  la VM: usar `[skip ci]` o una rama si no se quiere desplegar

---

## 0. Plan vigente (2026-10-18)

El pre-registro del universo ampliado no pasó (ver §1, "Universo ampliado"). El dueño del
modelado decidió cambiar de técnica: **A — trend following multi-activo** primero,
**B — residuos de factores + señal aprendida** después. Plan, fases, compuertas y reglas
de archivos para trabajo en paralelo: [`PLAN_TECNICAS.md`](PLAN_TECNICAS.md). Rangos
reservados: A → ADR-0006, SPEC-014–019, `docs/tecnicas/A-trend-following/`; B → ADR-0007,
SPEC-020–029, `docs/tecnicas/B-residuos-ml/`.

## 1. Decisión vigente — ADR-0005 aceptado (Opción A)

**2026-10-15: se pivota de pares cointegrados a residuos de un modelo de factores
(PCA, Avellaneda-Lee).** Detalle y razonamiento en
[`adr/0005-pivote-a-residuos-de-factores.md`](adr/0005-pivote-a-residuos-de-factores.md).

Por qué: el pipeline de pares no encontró nada (0/496 y 0/465 pares; con 2,961
observaciones, 22 hits crudos contra ~23 esperados por azar) y la literatura
([`LITERATURE.md`](LITERATURE.md)) documenta el OU-con-thresholds sobre pares como
metodología obsoleta con Sharpe neto negativo. Benchmark objetivo del enfoque nuevo:
**~1.57 de Sharpe neto** (antes del descuento de McLean-Pontiff).

Consecuencias ya aplicadas en los docs:

- **SPEC-007 y SPEC-008 → Descartada.** Sus tests siguen como `xfail` hasta que se
  borre el código de pares; se eliminan junto con él.
- **SPEC-011 → Aceptada** con tests escritos (`tests/test_spec_011_factor_model.py`,
  xfail strict) y generador `factor_panel` en `tests/synthetic.py`. Siguiente paso:
  `/spec-do 011`, y después una corrida de diagnóstico sobre datos reales (varianza
  explicada, half-life de los residuos acumulados).
- **SPEC-012/013** desbloqueadas, siguen en *Borrador*.

### Qué pasó en la sesión del 2026-10-15

1. Se aceptó ADR-0005 (Opción A). 007/008 descartadas.
2. SPEC-011: se corrigieron AC5 y AC10 antes de aceptar (AC5 por ticker era flaky con
   código correcto; AC10 no tenía umbral). Se aceptó.
3. Al escribir los tests, una **implementación de referencia** (descartable, no está
   en `src/`) mostró que AC2 (`≥ 0.90` por ticker) no era cumplible con N = 20:
   mínimo 0.877, mediana 0.96. Causa: PCA con N chico filtra el residuo de las
   acciones con peso grande en un autovector. Se devolvió a Borrador, AC2 pasó a
   mediana `≥ 0.90` + mínimo `≥ 0.80`, y se re-aceptó. Detalle en el historial del
   spec; consecuencia en `BACKLOG.md` (**ampliar el universo a N ≥ 50**).
4. La referencia pasa AC1, AC2 (corregido), AC3, AC5 y AC10 — los ACs son
   cumplibles. AC4, 6, 7, 8, 9 y 11 son de contrato/errores, sin riesgo numérico.

### Diagnóstico 2026-10-17 (SPEC-011 sobre datos reales)

96 large caps de 11 sectores, train 2015-01-05 → 2024-12-31, OOS 2025-01-02 → 2026-10-16
(449 días), K = 5. Página: https://claude.ai/artifact/FRSae1YXZwx8prnMm3CkuE (privada).

- Los factores funcionan: PC1 39 %, K=5 suma 56 %; R² mediano OOS por acción 0.40.
- **Fuera de muestra no hay reversión distinguible del azar**: test de permutación por
  acción sobre el residuo acumulado → 7 con p < 0.05 vs 4.8 esperados, **0 tras BH**.
- **El criterio de half-life en ventanas de 60 días (Avellaneda-Lee) no discrimina**:
  63 % de ventanas reales en (5, 30) vs 65 % con residuos barajados. Consecuencia para
  SPEC-012: el screening necesita nula explícita + BH, no un rango de half-life.
- Potencia con 449 días: OU puro con hl ≤ 15 d se detecta ≥ 78 %; OU mezclado 50/50 con
  camino aleatorio, ~10 %. No se puede descartar reversión débil.
- In-sample (con look-ahead) 5 pasan BH (EOG, KO, MSFT, RTX, SHW), pero con hl 47–56 d.
- Siguiente prueba con más potencia: walk-forward con re-ajuste anual 2016–2026; variante
  de factores por ETF sectorial. Los scripts quedaron en el scratchpad de la sesión y **se
  perdieron** con un reinicio de la PC (WSL limpia `/tmp`); los números de arriba solo
  viven en este archivo y en la página.

### Walk-forward 2026-10-18

Página Streamlit: `uv run streamlit run app/dashboard.py` → "walk forward 011" (lector
puro de `resultado.json`). Script **en el repo**: `research/wf011/walk_forward.py` (precios cacheados en
`data/wf011_precios.parquet`, gitignored; resultado en `research/wf011/resultado.json`;
~8 min). Mismo universo (96), re-ajuste cada 1 de enero con datos estrictamente
anteriores → **2,713 días OOS (2016-01-04 → 2026-10-16)**, s-score de 60 días.

Dos tests contra permutación: **A** por acción (pendiente de ΔX sobre X₋₁, como el
diagnóstico anterior) + BH; **B** IC agregado entre s-score(t) y el residuo acumulado de
t+1..t+h, con la **misma permutación de fechas para todas las acciones** (barajar cada
acción por separado rompe la correlación cruzada y achica la nula: en modo rápido daba
z ≈ −5 donde la nula correcta da −4). Además una señal de juguete (−s normalizado, sin
costos, sin cobertura real de factores — **no es backtest**) para traducir a Sharpe bruto.

| Config | A: BH | B: IC h=5 (z) | Sharpe bruto juguete (p) | Breakeven |
|---|---|---|---|---|
| **K=5, train 252 (A-L, la pre-registrada)** | 0 | −0.003 (+0.6) | **−0.12** (0.82) | — |
| K=5, train expansivo | 0 | −0.025 (−3.5) | 0.53 (0.04) | 4.4 bps |
| K=15, train 504 | 0 | −0.020 (−2.6) | 0.46 (0.22) | 3.3 bps |
| K=5, train 504 | 0 | −0.012 (−0.9) | 0.22 (0.49) | 1.9 bps |
| K=1 / 3 / 10, train 252 | 0 | +0.007 / −0.003 / −0.009 | −0.43 / −0.12 / 0.02 | — |

Lectura:

- **Potencia ya no es la excusa.** B detecta con z ≈ −7 un universo donde el residuo es
  25 % OU (hl 15 d) + 75 % camino aleatorio; esa mezcla daría Sharpe bruto ~2.7. Lo
  observado es un orden de magnitud más chico. A por acción sigue sin potencia (10–20 %
  para mezclas) — **para SPEC-012 el test por acción no sirve; el agregado sí**.
- **Hay reversión débil y real *dentro de cada año*** (IC anual por debajo de su nula en
  8–10 de 11 años, p ≤ 0.01 en todas las configs), pero está compensada por **drift
  persistente del residuo** (alfa/momentum idiosincrático): el IC de muestra completa,
  que es lo operable, es nulo con train 252. Ojo: el IC por año tiene sesgo negativo
  bajo la nula (≈ −0.067 a h=5), compararlo contra 0 inventa señal.
- La única variante con algo (expansiva) **se eligió mirando 7 configs × 4 horizontes**,
  no es un factor común colado (sobrevive a quitar promedio de mercado y de sector), está
  repartida en los 11 sectores y **decae**: Sharpe bruto 0.63 en 2016–20 → 0.28 en
  2021–26. Con 2–5 bps por pierna y la rotación de ~25 %/día de la exposición bruta, más
  las patas de cobertura, queda en ≲ 0.3 neto. Benchmark ADR-0005: 1.57.
- Conclusión: **con 96 large caps, el pipeline Avellaneda-Lee no tiene reversión
  operable 2016–2026.** Lo que queda es del tamaño que McLean-Pontiff predice para una
  anomalía publicada en 2010.

Qué falta decidir (dueño del modelado):

1. **Cerrar la línea de residuos en este universo** y volver a `LITERATURE.md` por otra
   técnica, o
2. **Una última prueba barata**: factores por ETF sectorial (BACKLOG) y/o universo de
   cientos de acciones (A-L usaba ~1,400; N=96 es donde PCA filtra más). Si se hace,
   **pre-registrar** config y test (B con nula conjunta) antes de mirar.
3. Pase lo que pase, SPEC-012 debería usar el test agregado con nula conjunta, no
   half-life en rango ni p-values por acción.

→ Se hizo la opción 2 el mismo día (sección siguiente).

### Universo ampliado + ETF sectorial 2026-10-18 (pre-registrado)

Pre-registro **escrito antes de descargar los datos**: `research/wf_universo/PREREGISTRO.md`.
Script `research/wf_universo/universo.py` (~22 min), resultado en `resultado.json`,
página Streamlit "universo ampliado" (pestañas PCA / ETF sectorial / comparación con 96).

Universo: S&P 500 actual con historia desde 2014 → **455 acciones** (sesgo de
supervivencia declarado: favorece encontrar reversión). Mismo diseño que wf011.
Regla: H1 (PCA K=15) o H2 (ETF del sector, IYR/VOX en vez de XLRE/XLC) pasan si IC a
5 días con p < 0.025 **y** Sharpe bruto de juguete ≥ 1.0 **y** breakeven ≥ 5 bps.

| | p IC h=5 | Sharpe bruto | Breakeven | ¿Pasa? |
|---|---|---|---|---|
| **H1** PCA K=15, train 252 | 0.50 (z 0.0) | +0.04 | 0.3 bps | ❌ |
| **H2** ETF sectorial, train 252 | 1.00 (z **+3.7**) | −0.47 | — | ❌ |

**Ninguna pasa → la regla pre-registrada indica cerrar la línea de residuos para
acciones de EE.UU. en daily** (pendiente: confirmación del dueño del modelado). Potencia: con N = 455, un residuo apenas 10 % OU
(hl 30 d) daría z ≈ −3.4 y Sharpe bruto ≈ 1.5; nada de ese tamaño existe.

Descriptivo (no decide, pero hay que dejarlo escrito):

- **ETF sectorial: el residuo tiene *momentum*, no reversión**, a 5–20 días (z +3.7 a
  +5.1, robusto a quitar mercado y sector). Encontrado a posteriori: no es una
  estrategia, a lo sumo una hipótesis para otro pre-registro.
- **PCA K=15 con ventana expansiva replica lo de wf011**: z −5.9, Sharpe bruto 0.77,
  breakeven 5.5 bps (en 96: 0.53 y 4.4 bps). Es el único patrón que se repite en dos
  universos, pero los universos se solapan, el período es el mismo y no llega al umbral
  económico. Ya no queda período OOS sin mirar: la única prueba limpia sería
  **forward / paper trading** desde hoy.
- Reversión dentro de cada año en todas las configs (z anual hasta −8.7), anulada por
  el drift del residuo: no operable (ver wf011).
- Test A por acción: 43–63 con p < 0.05 vs 22.8 esperadas, **0 tras BH** en todas.

### Cómo retomar

1. ~~`/spec-do 011`~~ — hecho el 2026-10-17 (`src/botcito_core/factor_model.py`,
   `FactorModel` en `types.py`, 11/11 ACs en verde). Verificada el mismo día.
2. **Corrida de diagnóstico** sobre datos reales (antes de 012/013): varianza
   explicada por factor y distribución de half-life de los residuos acumulados. Es
   la primera respuesta a "¿hay reversión en 5–30 días con este enfoque?". Ojo con el
   tamaño del universo (BACKLOG).
3. Recién después: aceptar contratos de **012** (screening) y **013** (backtest) y
   escribir sus tests. Las métricas de trading (Sharpe, PnL) necesitan además
   **004** y **005** para estar bien calculadas.
- La opción B (pares de clases duales) no se adopta como línea de trabajo; queda solo
  como herramienta puntual si hace falta un dato real con media-reversión verdadera.

---

## 2. Qué NO hacer

Tres cosas que parecen razonables y no lo son:

1. **No implementar SPEC-007 ni SPEC-008.** Están descartadas: son trabajo sobre
   `test_cointegration` y `compute_hedge_ratio`, que el pivote borra.
2. **No bajar `alpha` ni saltarse BH-FDR.** Eso devuelve los 16 pares falsos de la
   versión sin corregir (AAPL/BAC, AVGO/MS). Es cómo se pierde dinero con cara de
   rigor.
3. **No agregar más tickers de tech ni pasar a 1-min.** El universo mega-cap tech es
   el peor caso para pairs trading, y `METHODOLOGY.md` §4.2 explica por qué intraday
   es más difícil, no más fácil. ADR-0002 (daily) sigue vigente.

---

## 3. Mapa de la documentación

| Documento | Qué responde |
|---|---|
| **`STATUS.md`** (este) | ¿Dónde estoy y qué sigue? |
| [`METHODOLOGY.md`](METHODOLOGY.md) | ¿Está bien implementado lo que hay? 7 hallazgos P0 + 7 P1 |
| [`LITERATURE.md`](LITERATURE.md) | ¿Vale la pena esta técnica? Qué dice la evidencia científica hoy |
| [`specs/README.md`](specs/README.md) | Índice de specs, ciclo de estados, orden de implementación |
| [`specs/BACKLOG.md`](specs/BACKLOG.md) | Todo lo pendiente que aún no tiene spec |
| [`adr/README.md`](adr/README.md) | Decisiones transversales y su estado |

---

## 4. Estado de cada spec

| # | Título | Estado |
|---|---|---|
| 001 | Correlación: snapshot, no rolling | Borrador |
| 002 | Corrección BH-FDR en el screening | **Implementada** ✅ |
| 003 | z-score consistente backtest ≡ live | Borrador (desbloqueado, ADR-0001 aceptado) |
| 004 | Sharpe anualizado | Borrador |
| 005 | PnL sobre capital invertido | Borrador |
| 006 | Hold-out test tras el tuning | Borrador |
| 007 | Engle-Granger bidireccional / Johansen | Descartada (ADR-0005) |
| 008 | Deduplicar `compute_hedge_ratio` | Descartada (ADR-0005) |
| 009 | Artefacto de resultados + dashboard | **Implementada** ✅ (AC11 bloqueado por 004/005) |
| 010 | Loader de precios | **Implementada** ✅ |
| 011 | Modelo de factores PCA, residuos y s-score | **Verificada** ✅ (2026-10-17) |
| 012 | Screening de residuos con FDR | Borrador (desbloqueado) |
| 013 | Backtest multi-pierna sobre residuos | Borrador (desbloqueado) |

**012 y 013 no tienen tests todavía:** se escriben al aceptar cada contrato.

ADRs: **0001** z-score rolling causal, **0002** daily primero, **0003** retornos por
período sobre capital, **0004** el reporting lee un artefacto — todos aceptados.
**0005** aceptado el 2026-10-15 (Opción A).

### Orden de implementación (vigente)

**011 → 012 → 005 → 004 → 013**, con 003 y 006 detrás. 001 es independiente y de
10 minutos.

---

## 5. Cómo retomar, en concreto

```bash
cd ~/workspace/botcito-for-millions
uv sync
uv run pytest -q                       # debe dar 90 passed, 44 xfailed
uv run ruff check tests/               # debe dar limpio
```

**Ver la última corrida:**

```bash
uv run streamlit run app/dashboard.py  # lee runs/
```

Hay **un** artefacto en `runs/`: `2026-10-13T02-50-39Z.json` (424 KB, 496 pares,
0 modelos, 0 backtests, 6 advertencias). El dashboard muestra la tabla de screening
con p-value crudo y corregido lado a lado, y la sección de detalle dice que no hay
backtests — correcto, no hay par válido.

**Correr el pipeline de nuevo:**

```bash
uv run jupyter lab notebooks/02_pipeline_run.ipynb
```

⚠️ **Dos cosas del notebook:**

1. La corrida del 2015–2026 **quedó a medias**: se ejecutaron las celdas 0-2 (config,
   datos, screening) pero **no** las 3-6, así que su artefacto nunca se escribió. Los
   `execution_count` están desordenados (9, 10, 11, 5, 6, 7). Si querés ese artefacto
   en `runs/`, corré el notebook completo de nuevo.
2. `notebooks/01_selector_pairs.ipynb` está **obsoleto**: usa
   `screen_pair(...)["valido"]`, clave que SPEC-002 eliminó a propósito. Usá el 02.

**Trabajar con los agentes:**

| Comando | Qué hace |
|---|---|
| `/spec-new <hallazgo>` | Escribe un spec nuevo (`spec-author`) |
| `/spec-do <id>` | Implementa un spec *Aceptada* (`spec-implementer`) |
| `/spec-verify <id>` | Audita con experimentos, read-only (`backtest-auditor`) |
| `/review-strategy <ruta>` | Revisión metodológica (`quant-reviewer`) |

Una tarea útil pendiente, en paralelo: **`/spec-verify 002`** y
**`/spec-verify 009`** dan una auditoría de un agente que no escribió ese código.

---

## 6. Lo que se construyó y funciona

- **`screen_universe`** (SPEC-002): BH-FDR sobre el universo. `screen_pair` ya no
  emite veredicto de validez.
- **`reporting.py`** (SPEC-009): artefacto de corrida versionado. Es el contrato
  entre el pipeline y cualquier consumidor (ADR-0004).
- **`data_loader.py`** (SPEC-010): `load_yfinance` + `clean_prices`, con la higiene
  separada de la descarga para que sea testeable sin red.
- **`app/dashboard.py`**: Streamlit local, **lector puro** del artefacto — un test
  sobre su AST verifica que no importe `run_backtest`, `screen_universe` ni `train`.
- **`notebooks/02_pipeline_run.ipynb`**: orquestador, cero lógica en celdas.
- **`tests/synthetic.py`**: generadores con ground truth conocido (OU con half-life
  analítica, pares cointegrados con beta conocido, universos independientes para
  medir falsos positivos, `corrupt_after`/`corrupt_between` para tests de leakage).

Y el dato que justifica haber montado el arnés de specs antes de pivotar: **seis de
los ocho specs originales (001–006) sobreviven íntegros a un cambio completo de
metodología**, porque son sobre look-ahead, multiple testing, consistencia
backtest≡live, unidades de las métricas y hold-out — no sobre la técnica.
