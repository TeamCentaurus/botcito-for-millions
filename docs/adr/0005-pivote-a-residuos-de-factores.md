# ADR-0005 — Pivote de cointegración por pares a residuos de un modelo de factores

- **Estado:** Aceptada ✅
- **Decidido por:** Leonel (dueño del modelado), 2026-10-15 — Opción A
- **Fecha:** 2026-10-12
- **Specs que dependen:** SPEC-011, SPEC-012, SPEC-013. Deja obsoletas SPEC-007 y SPEC-008
- **Origen:** `docs/LITERATURE.md` + dos corridas empíricas sin resultados

## Contexto

Hay dos clases de evidencia apuntando al mismo lado.

### Empírica, de este repo

| Corrida | Universo | Ventana | Obs. | Pares | p<0.05 crudos | Esperado por azar | Válidos (BH) |
|---|---|---|---|---|---|---|---|
| 1 | 32 mega-caps US | 2023–2026 | ~500 | 496 | 13 | ~25 | **0** |
| 2 | 31 mega-caps US | 2015–2026 | 2,961 | 465 | 22 | ~23 | **0** |

La corrida 2 es la que decide. Con **2,961 observaciones** el test de Engle-Granger
tiene poder de sobra, así que "no hay poder estadístico" deja de ser explicación. Y
**22 hits contra ~23 esperados por azar** es la distribución nula exacta: en este
universo no hay nada que encontrar.

Dos señales de apoyo de la corrida 1 (diagnosticadas desde el artefacto): solo el
**7 %** de los pares tiene spread estacionario por ADF, y la **half-life mediana es
de 56.8 días** — donde hay reversión, es demasiado lenta para operar.

### De la literatura (detalle completo en `docs/LITERATURE.md`)

- **Do & Faff (2010)**: el retorno del pairs trading por distancia cayó de 0.86 % a
  0.24 % mensual entre 1962 y 2009, y el driver es el **empeoramiento del riesgo de
  arbitraje** (divergencias más grandes y frecuentes), no la eficiencia de mercado.
- **Attention Factors (2025)**: en su comparación de benchmarks, el **modelo
  paramétrico OU con thresholds — que es exactamente lo que implementa
  `botcito_core` — tiene Sharpe neto negativo** después de costos.
- **Avellaneda & Lee (2010)**, **Guijarro-Ordóñez/Pelger/Zanotti (Management
  Science)**: la línea con evidencia es el arbitraje estadístico sobre **residuos de
  un modelo de factores**, que *generaliza* el pairs trading (un par cointegrado es
  el caso de 1 factor con 2 activos).

## Opciones consideradas

### A — Pivotar a residuos de un modelo de factores (PCA)

En vez de buscar un socio para cada acción, se estima un modelo de factores sobre
toda la sección cruzada y se opera la media-reversión del **residuo idiosincrático**:

```
antes:  spread_ij = precio_i − β · precio_j
ahora:  residuo_i = retorno_i − Σₖ βᵏᵢ · factorᵏ
```

- ✅ Es donde está la evidencia revisada por pares.
- ✅ El benchmark alcanzable **sin deep learning y sin datos de pago** (PCA necesita
  solo retornos) está reportado en **~1.57 de Sharpe neto**.
- ✅ Reusa la mayor parte de `botcito_core` (ver Consecuencias).
- ✅ No depende de encontrar pares: usa las N acciones que haya.
- ⚠️ Introduce una decisión nueva que hay que validar: cuántos factores.
- ⚠️ El backtest pasa de 2 piernas a 1 + K piernas, lo que complica el sizing y
  multiplica los costos de transacción por pierna.

### B — Seguir con pares, pero cambiar el tipo de instrumento

Buscar pares con vínculo **estructural** en vez de estadístico: clases duales de la
misma empresa (GOOGL/GOOG), ETFs que siguen el mismo índice, productores del mismo
commodity.

- ✅ Cero código nuevo: el pipeline actual sirve tal cual.
- ✅ **Garantiza al menos un par que cointegra de verdad**, lo cual es justo lo que
  falta para implementar y verificar SPEC-003/004/005 contra datos reales en vez de
  sintéticos.
- ❌ Esos spreads son tan chicos que los costos se los comen. Sirve para **validar la
  pipeline**, no para operar.

