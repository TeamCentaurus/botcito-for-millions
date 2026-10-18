# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Caso de uso

Bot de trading cuantitativo de **pairs trading** (arbitraje estadístico). Identifica pares de acciones cointegradas, modela el spread y emite señales `LONG_A_SHORT_B / SHORT_A_LONG_B / CLOSE / STOP` cuando el z-score del spread cruza umbrales calibrados. La pipeline operativa vive en GCP: una Cloud Function ingesta precios cada minuto a GCS, Airflow (en una VM) orquesta inferencia y alertas, y un servicio de notificaciones avisa al usuario.

## Arquitectura de alto nivel

El repo es un monorepo con **cuatro componentes desplegables independientes** (cada uno con su propio CI/CD) más una librería compartida:

```
                ┌─────────────────────────────────┐
   Scheduler ──▶│ Cloud Function                  │──▶ GCS (parquet por minuto)
   (Pub/Sub)    │ functions/handle_stock_request  │
                └─────────────────────────────────┘
                                                              │
                ┌─────────────────────────────────┐           │
   Cron DAG ───▶│ Airflow (VM)                    │◀──────────┘
                │ dags/  +  src/botcito_core      │
                └─────────────────────────────────┘
                            │ señales
                            ▼
                ┌─────────────────────────────────┐
                │ src/notifications_service       │──▶ Telegram / etc.
                └─────────────────────────────────┘
```

1. **`functions/handle_stock_request/`** — GCP Cloud Function 2ª gen (Python 3.11). Disparada por el topic Pub/Sub `cron-stock-topic` (Cloud Scheduler corre `*/1 9-16 * * 1-5` hora Lima). Llama a Twelvedata, valida que el dato pertenezca al día actual NY, agrega metadata de `lateness`, y escribe `gs://$BUCKET/botcito/stocks/YYYY-MM-DD/HHMMSS_<event_id>.parquet`.
2. **`dags/`** — DAGs de Airflow. Hoy solo `airflow_healthcheck_dag.py`. El plan (ver README) es agregar `data_ingestion.py` y `strategy_inference.py`. Los DAGs importan la lógica desde `botcito_core`.
3. **`src/botcito_core/`** — librería compartida (Python 3.12, paquete instalable `botcito_core`). Pipeline de modelado:
   - `statistical_validation.py`: filtrado por correlación → test de cointegración Engle-Granger → ADF sobre el spread → half-life. `screen_pair()` orquesta todo y devuelve veredicto.
   - `spread_calculator.py`: hedge ratio (OLS estático o Kalman dinámico), spread `A - β·B`, z-score rodante.
   - `model.py`: `train()` produce un `PairModel` (dataclass en `types.py`) con hedge ratio, media/std del spread y thresholds. `optimize_thresholds()` hace grid search por Sharpe.
   - `backtest.py`: simulación con costos de transacción, retorna Sharpe / win rate / max drawdown.
   - `alerts.py`: `Signal` enum + `generate_signal(zscore, model)`.
   - `data_loader.py`: `load_yfinance` (descarga) + `clean_prices` (higiene: cobertura mínima + ffill). SPEC-010.
   - `reporting.py`: artefacto de resultados versionado — `build_run`, `validate_run`, `write_run`, `read_run`, `list_runs`. Es el contrato entre el pipeline y el dashboard (ADR-0004). SPEC-009.
   - `news_agent.py`: sentimiento financiero con FinBERT (`ProsusAI/finbert`).
4. **`src/notifications_service/`** — microservicio (hoy es un stub). Está pensado para consumir señales y enviar alertas.
5. **`infra/`** — Terraform que provisiona una VM `e2-standard-2` en `us-central1-a` con startup script que instala Docker + docker-compose. Estado en bucket GCS `${PROJECT_ID}-gcs02-github-terraform-state-bucket`. Acceso vía IAP tunnel (puertos 22 / 8080 / 9000 / 9001). Lista de usuarios autorizados: `infra/variables.tf::iap_users`.

