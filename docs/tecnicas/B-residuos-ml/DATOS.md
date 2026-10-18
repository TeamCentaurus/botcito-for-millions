# Técnica B — Datos, dependencias y cómputo

- **Fecha:** 2026-10-18
- **Autor:** agente B (fase 1, solo documentos)
- **Relacionado:** `PREREGISTRO.md` (este directorio), `research/wf_universo/`

Todo lo marcado **(estimado)** es una cuenta hecha en papel, no una medición. La
primera tarea de la fase 2 es medirlo (§5.4).

---

## 1. Universo

### Lo que ya está en disco

`data/wfu_precios_sp500.parquet` (gitignored, 10 MB): **455 acciones** del S&P 500
actual (snapshot 2026-10-18, `research/wf_universo/sp500_constituyentes.csv`) con
cobertura ≥ 95 % desde 2014. Verificado con una lectura corta:

| | Valor |
|---|---|
| Forma | 3,072 días × 455 acciones, **sin NaN** |
| Rango | 2014-07-31 → 2026-10-16 |
| Días desde 2021-07-01 (test sellado propuesto) | **1,330** |
| Días 2016-01-01 → 2021-06-30 | 1,383 |
| Precios | cierre ajustado (`load_yfinance(auto_adjust=True)`) |

### Lo que falta para el pre-registro propuesto

El período de **desarrollo** que propone `PREREGISTRO.md` (señal OOS desde 2009, con
residuos desde 2005 y ventanas de entrenamiento de 1,000 días) necesita precios
**desde 2004**. Hay que re-descargar con `load_yfinance` (SPEC-010) el mismo
universo con `start="2004-01-01"`. Cuántas de las 455 tienen historia desde 2004 es
**desconocido** hasta descargar; lo razonable es esperar que una parte no la tenga
(IPOs posteriores). Dos opciones, a decidir en el pre-registro:

- **Panel no balanceado** (como GPZ y AF): cada año de entrenamiento usa las acciones
  con cobertura completa en su ventana. Más acciones, más código.
- **Panel balanceado** con las que tienen historia desde 2004. Más simple, menos
  acciones y más sesgo de supervivencia.

La descarga **no entra en la fase 1** (regla del plan).

### Sesgo de supervivencia — dónde pega y hacia dónde

El universo son empresas que **están hoy** en el S&P 500. Dos efectos:

1. **Supervivencia clásica**: faltan las que quebraron o salieron del índice. Las
   acciones que cayeron y no volvieron no están, así que el panel tiene más
   "perdedoras que se recuperaron" de las que hubo. Eso **infla la reversión**, y un
   modelo aprendido puede aprender exactamente eso: "comprá lo que cayó, vuelve".
2. **Entrada al índice por haber subido**: empresas que hoy están porque crecieron
   (en 2005 eran mid caps). Infla el **momentum** de largo plazo.

Los dos crecen con la distancia a hoy. Consecuencias para el diseño:

- En **desarrollo (2009–2021-06)** el sesgo es grande. Sirve para elegir el escalón,
  no para estimar el Sharpe.
- En el **test sellado (2021-07 → 2026-10)** el sesgo es más chico (≈ 5 años), pero
  no cero. Es la razón para exigir umbral económico además del estadístico.
- La única replicación de GPZ que encontramos (Long & Xiao 2024) se retiró y un
  comentario señala justamente el uso de una lista estática del S&P 500
  (`LITERATURA.md` §4).

**Mitigación posible (no obligatoria):** una lista de membresía histórica del S&P 500
permitiría usar en cada fecha solo las acciones que estaban en el índice *en esa
fecha*. Corrige el efecto 2, no el 1: yfinance no tiene precios de la mayoría de los
deslistados. Fuentes candidatas: repositorios públicos de constituyentes históricos
**(no verificado: ni la fuente ni su calidad)**. No se propone como requisito.

### ETFs

