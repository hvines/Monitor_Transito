# MongoDB a Elasticsearch - Datos Brutos
FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código del conector
COPY app.py .

# Variables de entorno por defecto
ENV MONGO_URI="mongodb://root:example@mongodb:27017/?authSource=admin"
ENV ES_HOST="elasticsearch:9200"

# Comando por defecto
CMD ["python", "app.py"]
