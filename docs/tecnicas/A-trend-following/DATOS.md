# Técnica A — Datos

- **Consulta hecha:** 2026-10-18, `yfinance` del entorno del repo (`uv run python -c ...`),
  `period="max"`, `auto_adjust=True`. Último dato: **2026-10-16**. No se guardó ningún
  archivo de datos.
- **Qué se miró:** fecha de inicio, huecos, volumen mediano 2017+ (solo para tiers de
  liquidez; ver nota al final) y, para el cálculo de apalancamiento, volatilidades
  **2009–2016**. **No se miró ningún retorno ni señal del período de test.**

---

## 1. ETFs vs futuros continuos de yfinance

Los papers (MOP, HOP) usan futuros. yfinance ofrece "futuros continuos" (`ES=F`,
`ZN=F`, `CL=F`, `GC=F`, `6E=F`…). Se probaron 13 contratos:

| Hallazgo | Evidencia de la consulta |
|---|---|
| Historia solo desde **2000** | `ES=F` 2000-09-18, `ZN=F` 2000-09-21, `CL=F` 2000-08-23, `GC=F` 2000-08-30, `6E=F` 2000-09-12 |
| **Rolls sin ajustar** | La serie salta de contrato a contrato sin back-adjustment; el salto del roll aparece como retorno. yfinance no publica fechas de roll |
| Datos corruptos | `6J=F`: \|log-retorno\| máximo de **2.31** en 2001-12-18 (imposible para el yen); `CL=F`: precio negativo el 2020-04-20, log-retorno indefinido |
| Sin tasa de financiamiento | El retorno de un futuro ya es "en exceso"; en ETFs hay que restar la tasa libre de riesgo |

**Decisión recomendada: ETFs.** Ganar 7 años de historia (2000 vs ~2007) no compensa
series con rolls contaminados y errores, que habría que limpiar a mano (cada limpieza
es una decisión de investigador). Los ETFs tienen precio ajustado por dividendos,
calendario único (todos cotizan en EE.UU.) y **son lo que se puede operar** desde una
cuenta minorista. Lo que se pierde:

- Fricciones de fondeo (préstamo de cortos, margen) que el futuro no tiene.
- Expense ratio (ya descontado en el precio ajustado; ver §4).
- Menos mercados y algunos poco líquidos (divisas).

Futuros continuos: **fuera** del test primario. Si alguna vez se quiere usar futuros, hace
falta una fuente con rolls ajustados (datos de pago o del broker): sería otro ADR.

### Excluidos por diseño

- **Apalancados e inversos** (`SSO`, `TQQQ`, `SH`, `TBT`…): reset diario → decaimiento
  por volatilidad dependiente del camino. El apalancamiento lo pone la estrategia, no
  el instrumento. Un corto se hace vendiendo el ETF, no comprando el inverso.
- **ETPs de VIX** (`VXX`…): contango estructural extremo, cambios de producto y cierres.
- **ETNs**: riesgo de crédito del emisor y cierres (p. ej. `CYB`, yuan, ya no existe en
  yfinance: "possibly delisted").

---

## 2. Universo propuesto (29 ETFs)

Criterios, fijados **antes** de mirar desempeño:

1. Una clase de activo de HOP (acciones, bonos, commodities, divisas) más REITs.
2. Inicio **≤ 2007-12-31**, para tener un período previo usable y el test 2017–2026
   completo con ventanas de 12 meses y covarianza de 3 años.
3. No apalancado, no inverso, no ETN.
4. Evitar duplicados casi perfectos (p. ej. `IAU` vs `GLD`, `VWO` vs `EEM`, `AGG`/`BND`
   ≈ mezcla de los bonos ya incluidos, `UUP` ≈ inverso de la canasta de divisas).

Fechas de inicio **verificadas con yfinance** (todas con 0 huecos desde el inicio):

### Acciones (8)

