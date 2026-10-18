# SPEC-013 — Backtest multi-pierna sobre residuos

- **Estado:** Borrador (desbloqueado: ADR-0005 aceptado el 2026-10-15)
- **Origen:** consecuencia de ADR-0005; generaliza `run_backtest` de 2 a 1+K piernas
- **ADRs relacionados:** ADR-0005, ADR-0003 (unidad de retorno y PnL), ADR-0001
- **Timeframe objetivo:** daily
- **Archivos afectados:** `src/botcito_core/backtest.py`
- **Depende de:** SPEC-011, SPEC-012, **SPEC-005 y SPEC-004** (las unidades de PnL y el Sharpe tienen que estar bien antes de generalizar el bucle)

## 1. Problema

`run_backtest` asume **dos** piernas: `shares_a` de A contra `hedge_ratio · shares_b`
de B. Con el pivote, una posición es:

- **larga 1 unidad** de la acción `i`,
- **corta `βᵏᵢ`** de cada uno de los K eigenportafolios.

O sea **1 + K piernas**, y cada eigenportafolio es a su vez una combinación de las N
acciones. Eso cambia tres cosas de fondo:

1. **El sizing.** El notional de la cobertura es `Σₖ |βᵏᵢ| · notional_factorₖ`, que no
   es `β · precio_b` como hoy.
2. **Los costos.** Un round-trip pasa de 4 legs a `2 · (1 + K)` legs — con K=5, de 4
   a 12. A los costos de 0.1 % por leg eso es la diferencia entre operable y no.
3. **La señal.** El z-score se calcula sobre el residuo acumulado (SPEC-011), no sobre
   un spread de precios.

Implementar esto antes de SPEC-004 y SPEC-005 sería construir sobre métricas que ya
sabemos mal (Sharpe sin anualizar, PnL en unidades de `spread_std`).

## 2. Decisión metodológica

Generalizar, no duplicar: **una sola función de backtest** que recibe el conjunto de
piernas, con el caso de pares como instancia de 2 piernas. Dos implementaciones del
bucle de backtest es el camino directo a que diverjan, que es el error que ADR-0001
acaba de cerrar.

El sizing se deriva igual que en ADR-0003 — notional bruto desplegado = `capital` —
repartido entre la pierna larga y las K de cobertura en proporción a sus pesos.

**Decisión práctica sobre la cobertura:** en vez de operar los K eigenportafolios
como instrumentos separados, se agregan a **pesos netos por acción** antes de
ejecutar. Un eigenportafolio es una combinación de las N acciones; dos
eigenportafolios comparten las mismas acciones con signos posiblemente opuestos.
Agregando primero, los costos se pagan sobre la posición **neta** por acción, no por
pierna nocional. Sin esto el modelo de costos sobreestima de forma grosera.

## 3. Contrato

```python
@dataclass(frozen=True)
class Leg:
    """Una pierna de una posición: cuántas acciones de qué ticker."""
    ticker: str
    shares: float

def build_legs(model: FactorModel, ticker: str, capital: float,
               prices_entry: pd.Series) -> tuple[Leg, ...]:
    """
    Piernas de una posición larga en `ticker` cubierta con los K eigenportafolios,
    agregadas a pesos netos por acción. El notional bruto suma `capital`.
    """

def run_residual_backtest(prices: pd.DataFrame,
                          cumulative: pd.DataFrame,
                          model: FactorModel,
                          tickers: list[str],
                          start: str, end: str,
                          window: int,
                          entry: float, exit_: float, stop: float,
                          capital: float = 10_000.0,
                          transaction_cost: float = 0.001,
                          annualization_factor: int = 252) -> dict:
    """
    Backtest sobre residuos. Devuelve el mismo dict que `run_backtest` (SPEC-005),
    más `legs_por_trade` y `n_factors`.
    """
```

**Invariantes** (las de SPEC-005 se mantienen y se añaden tres):

