# Base oficial de Airflow
FROM apache/airflow:2.10.2-python3.12

USER root

# Instalar Java (Requerido para PySpark)
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-17-jre-headless \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Instalar 'uv'
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Configurar Java Home
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64

USER airflow

# Copiamos los archivos de dependencias
COPY pyproject.toml uv.lock ./

# Instalamos las librerías usando uv
# Nota: Instalamos en el sistema (no venv) porque Airflow ya maneja su entorno
RUN uv pip install --system --no-cache -r pyproject.toml