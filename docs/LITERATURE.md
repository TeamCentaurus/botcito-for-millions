# Literatura de la metodología

Revisión de la evidencia científica sobre qué técnicas de trading cuantitativo tienen
soporte empírico **hoy**, y qué implica para este repo.

`docs/METHODOLOGY.md` audita *cómo está implementado* el pipeline actual. Este
documento pregunta algo distinto y previo: *¿vale la pena implementar esta técnica?*

> **TL;DR**: el pairs trading por distancia/cointegración en large caps de EE.UU. está
> documentado como decaído, y el modelo paramétrico OU-con-thresholds que implementa
> `botcito_core` aparece en la literatura reciente como el benchmark que **pierde
> dinero después de costos**. Lo que sí tiene evidencia: trend following
> (136 años de datos) y statistical arbitrage sobre **residuos de un modelo de
> factores**, que generaliza el pairs trading en vez de abandonarlo. Antes de creerle
> a cualquier paper, leer la §2: la literatura financiera tiene su propio problema de
> multiple testing, exactamente el mismo que corrige `screen_universe`.

Revisión hecha el **2026-10-12**. Todas las cifras citadas son de los papers, no
reproducidas por nosotros.

> **Correcciones del 2026-10-18** (verificadas en la fuente por los agentes de la fase 1
> de `PLAN_TECNICAS.md`; detalle en `docs/tecnicas/*/LITERATURA.md`). Prevalecen sobre
> el texto de abajo:
>
> - **Hurst-Ooi-Pedersen (§3.1):** el Sharpe es **neto de comisiones 2/20** de hedge
>   fund. Verificado en el texto: **0.77** (1880–2013) y **0.62** (2000–2013). El 0.76
>   de 1880–2016 de la versión publicada no se pudo leer (tabla en imagen).
> - **Guijarro-Ordóñez/Pelger/Zanotti (§3.2):** "Sharpe > 4" es **bruto**. Con costos:
>   IPCA 0.94–1.24; **PCA 0.81–0.90 con K ≤ 5 y negativo con K ≥ 10** (−0.08 con K=10,
>   −0.87 con K=15). Publicado en *Management Science* 72(9), 2026.
> - **Attention Factors (§3.2):** publicado en las actas de **ICAIF '25**. El "~1.57" de
>   PCA + LongConv es el **máximo** entre 8 valores de K (rango 1.19–1.57 neto), y
>   **LongConv es deep learning**: no es un benchmark "sin deep learning". Sin deep
>   learning, lo que reportan es OU + umbral, con Sharpe neto negativo.
> - **Replicación:** la única replicación independiente conocida de GPZ (Long & Xiao
>   2024) fue retirada por sus autores. Fischer & Krauss (2018): ML diario sobre el
>   S&P 500 ≈ 0 neto desde 2010.

---

## 1. Qué decayó, y por qué

### Do & Faff (2010) — el paper que lo mide

*Does Simple Pairs Trading Still Work?*, **Financial Analysts Journal** 66(4), 83–95.

Retorno medio en exceso del portafolio de los 20 mejores pares, estrategia de
distancia clásica (Gatev-Goetzmann-Rouwenhorst):

| Período | Retorno mensual |
|---|---|
| 1962–1988 | 0.86 % |
| 1989–2002 | 0.37 % |
| 2003–2009 | **0.24 %** |

**El diagnóstico es contraintuitivo y nos concierne directamente:** el deterioro
**no** viene de más eficiencia de mercado, ni de competencia del sector de hedge
funds. Viene del aumento en la **frecuencia y magnitud de las divergencias** — o sea,
empeoró el *riesgo de arbitraje*.

Los spreads todavía revierten. Lo que cambió es que se alejan más y por más tiempo
antes de hacerlo.

