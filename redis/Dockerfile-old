FROM python:3.9-slim

LABEL maintainer="Query Cache Service"
LABEL description="Proxy con caché Redis para consultas a Elasticsearch"

# Variables de entorno
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Crear directorio de trabajo
WORKDIR /app

# Copiar requirements e instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente
COPY app.py .

# Crear usuario no-root
RUN useradd --create-home --shell /bin/bash querycache && \
    chown -R querycache:querycache /app
USER querycache

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:9201/health || exit 1

# Puerto del proxy
EXPOSE 9201

# Comando por defecto
CMD ["python", "app.py"]
