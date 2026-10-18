# Técnica A — Literatura de trend following / time-series momentum

- **Revisión:** 2026-10-18 (fase 1, agente A)
- **Complementa:** `docs/LITERATURE.md` §3.1 (no lo reemplaza; lo edita el orquestador)
- **Regla de lectura:** antes de creerle a cualquier número de acá, `docs/LITERATURE.md` §2
  (multiple testing, McLean-Pontiff). Las cifras son **de los papers**, no reproducidas
  por nosotros, salvo donde se dice "cálculo nuestro".

Convención de verificación:

- **Verificado** = leído en el texto del paper (PDF) o en el abstract de la editorial/
  repositorio, con el enlace indicado.
- **Verificado (secundario)** = la cifra sale de un resumen confiable que cita el
  abstract, no del paper.
- **(no verificado)** = no pude confirmar la cifra con una fuente primaria. No usar para
  decidir.

> **TL;DR.** El trend following tiene la evidencia más larga de las finanzas
> cuantitativas, pero el número que circula en el repo (Sharpe 0.76) es **neto de
> comisiones 2-y-20 de un hedge fund** y se apoya en futuros sobre 67 mercados. Después
> de 2009 su desempeño en la industria fue irregular (2009–2013 plano, 2018–19 malo,
> 2022 bueno, 2024–25 malo), y hay dos críticas serias: que buena parte del efecto es
> **escalado por volatilidad** y no tendencia (Kim-Tse-Wald), y que la evidencia
> activo-por-activo es **débil** una vez que se hace bien la inferencia (Huang et al.).
> Expectativa realista para nuestra versión con ~29 ETFs, neta de costos: **Sharpe
> 0.3, rango plausible 0.0–0.6**. Con 10 años de test eso es muy difícil de distinguir
> de cero (ver `PREREGISTRO.md`, potencia).

---

## 1. Los papers fundacionales

### 1.1 Moskowitz, Ooi & Pedersen (2012) — la definición