### C — Trend following (time-series momentum)

- ✅ La evidencia más fuerte que existe: Hurst-Ooi-Pedersen, 67 mercados, 1880–2016,
  Sharpe 0.76.
- ✅ Implementación simple, funciona con datos diarios de yfinance.
- ❌ Es **otro proyecto**: índices y futuros, no sección cruzada de acciones. Tira
  casi todo `botcito_core`.

### D — Parar

Conclusión legítima: la infraestructura (ingesta, Airflow, CI/CD, arnés de specs) ya
tiene valor como proyecto de ingeniería, independientemente de la estrategia.

## Decisión

**Opción A — pivotar a residuos de un modelo de factores (PCA, Avellaneda-Lee).**
Decidido el 2026-10-15 por el dueño del modelado.

Razón: no tiene sentido seguir invirtiendo en una metodología que la literatura ya
documenta como obsoleta (OU-con-thresholds sobre pares con Sharpe neto negativo,
decaimiento de Do & Faff) y que en este repo no produjo un solo par válido con
poder estadístico de sobra. El esfuerzo va al enfoque donde hoy está la evidencia.

**B no se adopta como línea de trabajo.** Queda disponible solo como herramienta
puntual si en algún momento hace falta un dato real con media-reversión verdadera
para verificar SPEC-003/004/005; no condiciona el plan.

Consecuencias inmediatas: SPEC-007 y SPEC-008 pasan a `Descartada`; SPEC-011/012/013
quedan desbloqueadas (siguen en `Borrador` hasta que se acepten sus contratos).

---

*Recomendación original al proponer el ADR (se conserva como registro):* **A, con B
como vía de validación en paralelo**:

1. **A** es el objetivo: es donde está la evidencia y reusa el pipeline.
2. **B** resuelve un problema que A no resuelve: hoy no existe en el repo **ningún
   dato real con media-reversión verdadera** contra el cual verificar SPEC-003, 004 y
   005. Un par de clases duales lo da gratis, sin pretender que sea operable.
3. **C** queda registrada como alternativa si A no produce resultado out-of-sample.

**No** se recomienda tocar el timeframe: ADR-0002 (daily) sigue vigente, y todos los
papers de la §3 de `LITERATURE.md` trabajan con datos diarios.

## Consecuencias

### Lo que sobrevive de `botcito_core`

| Módulo | Con el pivote |
|---|---|
| `compute_zscore` | **Igual.** El *s-score* de Avellaneda-Lee es el z-score rolling del residuo acumulado, así que **ADR-0001 se hereda tal cual** |
| `generate_signal`, `Signal` | **Igual**, sobre el s-score |
| `compute_half_life` | **Igual**, sobre el residuo acumulado |
| `screen_universe` (BH-FDR) | **Sigue siendo necesario**: testear estacionariedad de N residuos es otro screening múltiple |
| `run_backtest` | Se generaliza a 1 + K piernas (SPEC-013) |
| `reporting.py`, `data_loader.py`, dashboard | **Igual**, con `schema_version` 2 |

### Lo que muere

`compute_hedge_ratio`, `_kalman_hedge_ratio`, `test_cointegration`, `screen_pair` y
`PairModel`: son específicos de 2 activos.

**Consecuencia inmediata en el backlog: SPEC-007 (Engle-Granger bidireccional) y
SPEC-008 (deduplicar `compute_hedge_ratio`) quedan obsoletas.** Son trabajo sobre
código que se borraría. Si se acepta este ADR, hay que marcarlas `Descartada` con
referencia acá, no implementarlas.

### Lo que no cambia

SPEC-001, 002, 003, 004, 005 y 006 siguen íntegras. Son sobre look-ahead, multiple
testing, consistencia backtest≡live, unidades de las métricas y hold-out: agnósticas
a la técnica. **Esto es lo que justifica haber hecho el trabajo de specs antes del
pivote** — seis de los ocho specs sobreviven a un cambio de metodología.

### Costo

Tres specs nuevos (011, 012, 013), un `ResidualModel` que reemplaza a `PairModel`, y
`schema_version` 2 del artefacto. El dashboard necesita un panel nuevo (varianza
explicada por factor) pero su frontera de lector puro no cambia.
