# ADR-0006 — Trend following multi-activo con ETFs (técnica A)

- **Estado:** Propuesta
- **Fecha:** 2026-10-18
- **Specs que dependen:** SPEC-014 a SPEC-018 (rango reservado SPEC-014 a 019, ver
  Consecuencias). Prerrequisitos: SPEC-004 y SPEC-005
- **Origen:** `docs/PLAN_TECNICAS.md` §2; la línea de residuos con s-score lineal no pasó
  su pre-registro (`research/wf_universo/PREREGISTRO.md`, `docs/STATUS.md` §1)
- **Documentos de soporte:** `docs/tecnicas/A-trend-following/LITERATURA.md`,
  `DATOS.md`, `PREREGISTRO.md` (borrador)

## Contexto

Tres pruebas con potencia dicen que el s-score lineal sobre residuos de factores no
predice en acciones de EE.UU. daily 2016–2026. El dueño del modelado decidió probar dos
técnicas nuevas, **A primero**: trend following (time-series momentum) multi-activo.

Lo que dice la evidencia (detalle y verificación en `LITERATURA.md`):

- **A favor:** MOP 2012 (58 futuros, 1985–2009, Sharpe bruto > 1, positivo en los 58);
  HOP 2017 (67 mercados, 1880–2016; **0.77 neto de comisiones 2-y-20** hasta 2013,
  verificado); Babu et al. 2020 (82 instrumentos nuevos fuera de muestra).
- **En contra o matizando:** Kim-Tse-Wald 2016 (el alfa cae de 1.27 % a 0.41 % mensual
  sin escalado por volatilidad); Huang et al. 2020 (evidencia activo por activo débil;
  el t agrupado no pasa bootstrap; rinde parecido a una estrategia de media histórica);
  la industria tuvo 2009–2013 plano y en 2024–25 el peor drawdown de 12 meses de su
  registro (−18.6 %, Man Group).
- **Expectativa realista** para ~29 ETFs, neto de costos: **Sharpe ≈ 0.3** (rango
  0.0–0.6). Su valor es de diversificación, no de Sharpe alto.

Tres hechos de este repo que condicionan la decisión:

1. Los papers usan datos hasta **2016** → **2017–2026 es un test post-publicación** que
   nuestra especificación no tocó (aunque el desempeño de la industria sea público).
2. yfinance da ETFs desde 1993–2007 y futuros continuos desde 2000, pero los futuros
   vienen **sin ajustar por roll y con errores** (`6J=F` con un log-retorno de 2.31;
   `CL=F` con precio negativo). Ver `DATOS.md` §1.
3. Con ~9.75 años de test, un Sharpe verdadero de 0.3 se detecta con **potencia ≈ 24 %**.
   El test refuta mejor de lo que confirma.

## Opciones consideradas

### A — TSMOM canónico (HOP 2017) sobre 29 ETFs, daily, test 2017–2026 pre-registrado

Señal 1/3/12 meses, escalado por vol EWMA, cartera a 10 % de vol, rebalanceo mensual,
costos de ETF (spread por tier de liquidez, préstamo de cortos, margen).

- ✅ Usa la señal de un paper cuya muestra termina justo antes del test.
- ✅ Datos gratis y limpios; es lo que se puede operar desde una cuenta minorista.
- ✅ Rotación baja: los costos, que mataron a los residuos, pesan poco.
- ✅ Reusa el instrumento de evaluación (pre-registro, nula explícita, potencia con
  sintéticos, umbral económico) y piezas del repo (SPEC-009, 010; 004/005 cuando se
  implementen).
- ⚠️ Menos mercados que los papers (29 vs 67) y fricciones de fondeo: Sharpe esperado
  más bajo que el publicado.
- ⚠️ Potencia baja: el resultado más probable aun si funciona es la zona gris.
- ❌ Casi nada de `botcito_core` de pares/residuos sirve (`run_backtest`,
  `compute_zscore`, `screen_universe`, `factor_model`).

### B — Lo mismo con futuros continuos de yfinance

- ✅ Más cerca del paper (sin préstamo ni margen), 7 años más de historia (2000).
- ❌ Rolls sin ajustar y errores de datos: limpiarlos a mano introduce grados de
  libertad del investigador justo donde no queremos tenerlos.
- ❌ No es lo que se operaría.

### C — Futuros reales con datos de pago o del broker

- ✅ Lo más fiel a la literatura; más mercados.
- ❌ Dependencia y costo nuevos, cuenta de futuros, tamaño mínimo de contrato
  incompatible con capital chico. Prematuro antes de saber si la versión ETF muestra
  algo.

### D — No hacer A y pasar directo a B (residuos + señal aprendida, ADR-0007)