No hacen falta para el escalonado principal (factores PCA). `data/wfu_precios_etf.parquet`
queda disponible si algún día se quiere la variante por ETF sectorial, que en el
pre-registro anterior mostró **momentum** en vez de reversión.

---

## 2. ¿Hacen falta características de firma?

**No, para todo lo que propone el pre-registro.** Los escalones E0–E4 usan factores
PCA, que necesitan **solo retornos**, y la señal sale de la trayectoria del residuo.
Es la variante "two-step PCA" de Attention Factors y la familia PCA de GPZ.

Las características solo hacen falta para IPCA (GPZ) o *attention factors* (AF), que
son el paso siguiente si B funciona con PCA. Sobre `openassetpricing`
(Chen & Zimmermann):

| Pregunta | Respuesta |
|---|---|
| ¿Qué da? | Retornos de portafolios de 212 predictores y **209 características a nivel firma** de OSAP + 3 de CRSP (Price, Size, STreversal) — según el README de [open-asset-pricing-download](https://github.com/mk0417/open-asset-pricing-download) |
| ¿Hace falta WRDS? | "To download all signals, you need a WRDS account" (README). El paquete de R equivalente dice que las variables de CRSP requieren suscripción a WRDS |
| Identificador | Por `permno` de CRSP **(no verificado)** |
| Frecuencia | Mensual **(no verificado)** |

El obstáculo práctico es el **mapeo `permno` → ticker** de yfinance: sin CRSP no hay
una tabla de enlace confiable, y los tickers cambian y se reciclan. **Conclusión: no
sirve sin WRDS para este proyecto hoy.** Si B pasa su test con PCA, evaluar IPCA es
otro pre-registro y otra discusión de datos.

---

## 3. Dependencias nuevas

`pyproject.toml` hoy tiene numpy, pandas, statsmodels (y scipy por arrastre), sin
scikit-learn ni PyTorch. Lo edita **solo el orquestador**; esto es la propuesta.

| Escalón | Necesita | Tamaño aprox. | Propuesta |
|---|---|---|---|
| E0 (baselines) | nada nuevo | — | — |
| E1 (ridge) | `scikit-learn` (o numpy a mano) | wheel ~10–15 MB **(no verificado)** | Grupo opcional `ml` |
| E2 (árboles) | `scikit-learn` (`HistGradientBoostingRegressor`) | ídem | Mismo grupo; **no** hace falta LightGBM/XGBoost |
| E3–E4 (redes) | `torch` **CPU-only** | ~200 MB de descarga, del orden de 1 GB instalado **(no verificado; medir con `uv`)** | Grupo opcional `ml-torch`, desde el índice CPU de PyTorch vía `[tool.uv.sources]` |

Reglas propuestas:

- **Nunca en las dependencias principales.** El `Dockerfile` de Airflow instala
  `pyproject.toml`; meter torch ahí agranda la imagen de la VM `e2-standard-2` sin
  motivo. Si B llega a producción, la inferencia (no el entrenamiento) se evalúa
  aparte.
- **CPU-only explícito**: el wheel por defecto de PyPI para Linux trae CUDA y pesa
  varias veces más **(no verificado el tamaño exacto)**.
- Fijar versión exacta en `uv.lock`, como el resto.
- Se instala **solo si el escalonado llega a E3** (ver regla de subida del
  pre-registro). Si E1–E2 ya deciden, torch no entra nunca.

---

## 4. Memoria

| Objeto | Tamaño (estimado) |
|---|---|
| Panel de precios 2004–2026, ~455 acciones | 5,700 días × 455 × 8 B ≈ 21 MB |
| Ventanas de 30 días para una ventana de entrenamiento de 1,000 días | 455 × 1,000 × 30 × 4 B (float32) ≈ 55 MB |
| Matriz de composición del residuo Φ por día (N × N) | 455² × 8 B ≈ 1.7 MB por día; **no guardar todas**: se recalcula o se guarda solo `loadings`/`eigenvectors` (N × K) |
| Features E1–E2 (≈ 16 por acción-día), panel completo | 455 × 5,700 × 16 × 4 B ≈ 165 MB |

Con 15 GB de RAM disponibles en WSL, ninguna es un problema.

---

## 5. Cómputo en la PC (16 cores, sin GPU)

### 5.1 Residuos (todos los escalones)

PCA sobre 252 días, re-estimado **cada día** (como GPZ y AF): ≈ 4,400 días hábiles
2005–2026 × una descomposición de una matriz 455 × 455 + N regresiones de K = 5.
**(estimado) minutos**, un orden de magnitud por debajo de los ~22 min de
`research/wf_universo/universo.py`, que además corría 1,000 permutaciones.

### 5.2 E0–E2 (sin redes)

- E0: operaciones vectorizadas sobre el panel; segundos.
- E1 ridge: ~455k filas × 16 features por ventana de entrenamiento, ~18
  re-entrenamientos anuales (2009–2026): **segundos**.
- E2 árboles (`HistGradientBoosting`, multihilo): decenas de segundos por
  re-entrenamiento **(estimado)** → **minutos** por configuración.

### 5.3 E3–E4 (redes)

Referencia publicada: GPZ tarda **≈ 7 horas en 8 GPUs Titan V** por corrida completa
de un modelo (19 años OOS, re-entrenamiento cada 125 días ≈ 30 re-entrenamientos,
100 épocas, ~550 acciones).

Estimación propia para CPU **(estimado, orden de magnitud)**:

- Un CNN+Transformer del tamaño de GPZ (8 filtros, 4 cabezas, L = 30) hace del orden
  de 10⁵ FLOPs por secuencia hacia adelante y ~3× con el gradiente.
- Una época = 455 acciones × 1,000 días ≈ 4.6·10⁵ secuencias ≈ 10¹¹ FLOPs.
- En CPU, con un modelo tan chico dominado por overhead, rinde 5–50 GFLOP/s
  efectivos → **2–30 s por época** → 100 épocas = **3–50 min por re-entrenamiento**.
- Re-entrenando **una vez por año** (≈ 18 veces): **1–15 horas por configuración**.

| Escalón | Configs (máx., pre-registro) | Tiempo total (estimado) |
|---|---|---|
| E3 (CNN chica) | 2 | 2–30 h |
| E4 (CNN+Transformer) | 2 | 2–30 h |

Es decir: **entre una noche y un par de días de CPU** para todo el escalonado neural.
Factible, pero no barato si hay que repetir. Decisiones que lo abaratan, ya tomadas
en el pre-registro: re-entrenamiento anual (no cada 125 días), máximo 4
configuraciones neurales, y **las permutaciones de la nula no re-entrenan** (se
permutan los retornos realizados contra pesos fijos), así que la nula cuesta lo
mismo que en wf011.

### 5.4 Primera tarea de la fase 2: medir antes de comprometerse

Antes de correr ninguna configuración neural: **un re-entrenamiento de E4 cronometrado
sobre datos sintéticos** (`tests/synthetic.py::factor_panel`, mismo tamaño que el
real). Si una época tarda > 60 s, se baja a re-entrenamiento cada 2 años o se recorta
el universo, **y se anota en el pre-registro antes de mirar datos reales**.

---

## 6. Resumen de lo que hay que traer

| Qué | Para qué | ¿Bloquea? |
|---|---|---|
| Precios 2004 → hoy del universo de 455 (yfinance, `load_yfinance`) | Desarrollo con ventanas de 1,000 días | Sí, para el desarrollo |
| `scikit-learn` (grupo opcional) | E1–E2 | Sí, para E1–E2 |
| `torch` CPU (grupo opcional) | E3–E4 | Solo si se sube a E3 |
| Membresía histórica del S&P 500 | Mitigar sesgo de entrada al índice | No |
| Características de firma / WRDS | IPCA, attention factors | No (fuera de alcance) |
