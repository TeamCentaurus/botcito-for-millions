# Pre-registro — Técnica A: trend following multi-activo con ETFs (BORRADOR)

- **Estado:** **Borrador.** Lo acepta el dueño del modelado; al aceptarse, las secciones
  *Universo* a *Umbral de decisión* se congelan (misma regla que §3/§4 de un spec).
- **Escrito:** 2026-10-18, **antes** de calcular cualquier señal o retorno de estrategia
  sobre estos ETFs. Lo único consultado está en `DATOS.md` (fechas de inicio, huecos,
  volumen, volatilidades 2009–2016).
- **Contexto:** la línea de residuos con s-score lineal no pasó su pre-registro
  (`research/wf_universo/PREREGISTRO.md`). El plan (`docs/PLAN_TECNICAS.md`) pone A
  primero. Evidencia y Sharpe esperado en `LITERATURA.md`; datos en `DATOS.md`.
- **ADR:** `docs/adr/0006-trend-following-multi-activo.md` (Propuesta).

La pregunta es una sola: **¿el trend following canónico de la literatura, implementado
con ETFs y neto de costos realistas, sigue teniendo Sharpe positivo después de
publicado (2017–2026)?** Nada de lo que sigue se elige mirando ese período.

---

## Universo

Los **29 ETFs** de `DATOS.md` §2, sin cambios:

| Clase | Tickers |
|---|---|
| Acciones (8) | SPY, IWM, EWJ, EWG, EWU, EWC, EWA, EEM |
| Bonos (7) | IEI, IEF, TLT, TIP, BWX, LQD, EMB |
| Commodities (6) | GLD, SLV, USO, UNG, DBA, DBB |
| Divisas vs USD (6) | FXE, FXY, FXB, FXF, FXA, FXC |
| REITs (2) | VNQ, RWX |

Tasa libre de riesgo: `^IRX`, `rf_d = IRX/100/252`.
Precios: `load_yfinance(..., start="2007-12-01", auto_adjust=True)` → `clean_prices`,
cacheados una vez; la fecha de descarga va al artefacto.

Sesgos declarados: supervivencia leve (ETFs que siguen listados); universo elegido por
clase de activo con conocimiento de qué ETFs son "los conocidos" hoy.

---

## Señal (una sola, la de Hurst-Ooi-Pedersen 2017, sin optimizar)

En cada fecha de señal `t` (último día hábil de cada mes), para cada activo `i`, con
datos **hasta el cierre de `t` inclusive**:

1. Retorno en exceso acumulado a `h ∈ {21, 63, 252}` días hábiles (1, 3 y 12 meses):
   `R_i^h = Σ_{d=t−h+1..t} (log(1+r_{i,d}) − log(1+rf_d))`.
2. `s_i = (sign(R_i^21) + sign(R_i^63) + sign(R_i^252)) / 3` ∈ {−1, −⅓, +⅓, +1}.
3. Vol ex-ante `σ_i`: EWMA de retornos diarios en exceso al cuadrado (desviados de su
   media EWMA), **centro de masa 60 días** (δ = 60/61), anualizada con **252**.
4. Peso crudo `w̃_i = s_i / σ_i` (igual riesgo por activo).
5. Escala de cartera: `k_t` tal que la vol ex-ante de `Σ k_t w̃_i r_i` sea **10 %
   anual**, con covarianza muestral **equiponderada** de los **756** retornos diarios en
   exceso anteriores (mínimo 252 al inicio, ventana expansiva hasta llegar a 756).
6. **Tope de apalancamiento bruto `G_max = 2.0`** (ver decisión abierta 2): si
   `Σ |k_t w̃_i| > G_max`, se reescala **toda** la cartera uniformemente hasta `G_max`. Sin
   tope por activo.

**Por qué esta y no otra:**

- **Horizontes 1/3/12 meses, equiponderados**: es exactamente HOP 2017, el paper cuya
  muestra termina en 2016. Usar su señal hace que 2017+ sea un test fuera de muestra **de
  ese paper**. MOP (solo 12 meses) es un caso particular; se reporta como secundario.
- **Signo, no magnitud**: HOP y MOP usan signo. Las señales continuas
  (Baltas-Kosowski) bajan rotación, pero serían una elección nuestra.
- **Escalado por vol EWMA con centro de masa 60**: MOP, ecuación (1). Anualización 252
  en vez de 261 por consistencia con ADR-0002; es un factor constante que el paso 5
  absorbe.
- **Vol de cartera 10 %**: HOP. El nivel no afecta al Sharpe salvo a través de costos y
  del tope.