- **I1–I7** — Las de SPEC-005: invarianza de escala, linealidad del PnL, retornos por
  período, drawdown sobre equity, costos por leg, notional = capital.
- **I8 (agregación neta)** — `build_legs` devuelve **a lo sumo una pierna por
  ticker**: las contribuciones de los K eigenportafolios se netean antes de ejecutar.
- **I9 (neutralidad al factor)** — La exposición neta de la posición a cada
  eigenportafolio es ≈ 0 por construcción: `|Σ piernas · βᵏ| < 1e-8`.
- **I10 (costos escalan con piernas)** — El costo de un round-trip es
  `transaction_cost × Σ|notional de cada pierna neta|`, abierto y cerrado.

**Errores:** los de SPEC-005, más `ValueError` si `tickers` tiene nombres que no están
en `model.tickers`, y si `prices` y `cumulative` no comparten índice.

## 4. Criterios de aceptación

- **AC1 (I8)** — `build_legs` no devuelve dos piernas con el mismo `ticker`.
- **AC2 (I9)** — La exposición neta a cada factor es `< 1e-8`.
- **AC3 (I6 de SPEC-005)** — `Σ |shares · precio|` de las piernas `== capital`.
- **AC4 (I1)** — Invarianza de escala: duplicar `capital` no cambia `sharpe_ratio`,
  `total_return` ni `max_drawdown`.
- **AC5 (I10)** — Caso cerrado de un trade: la diferencia entre
  `transaction_cost=0` y `=c` coincide con el recálculo desde las piernas
  registradas.
- **AC6 (I3)** — `len(returns)` == nº de barras evaluadas; las barras flat aportan
  `0.0`.
- **AC7 (compatibilidad)** — Sobre un `FactorModel` de **K=1 y 2 tickers**, el
  resultado coincide con `run_backtest` de SPEC-005 sobre el par equivalente, dentro
  de `1e-6`. Es el AC que demuestra que esto **generaliza** el caso de pares en vez de
  reemplazarlo por algo distinto.
- **AC8 (warmup)** — Ninguna posición se abre en las primeras `window − 1` barras.
- **AC9** — Ticker fuera de `model.tickers`, índices desalineados, `capital <= 0` y
  `transaction_cost < 0` lanzan `ValueError`.
- **AC10 (costos realistas)** — Caso numérico documental: con K=5 y
  `transaction_cost=0.001`, el costo de round-trip sobre el notional desplegado se
  reporta explícitamente en el dict, para que el impacto de pasar de 4 a 12 legs sea
  visible y no una sorpresa en el Sharpe.

## 5. Verificación

- **Archivo:** `tests/test_spec_013_backtest_residuos.py`
- **Comando:** `uv run pytest tests/test_spec_013_backtest_residuos.py -v`

**AC7 es el criterio central.** Si el backtest multi-pierna no reproduce el de pares
en el caso K=1/N=2, una de las dos implementaciones está mal y no sabríamos cuál.

## 6. Fuera de alcance

- **Triple-barrier** (P1.3) → `BACKLOG.md`.
- **Position sizing por volatilidad o Kelly** → `BACKLOG.md`. Acá el sizing es
  notional fijo = `capital`.
- **Límites de concentración** entre posiciones simultáneas (varias acciones pueden
  querer la misma cobertura) → `BACKLOG.md`. Es el "correlación entre posiciones
  abiertas" de METHODOLOGY §Riesgo, y con factores se vuelve más agudo.
- **Impacto de mercado y slippage** → `BACKLOG.md`.
- **Costo de financiamiento del short** → `BACKLOG.md`. Con K=5 las piernas cortas se
  multiplican, así que esto deja de ser despreciable antes que en el caso de pares.

## 7. Referencias

- **Avellaneda & Lee (2010)** §4 — construcción de la cartera y tratamiento de costos.
- **ADR-0003** — unidad de retorno y PnL, de donde se deriva el sizing.
- `docs/specs/005-pnl-sobre-capital.md` — el caso de 2 piernas que este spec
  generaliza.