*Time Series Momentum*, **Journal of Financial Economics** 104(2), 228–250.
DOI [10.1016/j.jfineco.2011.11.003](https://doi.org/10.1016/j.jfineco.2011.11.003).
PDF leído: <https://fairmodel.econ.yale.edu/ec439/jpde.pdf>. **Verificado** (texto).

| Qué | Valor |
|---|---|
| Universo | **58** futuros/forwards líquidos: índices de acciones, divisas, commodities, bonos soberanos |
| Muestra principal | **enero 1985 – diciembre 2009** (resúmenes desde 1965) |
| Señal | signo del **retorno en exceso de los últimos 12 meses**, holding de 1 mes |
| Sizing | posición = **40 % / σ_{t−1}**, con σ = vol ex-ante EWMA de retornos diarios al cuadrado, **centro de masa 60 días**, anualizada con 261 |
| Cartera | promedio equiponderado de las posiciones disponibles; vol realizada ≈ **12 % anual** |
| Resultado por activo | los 58 tienen retorno TSMOM positivo; **52 significativos al 5 %** |
| Resultado cartera | **Sharpe anual "mayor a uno"** (bruto, sin costos) |
| Fuera de su muestra hacia atrás | 1966–1985: Sharpe **1.1** |
| vs. momentum cross-sectional | beta 0.66 (t 15.17), **alfa 76 bps/mes (t 5.90)** |

Dos detalles que importan para nosotros:

- La vol ex-ante se estima con datos hasta **t−1** y se aplica al retorno de t: es la
  misma regla de causalidad que ADR-0001.
- Los retornos persisten 1–12 meses y **se revierten parcialmente** a horizontes más
  largos. Por eso la ventana de 12 meses no es arbitraria, pero tampoco es "la óptima":
  es la que el paper eligió.

### 1.2 Hurst, Ooi & Pedersen (2017) — el siglo de evidencia

*A Century of Evidence on Trend-Following Investing*, **Journal of Portfolio
Management** 44(1), 15–29 (Fall 2017).
PDF del artículo publicado: <https://fairmodel.econ.yale.edu/ec439/hurst.pdf>.
Versión de trabajo de AQR (datos hasta 2013):
<https://www.TrendFollowing.com/whitepaper/Century_Evidence_Trend_Following.pdf>.

**Construcción (verificado en el texto publicado):**

- **67 mercados**: 29 commodities, 11 índices de acciones, 15 mercados de bonos, 12
  pares de divisas. **Enero 1880 – diciembre 2016.**
- Combinación **equiponderada de tres señales TSMOM: 1, 3 y 12 meses**. Cada señal es
  long si el retorno en exceso del horizonte es positivo, short si es negativo:
  **siempre hay posición** en cada mercado.
- Cada posición se dimensiona para el **mismo riesgo**; la suma de las tres se escala
  para una **vol ex-ante de cartera del 10 % anual**, con una matriz de covarianza
  **rolling de 3 años de retornos mensuales** (nota 7).
- Rebalanceo **mensual**.
- Costos de transacción estimados por clase en 2012, ×2 para 1993–2002 y ×6 para
  1880–1992; **no incluyen el costo de roll** de los futuros. Comisiones simuladas
  **2 % de gestión + 20 % de performance** con high-water mark.

**Números:**

| Cifra | Valor | Estado |
|---|---|---|
| Sharpe medio **por activo** (bruto de fees y costos), 1880–2016 | ≈ **0.4** | Verificado (texto) |
| Sharpe cartera, **neto de 2/20**, 1880–**2013** | **0.77** | Verificado (tabla de la versión de trabajo) |
| Retorno en exceso anual, bruto de fees / neto de 2/20, 1880–2013 | 14.9 % / 11.2 %, vol 9.7 % | Verificado (ídem) |
| Década 2000–2013, neto de 2/20 | retorno 7.9 %, **Sharpe 0.62** | Verificado (ídem) |
| Peor década (1910–19), neto de 2/20 | Sharpe 0.13 | Verificado (ídem) |
| Sharpe cartera neto de 2/20, 1880–**2016** (versión publicada) | 0.76 | **(no verificado)**: la tabla del artículo publicado es imagen y no se pudo leer; es la cifra que cita `LITERATURE.md` |
| Sharpe bruto de fees implícito, 1880–2013 | ≈ 1.5 (14.9 / 9.7) | **Cálculo nuestro**, aproximado: la tabla reporta una sola volatilidad |

Lo que el paper dice además, y que nos sirve:

- Con la señal **rezagada un mes**, el desempeño "se deteriora naturalmente, sobre todo
  en las señales cortas" (verificado, texto). Nuestro rezago de 1 día (ver
  `PREREGISTRO.md`) es mucho menor, pero la dirección del sesgo está documentada.
- Los propios autores proponen como escenario conservador un Sharpe futuro de **0.4 neto
  de fees y costos** ("la mitad de lo observado") (versión de trabajo, verificado).
- Las primeras ~10 décadas son out-of-sample respecto de MOP (que arranca en 1985).

> **Corrección para `docs/LITERATURE.md` §3.1** (la aplica el orquestador): el "Sharpe
> 0.76" es **neto de 2-y-20**, no el Sharpe de la estrategia. Para nosotros, que no
> pagamos fees de hedge fund, la cifra comparable es la bruta de fees y neta de costos
> (≈ 1.2–1.5 según período, cálculo nuestro), y **esa** es la que hay que descontar por
> McLean-Pontiff, menos activos y fricciones de ETF.

### 1.3 Babu, Levine, Ooi, Pedersen & Stamelos (2020) — evidencia fuera de muestra en activos nuevos