- ✅ B es donde el plan ve el Sharpe más alto publicado.
- ❌ B es la técnica con más riesgo de autoengaño y no tiene período de test limpio; A
  es barata, tiene un test post-publicación genuino y responde rápido. El plan ya
  decidió el orden.

## Decisión recomendada

**Opción A**, con el pre-registro de `docs/tecnicas/A-trend-following/PREREGISTRO.md`
aceptado **antes** de escribir código de estrategia. Futuros (B/C) solo si A da zona
verde y se quiere ampliar el universo, con ADR propio.

Al aceptar, el dueño del modelado resuelve las tres decisiones abiertas del
pre-registro: umbral de significancia (recomendado p < 0.05 con zona gris), tope de
apalancamiento (recomendado 2.0×) y long/short vs long/flat (recomendado long/short).

## Consecuencias

### Convivencia con la línea de residuos (B, ADR-0007)

- **Independientes.** A no reemplaza a ADR-0005 ni a ADR-0007, y no depende de ellos.
  Si se aceptan los dos, conviven como líneas separadas con carpetas, specs y research
  propios (`docs/PLAN_TECNICAS.md` §5).
- **Orden:** A se implementa primero. B puede avanzar en paralelo en documentos.
- **Piezas compartidas:** la función de Sharpe (SPEC-004), la convención de retorno por
  período sobre capital (SPEC-005), el artefacto (SPEC-009) y probablemente el bootstrap
  por bloques. Se escriben **una vez** en `botcito_core` y las dos líneas las usan;
  cualquier cambio en esas piezas lo coordina el orquestador.
- **Ninguna línea se usa para "rescatar" a la otra:** un resultado de A no cambia el
  pre-registro de B, ni viceversa.
- Si A y B terminan en verde, la combinación es una decisión nueva (otro ADR), no un
  ajuste.

### Relación con los ADRs vigentes

| ADR | Con A |
|---|---|
| 0001 (z-score rolling causal, idéntico backtest y live) | El z-score no aplica, pero el **principio** se hereda: señal y vol con datos hasta `t`, ejecución en `t+1`, misma función en backtest y live |
| 0002 (daily) | Se cumple: datos diarios, rebalanceo mensual |
| 0003 (retornos por período sobre capital) | Se aplica tal cual; el retorno diario de cartera es la unidad |
| 0004 (el reporting lee un artefacto) | Se aplica; página nueva del dashboard lectora pura |
| 0005 (pivote a residuos) | No se toca. El cierre de la línea de residuos es una decisión aparte, pendiente en `STATUS.md` |

### Specs que dependerían (rango reservado SPEC-014 a 019)

Todos nacen en *Borrador* y quedan **bloqueados hasta que este ADR esté Aceptado**:

| Spec | Contenido | Depende de |
|---|---|---|
| SPEC-014 | Panel multi-activo de ETFs + tasa libre de riesgo (`^IRX`) + tiers de liquidez con datos previos al test | SPEC-010 |
| SPEC-015 | Señal TSMOM 1/3/12 y vol EWMA (centro de masa 60), causal; ACs con sintéticos de tendencia conocida y tests de look-ahead (`corrupt_after`) | SPEC-014 |
| SPEC-016 | Construcción de cartera (target 10 %, covarianza 756 días, tope bruto) y backtest multi-activo con costos, préstamo y margen; retornos por período sobre capital | SPEC-004, SPEC-005, SPEC-015 |
| SPEC-017 | Evaluación: bootstrap estacionario, Ledoit-Wolf ΔSR, nulas secundarias y **análisis de potencia con sintéticos** (generador nuevo en `tests/synthetic.py`) | SPEC-016 |
| SPEC-018 | Artefacto de la corrida (`schema_version` nuevo) y página del dashboard | SPEC-009 |
| SPEC-019 | **Reservado**: generación de señal live/paper trading (DAG de Airflow con cierres diarios). Solo se escribe si el resultado cae en verde o gris | Resultado del pre-registro |

### Costo

Cinco specs de tamaño chico-medio, un módulo nuevo en `botcito_core` (señal y cartera
de trend), un script en `research/trend/` y una página del dashboard. **Cero
dependencias nuevas** (`DATOS.md` §6). La ingesta productiva (Cloud Function de
Twelvedata por minuto) no sirve tal cual para A; recién importa si se llega a SPEC-019.

### Riesgo principal

Que el resultado sea **gris** (lo más probable si el Sharpe verdadero es ~0.3) y la
tentación sea "ajustar un poco" para llevarlo a verde. El pre-registro lo prohíbe
explícitamente; el período 2017–2026 queda consumido con la primera corrida.