### Cómo `botcito_core` llega a Airflow

`docker-compose.yml` monta `./src` dentro del contenedor Airflow en `/opt/airflow/plugins/src` y define `PYTHONPATH=/opt/airflow/plugins`. Por eso los DAGs hacen `from botcito_core...` directamente. El `Dockerfile` de Airflow (`docker/airflow/Dockerfile`) instala las deps de `pyproject.toml` con `uv pip install --system` sobre `apache/airflow:2.10.2-python3.12` con OpenJDK 17 (necesario para PySpark).

### Dependencias por componente (importante: no son las mismas)

- **Repo principal / Airflow / `botcito_core`**: `pyproject.toml` + `uv.lock`, Python **3.12**, gestionado con `uv`.
- **Cloud Function**: `functions/handle_stock_request/requirements.txt` aparte, Python **3.11** (lo exige `gcloud functions deploy --runtime=python311`). No agregues deps de la función al `pyproject.toml`.

## Comandos comunes

### Desarrollo local (Python / `botcito_core`)

```bash
uv sync                              # instala deps del pyproject + grupo dev (jupyter, matplotlib)
uv run python -c "import botcito_core"
uv run jupyter lab                   # notebooks/ contiene 01_selector_pairs.ipynb y test-models.ipynb
```

### Stack local (Airflow + Postgres + MinIO)

Requiere `.env` (ver `.env.example`) con `MINIO_ADMIN_USER`, `MINIO_ADMIN_PASSWORD`, `AIRFLOW_FERNET_KEY`.

```bash
docker compose up -d --build         # primer levantamiento (compila imagen de Airflow)
docker compose up -d                 # cambios menores en DAGs (sin rebuild)
docker compose logs -f airflow-scheduler
docker compose down                  # detiene; los volúmenes postgres_data/minio_data persisten
```

UIs locales: Airflow `http://localhost:8080` (admin/admin), MinIO console `http://localhost:9001`.

### Cloud Function (deploy manual / debugging)

```bash
cd functions/handle_stock_request
export PROJECT_ID=$(gcloud config get-value project)
export BUCKET_NAME=$PROJECT_ID-gcs02-github-terraform-state-bucket
export TWELVEDATA_API_KEY=...
gcloud functions deploy handle-stock-request \
  --gen2 --region=us-central1 --runtime=python311 \
  --source=. --entry-point=handle_stock_request \
  --trigger-topic=cron-stock-topic \
  --service-account=function-stock-sa@$PROJECT_ID.iam.gserviceaccount.com \
  --set-env-vars=BUCKET_NAME=$BUCKET_NAME,TWELVEDATA_API_KEY=$TWELVEDATA_API_KEY \
  --memory=1024Mi --timeout=50s

# Disparar manualmente
gcloud pubsub topics publish cron-stock-topic --message='{"source":"manual-test"}'
```

Setup completo (APIs, SA, Pub/Sub, Scheduler) está documentado paso a paso en `functions/handle_stock_request/README.md`.

### Infra (Terraform)

```bash
cd infra
export TF_VAR_project_id=$(gcloud config get-value project)
terraform init -backend-config="bucket=${TF_VAR_project_id}-gcs02-github-terraform-state-bucket" \
               -backend-config="prefix=terraform/state"
terraform plan
terraform apply
```

### Acceso a la VM de Airflow (prod)

```bash
export PROJECT_ID=$(gcloud config get-value project)
gcloud compute ssh airflow-server-prod-vm-02 --zone=us-central1-a --project=$PROJECT_ID --tunnel-through-iap

# Tunneles para UIs (correr en local):
gcloud compute start-iap-tunnel airflow-server-prod-vm-02 8080 --local-host-port=localhost:8080 --zone=us-central1-a
gcloud compute start-iap-tunnel airflow-server-prod-vm-02 9001 --local-host-port=localhost:9001 --zone=us-central1-a
```

