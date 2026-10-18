# Técnica B — Literatura: residuos de factores + señal aprendida

- **Fecha:** 2026-10-18
- **Autor:** agente B (fase 1, solo documentos)
- **Alcance:** qué hacen exactamente los dos papers que sostienen la técnica B, qué
  baselines reportan, qué replicaciones independientes existen y qué Sharpe es
  razonable esperar. Complementa `docs/LITERATURE.md` §2 y §3.2; no lo reemplaza.

Regla de este documento: **cada cifra sale de la fuente enlazada** y se leyó en el
texto del paper (no en resúmenes de terceros). Lo que no se pudo leer en la fuente
primaria va marcado **(no verificado)**.

> **TL;DR**
>
> 1. El "Sharpe > 4" de Guijarro-Ordóñez/Pelger/Zanotti es **bruto, sin costos**. Con
>    costos (5 bps por transacción + 1 bp de short) y **factores PCA** el Sharpe neto es
>    **0.81–0.90 con K = 1–5 y negativo con K = 10 y 15** (2002–2016).
> 2. El "~1.57" de Attention Factors para PCA + LongConv es **el mejor de 8 valores de
>    K**; el rango es 1.19–1.57 neto (1998–2021). Es una señal aprendida con objetivo
>    Sharpe, no un s-score.
> 3. En los dos papers el **OU con umbrales** sobre residuos PCA tiene Sharpe bruto
>    bajo (≈ 0.2–1.3) y en Attention Factors **neto negativo en todos los K**. Nuestro
>    nulo lineal 2016–2026 es **compatible** con eso.
> 4. La información que explotan las redes está en la **forma de los últimos ~10–30
>    días** del residuo, con rebalanceo diario y rotación alta. Eso es justo lo que
>    nuestro s-score de 60 días no mira, y justo donde los costos pegan más fuerte.
> 5. **No hay replicación independiente publicada** con costos y período posterior a
>    2016. La única que encontramos (Long & Xiao 2024) está **retirada** por los
>    propios autores. La evidencia de ML diario sobre el S&P 500 más vieja
>    (Fischer & Krauss 2018) dice que el exceso de retorno **desapareció desde 2010**.
> 6. Expectativa tras McLean-Pontiff y nuestros costos: **Sharpe neto 0–0.5**, con
>    probabilidad no despreciable de 0.

---

## 1. Guijarro-Ordóñez, Pelger & Zanotti — *Deep Learning Statistical Arbitrage*

