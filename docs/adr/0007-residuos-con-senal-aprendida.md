# ADR-0007 — Residuos de factores con señal aprendida (técnica B)

- **Estado:** Propuesta
- **Fecha:** 2026-10-18
- **Specs que dependen:** SPEC-020 a SPEC-027 (por escribir; detalle en
  `docs/tecnicas/B-residuos-ml/PREREGISTRO.md` §10). Prerrequisitos: SPEC-004 y SPEC-005
- **Relación con otros ADR:** **extiende** ADR-0005 y lo **reemplaza parcialmente**
  (la señal); se ejecuta **después** de ADR-0006 (técnica A); hereda ADR-0001, 0002,
  0003 y 0004
- **Origen:** `docs/PLAN_TECNICAS.md` §3; evidencia en
  `docs/tecnicas/B-residuos-ml/LITERATURA.md`

## Contexto

ADR-0005 pivotó de pares cointegrados a **residuos de un modelo de factores**
(Avellaneda-Lee) con el s-score lineal como señal, y citó como benchmark alcanzable
"~1.57 de Sharpe neto, sin deep learning".

Desde entonces pasaron dos cosas:

**1. Nuestra evidencia: el s-score lineal no predice el residuo.** Tres pruebas con
potencia (96 acciones con un corte; 96 con walk-forward 2016–2026; 455 pre-registradas):

| Prueba | Resultado |
|---|---|
| wf011, PCA K = 5, train 252 (la de Avellaneda-Lee) | IC h = 5 nulo, Sharpe bruto de juguete −0.12 |
| wf_universo H1, PCA K = 15, 455 acciones | IC nulo (z 0.0), Sharpe bruto +0.04 |
| wf_universo H2, ETF sectorial | **Momentum**, no reversión (z +3.7) |

La regla pre-registrada indicó cerrar la línea con s-score lineal (`STATUS.md` §1).

**2. La literatura, leída en detalle, dice lo mismo sobre el s-score y otra cosa
sobre la línea.** (`LITERATURA.md` §1–2, §7)