- **Covarianza de 3 años**: HOP usa 3 años de retornos **mensuales**; acá **diarios**
  (desvío declarado): con ETFs que nacen en 2007 los mensuales dejarían el período previo
  en 2011, y los diarios son más estables con 29 activos. El test 2017+ tiene siempre
  los 756 días completos.

---

## Rebalanceo y ejecución

- **Mensual.** Señal con el cierre del último día hábil del mes `t`; **se opera al cierre
  del día hábil siguiente** (rezago de 1 día, conservador frente a HOP, que opera en el
  mismo cierre; respeta la causalidad de ADR-0001).
- Entre rebalanceos las posiciones se mantienen **constantes en unidades** (los pesos
  derivan con los precios).
- Retornos **diarios, por período, sobre capital** (ADR-0003):

  ```
  r_p,d − rf_d = Σ_i w_{i,d} · (r_{i,d} − rf_d) − costos_d − préstamo_d − margen_d
  ```

  con `w_{i,d}` el peso derivado (notional / capital de la mañana del día `d`).
- Sharpe = media / desvío de `r_p − rf` diario × √252 (SPEC-004).

---

## Modelo de costos

| Componente | Supuesto | Base |
|---|---|---|
| Spread + comisión, por unidad de notional negociado (una punta) | **3 bps** si volumen mediano diario en US$ 2014–2016 ≥ 100 M; **8 bps** si 10–100 M; **20 bps** si < 10 M | Supuesto nuestro, conservador; comisiones tipo IBKR ≤ 1 bp incluidas. Tier calculado por el código con datos **anteriores** al test |
| Rotación | `Σ_i |w_i^nuevo − w_i^derivado|` en cada rebalanceo | Mecánico |
| Préstamo de cortos | **1 %/año** sobre notional corto, devengado diario | Supuesto; cubre fee de préstamo y rebate perdido |
| Margen | **1 %/año sobre la tasa libre** por notional largo que exceda el capital | Supuesto (spread típico minorista, no verificado) |
| Expense ratio | **0**: ya está en el precio ajustado | `DATOS.md` §4 |
| Impuestos | No se modelan | Fuera de alcance |

Se reporta además el **breakeven**: costo uniforme por unidad negociada que lleva el
Sharpe neto a 0.

---

## Partición de la muestra

| Tramo | Fechas | Rol |
|---|---|---|
| Calentamiento | 2007-12-19 → fin 2008 | Solo para inicializar ventanas |
| **Período previo** | primer mes con las 3 señales y ≥ 252 días de covarianza (≈ 2009-01) → **2016-12-30** | **Descriptivo y chequeo de tubería.** Solapa con la muestra de HOP: no es evidencia nueva. **No se usa para elegir nada** (no hay nada que elegir) |
| **Test** | **2017-01-03 → 2026-09-30** | El único que decide. ≈ 9.75 años |

Las dos partes salen **de la misma corrida** (las ventanas del test usan datos de 2016
hacia atrás, como corresponde). No hay iteración: si el período previo da algo raro, se
investiga como bug de tubería, **sin tocar la especificación**; si hubiera que tocarla,
el pre-registro vuelve a Borrador con nota antes de mirar el test.

Sesgo declarado: **el test no es ciego para nosotros.** El desempeño público de la
industria (índice SG Trend: 2018–19 malo, 2019–24 fuerte, 2024–25 peor drawdown del
registro; `LITERATURA.md` §3.1) ya se conoce. Es fuera de muestra respecto del diseño
del paper y de nuestra especificación, no respecto de nuestro conocimiento. Mitigación:
la especificación es la del paper, no hay grados de libertad que ese conocimiento pueda
haber sesgado salvo el universo (justificado por clase en `DATOS.md`).

---

## Hipótesis primarias (las únicas que deciden)

| | Hipótesis | Para qué |
|---|---|---|
| **H1** | Sharpe neto de TSMOM en el test **> 0** | ¿Sobrevivió la técnica? |
| **H2** | Sharpe neto de TSMOM **>** Sharpe neto del benchmark **vol-escalado siempre largo** | ¿Es tendencia o es escalado por volatilidad? (Kim-Tse-Wald) |

**Benchmark de H2**: misma tubería con `s_i ≡ +1` (mismo universo, `σ_i`, target 10 %,
covarianza, tope, costos, rebalanceo). Es la "risk parity ingenua".

**Orden jerárquico (gatekeeping):** H2 solo se evalúa si H1 está en zona verde. Así
el α global no se infla y no hace falta Bonferroni.

---

## Test y nula

**H1.** Estadístico: Sharpe anualizado de `r_p − rf` diario en el test.
Nula: media 0. Distribución: **bootstrap estacionario** (Politis-Romano 1994) de la serie
diaria **centrada**, largo medio de bloque **21 días** (un período de holding), **10,000**
réplicas, semilla fija. p unilateral = fracción de réplicas con Sharpe ≥ observado.