El repo en la VM vive en `/opt/botcito` y es propiedad del grupo `botcito-devs`.

### Tests

`pytest` + `ruff` configurados en `pyproject.toml` (grupo `dev`). Los tests viven en
`tests/` (la carpeta `test/`, singular, está vacía y sin trackear — ignórala).

```bash
uv run pytest -q                                  # suite completa
uv run pytest tests/test_spec_002_fdr.py -v       # los ACs de un spec
uv run ruff check tests/                          # lint (src/ todavía no se lintea)
```

### Correr el pipeline y ver resultados

```bash
uv run jupyter lab notebooks/02_pipeline_run.ipynb   # corrida → runs/<run_id>.json
uv run streamlit run app/dashboard.py                # dashboard local (lee runs/)
```

`notebooks/02_pipeline_run.ipynb` es **solo orquestador**: llama funciones de
`botcito_core` y escribe el artefacto. Nada de lógica en celdas — si hace falta una
función nueva, va a `botcito_core` con su spec y sus tests.

El dashboard es un **lector puro** del artefacto (ADR-0004): no importa
`run_backtest`, `screen_universe` ni `train`, y un test sobre el AST lo verifica.
`notebooks/01_selector_pairs.ipynb` quedó **obsoleto**: usa `screen_pair(...)["valido"]`,
clave que SPEC-002 eliminó a propósito.

Dos tipos de test conviven:

- **Tests de criterios de aceptación** (`tests/test_spec_00X_*.py`): uno por spec de
  `docs/specs/`. Los ACs aún no implementados llevan
  `@pytest.mark.xfail(strict=True)`, así que la suite está verde hoy. Al implementar el
  spec el test pasa, el **XPASS rompe la suite** y obliga a quitar el marker — es
  intencional: no se puede implementar en silencio.
- **Guardas de regresión** (`tests/test_regresion_*.py`, `tests/test_synthetic.py`): sin
  marker. Protegen comportamiento que ya es correcto.

`tests/synthetic.py` genera datos con **ground truth conocido** (OU con half-life
analítica, pares cointegrados con beta conocido, random walks independientes para medir
falsos positivos, y `corrupt_after`/`corrupt_between` para tests de leakage). Es la base
de todo AC falsificable: úsalo antes de inventar fixtures nuevas.

## Flujo de trabajo spec-driven

> **Para retomar el proyecto después de una pausa: leer `docs/STATUS.md` primero.**
> Tiene la decisión vigente (ADR-0005, pivote a factores), el estado de cada spec, qué no hacer y los
> comandos para arrancar en frío.


Los hallazgos metodológicos no se arreglan directo: se convierten en **specs** con
contrato y criterios de aceptación atados a tests.

| Dónde | Qué es |
|---|---|
| `docs/METHODOLOGY.md` | Auditoría de origen: 7 hallazgos P0 (correctitud) + 7 P1 (metodología) |
| `docs/LITERATURE.md` | Qué técnicas tienen evidencia científica hoy, con citas. **Leerlo antes de proponer una técnica nueva**: documenta que el OU-con-thresholds del repo aparece en la literatura como benchmark con Sharpe neto negativo |
| `docs/specs/` | Un spec por hallazgo: contrato, invariantes, ACs. `README.md` tiene el índice y el orden de implementación; `TEMPLATE.md` la estructura; `BACKLOG.md` lo pendiente sin spec |
| `docs/adr/` | Decisiones transversales, todas aceptadas: **ADR-0001** z-score rolling causal en backtest y live, **ADR-0002** daily, **ADR-0003** retornos por período sobre capital, **ADR-0004** el reporting lee un artefacto y no recalcula. **ADR-0005** pivota de pares a residuos de factores (aceptado 2026-10-15) |
| `tests/` | El criterio de cierre de cada spec |

Ciclo: `Borrador` → `Aceptada` (la acepta el dueño del modelado; §3 y §4 se congelan) →
`Implementada` → `Verificada`.

