# Pre-registro — universo ampliado + factores por ETF sectorial

- **Escrito:** 2026-10-18, **antes** de descargar los precios del universo nuevo y de
  correr cualquier test sobre él.
- **Contexto:** el walk-forward sobre 96 large caps (`research/wf011/`) no encontró
  reversión operable con la configuración de Avellaneda-Lee. La única señal (ventana
  expansiva) salió de mirar 28 combinaciones. Este experimento existe para que la
  próxima respuesta no tenga ese problema: **qué se mira y qué decide se fija acá.**

## Universo

Componentes **actuales** del S&P 500 (snapshot del 2026-10-18 en
`sp500_constituyentes.csv`, fuente `github.com/datasets/s-and-p-500-companies`), que
tengan cobertura ≥ 95 % desde 2014-01-01 (`clean_prices`).

Sesgo declarado: **supervivencia**. Son empresas que siguen en el índice hoy. Eso
*favorece* encontrar reversión (las que cayeron y no volvieron no están), así que un
resultado negativo es conservador y uno positivo hay que descontarlo.

## Diseño (igual al de wf011)

Re-ajuste cada 1 de enero con los **252 días hábiles anteriores**; proyección sobre el
año siguiente. OOS 2016-01-04 → 2026-10-16. s-score = z-score rolling causal de 60 días
del residuo acumulado (`compute_sscore`).

## Hipótesis primarias (las únicas que deciden)

| | Factores | Por qué |
|---|---|---|
| **H1** | PCA, **K = 15** | Es la elección de Avellaneda-Lee para un universo grande (~1,400 en el paper) |
| **H2** | **ETF del sector** de la acción, 1 factor | La otra variante del paper (§2): residuo contra su ETF sectorial |

ETFs: XLK, XLF, XLE, XLV, XLI, XLP, XLY, XLU, XLB, **IYR** (inmobiliario: XLRE nace en
2015-10, no alcanza para entrenar 2016) y **VOX** (comunicaciones: XLC nace en 2018-06).
Desvío declarado respecto del paper: el beta contra el ETF se estima una vez por año
sobre 252 días, no en ventanas de 60, para que sea comparable con H1 y con wf011.

## Test y umbral de decisión

- **Estadístico:** IC agregado a **h = 5 días** (correlación entre s-score(t) y el
  residuo acumulado de t+1..t+5, promediada sobre acciones). Nula: **misma permutación
  de fechas para todas las acciones**, 1,000 permutaciones.
- **Significancia:** p < **0.025** (Bonferroni sobre 2 hipótesis).
- **Relevancia económica:** señal de juguete (peso −s normalizado, sin costos) con
  **Sharpe bruto ≥ 1.0** y **breakeven ≥ 5 bps** por unidad negociada.

**Regla:** si H1 o H2 cumple **las tres** condiciones, se sigue con esa configuración a
SPEC-012/013. Si ninguna las cumple, **se cierra la línea de residuos** para acciones de
EE.UU. en daily y se vuelve a `docs/LITERATURE.md`.

## Secundario (descriptivo, NO decide)

PCA K=5; ETF sector + SPY (2 factores); ventana expansiva para H1 y H2; H2 sobre el
universo de 96 de wf011; IC a 1/10/20 días; IC por año; test por acción (A) con BH;
robustez (sin mercado / sin sector / mitades); potencia del test agregado con N nuevo.
