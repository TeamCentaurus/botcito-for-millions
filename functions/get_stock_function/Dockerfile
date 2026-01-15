FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

# Instalar dependencias del sistema necesarias para pyarrow
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libc6-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY tickers.json .

# Exponer puerto (Cloud Run / Functions)
EXPOSE 8080

# Comando de arranque
CMD ["functions-framework", "--target=handle_stock_request", "--port=8080"]