> **Implicación para este repo:** eso es exactamente lo que mata una estrategia con
> `stop_loss_threshold = 3.5` (`types.py`): el stop se dispara justo antes de la
> reversión. El problema no es detectar la media-reversión, es **sobrevivirla**.
> También explica por qué el trabajo de SPEC-005 (PnL sobre capital) importa: sin
> medir el drawdown en unidades de capital, este modo de fallo es invisible.

Un hallazgo secundario del mismo paper que vale registrar: la estrategia **rinde bien
en períodos de turbulencia prolongada**, incluida la crisis de 2008.

### Krauss (2017) — el survey

*Statistical Arbitrage Pairs Trading Strategies: Review and Outlook*, **Journal of
Economic Surveys** 31(2). Llega a la misma conclusión por otra vía: el enfoque
clásico está arbitrado en acciones grandes de EE.UU., y señala cópulas y selección
por machine learning como las líneas que resisten mejor.

### Evidencia reciente sobre la inestabilidad de la cointegración

Trabajo de 2024–2025 sobre ETFs cointegrados reporta que **la vida útil
out-of-sample de un par que funciona es de a lo sumo dos años**, lo que obliga a
re-correr los tests de cointegración y re-seleccionar el portafolio de pares cada
año o dos.

> **Implicación:** un `PairModel` serializado sin fecha ni período de entrenamiento
> (hoy `model.save_model` escribe un `.pkl` sin metadata) es un riesgo operativo
> directo, no deuda técnica cosmética.

---

## 2. Cómo leer esta literatura (leer antes que cualquier paper)

La pregunta "¿qué técnica es científicamente válida?" asume que *publicado* ≈
*cierto*. En finanzas esa inferencia es débil, y la razón es **exactamente el sesgo
que corrige `screen_universe`**: la literatura de anomalías es un screening de
cientos de hipótesis del que se publican las que pasaron.

### El caso pesimista

**Harvey, Liu & Zhu (2016)**, *…and the Cross-Section of Expected Returns*, **Review
of Financial Studies** 29(1), 5–68. Documentan al menos **316 factores publicados**
que dicen predecir retornos. Aplican Bonferroni, Holm y **Benjamini-Hochberg-Yekutieli**
y concluyen que un factor nuevo debería superar un **t ≈ 3.0** (≈ 0.5 % de
significancia de test único), no el 1.96 habitual.

> Es literalmente la corrección que corre `screen_universe` con `method="fdr_bh"`,
> aplicada a la literatura entera en vez de a un universo de pares.

**Hou, Xue & Zhang (2020)**, *Replicating Anomalies*, **Review of Financial Studies**
33(5), 2019–2133. Replican **452 anomalías** con breakpoints de NYSE y retornos
value-weighted (es decir, sin dejar que los microcaps hagan el trabajo):

| Criterio | Fallan |
|---|---|
| Significancia al 5 % | **286 (64 %)** |
| `\|t\| > 1.96` | 65 % |
| `\|t\| > 2.78` (multiple testing) | **82 %** |

Y añaden que incluso las que replican tienen magnitudes económicas mucho menores que
las reportadas originalmente.

**McLean & Pontiff (2016)**, *Does Academic Research Destroy Stock Return
Predictability?*, **Journal of Finance** 71(1), 5–32. Siguen 97 predictores
publicados: los retornos son **26 % menores out-of-sample** y **58 % menores después
de publicados**. Atribuyen la diferencia (32 %) a trading informado por la
publicación.

> **Implicación:** una estrategia publicada pierde más de la mitad de su retorno
> medido *por el hecho de haberse publicado*. Cualquier Sharpe de un paper es un
> techo optimista.

### El contrapeso

**Jensen, Kelly & Pedersen (2023)**, *Is There a Replication Crisis in Finance?*,
**Journal of Finance** 78(5). Rehacen el ejercicio con un modelo jerárquico bayesiano
sobre **153 factores en 93 países**: la tasa de replicación sube a **82.4 %** sobre
alfas del CAPM, con error estándar posterior de 2.8 % y un **FDR bayesiano de 0.1 %**.
Publicaron datos y código.

