# Botcito for millions

## Estructura del repo

```text
BOTCITO-FOR-MILLIONS/
├── .github/                   # CI/CD workflows
├── dags/                      # 1. ORQUESTACIÓN (Airflow DAGs)
│   ├── data_ingestion.py      # Pipeline: Fetch Data -> Kafka/MinIO
│   └── strategy_inference.py  # Pipeline: Read Data -> ML Model -> Buy/Sell Signal
├── docker/                    # 2. CONFIGURACIÓN DE CONTENEDORES
├── infra/                     # 3. INFRAESTRUCTURA (Terraform - ya lo tienes)
│   ├── main.tf
│   └── ...
├── notebooks/                 # 4. EXPERIMENTACIÓN
│   └── test-models.ipynb
├── src/                       # 5. CÓDIGO FUENTE (Lógica de Negocio)
│   ├── bot_core/              # LIBRERÍA COMPARTIDA (Tu "Business Logic")
│   │   ├── __init__.py
│   │   ├── connectors.py      # Wrappers para MinIO, Postgres, Kafka
│   │   ├── strategies.py      # Lógica de trading y ML (Modelos LGBM aquí)
│   │   └── utils.py
│   └── notification_service/  # MICROSERVICIO (API / Worker)
│       ├── main.py            # FastAPI/Flask app
│       └── telegram_bot.py    # Lógica de envío de alertas
├── tests/                     # Unit & Integration tests
├── .env                       # Variables de entorno (NO subir a git)
├── docker-compose.yml         # El orquestador de infraestructura local/VM
├── pyproject.toml             # Definición del paquete y dependencias (uv)
├── uv.lock                    # Librrerias con hashes para reproducibilidad
└── README.md
```