- Por qué bloques y no permutación simple: los retornos de una cartera rebalanceada
  mensualmente tienen dependencia (heterocedasticidad, exposición persistente). Huang et
  al. (2020) muestran que el t ingenuo exagera la evidencia de TSMOM.
- Por qué no "permutación conjunta de fechas" como en `wf_universo`: allá la nula era
  "el s-score no predice"; acá el objeto es una serie de retornos de cartera, y la
  pregunta es si su media es positiva.

**H2.** ΔSR con el test de **Ledoit & Wolf (2008)** (bootstrap por bloques circular
studentizado para diferencia de Sharpe, bloque 21, 10,000 réplicas). Ojo: con 10 años
este test tiene **muy poca potencia**; ver la regla.

**Nulas secundarias (descriptivas, no deciden):**

- **Desplazamiento circular conjunto**: la matriz de señales `s_{i,t}` se desplaza en
  bloque un número aleatorio de meses (≥ 12) respecto de los retornos, **igual para
  todos los activos**. Preserva persistencia, rotación y correlación cruzada de las
  señales; destruye solo el timing. Responde "¿el timing aporta sobre una exposición con
  la misma dinámica?". 1,000 réplicas.
- **Signos aleatorios** por activo y rebalanceo (misma magnitud de pesos): "¿la
  dirección tiene información?".

---

## Potencia (lo que este test puede y no puede decir)

Aproximación analítica (Lo 2002, retornos i.i.d.): `SE(SR) ≈ √((1 + SR²/2) / T)`,
`T = 9.75` años → SE ≈ 0.32 bajo la nula. El Sharpe crítico al 5 % unilateral es
**≈ 0.53**.

| Sharpe neto verdadero | Potencia al 5 % | Potencia al 10 % |
|---|---|---|
| 0.2 | 0.16 | 0.26 |
| 0.3 | **0.24** | 0.37 |
| 0.5 | 0.47 | 0.60 |
| 0.7 | 0.69 | 0.79 |
| 1.0 | 0.89 | 0.93 |

Para potencia 80 % al 5 % harían falta **~26 años** con Sharpe 0.5 y **~70 años** con
Sharpe 0.3. **No existen** con ETFs.

Conclusión honesta: con el Sharpe que esperamos (0.3, `LITERATURA.md` §4), el test
**probablemente no rechace la nula aunque la técnica funcione**. Lo que sí puede hacer
es **refutar**: un Sharpe neto observado bajo, o por debajo del benchmark, es
informativo. La regla de decisión está construida para eso.

**Antes de correr sobre datos reales** (fase 2, sin mirar el test): análisis de potencia
**con sintéticos** que reproduzca la tubería completa (bootstrap estacionario incluido)
sobre 29 activos con un componente de tendencia calibrado a Sharpe 0, 0.3, 0.5 y 0.7, y
correlaciones del período previo. Hace falta un generador nuevo en `tests/synthetic.py`
(ver SPEC-017 en el ADR). Ese análisis **documenta** la potencia real (la aproximación
i.i.d. puede ser optimista o pesimista); **no cambia los umbrales**.

---

## Umbral de decisión y regla

Umbral económico fijo: **Sharpe neto 0.2** como piso de "vale la pena seguir mirando",
y **breakeven ≥ 2 × el costo supuesto** (promedio ponderado por rotación) como margen
contra el modelo de costos.

| Zona | Condición (test 2017-01-03 → 2026-09-30) | Qué se hace |
|---|---|---|
| **Verde** | H1 con **p < 0.05** (≈ Sharpe ≥ 0.53) **y** breakeven ≥ 2× costo | Se evalúa H2. Si **ΔSR > 0** (estimación puntual; el p de Ledoit-Wolf se reporta pero no decide, por falta de potencia): se sigue con **TSMOM** a los specs de implementación (SPEC-014 a 018) y **paper trading de 6 meses** antes de cualquier capital. Si **ΔSR ≤ 0**: no se adopta TSMOM; lo que funcionó es el escalado; se documenta y el dueño decide si una cartera risk-parity long-only es parte de este proyecto (sería otro ADR) |
| **Gris** | Sharpe neto **≥ 0.2** y p ≥ 0.05 | **Sin capital.** Compatible con la literatura pero no demostrable con 10 años. No se re-especifica nada (el período de test queda **consumido**). Opción: paper trading 12 meses con la especificación congelada, **solo como monitoreo**; no se re-evalúa con el mismo período |
| **Roja** | Sharpe neto **< 0.2** | **Se cierra la técnica A** con ETFs en daily. Se pasa a B (`docs/tecnicas/B-residuos-ml/`) o se vuelve a `LITERATURE.md` |