La discrepancia con Hou-Xue-Zhang es **metodológica**, no empírica: cómo se maneja el
multiple testing y si se permite agrupar factores (*shrinkage* jerárquico) en vez de
tratarlos como hipótesis independientes.

### El criterio que sale de todo esto

No hay una lista de "técnicas válidas". Hay un criterio, y es el único que sobrevive
a los dos campos:

> **Credible = evidencia multi-década, multi-mercado y multi-clase de activo, con
> magnitud económica que sobrevive a costos realistas.**
>
> Un hallazgo de un mercado, un período y una configuración no es evidencia: es un
> candidato. Que es exactamente lo que `screen_universe` dice de un par con p=0.0026
> entre 496.

---

## 3. Qué tiene evidencia hoy

### 3.1 Time-series momentum / trend following — la evidencia más larga que existe

**Hurst, Ooi & Pedersen (2017)**, *A Century of Evidence on Trend-Following
Investing*, **Journal of Portfolio Management** 44(1).

- **67 mercados**, 4 clases de activos: 29 commodities, 11 índices de acciones,
  15 mercados de bonos, 12 pares de divisas.
- **Enero 1880 – diciembre 2016.**
- Sharpe del siglo completo: **0.76**. Correlación baja con activos tradicionales.

136 años de evidencia es incomparable con cualquier otra cosa en finanzas
cuantitativas. El precio: Sharpe 0.76 no es espectacular, y trend tuvo una década
pobre en los 2010s.

**Encaje con este repo:** es la implementación más simple posible (señal por
cruce/vol-scaling sobre precios diarios), funciona con datos de yfinance, y no
necesita sección cruzada. Pero es **otro proyecto**: índices y futuros, no pares.

### 3.2 Statistical arbitrage sobre residuos de un modelo de factores

Esta es la línea que **generaliza** el pairs trading en lugar de abandonarlo, y es la
ruta de migración natural para `botcito_core`.

**La idea central:**

```
enfoque actual:   spread_ij = precio_i − β · precio_j
                  (2 activos; se busca cointegración por pares)

enfoque moderno:  residuo_i = retorno_i − Σₖ βᵏᵢ · factorᵏ
                  (N activos; se busca media-reversión en el residuo idiosincrático)
```

Un par cointegrado es el caso especial de un modelo de 1 factor con 2 activos. El
enfoque de factores usa toda la sección cruzada para construir el "activo de
comparación", en vez de apostar a que existe un único socio para cada acción.

#### Avellaneda & Lee (2010) — el paper fundacional

*Statistical Arbitrage in the US Equities Market*, **Quantitative Finance** 10(7),
761–782. Construyen estrategias market-neutral sobre el universo amplio de acciones
de EE.UU., usando **PCA sobre los retornos** o **regresión contra ETFs sectoriales**
para extraer los factores, y modelan el **residuo acumulado** como un proceso de
Ornstein-Uhlenbeck, del que derivan un *s-score* (el análogo del z-score).

> **Detalle técnico que es fácil de errar y que decide si esto funciona:** el proceso
> que se modela como OU es el **residuo acumulado** `X(t) = Σ_{s≤t} ε(s)`, no el
> residuo `ε(t)`. Los residuos de un modelo de factores son aproximadamente ruido
> blanco; lo que revierte a la media es su suma acumulada. Implementarlo sobre `ε(t)`
> directamente da una estrategia que no funciona y cuyo bug es invisible.

#### Guijarro-Ordóñez, Pelger & Zanotti — el estado del arte revisado por pares

*Deep Learning Statistical Arbitrage*, **Management Science** (Crowell Memorial
Second Prize, 2022). Residuos de **modelos de factores latentes condicionales**,
señal extraída con un **CNN + transformer**, y optimización **directa de la política
de trading** (no predicción seguida de reglas). Reportan Sharpe out-of-sample
**mayor a 4** en acciones diarias de EE.UU., y afirman que sigue siendo rentable
después de fricciones y costos.