**Regla dura:** una vez *Aceptada*, no se editan §3 Contrato ni §4 Criterios de
aceptación. Si el contrato está mal, el spec vuelve a `Borrador` con una nota. Ajustar
el criterio para que el código pase es borrar la verificación.

Agentes y comandos (`.claude/`):

| Comando | Agente | Rol |
|---|---|---|
| `/spec-new <hallazgo>` | `spec-author` | Escribe el spec. Solo toca `docs/specs/` y `docs/adr/` |
| `/spec-do <id>` | `spec-implementer` | Implementa un spec *Aceptada*. No puede tocar el contrato ni los ACs |
| `/spec-verify <id>` | `backtest-auditor` | Reproduce los ACs y busca leakage con experimentos. Read-only |
| `/review-strategy <ruta>` | `quant-reviewer` | Segunda opinión metodológica contra el spec vigente |

Decisiones vigentes: **z-score rolling causal, idéntico en backtest y live** (ADR-0001 —
`spread_mean`/`spread_std` del training son diagnóstico, no insumo de la señal), **daily**
como timeframe (ADR-0002; 1-min diferido con condiciones de entrada explícitas) y
**retornos por período sobre capital invertido** (ADR-0003, que corrige la fórmula de
sizing de METHODOLOGY §P0.5).

El andamiaje SDD (`.claude/`, `CLAUDE.md`, `docs/`, `tests/`, `research/`, `app/`) está
commiteado en `main` desde el 2026-10-18 (con `[skip ci]`). Todavía no hay workflow de CI
de tests. **Ojo:** cualquier push a `main` dispara `deploy_airfllow_image.yml` (deploy a
la VM); para commits que no deben desplegar, usar `[skip ci]` en el mensaje o una rama.

## CI/CD

Tres workflows en `.github/workflows/`, cada uno disparado por paths distintos:

| Workflow | Trigger | Runner | Acción |
|---|---|---|---|
| `terraform_infra.yml` | push/PR a `main` con cambios en `infra/**` | `ubuntu-24.04` + Workload Identity Federation | `terraform plan` + `apply` (apply solo en push a main) |
| `deploy_handle_stock_request.yml` | push a `main` con cambios en `functions/handle_stock_request/**` | `ubuntu-latest` + WIF | `gcloud functions deploy` |
| `deploy_airfllow_image.yml` | push a `main` (sin filtro de path) | **self-hosted** runner en la VM | `git reset --hard origin/main` + `docker-compose up -d`. Solo rebuilda imagen si cambian `docker/`, `src/`, `pyproject.toml`, `uv.lock` o `docker-compose.yml` |

Secrets requeridos en el repo: `IDENTITY_PROVIDER`, `SERVICE_ACCOUNT`, `TWELVEDATA_API_KEY`. Variable: `GCP_PROJECT_ID`.

## Convenciones y notas

- Los imports dentro de `botcito_core` usan el nombre del paquete (`from botcito_core.xxx import ...`), no rutas relativas. `pyproject.toml` declara `where = ["src"]` para que `setuptools` lo encuentre.
- `src/botcito_core/monitoring.py` tiene imports legacy (`from src.data_loader ...`, `from src.alerts ...`) que **no resuelven** contra el layout actual — tratarlo como código a refactorizar, no como referencia.
- `notebooks/` está en `.gitignore` y no debería commitearse. La carpeta existe localmente para experimentación.
- El esquema de datos en GCS es `gs://$BUCKET/botcito/stocks/YYYY-MM-DD/HHMMSS_<event_id>.parquet` con columnas: `ticker, datetime, open/high/low/close/volume, ingested_at, event_time, is_late, lateness_seconds`.
- La Cloud Function descarta silenciosamente datos cuya fecha NY no coincida con "hoy NY" — no es un bug, es protección contra datos rezagados de Twelvedata fuera de horario de mercado.