*Trends Everywhere*, **Journal of Investment Management** 18(1), 52–68.
Página: <https://www.aqr.com/insights/research/journal-article/trends-everywhere>.
**Verificado** (abstract): evidencia out-of-sample en **82 instrumentos no estudiados
antes** (futuros de acciones emergentes, swaps de tasas, divisas emergentes, commodities
exóticos, índices de CDS, futuros de volatilidad) y **16 factores long-short de
acciones**; TSMOM "funcionó" en esas clases y horizontes.
Sharpe bruto 1.17 para TSMOM 12 meses en activos tradicionales: **verificado
(secundario)**, resumen de Quantpedia (<https://quantpedia.com/?p=4233>); la página de
AQR no da cifras.

Es un test fuera de muestra **de activos**, no de tiempo: los mismos autores, el mismo
período. No resuelve la pregunta post-publicación.

---

## 2. Críticas: qué parte del efecto es tendencia

### 2.1 Kim, Tse & Wald (2016) — el escalado por volatilidad

*Time Series Momentum and Volatility Scaling*, **Journal of Financial Markets** 30,
103–124. DOI [10.1016/j.finmar.2016.05.003](https://doi.org/10.1016/j.finmar.2016.05.003).
**Verificado (secundario)**, abstract citado en
<https://quantpedia.com/deconstructing-the-time-series-momentum-strategy/>:

- Con 55 futuros, misma ventana que MOP (1985–2009), el **alfa mensual cae de 1.27 %
  (con pesos escalados por volatilidad) a 0.41 % sin escalado**.
- Sin escalado, TSMOM no supera al momentum cross-sectional (alfa 0.95 %).

**Implicación directa para el diseño:** el benchmark relevante no es "nada" ni
buy-and-hold, es una **cartera siempre long con el mismo escalado por volatilidad**
(risk parity ingenua). Si TSMOM no le gana a eso, lo que funciona es el escalado, no la
tendencia, y la implementación correcta es la más barata. Entra en el pre-registro como
H2.

### 2.2 Harvey, Hoyle, Korgaonkar, Rattray, Sargaison & Van Hemert (2018) — cuándo ayuda el escalado

*The Impact of Volatility Targeting*, **Journal of Portfolio Management** 45(1), 14–33.
DOI [10.3905/jpm.2018.45.1.014](https://doi.org/10.3905/jpm.2018.45.1.014).
PDF: <https://people.duke.edu/~charvey/Research/Published_Papers/P135_The_impact_of.pdf>.
**Verificado** (texto): más de 60 activos, datos diarios desde 1926. El targeting de
volatilidad **sube el Sharpe en activos de riesgo** (acciones, crédito) y en carteras
con mucho de ellos; en **bonos, divisas y commodities el efecto es despreciable**. Reduce
colas extremas en todas las clases. Mecanismo: el *leverage effect* de las acciones hace
que escalar por vol introduzca algo de momentum.

Lectura conjunta con 2.1: en un universo de ETFs cargado de acciones, el benchmark
vol-escalado long-only va a ser **difícil** de batir.

### 2.3 Huang, Li, Wang & Zhou (2020) — ¿está ahí?

*Time Series Momentum: Is It There?*, **Journal of Financial Economics** 135(3),
774–794. DOI [10.1016/j.jfineco.2019.08.004](https://doi.org/10.1016/j.jfineco.2019.08.004).
Abstract en <https://ideas.repec.org/a/eee/jfinec/v135y2020i3p774-794.html>.
**Verificado** (abstract):

- Regresiones activo por activo: **poca evidencia** de TSMOM, dentro y fuera de muestra.
- La regresión agrupada (pooled) da un t grande, pero **no supera los valores críticos
  de bootstrap** paramétrico y no paramétrico.
- La estrategia TSMOM es rentable, pero rinde **casi igual que una estrategia basada en
  la media histórica**, que no requiere predictibilidad.

Es exactamente el problema que el repo ya aprendió con el s-score: **el t-estadístico
ingenuo exagera**, y la nula correcta tiene que respetar la estructura de dependencia.
Consecuencia en el pre-registro: inferencia por **bootstrap por bloques**, no por t de
la media.

### 2.4 Goyal & Jegadeesh (2018) — la exposición neta

*Cross-Sectional and Time-Series Tests of Return Predictability: What Is the
Difference?*, **Review of Financial Studies** 31(5), 1784–1824.
Registro: <https://serval.unil.ch/notice/serval:BIB_03CCC0B82778>. **Verificado**
(abstract): la diferencia de desempeño entre TSMOM y momentum cross-sectional viene
sobre todo de la **exposición neta larga variable** de TSMOM; en clases de activos
internacionales, escalando igual, **el cross-sectional rinde más**.

Implicación: en el reporte hay que separar **exposición neta** (beta de la cartera al
mercado) de timing. No decide, pero se reporta.

### 2.5 Baltas & Kosowski — rotación y correlaciones

*Demystifying Time-Series Momentum Strategies: Volatility Estimators, Trading Rules and
Pairwise Correlations*, SSRN 2140091 (<https://papers.ssrn.com/abstract=2140091>).
**Verificado (secundario)**, abstract vía SSRN/Imperial:

- Mejor estimación de vol y señales continuas en vez de signo **bajan la rotación en más
  de un tercio** sin pérdida significativa de desempeño.
- El mal desempeño **post-2008** se explica por el **aumento de las correlaciones de a
  pares** entre activos.

Versión publicada en revista: **(no verificado)**.

---

## 3. Después de publicarse: 2010s y 2020s

No encontré un paper revisado por pares que mida TSMOM en futuros **subperíodo a
subperíodo después de 2012** con la metodología de MOP/HOP. Lo que hay:

### 3.1 La industria (índice SG Trend)

Korgaonkar (Man Group), *Trend Following and Drawdowns: Is This Time Different?*,
17-jun-2025, <https://www.man.com/insights/is-this-time-different>. **Verificado**
(lectura del artículo; es material de un gestor, no un paper):

| Período | Índice SG Trend |
|---|---|
| 2009–2013 (acumulado) | **−1.8 %** |
| 2014 | +19.7 % |
| 12 meses a enero 2019 | −16.0 % (peor ventana de 12 meses hasta entonces) |
| Ene 2019 → may 2024 | **+82.5 %** |
| 12 meses a abril 2025 | **−18.6 %** (nuevo peor registro) |

Año 2023: −3.3 % según StoneX; 2025 cerró en +2.39 % según Top Traders Unplugged:
**(no verificado)**, solo vistos en resúmenes de búsqueda.

Lectura: después de la publicación hubo una década irregular, un buen tramo
2019–2024 (que incluye 2022) y el peor drawdown de 12 meses del registro en 2024–25.
**Esto ya es público y lo sabemos**: el período 2017–2026 no es ciego para nosotros (ver
`PREREGISTRO.md`, sesgos declarados).

### 3.2 Decaimiento post-publicación en general

- **McLean & Pontiff (2016)** (ya en `docs/LITERATURE.md` §2): −26 % fuera de muestra,
  −58 % después de publicar, para 97 predictores **de acciones**. No incluye TSMOM.
- **Falck, Rej & Thesmar**, *Why and how systematic strategies decay*, arXiv 2105.01380
  (<https://arxiv.org/abs/2105.01380>). **Verificado** (abstract): el año de publicación
  explica 30 % de la varianza del decaimiento de Sharpe; el decaimiento de los factores
  nuevos crece ~5 puntos porcentuales por año. Es sobre anomalías de acciones, **no**
  sobre trend. Publicación en *Quantitative Finance* (2022) con el título *When do
  systematic strategies decay?*: **(no verificado)**, solo visto en búsqueda.

### 3.3 Evidencia con ETFs

No encontré un paper revisado por pares que pruebe TSMOM **con ETFs** y desempeño
post-2016. Lo más cercano es **Faber (2007)**, *A Quantitative Approach to Tactical Asset
Allocation*, Journal of Wealth Management (filtro de media móvil de 10 meses sobre 5
clases de activos): **(no verificado)**, solo resúmenes secundarios. Es long/flat, no
long/short, y no se usa para decidir nada.

Diferencias de un universo de ETFs respecto de los papers, todas en contra:

1. **Menos mercados** (~29 vs 58–67) y menos independientes (divisas solo contra USD,
   commodities agregados). TSMOM es una estrategia de **diversificación**: su Sharpe de
   cartera depende de la cantidad de apuestas no correlacionadas.
2. **Fricciones de financiación**: los ETFs son instrumentos fondeados. Ir corto cuesta
   préstamo del título; el apalancamiento que pide el target de vol cuesta margen por
   encima de la tasa libre de riesgo.
3. **Expense ratios** de 0.1–0.9 %/año (ver `DATOS.md`), ya incluidos en el precio.
4. Los ETFs de commodities y VIX cargan el costo de roll y contango; en futuros también
   existe, pero HOP declara que **no lo modeló**.

---

## 4. Sharpe neto esperado

**Estimación: 0.3, rango plausible 0.0–0.6.** Es un juicio, no una medición. Razonamiento:

| Paso | Sharpe | De dónde |
|---|---|---|
| HOP, bruto de fees, neto de costos, 2000–2013 | ≈ 1.2 | 11.3 % / 9.6 %, cálculo nuestro sobre la tabla verificada |
| MOP, bruto, 1985–2009 | > 1 | Verificado |
| Descuento post-publicación (McLean-Pontiff, 58 %; HOP mismo propone "la mitad") | ≈ 0.5–0.6 | §3.2 y §1.2 |
| Menos mercados (29 vs 67) y más correlación post-2008 (Baltas-Kosowski) | ≈ 0.4–0.5 | §2.5, §3.3 |
| Fricciones ETF: préstamo de cortos, spread de margen, spreads de FX/commodities | ≈ **0.3** | `PREREGISTRO.md`, modelo de costos |

Contraste: la industria (SG Trend) muestra una década 2009–2019 cercana a cero y un
2019–2024 fuerte; un Sharpe de largo plazo de 0.3 es compatible con eso. Pero también lo
es 0.0.

**Lo que importa de este número para el diseño del test:** con ~9.75 años de test, el
error estándar del Sharpe anualizado es ≈ 0.32 (Lo, 2002: `√((1 + SR²/2)/T)`). Un
Sharpe verdadero de 0.3 se detecta al 5 % con **potencia ≈ 24 %**. El pre-registro tiene
que asumir esto de frente: el test puede **refutar** ("no hay nada, o le gana el
benchmark") mucho mejor de lo que puede **confirmar**.

Y el valor de la técnica, como dice el plan, es **diversificación y baja correlación con
acciones**, sobre todo en caídas prolongadas (MOP y HOP documentan el "smile"), no un
Sharpe alto aislado.

---

## 5. Pendientes de verificación (no usar para decidir hasta verificarlos)

| Cita | Qué falta |
|---|---|
| HOP 2017, Sharpe 0.76 (1880–2016) | La tabla publicada es imagen; verificado solo 0.77 hasta 2013 |
| Babu et al. 2020, Sharpe 1.17 | Solo resumen secundario |
| Kim-Tse-Wald, cifras 1.27 % → 0.41 % | Abstract vía resumen; paper con paywall |
| Baltas & Kosowski, revista | Solo SSRN |
| Falck-Rej-Thesmar en Quantitative Finance | Solo visto en búsqueda |
| Faber 2007 | Solo resúmenes secundarios |
| SG Trend 2023 (−3.3 %) y 2025 (+2.39 %) | Solo resúmenes de búsqueda |
