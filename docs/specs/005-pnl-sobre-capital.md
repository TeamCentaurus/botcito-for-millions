# SPEC-005 — PnL sobre capital invertido

- **Estado:** Borrador
- **Origen:** `docs/METHODOLOGY.md` §P0.5
- **ADRs relacionados:** ADR-0003 (unidad de retorno y PnL)
- **Timeframe objetivo:** daily
- **Archivos afectados:** `src/botcito_core/backtest.py`

## 1. Problema

```python
# backtest.py:61-67
pnl = position * (spread.iloc[i] - entry_spread)
pnl = pnl / model.spread_std      # ← unidades de "sigmas del spread"
pnl -= transaction_cost           # ← un solo costo por round-trip de DOS legs
returns.append(pnl)
```

Tres defectos encadenados:

1. **Unidad sin sentido económico.** `pnl / spread_std` no son dólares ni retorno
   sobre capital. El `total_pnl` reportado no se puede interpretar ni comparar con un
   benchmark. Y como el Sharpe se calcula sobre esta serie, su numerador y denominador
   están en la misma unidad rara (SPEC-004 depende de arreglar esto primero).
2. **Costos por trade, no por leg.** Un round-trip de un par toca **4 legs**: abrir A,
   abrir B, cerrar A, cerrar B. Restar `transaction_cost` una vez subestima los costos
   en ~4×, lo que es exactamente la diferencia entre un Sharpe operable y uno que no.
3. **Serie por trade, no por período.** `returns` tiene un elemento por trade cerrado.
   El `max_drawdown` (`backtest.py:121-129`) se calcula sobre `cumsum` de esos
   PnL-por-trade, así que no es el drawdown que vería la cuenta: ignora el mark-to-market
   de las posiciones abiertas.

## 2. Decisión metodológica

Definida en **ADR-0003**: retornos **por período** en unidades de **capital
invertido**, sizing por unidades de spread, costos **por leg**.

El PnL intermedio se calcula en dólares a partir de shares y precios, no del spread.
Eso obliga a que el backtest guarde los precios de entrada, no solo el spread de
entrada — es el cambio estructural de este spec.

⚠️ **ADR-0003 corrige la fórmula de sizing de METHODOLOGY §P0.5.** El boceto de la
auditoría da `C/2` de notional a cada pierna y además multiplica B por `hedge_ratio`,
con lo que B queda con `β·C/2` y el notional bruto desplegado es `(1+β)·C/2` en vez de
`C`. Este spec implementa la versión consistente: una unidad de spread es *long 1
acción de A / short β acciones de B* y cuesta `p_a + β·p_b`.

## 3. Contrato

```python
def run_backtest(prices: pd.DataFrame, model: PairModel,
                 start: str, end: str,
                 capital: float = 10_000.0,
                 transaction_cost: float = 0.001,
                 annualization_factor: int = 252) -> dict:
    """
    transaction_cost: fracción del notional, aplicada POR LEG. Un round-trip de un
        par cuesta ~4 * transaction_cost sobre el notional involucrado.
    capital: capital nominal asignado al par. Los retornos son invariantes a su valor;
        solo escala `total_pnl` y `equity_curve`.
    """
```

Cálculo de la posición (`C = capital`, notional bruto desplegado `= C`):

```python
unidades = capital / (price_a_entry + model.hedge_ratio * price_b_entry)
shares_a = unidades
shares_b = unidades * model.hedge_ratio
pnl_dolares = position * (
    shares_a * (price_a_t - price_a_entry)
    - shares_b * (price_b_t - price_b_entry)
)
# Forma cerrada equivalente del retorno:
#   retorno = position * Δspread / (price_a_entry + hedge_ratio * price_b_entry)
```

Costos por leg, sobre el notional de cada leg:

```python
costo_apertura = transaction_cost * (shares_a * price_a_entry + shares_b * price_b_entry)
costo_cierre   = transaction_cost * (shares_a * price_a_exit  + shares_b * price_b_exit)
```

Como los legs de apertura suman `C` por construcción, `costo_apertura / C ==
transaction_cost` exactamente, y el round-trip cuesta ≈ `2 * transaction_cost`.

Claves del dict devuelto:

| Clave | Tipo | Significado |
|---|---|---|
| `returns` | `np.ndarray` | Retorno **por período** (barra), `0.0` cuando está flat |
| `equity_curve` | `np.ndarray` | `(1 + returns).cumprod()` |
| `total_pnl` | `float` | **Dólares** |
| `total_return` | `float` | Fracción sobre `capital` |
| `sharpe_ratio` | `float` | Anualizado (SPEC-004) |
| `win_rate` | `float` | Sobre trades cerrados |
| `max_drawdown` | `float` | Fracción en `[0, 1]`, sobre `equity_curve` |
| `total_trades` | `int` | Trades cerrados |
| `trades` | `list[dict]` | Por trade: fechas, z y **precios** de entrada/salida (`price_a_entry`, `price_b_entry`, `price_a_exit`, `price_b_exit`), `shares_a`, `shares_b`, `posicion` (+1/-1), `pnl` en dólares y `costos` en dólares |

