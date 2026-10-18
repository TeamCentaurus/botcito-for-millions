# SPEC-002 — Corrección BH-FDR en el screening

- **Estado:** Implementada ✅
- **Aceptada por:** Leonel, 2026-10-12
- **Implementada:** 2026-10-12
- **Origen:** `docs/METHODOLOGY.md` §P0.2
- **ADRs relacionados:** ninguno
- **Timeframe objetivo:** daily
- **Archivos afectados:** `src/botcito_core/statistical_validation.py`
- **Depende de:** SPEC-007 (necesita un p-value por par bien definido)

## 1. Problema

```python
# statistical_validation.py:160-164
es_valido = (
    coint_result["cointegrado"] and      # p < 0.05, por par, sin corregir
    adf_result["estacionario"] and
    1 < hl < 60
)
```

`screen_pair` emite veredicto a α=0.05 **por par, de forma aislada**. Pero el uso real
es barrer un universo: con N tickers se generan `C(N,2)` pares — N=30 da 435 pares,
N=100 da 4,950. A α=0.05, **~5% de los pares aparecen "cointegrados" por puro azar**:
22 falsos positivos con N=30, 247 con N=100.

`functions/handle_stock_request/tickers.json` define el universo que se está
ingestando, así que este no es un riesgo teórico: es el escenario de uso.

Peor: no hay ninguna función que haga el barrido. Cada caller itera `screen_pair` por
su cuenta, así que no hay un lugar donde la corrección pueda aplicarse. Hay que crear
ese lugar.

## 2. Decisión metodológica

**Benjamini-Hochberg (control de FDR)** sobre la lista completa de p-values de
cointegración del universo barrido. BH sobre Bonferroni porque con miles de tests
Bonferroni es tan conservador que no sobrevive ningún par verdadero; FDR controla la
*proporción esperada* de falsos descubrimientos, que es la pregunta correcta cuando se
buscan candidatos para validar después.

Y una decisión estructural: **`screen_pair` deja de emitir veredicto de validez.** Un
par no puede saber si es válido sin conocer cuántos pares más se probaron. `screen_pair`
reporta diagnósticos; `screen_universe` decide. Esto elimina por construcción el camino
en que alguien usa el veredicto per-par sin corregir.

**El costo de BH es real y hay que conocerlo.** Con 231 tests, un par necesita
p ≲ 4·10⁻⁴ para sobrevivir en el segundo lugar del ranking: un par genuinamente
cointegrado con p=0.0009 **no** pasa (verificado empíricamente al diseñar los ACs). No
es un defecto de BH, es el precio de barrer un universo grande — y es el argumento
cuantitativo a favor del clustering previo (P1.5): reducir `C(N,2)` sube el poder
estadístico de cada test que sí se hace.

## 3. Contrato

```python
def screen_pair(prices: pd.DataFrame, ticker_a: str, ticker_b: str,
                hedge_method: str = "ols") -> dict:
    """
    Diagnósticos de UN par. NO emite veredicto de validez: eso requiere conocer el
    tamaño del universo barrido. Usar screen_universe().
    """

def screen_universe(prices: pd.DataFrame,
                    pairs: list[tuple[str, str]],
                    alpha: float = 0.05,
                    hedge_method: str = "ols") -> list[dict]:
    """
    Barre `pairs`, aplica Benjamini-Hochberg sobre los p-values de cointegración y
    emite el veredicto `valido` por par.
    """
```

Cambios en el dict de `screen_pair`:

- **Se elimina** la clave `valido`.
- **Se conserva**: `par`, `cointegracion`, `estacionariedad`, `half_life_dias`,
  `hedge_ratio`.
- **Se añade** `cumple_filtros_locales: bool` — solo ADF y half-life (los que sí son
  decidibles por par).

El dict de cada elemento de `screen_universe` es el de `screen_pair` más:

| Clave | Tipo | Significado |
|---|---|---|
| `p_value_corregido` | `float` | p-value ajustado por BH-FDR |
| `rechaza_h0_fdr` | `bool` | Decisión de BH al nivel `alpha` |
| `valido` | `bool` | `rechaza_h0_fdr and cumple_filtros_locales` |
| `n_pares_probados` | `int` | Tamaño del universo barrido (trazabilidad) |