- El "~1.57" de ADR-0005 **no es sin deep learning**: es PCA + **LongConv**, una red
  entrenada con objetivo Sharpe neto (Attention Factors, ICAIF '25), y es el máximo
  de 8 valores de K.
- El OU con umbrales sobre residuos PCA —nuestro s-score— tiene en esos mismos papers
  Sharpe bruto 0.2–1.3 y **neto negativo en todo K**. Nuestro nulo es **compatible**
  con lo publicado.
- Lo que funciona en los papers es una **función aprendida de la trayectoria reciente
  (30 días)** del residuo, con rebalanceo diario. Eso no lo probamos.
- Con costos y factores PCA, GPZ (Management Science 2026) reporta Sharpe neto
  **0.81–0.90 con K ≤ 5 y negativo con K ≥ 10**, en 2002–2016. Después del descuento
  de McLean-Pontiff, la expectativa razonable es **0–0.5 neto**.

**Restricción metodológica:** los datos 2016–2026 ya se miraron con estadísticos
lineales. Cualquier prueba nueva sobre ellos necesita un test sellado definido antes
de entrenar.

## Opciones consideradas

### A — Residuos PCA + señal aprendida, con escalera de modelos y test sellado

Mantener los residuos de SPEC-011 y reemplazar el s-score por una señal aprendida,
subiendo de complejidad solo si hace falta: baselines (incluida la reversión corta
del residuo, nunca medida) → features de la trayectoria + ridge/árboles → CNN chica →
CNN+Transformer de GPZ con sus hiperparámetros publicados. Desarrollo 2009–2021-06,
**test sellado 2021-07-01 → 2026-10-16** (posterior a la publicación de GPZ), una
sola corrida, umbral estadístico + económico, forward de 6 meses si pasa.

- ✅ Es donde está la evidencia revisada por pares (Management Science 2026).
- ✅ Reusa SPEC-011 y todo el instrumento de evaluación de wf011 / wf_universo.
- ✅ El test sellado mide justo lo que importa: si la señal sobrevivió a su publicación.
- ✅ La escalera puede cerrar la técnica barato: si E0–E2 no muestran nada en un
  desarrollo que se solapa con la muestra de los papers, se para sin PyTorch.
- ⚠️ Es la técnica con más riesgo de autoengaño: muchos grados de libertad sobre un
  panel de 455 × 20 años. El protocolo (máx. 24 configuraciones, DSR, nula conjunta,
  registro append-only) existe por eso.
- ⚠️ El test tiene poca potencia para Sharpe netos realistas (≈ 50 % para 0.5).
- ⚠️ Dependencia nueva pesada (PyTorch CPU) y entre una noche y dos días de CPU para
  los escalones neurales (estimado, `DATOS.md` §5).
- ⚠️ Sesgo de supervivencia del universo (S&P 500 actual), grande en desarrollo.

### B — Cerrar la línea de residuos y quedarse solo con la técnica A

- ✅ Cero riesgo de sobreajuste, cero dependencias, foco total en A.
- ❌ Descarta la línea sin haber probado lo que la literatura dice que funciona: el
  nulo lineal no refuta una señal no lineal de corto plazo (`LITERATURA.md` §7).

### C — Solo forward / paper trading de la variante PCA expansiva

La única regularidad que se repitió en dos universos (Sharpe bruto 0.53–0.77, breakeven
4.4–5.5 bps).

- ✅ Dato limpio de verdad.
- ❌ Ya está por debajo del umbral económico antes de costos de cobertura, y decae.
  Años de espera para una señal que no llega al umbral.

### D — Replicar GPZ directamente (saltar la escalera)

- ✅ Más rápido a "la" respuesta de la literatura.
- ❌ Si funciona, no sabemos si hacía falta la red; si no funciona, no sabemos si
  falla la señal o la implementación. Consume el presupuesto de configuraciones en lo
  más caro primero.

## Decisión

**Propuesta: Opción A**, con este orden y estas condiciones:

1. **A (trend following, ADR-0006) va primero en la implementación**, como decidió el
   dueño del modelado (`PLAN_TECNICAS.md`). B no arranca la fase 2 hasta que A tenga
   su corrida contra umbral o hasta que la carga de revisión permita paralelizar.
   Las dos comparten prerrequisitos (SPEC-004/005) y el instrumento de evaluación;
   B no comparte código de señal ni datos con A.
2. **El s-score lineal queda descartado como señal operable** por evidencia (propia y
   publicada). Sobrevive como **baseline** (E0a) y como feature.
3. El pre-registro `docs/tecnicas/B-residuos-ml/PREREGISTRO.md` se acepta junto con
   este ADR; sin pre-registro aceptado no se descarga, no se instala y no se entrena.
4. `torch` CPU entra solo como **grupo opcional** de dependencias, nunca en la imagen
   de Airflow, y solo si la escalera llega a E3.

## Consecuencias

### Sobre ADR-0005

| De ADR-0005 | Con ADR-0007 |
|---|---|
| Premisa: operar el residuo idiosincrático de un modelo de factores | **Se mantiene** |
| PCA (Avellaneda-Lee), SPEC-011 | **Se mantiene**, con K = 5 fijo y PCA rodante diario de 252 días |
| Señal = s-score (z rolling del residuo acumulado) + umbrales | **Reemplazada**: baseline, no señal |
| Benchmark "~1.57 sin deep learning" | **Corregido**: es una señal aprendida, máximo de grilla; expectativa post-publicación 0–0.5 |
| SPEC-012 (screening por acción con BH) | **Sin uso en B**: B opera todos los residuos. El orquestador decide si se descarta |
| SPEC-013 (backtest 1 + K piernas por posición) | **Reemplazada en B** por cartera a nivel portafolio (`w_R = Φᵀ w_ε`, SPEC-022). Su decisión práctica (costos sobre pesos netos por acción) se conserva |

ADR-0005 **no** pasa a *Reemplazada*: su decisión (pivotar a residuos) sigue vigente;
lo que cambia es la señal. Sugerencia para el orquestador: anotar en ADR-0005 un
enlace a este ADR al aceptarlo.

### Sobre los demás ADR

- **ADR-0001** (z-score causal idéntico en backtest y live): se generaliza a
  "**la misma función produce los pesos en backtest y en live**". Para una red, eso
  incluye los pesos entrenados y la versión de las dependencias. La prueba forward
  (§8.3 del pre-registro) lo verifica bit a bit.
- **ADR-0002** (daily): se mantiene; todos los papers son daily.
- **ADR-0003** (retorno sobre capital): ‖w_R‖₁ = 1 es exposición bruta = capital; el
  PnL se cobra sobre retornos de acciones, no de residuos.
- **ADR-0004** (reporting lee artefacto): el resultado de B es un artefacto; el
  dashboard no importa modelos.

### Sobre la técnica A (ADR-0006)

Independientes en señal, datos y código. Comparten: prerrequisitos SPEC-004/005, la
lógica de pre-registro y nula, y el criterio de decisión por Sharpe neto. Si las dos
pasan, su combinación es otro ADR (la correlación esperada entre trend following y
stat arb neutral a factores es baja, pero no se mide acá).

### Si B no pasa

Se cierra la línea de residuos de factores para acciones de EE.UU. en daily, y el
período 2021–2026 queda gastado para cualquier variante de B.

### Costo

Hasta 8 specs (SPEC-020 a 027), una re-descarga de precios desde 2004,
`scikit-learn` + `torch` CPU como grupos opcionales, y entre horas y un par de días
de CPU para los escalones neurales.