Tasas de error de la regla (aproximación i.i.d., T = 9.75):

| Sharpe verdadero | P(verde) | P(gris) | P(roja) |
|---|---|---|---|
| 0.0 | 0.05 | 0.22 | 0.73 |
| 0.3 | 0.24 | 0.38 | 0.38 |
| 0.5 | 0.47 | 0.34 | 0.19 |
| 0.7 | 0.69 | 0.23 | 0.08 |

Es decir: si la técnica no sirve, hay 5 % de chance de darle capital por error (verde) y
22 % de quedarse en gris (que no compromete capital). Si sirve con Sharpe 0.3, hay 38 %
de cerrarla por error. **Ese es el precio de 10 años de datos**, y se acepta a sabiendas.

**Prohibido después de ver el resultado:** cambiar horizontes, target de vol, tope,
universo, costos, fecha de corte o tamaño de bloque; "probar solo con los líquidos";
reportar el secundario que mejor dé como si fuera el primario.

---

## Secundario (descriptivo, NO decide)

Todo sobre el test, y entre paréntesis lo mismo para el período previo:

1. Sharpe, retorno, vol realizada, max drawdown y duración, apalancamiento bruto medio y
   % de meses con el tope activo.
2. Las mismas métricas para: benchmark vol-escalado siempre largo; **SPY buy-and-hold**;
   **60/40** (SPY/IEF, rebalanceo mensual); TSMOM **sin tope**; TSMOM con costos **×2**.
3. Señales por separado: solo 1 m, solo 3 m, solo 12 m (MOP); señal **rezagada un mes**
   (HOP Exhibit 2).
4. Sharpe por clase de activo (5 subcarteras) y por año.
5. Correlación con SPY y con 60/40, total y en los meses de peor retorno de SPY
   ("smile" de MOP/HOP); comportamiento en 2020-02/03 y 2022.
6. Exposición neta larga media (Goyal-Jegadeesh) y beta a SPY.
7. Estrategia de media histórica (Huang et al.): `s_i = sign(media expansiva de retornos
   en exceso)`.
8. Nulas de desplazamiento circular conjunto y de signos aleatorios.
9. Período previo completo (≈ 2009–2016) con las mismas métricas.

---

## Qué se reusa del repo y prerrequisitos

| Pieza | Uso | Estado |
|---|---|---|
| `data_loader.load_yfinance` / `clean_prices` (SPEC-010) | Descarga y limpieza del panel | Implementado |
| `reporting.build_run` / `write_run` (SPEC-009, ADR-0004) | Artefacto de la corrida; dashboard lector puro | Implementado; probablemente `schema_version` nuevo |
| **SPEC-005** (PnL sobre capital, retornos por período) | Define la unidad de `r_p` | **Borrador → prerrequisito** |
| **SPEC-004** (Sharpe anualizado) | El número que decide | **Borrador → prerrequisito** |
| `tests/synthetic.py` | Base del análisis de potencia; falta un generador de tendencia | A extender |
| Instrumento de evaluación de `research/wf011` y `wf_universo` | Pre-registro, nula explícita, potencia antes de mirar, umbral económico | Se reusa el método, no el código (aquellos son tests de IC) |
| `run_backtest`, `compute_zscore`, `screen_universe`, `factor_model` | — | **No se usan**: son de pares/residuos |

SPEC-004 y 005 hoy están escritos sobre `run_backtest` de pares. Para A hace falta que
la **función de Sharpe** (SPEC-004) y la **convención de retorno por período sobre
capital** (SPEC-005) queden como piezas reutilizables, no atadas a dos piernas. Eso lo
resuelve el orquestador al aceptar esos specs; el backtest multi-activo de A es SPEC-016.

Código de la corrida (fase 2): `research/trend/`.

---

## Decisiones abiertas para aceptar este pre-registro

1. **Umbral de significancia.** Recomendado: **p < 0.05** para verde, con la zona gris
   que no compromete capital. Alternativa: p < 0.10 (Sharpe crítico ≈ 0.41, potencia
   0.37 a Sharpe 0.3) a cambio de 10 % de falsos verdes.
2. **Tope de apalancamiento bruto.** Recomendado: **2.0×** (cuenta Reg-T) en el
   primario y sin tope como secundario. Alternativa: sin tope en el primario (como los
   papers, Sharpe "puro") y 2.0× como secundario de implementabilidad.
3. **Long/short vs long/flat.** Recomendado: **long/short**, como la literatura. Long/flat
   (corto → caja) evita el préstamo y es lo que permite una cuenta sin margen, pero es
   otra estrategia (estilo Faber) y no tiene la evidencia de §1 de `LITERATURA.md`; si se
   prefiere, entra como secundario, no como primario.