**Invariantes:**

- **I1** — `len(resultado) == len(pairs)`, en el mismo orden que `pairs`.
- **I2** — `p_value_corregido >= p_value` para todo par (BH nunca hace más permisivo).
- **I3** — `valido` implica `rechaza_h0_fdr`: ningún par válido escapa a la corrección.
- **I4** — `screen_pair` no expone `valido`.
- **I5** — Monotonía en `alpha`: el conjunto de pares válidos con `alpha=0.01` es
  subconjunto del de `alpha=0.05`.

**Errores:**

- `ValueError` si un ticker de `pairs` no está en `prices.columns`.
- `ValueError` si `pairs` está vacío.
- `ValueError` si `alpha` no está en `(0, 1)`.

## 4. Criterios de aceptación

- **AC1** — `screen_universe` existe con esa firma y devuelve un dict por par, en el
  mismo orden de entrada (I1).
- **AC2** — Cada resultado tiene `p_value_corregido`, `rechaza_h0_fdr`, `valido` y
  `n_pares_probados`.
- **AC3** — Los `p_value_corregido` coinciden exactamente con
  `multipletests(pvals, alpha=alpha, method="fdr_bh")[1]` de statsmodels sobre los
  mismos p-values crudos (caso numérico cerrado).
- **AC4 (I2)** — `p_value_corregido >= p_value` en todos los pares del barrido.
- **AC5 (falsos positivos)** — Con `independent_universe(n_tickers=20, n=500, seed=0)`
  → 190 pares, todos random walks independientes: **ningún** par sale `valido=True`.
  Medido sobre el código actual, sin corrección pasarían **4** pares a α=0.05
  (p mínimo 0.0182); con BH el p corregido mínimo sube a 0.7313 y no pasa ninguno.
- **AC6 (no mata la señal verdadera)** — Universo mixto: 18 tickers independientes + 2
  pares cointegrados construidos (`beta=2.0, theta=0.1, seed=11` y
  `beta=1.5, theta=0.15, seed=33`) → 22 tickers, 231 pares. Sin corregir hay **11**
  rechazos a α=0.05; con BH quedan **exactamente los 2 pares construidos**.
- **AC7 (I4)** — `"valido" not in screen_pair(...)`, y `cumple_filtros_locales` sí está.
- **AC8 (I5)** — Los válidos con `alpha=0.01` son subconjunto de los de `alpha=0.05`.
- **AC9** — Ticker inexistente, `pairs=[]` y `alpha=1.5` lanzan `ValueError`.

## 5. Verificación

- **Archivo:** `tests/test_spec_002_fdr.py`
- **Comando:** `uv run pytest tests/test_spec_002_fdr.py -v`

| AC | Test |
|---|---|
| AC1 | `test_ac1_screen_universe_existe_y_ordena` |
| AC2 | `test_ac2_claves_del_resultado` |
| AC3 | `test_ac3_coincide_con_statsmodels` |
| AC4 | `test_ac4_corregido_mayor_o_igual` |
| AC5 | `test_ac5_pares_independientes_no_pasan` |
| AC6 | `test_ac6_no_mata_senal_verdadera` |
| AC7 | `test_ac7_screen_pair_no_decide` |
| AC8 | `test_ac8_monotonia_en_alpha` |
| AC9 | `test_ac9_errores_de_entrada` |

## 6. Fuera de alcance

- Clustering previo para reducir `C(N,2)` → P1.5, `BACKLOG.md`.
- Corregir también los p-values del ADF del spread. BH se aplica a la cointegración
  porque es el test que define el universo; el ADF es confirmatorio sobre un par ya
  seleccionado. Anotado en `BACKLOG.md` como pregunta abierta.
- Endurecer el rango de half-life de `1 < hl < 60` a `5 < hl < 30` → `BACKLOG.md`
  (cambia qué pares son válidos; es modelado, no correctitud).

## 7. Referencias

- Benjamini & Hochberg (1995), *Controlling the False Discovery Rate*, JRSS-B 57(1) —
  el procedimiento.
- Krauss (2017), §3 — multiple testing como el sesgo dominante en screening de pares.
- López de Prado (2018), cap. 8 — data snooping y el coste de buscar en un universo
  grande sin corregir.