#### Attention Factors (2025) — el dato más directo sobre nuestro código

*Attention Factors for Statistical Arbitrage*, arXiv:2510.11616 (octubre 2025,
**preprint sin revisión por pares**).

- Universo: **500 acciones más grandes de EE.UU.**, retornos diarios, **1998–2021**
  (24 años), con 39 características a nivel firma.
- Sharpe anualizado **bruto 3.97**, **neto 2.28** después de costos, 16 % anual, sin
  correlación con el riesgo de mercado.
- Benchmarks en la misma comparación:

| Método | Sharpe neto |
|---|---|
| Attention factors + LongConv | **2.28** |
| Factores PCA + LongConv | ~1.57 |
| **OU paramétrico con thresholds** | **negativo** |

> **La última fila es la técnica que implementa `botcito_core` hoy.** En esa
> comparación, con ese universo y esos costos, pierde dinero después de fricciones.
> Es el enunciado científico más directo que encontramos sobre el enfoque actual del
> repo.

**Caveats obligatorios sobre estos números:**

1. Los costos se modelan como **5 bps por trade + 1 bp de shorting**, que es
   optimista y no incluye impacto de mercado para posiciones grandes.
2. El de Attention Factors es **arXiv, sin revisión por pares** todavía.
3. Son la **mejor configuración de los propios autores**; aplica el descuento de
   McLean-Pontiff (§2).
4. Requieren 39 características a nivel firma — datos de calidad Compustat.
5. Hay **restricciones de capacidad**: un Sharpe de 2.3 sobre las 500 acciones más
   líquidas no sobrevive necesariamente a un tamaño de posición grande.

#### La fila que importa para un proyecto personal

**Factores PCA + señal temporal ≈ 1.57 de Sharpe neto.** Ese es el benchmark
alcanzable sin deep learning y sin datos de pago: PCA necesita **solo retornos**.
Es el objetivo realista de este repo, y el que reusa la mayor parte del código
existente.

---

## 4. Datos abiertos