**Invariantes:**

- **I1 (invarianza de escala)** — `sharpe_ratio`, `total_return`, `max_drawdown` y
  `win_rate` **no cambian** al variar `capital`. Es la prueba de que el denominador es
  el correcto.
- **I2 (linealidad)** — `total_pnl` escala linealmente con `capital`.
- **I3** — `len(returns)` == número de barras evaluadas (no de trades). Las barras flat
  aportan `0.0`.
- **I4** — `max_drawdown >= 0` y, si hubo pérdida, coincide con el máximo peak-to-trough
  de `equity_curve`.
- **I5** — Con `transaction_cost=0`, el PnL de un trade es exactamente el PnL bruto en
  dólares de las dos piernas, recomputable desde los precios y shares registrados en el
  dict del trade.
- **I7 (notional)** — `shares_a * price_a_entry + shares_b * price_b_entry == capital`
  para todo trade: el notional bruto desplegado es el capital, ni más ni menos.
- **I6** — `backtest.py` no contiene ninguna división por `spread_std`.

**Errores:**

- `ValueError` si `capital <= 0`.
- `ValueError` si `transaction_cost < 0`.
- `ValueError` si el rango `start:end` no deja barras tras alinear ambas series.

## 4. Criterios de aceptación

- **AC1 (I6)** — No queda ninguna normalización por `model.spread_std` en el cálculo de
  PnL (verificable por comportamiento: cambiar `model.spread_std` a `1e9` no altera
  `total_pnl` ni `total_return`).
- **AC2 (I1)** — `run_backtest(..., capital=10_000)` y `capital=1_000_000` dan el mismo
  `sharpe_ratio`, `total_return` y `max_drawdown` (tolerancia `1e-9`).
- **AC3 (I2)** — `total_pnl` con `capital=20_000` es 2× el de `capital=10_000`.
- **AC4 (costos por leg)** — La diferencia de `total_pnl` entre `transaction_cost=0` y
  `transaction_cost=c` coincide exactamente con la suma de los 4 costos por leg
  recalculados desde los precios y shares registrados en cada trade (caso cerrado).
  Además, el costo de apertura en unidades de retorno es exactamente `c`.
- **AC5 (I3)** — `len(returns) == len(barras evaluadas)`, y las barras sin posición
  tienen retorno exactamente `0.0`.
- **AC6 (I4)** — Sobre una `equity_curve` construida con pérdida conocida, el
  `max_drawdown` coincide con el valor analítico.
- **AC7** — `total_pnl` en dólares coincide con el recálculo manual
  `shares × Δprecio` desde los precios registrados en cada trade (caso cerrado), y se
  cumple I7: el notional de entrada de cada trade es exactamente `capital`.
- **AC8** — `capital=0`, `capital=-1` y `transaction_cost=-0.1` lanzan `ValueError`.

## 5. Verificación

- **Archivo:** `tests/test_spec_005_pnl.py`
- **Comando:** `uv run pytest tests/test_spec_005_pnl.py -v`

| AC | Test |
|---|---|
| AC1 | `test_ac1_sin_normalizar_por_spread_std` |
| AC2 | `test_ac2_invarianza_de_escala` |
| AC3 | `test_ac3_pnl_escala_linealmente` |
| AC4 | `test_ac4_costos_por_leg` |
| AC5 | `test_ac5_retornos_por_periodo` |
| AC6 | `test_ac6_max_drawdown_sobre_equity` |
| AC7 | `test_ac7_pnl_en_dolares_caso_cerrado` |
| AC8 | `test_ac8_errores_de_entrada` |

## 6. Fuera de alcance

- Position sizing distinto de equal-dollar (vol-targeting, Kelly) → `BACKLOG.md`.
- Slippage y market impact → `BACKLOG.md`. Aquí solo comisión por leg.
- Triple-barrier → P1.3, `BACKLOG.md`.
- Costo de financiamiento del short (borrow fee) → `BACKLOG.md`.

## 7. Referencias

- `docs/METHODOLOGY.md` §P0.5 — el hallazgo, con el cálculo dollar-neutral propuesto.
- López de Prado (2018), cap. 14 — por qué el PnL debe expresarse sobre capital
  asignado para que las métricas sean comparables.