| Ticker | Qué | Inicio | Expense ratio |
|---|---|---|---|
| SPY | S&P 500 | 1993-01-29 | 0.09 % |
| IWM | Russell 2000 | 2000-05-26 | 0.19 % |
| EWJ | Japón | 1996-03-18 | 0.49 % |
| EWG | Alemania | 1996-03-18 | — |
| EWU | Reino Unido | 1996-03-18 | — |
| EWC | Canadá | 1996-03-18 | — |
| EWA | Australia | 1996-03-18 | — |
| EEM | Emergentes | 2003-04-14 | 0.72 % |

Por qué países y no `EFA`: HOP usa **índices por país** (11 índices). `EFA` (2001-08-27)
es una mezcla de los anteriores; se deja como alternativa si el dueño prefiere menos
peso en acciones.

### Bonos (7)

| Ticker | Qué | Inicio | Expense ratio |
|---|---|---|---|
| IEI | Tesoro EE.UU. 3–7 años | 2007-01-11 | — |
| IEF | Tesoro 7–10 años | 2002-07-30 | 0.15 % |
| TLT | Tesoro 20+ años | 2002-07-30 | 0.15 % |
| TIP | TIPS | 2003-12-05 | 0.18 % |
| BWX | Soberanos internacionales (sin cobertura FX) | 2007-10-11 | — |
| LQD | Corporativos grado de inversión | 2002-07-30 | 0.14 % |
| EMB | Soberanos emergentes en USD | 2007-12-19 | — |

**`SHY` (1–3 años, 2002-07-30) se excluye a propósito**: es casi caja (vol 2009–16 muy
baja; ver §5) y escalado a igual riesgo pediría un apalancamiento absurdo en un instrumento
fondeado. `IEI` cumple el rol del tramo corto. `HYG` (2007-04-11) queda fuera: su riesgo
es de acciones más que de tasas.

### Commodities (6)

| Ticker | Qué | Inicio | Expense ratio |
|---|---|---|---|
| GLD | Oro físico | 2004-11-18 | 0.40 % |
| SLV | Plata física | 2006-04-28 | 0.50 % |
| USO | Petróleo WTI (futuros) | 2006-04-10 | 0.86 % |
| UNG | Gas natural (futuros) | 2007-04-18 | — |
| DBA | Agrícolas (futuros) | 2007-01-05 | — |
| DBB | Metales industriales (futuros) | 2007-01-05 | — |

`DBC` (2006-02-06, 0.85 %) se excluye por solaparse con `USO`/`DBB` (es mayormente
energía). `CPER` (cobre) nace en **2011-11-15**: fuera por el criterio 2. `USO` y `UNG`
cargan contango y cambios de estructura (USO en 2020); queda en el precio, que es lo
que vería un inversor real.

### Divisas contra USD (6)

| Ticker | Qué | Inicio | Expense ratio |
|---|---|---|---|
| FXE | Euro | 2005-12-12 | 0.40 % |
| FXY | Yen | 2007-02-13 | 0.40 % |
| FXB | Libra | 2006-06-26 | — |
| FXF | Franco suizo | 2006-06-26 | — |
| FXA | Dólar australiano | 2006-06-26 | — |
| FXC | Dólar canadiense | 2006-06-26 | — |

`UUP` (2007-03-01, 0.75 %) se excluye: es una canasta del dólar contra las mismas
monedas, dominada por el euro, casi el inverso de `FXE`. Los ETFs de divisas son
**poco líquidos** (volumen mediano 2017+ de US$0.8–6.4 M/día); ver costos en el
pre-registro.

### REITs (2)

| Ticker | Qué | Inicio | Expense ratio |
|---|---|---|---|
| VNQ | REITs EE.UU. | 2004-09-29 | 0.13 % |
| RWX | REITs internacionales | 2006-12-19 | — |

`IYR` (2000-06-19) e `ICF` (2001-02-02) son alternativas a `VNQ`; no aportan nada para
2017+ y `VNQ` es más líquido y barato.

### Tasa libre de riesgo

`^IRX` (T-bill 13 semanas, rendimiento anualizado) desde **1960-01-04**. Alternativas
fondeadas: `BIL` (2007-05-30), `SHV` (2007-01-11). Se usa `^IRX` convertida a tasa
diaria (`IRX/100/252`, aproximación declarada: el IRX es rendimiento de descuento).