**Chen & Zimmermann**, *Open Source Cross-Sectional Asset Pricing*
([openassetpricing.com](https://www.openassetpricing.com/)) — Fed FEDS 2021-037 /
CFR Working Paper 20-04.

**212 predictores** y **209 características a nivel firma** replicados de la
literatura con código estandarizado, descargables gratis, con paquete de Python
(`openassetpricing`). Es la alternativa libre a Compustat/CRSP si alguna vez se
quiere pasar de PCA (que solo necesita retornos) a factores condicionales con
características.

---

## 5. Qué implica para este repo

| Enfoque | Evidencia | Encaje con la infra actual |
|---|---|---|
| Cointegración por pares (actual) | **Decaída** (Do & Faff, Krauss); benchmark perdedor en Attention Factors | Implementado, pero sin resultados: 0 de 496 pares en 2015–2026 |
| **PCA-residual stat arb** | Avellaneda & Lee; benchmark en ~1.57 Sharpe neto | **Alta** — reusa z-score, half-life, señales, backtest |
| Factores latentes + deep learning | Management Science, Sharpe > 4 | Baja — necesita características de pago y mucho cómputo |
| Trend following | **La más fuerte** (1880–2016, Sharpe 0.76) | Media — implementación simple, pero es otro proyecto |

Lo que **sobrevive** del repo con el pivote a residuos de factores:
`compute_zscore`, `generate_signal`, `compute_half_life`, `run_backtest` (con sizing
de N piernas) y `screen_universe` (testear estacionariedad de N residuos sigue siendo
un screening múltiple).

Lo que **muere**: `compute_hedge_ratio`, `test_cointegration` y `screen_pair` — son
específicos de 2 activos.

Lo que **no cambia**: SPEC-001, 002, 003, 004, 005 y 006. Son sobre look-ahead,
multiple testing, consistencia backtest≡live, unidades de las métricas y hold-out:
agnósticos a la técnica.

La decisión formal del pivote está en **ADR-0005**.

---

## 6. Referencias

### Deterioro del enfoque clásico

- **Do, B. & Faff, R. (2010)**. *Does Simple Pairs Trading Still Work?* Financial
  Analysts Journal 66(4), 83–95.
  [CFA Institute](https://rpc.cfainstitute.org/research/financial-analysts-journal/2010/does-simple-pairs-trading-still-work)
- **Krauss, C. (2017)**. *Statistical Arbitrage Pairs Trading Strategies: Review and
  Outlook.* Journal of Economic Surveys 31(2).

### Cómo leer la literatura (replicación y multiple testing)

- **Harvey, C., Liu, Y. & Zhu, H. (2016)**. *…and the Cross-Section of Expected
  Returns.* Review of Financial Studies 29(1), 5–68.
  [RFS](https://academic.oup.com/rfs/article/29/1/5/1843824) ·
  [PDF](https://people.duke.edu/~charvey/Research/Published_Papers/P118_and_the_cross.PDF)
- **Hou, K., Xue, C. & Zhang, L. (2020)**. *Replicating Anomalies.* Review of
  Financial Studies 33(5), 2019–2133.
  [Notas de clase de los autores](https://global-q.org/uploads/1/2/2/6/122679606/slides_replication_2021may.pdf)
- **McLean, R. D. & Pontiff, J. (2016)**. *Does Academic Research Destroy Stock
  Return Predictability?* Journal of Finance 71(1), 5–32.
  [Wiley](https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12365)
- **Jensen, T. I., Kelly, B. & Pedersen, L. H. (2023)**. *Is There a Replication
  Crisis in Finance?* Journal of Finance 78(5).
  [Acceso abierto](https://onlinelibrary.wiley.com/doi/full/10.1111/jofi.13249) ·
  [Código y datos](https://github.com/bkelly-lab/ReplicationCrisis)

### Lo que tiene evidencia

- **Hurst, B., Ooi, Y. H. & Pedersen, L. H. (2017)**. *A Century of Evidence on
  Trend-Following Investing.* Journal of Portfolio Management 44(1).
  [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2993026)
- **Avellaneda, M. & Lee, J.-H. (2010)**. *Statistical Arbitrage in the US Equities
  Market.* Quantitative Finance 10(7), 761–782.
  [PDF](https://traders.studentorg.berkeley.edu/papers/Statistical%20arbitrage%20in%20the%20US%20equities%20market.pdf)
- **Guijarro-Ordóñez, J., Pelger, M. & Zanotti, G.** *Deep Learning Statistical
  Arbitrage.* Management Science.
  [INFORMS](https://pubsonline.informs.org/doi/10.1287/mnsc.2022.03132) ·
  [Preprint](https://arxiv.org/abs/2106.04028)
- **Attention Factors for Statistical Arbitrage** (2025). arXiv:2510.11616
  (preprint). [HTML](https://arxiv.org/html/2510.11616v1)
- **Gu, S., Kelly, B. & Xiu, D. (2020)**. *Empirical Asset Pricing via Machine
  Learning.* Review of Financial Studies 33(5), 2223–2273. Árboles y redes
  neuronales dominan a los métodos lineales en predicción de primas de riesgo.
  [NBER PDF](https://www.nber.org/system/files/working_papers/w25398/w25398.pdf)

### Datos

- **Chen, A. Y. & Zimmermann, T.** *Open Source Cross-Sectional Asset Pricing.*
  [openassetpricing.com](https://www.openassetpricing.com/) ·
  [Fed FEDS 2021-037](https://www.federalreserve.gov/econres/feds/files/2021-037pap.pdf)

### Referencias del enfoque actual

Las canónicas del pipeline implementado (Engle-Granger, Johansen, Vidyamurthy, Chan,
Bertram, López de Prado) están en `docs/METHODOLOGY.md` §7. No se duplican acá.