**Cita.** J. Guijarro-Ordóñez, M. Pelger, G. Zanotti. *Deep Learning Statistical
Arbitrage*. **Management Science** 72(9), 7502–7549 (2026). Crowell Memorial Second
Prize 2022. Preprint: [arXiv:2106.04028](https://arxiv.org/abs/2106.04028) (v1
2021-06-08, v2 2022-10-07). Publicación verificada en la
[página de investigación de Pelger](https://mpelger.people.stanford.edu/research).
Las cifras de abajo son del **arXiv v2** (no se pudo leer la versión de la revista;
si difieren, manda la revista).

### Qué hacen

| Pieza | Qué hacen exactamente |
|---|---|
| **Universo** | ≈ 550 acciones más grandes y líquidas de EE.UU. (≈ S&P 500), panel no balanceado, datos CRSP |
| **Período** | Residuos OOS 1998-01 → 2016-12; **trading OOS 2002-01 → 2016-12** (los primeros 4 años solo entrenan) |
| **Factores** | Tres familias: Fama-French observados (K = 1, 3, 5, 8), **PCA** local (K = 1, 3, 5, 8, 10, 15) e **IPCA** condicional con 46 características (K = 1…15). K = 0 = usar retornos crudos |
| **Estimación de factores** | Ventana rodante: Fama-French 60 días; **PCA 252 días** re-estimado en cada t−1; IPCA re-estimado anualmente |
| **Input de la señal** | Los **L = 30 últimos retornos acumulados del residuo** (robustez con L = 60, resultados muy parecidos) |
| **Arquitectura** | **CNN + Transformer**: 2 capas convolucionales con D = 8 filtros de tamaño 2 días + transformer con 4 cabezas de atención. Encima, una red feedforward que mapea la señal a un peso |
| **Objetivo** | **Sharpe directo de la cartera** (o media-varianza), no predicción + regla. Pesos normalizados con ‖w‖₁ = 1 en el espacio de acciones |
| **Partición** | Ventana de entrenamiento rodante de **1,000 días**, re-entrenada **cada 125 días**. Hiperparámetros elegidos con los primeros 1,000 días (1998–2001), sobre una grilla chica (Tabla A.II: 2 valores en 4 hiperparámetros) |
| **Costos** | Sin costos en los resultados principales. En §III.J: `0.0005·‖Δw‖₁ + 0.0001·‖min(w,0)‖₁` diario (5 bps por transacción + 1 bp por posición corta); **sin impacto de mercado** |
| **Cómputo** | PyTorch 1.5, **8 GPUs Titan V**, 2 Xeon de 32 cores, 1 TB RAM; ≈ **7 horas** por corrida completa de un modelo (19 años, L = 30, re-estimación cada 125 días) |

### Resultados (arXiv v2, Tabla I — Sharpe anualizado OOS 2002–2016, **sin costos**)

| Señal | Factores | K = 1 | K = 3 | K = 5 | K = 8 | K = 10 | K = 15 |
|---|---|---|---|---|---|---|---|
| CNN+Trans | PCA | 2.74 | 3.56 | 3.36 | 3.02 | 2.81 | 2.30 |
| CNN+Trans | IPCA | 3.22 | 3.93 | 4.16 | 3.95 | 3.97 | 4.17 |
| Fourier+FFN | PCA | 0.80 | 1.66 | 1.98 | 1.95 | 1.71 | 1.14 |
| OU+Umbral | PCA | 0.21 | 0.77 | 0.73 | 0.87 | 0.63 | 0.62 |

K = 0 (retornos crudos, sin factores): CNN+Trans **1.64**, Fourier+FFN 0.36, OU −0.18.

### Con costos (Tabla IX y Tabla A.X — CNN+Trans, objetivo Sharpe, 2002–2016)

| Factores | K = 0 | K = 1 | K = 3 | K = 5 | K = 10 | K = 15 |
|---|---|---|---|---|---|---|
| IPCA | 0.52 | 0.85 | 1.24 | 1.11 | 0.98 | 0.94 |
| **PCA** | 0.52 | **0.88** | **0.90** | **0.81** | **−0.08** | **−0.87** |

> **Esta es la fila que importa para nosotros** (PCA, solo retornos). Con costos
> modestos el Sharpe neto queda **por debajo de 1**, y con K = 15 —la configuración
> H1 de nuestro pre-registro anterior— es **negativo incluso con la red**. Más
> factores = residuos más chicos y una cartera de cobertura más cara.

### Otros hallazgos relevantes para el diseño

- **La señal vive en las últimas ~2 semanas**: la mitad del Sharpe desaparece al
  sostener la posición 1–2 semanas; con 22 días de tenencia sin solapamiento queda
  Sharpe ≈ 0.5 (§III, Fig. 12).
- **Un modelo constante** (entrenado una vez con 4 u 8 años y congelado) rinde menos
  que el re-entrenado, pero sigue ganándole a Fourier+FFN y a OU (Tablas VII–VIII):
  la señal es en parte estable.
- **Una FFN flexible sobre los residuos crudos** (sin filtro temporal) rinde peor que
  los modelos con filtro (§III.G): la ganancia está en la extracción de la señal
  temporal, no en la flexibilidad de la regla de asignación.
- Las estrategias con distintas familias de factores tienen correlación 0.2–0.45.

---

## 2. Epstein, Wang, Choi & Pelger — *Attention Factors for Statistical Arbitrage*

**Cita.** E. L. Epstein, R. Wang, J. Choi, M. Pelger. *Attention Factors for
Statistical Arbitrage*. **ICAIF '25** (6th ACM International Conference on AI in
Finance, Singapur, nov. 2025), DOI
[10.1145/3768292.3770398](https://doi.org/10.1145/3768292.3770398). Preprint
[arXiv:2510.11616](https://arxiv.org/abs/2510.11616) (2025-10-13).

> Corrección a `docs/LITERATURE.md` §3.2, que lo describe como "preprint sin revisión
> por pares": está publicado en las actas de una **conferencia** con revisión (ICAIF),
> no en una revista. Sigue siendo evidencia más débil que una revista de finanzas.

| Pieza | Qué hacen exactamente |
|---|---|
| **Universo** | 500 acciones más grandes por capitalización del mes previo, CRSP diario |
| **Período** | Datos 1990-01 → 2021-12; **OOS 1998-01 → 2021-12** (24 años) |
| **Características** | 39 de Chen et al. (Open Source Asset Pricing) + retorno/vol del día y semana previos + medianas transversales + tasa libre → dimensión 79 |
| **Factores** | *Attention factors*: pesos de factor = softmax sobre embeddings de las características (d = 32). Benchmark: **PCA sobre ventana rodante de 252 días** |
| **Input de la señal** | Los **30 últimos retornos diarios del residuo** (no el acumulado) |
| **Arquitectura** | **LongConv**: 1 capa, dimensión oculta 32, 32 convoluciones; Adam, lr 0.003, weight decay 0.05, dropout 0.1, 30 épocas |
| **Objetivo** | **Sharpe neto de costos** de la cartera + varianza explicada de los factores (λ = 100), en un solo paso. "Two-step" = factores estimados aparte y después la política LongConv entrenada con el mismo objetivo |
| **Partición** | Ventana rodante de **8 años**, re-entrenamiento **anual**; hiperparámetros con los últimos 2 años de la primera ventana. Dicen haber probado "a wide range of parameter choices" **sin decir cuántas** |
| **Costos** | Los mismos de GPZ: 5 bps por transacción + 1 bp de short |
| **Cómputo** | Cluster con 5 GPUs RTX A6000, 2 AMD EPYC 7763, 1 TB RAM; sin tiempos reportados |

### Resultados (Tabla 2, OOS 1998–2021, anualizado)

| Modelo | K | Sharpe bruto | Sharpe neto |
|---|---|---|---|
| Attention factors | 30 | 3.97 | **2.28** |
| Attention factors | 100 | 4.52 | 2.19 |
| **PCA + LongConv (two-step)** | 1 / 3 / 5 / 8 / 10 / 15 / 30 / 100 | 2.26 – 2.79 | **1.19 / 1.57 / 1.30 / 1.50 / 1.52 / 1.41 / 1.57 / 1.44** |
| **PCA + OU umbral** | 1 / 3 / 5 / 8 / 10 / 15 / 30 / 100 | 0.40 / 1.26 / 0.99 / 0.78 / 0.80 / 0.51 / 0.18 / −0.35 | **−2.54 a −7.05** |
| Mercado | – | 0.42 | 0.42 |

No reportan rotación, ni análisis por sub-período, ni Fourier/CNN+Trans como
benchmarks. Dicen que el desempeño se mantiene "even during the later part of the
sample", sin cifras.

> **Dos lecturas obligatorias.** (1) El "1.57" que cita ADR-0005 es el **máximo de
> una grilla de 8 K** reportada en la misma tabla; la mediana de la fila es ≈ 1.47.
> (2) La diferencia bruto → neto de PCA + LongConv es ≈ 1.1–1.2 de Sharpe: **la mitad
> del Sharpe bruto se va en costos** aun con 5 bps, que es optimista.

---

## 3. Qué baselines reportan, ordenados por complejidad

| Baseline | Dónde | Qué es | Resultado sobre residuos PCA |
|---|---|---|---|
| OU + umbral (Avellaneda-Lee) | GPZ, AF | κ, μ, σ del OU en ventana de 30 días → s-score → abrir con \|s\| > c, cerrar con \|s\| < c' (c ∈ {1, 1.25, 1.5}, c' ∈ {0.25, 0.5, 0.75}, elegidos en validación) | GPZ bruto 0.21–0.87; AF bruto −0.35–1.26, **neto negativo siempre** |
| FFN sobre residuos crudos | GPZ §III.G | La misma red de asignación, sin filtro temporal | Peor que los modelos con filtro (cifras en Tabla IV del paper, no transcriptas) |
| Fourier + FFN | GPZ | Coeficientes FFT de los 30 días acumulados → FFN con objetivo Sharpe | GPZ bruto 0.80–1.98 |
| K = 0 (sin factores) | GPZ | CNN+Trans sobre retornos crudos | Bruto 1.64, neto 0.52 |
| CNN + Transformer | GPZ | El modelo propuesto | Bruto 2.30–3.56 (PCA); neto 0.81–0.90 (K ≤ 5) |
| PCA + LongConv | AF | Señal temporal aprendida, objetivo Sharpe neto | Neto 1.19–1.57 |

**Ninguno de los dos papers reporta un baseline intermedio del tipo "features
hechas a mano de la trayectoria + modelo lineal o árboles".** Es el hueco que el
pre-registro llena con los escalones E1–E2: si una regresión sobre 15 features de
la trayectoria captura la mayor parte de lo que captura la red, la red no hace falta.

---

## 4. Antecedentes, replicaciones y críticas

### Avellaneda & Lee (2010) — el decaimiento ya estaba en el paper fundacional

*Statistical Arbitrage in the US Equities Market*, **Quantitative Finance** 10(7),
761–782 ([RePEc](https://ideas.repec.org/a/taf/quantf/v10y2010i7p761-782.html)).
Del abstract: estrategias PCA con Sharpe **1.44 neto en 1997–2007**, pero **solo 0.9
en 2003–2007**; ETF sectoriales 1.1 en 1997–2007. El supuesto de costos no figura en
el abstract (no verificado en el texto completo).

### Krauss, Do & Huck (2017) y Fischer & Krauss (2018) — ML diario sobre el S&P 500

- Krauss, Do & Huck, *Deep neural networks, gradient-boosted trees, random forests:
  Statistical arbitrage on the S&P 500*, **European Journal of Operational Research**
  259(2), 689–702 ([RePEc](https://ideas.repec.org/a/eee/ejores/v259y2017i2p689-702.html)).
  Constituyentes del S&P 500 **sin sesgo de supervivencia**, 1992–2015, señales a 1 día
  con retornos rezagados: > 0.45 % diario **antes de costos** para el ensamble con
  k = 10, y "profits are declining in recent years". El desglose 2010–2015 negativo
  que circula en resúmenes secundarios **(no verificado)** en la fuente primaria.
- Fischer & Krauss, *Deep learning with long short-term memory networks for financial
  market predictions*, **EJOR** 270(2), 654–669, DOI 10.1016/j.ejor.2017.11.054
  ([RePEc](https://ideas.repec.org/a/eee/ejores/v270y2018i2p654-669.html)). LSTM sobre
  el S&P 500, 1992–2015: 0.46 % diario y Sharpe 5.8 **antes de costos**, pero "as of
  2010, excess returns seem to have been arbitraged away with LSTM profitability
  fluctuating around zero after transaction costs". Y lo que la red aprendió: acciones
  de **volatilidad alta con perfil de reversión de corto plazo**.

> No son residuos de factores, pero son la evidencia publicada más cercana a "red
> neuronal sobre la trayectoria reciente de acciones del S&P 500 en daily", y dicen
> que la ganancia **se fue en 2010** y que lo que se aprendía era, en buena parte,
> **reversión de corto plazo**. Por eso el pre-registro incluye la reversión corta
> como baseline (E0c/E0d) y por eso el período de test no puede ser 2002–2016.

### Replicaciones de GPZ

- **Long & Xiao (2024)**, *A Deep Learning Approach for Trading Factor Residuals*,
  [arXiv:2412.11432](https://arxiv.org/abs/2412.11432). Dicen replicar GPZ en EE.UU.
  extendiendo el OOS a 2016–2024 y obtienen Sharpe "occasionally exceeding 10", que
  ellos mismos atribuyen a posible sobreajuste o costos mal contados. **La v2
  (2025-01-03) está marcada como retirada**, y un comentario en la página dice que
  usaron una lista **estática** del S&P 500 (sesgo de supervivencia). **No cuenta
  como evidencia**, y es un ejemplo exacto de lo que puede salir mal con nuestros
  datos (también usamos el S&P 500 actual).
- **Li & Papanicolaou**, *Statistical Arbitrage in Rank Space*,
  [arXiv:2410.06568](https://arxiv.org/abs/2410.06568) (v1 2024-10, v2 2026-06).
  Redes sobre residuos en "espacio de rangos" rinden mejor que en espacio de nombres.
  Las cifras que circulan (Sharpe 3.28 neto de 2 bps, 2007–2022) **(no verificado)**:
  no aparecen en el abstract y no se leyó el texto.
- **Adamczyk & Dąbrowski (2025)**, [arXiv:2512.02037](https://arxiv.org/abs/2512.02037):
  Avellaneda-Lee con PCA, ETFs y factores LSTM en Polonia (WIG20/mWIG40), 2017–2020.
  Mercado y método distintos (la red construye factores, no la señal); no informa
  sobre GPZ. Mencionado solo por completitud.

**No encontramos ninguna replicación independiente, publicada y no retirada, de
GPZ o de Attention Factors con datos posteriores a 2016 y con costos.** Hay que
leer los Sharpe de §1–2 como resultados de los autores, en su muestra.

---

## 5. Correcciones para `docs/LITERATURE.md` (las aplica el orquestador)

| Dice hoy | Lo que verificamos |
|---|---|
| GPZ "Sharpe OOS mayor a 4 … rentable después de fricciones" | > 4 es **bruto** (IPCA). Con costos: IPCA 0.94–1.24, **PCA 0.81–0.90 (K ≤ 5), negativo con K ≥ 10** |
| GPZ "Management Science (Crowell 2022)" | Publicado en **Management Science 72(9), 7502–7549, 2026** |
| Attention Factors "arXiv, sin revisión por pares" | Publicado en **ICAIF '25** (actas de conferencia, ACM) |
| AF "Sharpe bruto 3.97, neto 2.28" | Correcto para K = 30; el abstract dice "above 4" porque K = 100 da 4.52 bruto |
| "Factores PCA + LongConv ~1.57" | Es el **máximo** de 8 K (rango 1.19–1.57 neto) |
| "Factores PCA + señal temporal ≈ 1.57 … alcanzable sin deep learning" | **LongConv es deep learning** (red convolucional entrenada con objetivo Sharpe). Sin deep learning, lo que reportan es OU + umbral: neto negativo |
| AF input = trayectoria del residuo acumulado | AF usa los 30 **retornos** del residuo; GPZ usa los 30 **acumulados** |

---

## 6. Qué Sharpe esperar

Punto de partida, en la configuración más cercana a la nuestra (PCA, solo retornos,
large caps, costos de 5 bps + 1 bp de short):

| Fuente | Período | Sharpe neto PCA |
|---|---|---|
| GPZ, CNN+Trans, K = 1–5 | 2002–2016 | 0.81 – 0.90 |
| AF, PCA + LongConv, K = 1–100 | 1998–2021 | 1.19 – 1.57 |

Descuentos que aplican, en orden:

1. **McLean-Pontiff** (−58 % de retorno después de publicar; GPZ está en arXiv desde
   junio de 2021). Si la volatilidad no cambia, el Sharpe escala igual: 0.81–0.90 →
   **0.34–0.38**; 1.19–1.57 → **0.50–0.66**. Es una aproximación: McLean-Pontiff mide
   anomalías de sección cruzada mensuales, no estrategias diarias de stat arb.
2. **Selección del mejor K** en AF: el 1.57 es el máximo de la grilla; la mediana es
   ≈ 1.47.
3. **Costos más altos que 5 bps** para una cuenta personal (mínimos por orden,
   acciones enteras, spread efectivo). Con la mitad del Sharpe bruto yéndose en costos
   ya a 5 bps, duplicar el costo puede llevar el neto a cero.
4. **Fischer & Krauss**: para ML diario sobre el S&P 500, la ganancia neta ya era
   ≈ 0 desde 2010.

**Expectativa honesta: Sharpe neto entre 0 y 0.5 en 2021–2026, con probabilidad
real de que sea ≈ 0.** Un Sharpe neto ≥ 1 en nuestro test sellado sería más alto que
lo que los propios autores reportan para PCA con costos en 2002–2016, y habría que
tratarlo como sospechoso de leakage antes que como éxito (`PLAN_TECNICAS.md` §3).

---

## 7. ¿Es compatible nuestro resultado lineal nulo con lo publicado?

**Sí, y en dos sentidos.**

1. **Lo que probamos coincide con lo que los papers reportan como benchmark.** El
   s-score lineal / OU con umbrales sobre residuos PCA tiene en GPZ Sharpe bruto
   0.21–0.87 en 2002–2016 y en AF 0.18–1.26 bruto, **negativo neto en todo K**, en
   1998–2021. Nuestro Sharpe bruto de juguete en 2016–2026 fue −0.12 (96 acciones,
   K = 5) y +0.04 (455 acciones, K = 15). AF con K = 15 da 0.51 bruto sobre un período
   que incluye 1998–2015, los años fuertes de Avellaneda-Lee; que en 2016–2026 sea ≈ 0
   es la continuación del decaimiento que ya documentaba A-L (1.44 → 0.9 en 2003–07).
2. **Lo que no probamos es lo que los papers dicen que funciona.** Nuestros tests
   usaron un s-score de **60 días** con IC a h = 5. La señal de GPZ se concentra en
   los **últimos ~10 días** de una ventana de 30, con rebalanceo diario y una función
   no lineal de la forma de la trayectoria. Nuestro nulo **no refuta** eso: no lo
   miramos. Tampoco miramos la reversión corta del residuo (≤ 5 días), que es lo
   que Fischer & Krauss encontraron dentro de su LSTM.

Lo que sí nos dicen nuestros datos y hay que llevar al diseño:

- **El residuo tiene drift persistente** que anula la reversión dentro de cada año
  (STATUS, wf011). Un modelo re-entrenado con ventana rodante puede adaptarse a eso;
  un s-score fijo no. Es una razón legítima para probar B, no una garantía.
- **Con ETF sectorial el residuo tiene momentum** (z +3.7 a +5.1). Es un hallazgo a
  posteriori; si un modelo aprendido "descubre" momentum del residuo en desarrollo,
  hay que reconocerlo como algo que ya vimos, no como señal nueva.
- **K grande perjudica**: en GPZ con costos, K = 10 y 15 son negativos. Nuestra H1
  usó K = 15. El pre-registro B fija K = 5.

---

## 8. Implicaciones para el pre-registro

1. **Baselines obligatorios**: OU + umbral (benchmark de la literatura), s-score
   lineal (nuestro nulo conocido), reversión corta del residuo y reversión corta sin
   factores (K = 0). Si el modelo aprendido no le gana a la reversión corta, lo que
   aprendió es la anomalía de reversión de Lehmann/Jegadeesh (no verificado en este
   documento: citas conocidas, no releídas), no stat arb sobre residuos.
2. **Escalón intermedio que la literatura no reporta**: features de la trayectoria +
   ridge / árboles. Barato y diagnóstico.
3. **Test sellado posterior a la publicación de GPZ** (julio de 2021 en adelante),
   igual que la técnica A usa el período posterior a Hurst-Ooi-Pedersen.
4. **Costos sobre los pesos netos por acción**, incluida la cobertura de factores, y
   un escenario de estrés a 10 bps. GPZ y AF no modelan impacto.
5. **Universo con sesgo de supervivencia declarado**: la única replicación de GPZ que
   encontramos se cayó, entre otras cosas, por usar una lista estática del S&P 500.

---

## Fuentes

- Guijarro-Ordóñez, Pelger & Zanotti — [arXiv:2106.04028](https://arxiv.org/abs/2106.04028);
  publicación en Management Science 72(9) según [mpelger.people.stanford.edu/research](https://mpelger.people.stanford.edu/research)
- Epstein, Wang, Choi & Pelger — [arXiv:2510.11616](https://arxiv.org/abs/2510.11616),
  [HTML con tablas](https://arxiv.org/html/2510.11616)
- Avellaneda & Lee (2010) — [RePEc](https://ideas.repec.org/a/taf/quantf/v10y2010i7p761-782.html)
- Krauss, Do & Huck (2017) — [RePEc](https://ideas.repec.org/a/eee/ejores/v259y2017i2p689-702.html)
- Fischer & Krauss (2018) — [RePEc](https://ideas.repec.org/a/eee/ejores/v270y2018i2p654-669.html)
- Long & Xiao (2024, retirado) — [arXiv:2412.11432](https://arxiv.org/abs/2412.11432)
- Li & Papanicolaou — [arXiv:2410.06568](https://arxiv.org/abs/2410.06568)
- Adamczyk & Dąbrowski — [arXiv:2512.02037](https://arxiv.org/abs/2512.02037)
- Bailey & López de Prado (2014), *The Deflated Sharpe Ratio*, JPM 40(5), 94–107 —
  [SSRN 2460551](https://papers.ssrn.com/abstract=2460551) (usado en el pre-registro)
- McLean & Pontiff (2016), Harvey-Liu-Zhu (2016): ver `docs/LITERATURE.md` §2