**Expense ratios:** son los que devuelve `yf.Ticker(t).info["netExpenseRatio"]` hoy
(en %/año). Los "—" no se consultaron. Son **actuales**, no históricos, y no hacen falta
para el backtest (§4).

---

## 3. Período usable

| Tramo | Fechas | Uso |
|---|---|---|
| Arranque (calentamiento) | 2007-12-19 → 2008-12 | El último ETF (`EMB`) nace 2007-12-19; la señal de 12 meses necesita 252 días |
| **Período previo** | primera señal completa (≈ 2009-01) → 2016-12-30 | Solapa con la muestra de HOP (hasta 2016): **no es fuera de muestra respecto de la literatura**. Solo descriptivo y para chequear la tubería |
| **Test post-publicación** | **2017-01-03 → 2026-09-30** | Último mes completo a la fecha de la corrida. ≈ 9.75 años, ≈ 2,450 días hábiles |

`clean_prices` (SPEC-010) hace `ffill().dropna()`, así que recorta el panel al día en
que existen los 29 tickers (2007-12-19). Con descarga desde 2007-12-01 la cobertura de
cada ticker queda > 99 % y el filtro de 95 % no descarta a nadie.

---

## 4. Ajuste de precios y qué incluye el retorno

- `auto_adjust=True` → precio ajustado por **dividendos y splits** = retorno total.
  Correcto para TSMOM (MOP/HOP usan retornos en exceso totales).
- El **expense ratio ya está descontado en el NAV**, y por lo tanto en el precio. **No se
  resta otra vez.** (En un corto, el fee juega a favor; en la práctica lo compensa el
  costo de préstamo, que sí se modela.)
- El ajuste reescribe la historia hacia atrás cada vez que hay un dividendo: la corrida
  tiene que **cachear el panel** (como `research/wf011/`) y registrar la fecha de
  descarga en el artefacto.
- Sesgo de supervivencia leve: los 29 son ETFs que **siguen existiendo**. Se eligieron
  por clase de activo, no por desempeño, pero hubo cierres en el camino (p. ej. `CYB`).

---

## 5. Apalancamiento que pide el diseño (dato para decidir el tope)

Volatilidad anualizada **2009–2016** (período previo, no el test):

| Clase | Rango de vol |
|---|---|
| Acciones | 17–27 % |
| Bonos | 3.7 % (`IEI`) – 15.5 % (`TLT`) |
| Commodities | 15 % (`DBA`) – 42 % (`UNG`) |
| Divisas | 9–13 % |
| REITs | 21–29 % |

Con igual riesgo por activo y vol de cartera 10 % (covarianza 2009–2016):

- todo largo: apalancamiento bruto ≈ **1.5×**;
- con signos mezclados (correlación efectiva baja, el caso típico de TSMOM): ≈ **4.1×**.

Una cuenta Reg-T admite ~2× overnight. Por eso el pre-registro fija un **tope de
apalancamiento bruto** (decisión del dueño, ver `PREREGISTRO.md`).

---

## 6. Dependencias

**Ninguna nueva.** Alcanza con lo que ya está en `pyproject.toml`:

| Necesidad | Con qué |
|---|---|
| Descarga y limpieza | `yfinance` + `data_loader.load_yfinance` / `clean_prices` (SPEC-010) |
| Señal, vol EWMA, covarianza | `pandas` / `numpy` |
| Bootstrap estacionario por bloques, test de diferencia de Sharpe | `numpy` (~30 líneas; no hace falta `arch`) |
| Artefacto y dashboard | `reporting.py` (SPEC-009), Streamlit ya instalado |

El paquete `arch` tendría el bootstrap estacionario hecho, pero no vale una dependencia
nueva para algo que se testea mejor escrito a mano contra `tests/synthetic.py`.

---

## Nota sobre lo que se miró

Para los tiers de liquidez se consultó el **volumen mediano 2017+** de 11 ETFs. Es dato
del período de test, pero no contiene información sobre retornos ni señal. Igual, para
no depender de esa mirada, el pre-registro define los tiers con el **volumen 2014–2016**,
calculado por el código.
