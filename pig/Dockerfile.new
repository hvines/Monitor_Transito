# pig/Dockerfile - Simplified for auto-processing

FROM python:3.11

WORKDIR /app

# Instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Crear directorios
RUN mkdir -p /data/raw /data/processed /scripts

# Copiar scripts y el auto-processor
COPY scripts/ /scripts/
COPY pig_auto_processor.py .

# Variables de entorno
ENV MONGO_URI="mongodb://root:example@mongodb:27017/?authSource=admin"
ENV ES_HOST="elasticsearch:9200"

# Comando por defecto - ejecutar el auto-processor
CMD ["python", "pig_auto_processor.py"]
