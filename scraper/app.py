import requests  # type: ignore
import json
import os
import time
from pymongo import MongoClient, errors, ASCENDING  # type: ignore
from datetime import datetime
from redis import Redis  # type: ignore
from flask import Flask, request, jsonify  # type: ignore
import threading

redis_host = os.environ.get("REDIS_HOST", "redis")
cache = Redis(host=redis_host, port=6379, db=0)

# Configuración de Flask
app = Flask(__name__)

mongo_uri = os.environ.get("MONGO_URI")
if not mongo_uri:
    raise ValueError("La variable de entorno MONGO_URI no está definida.")

client = MongoClient(mongo_uri)
db = client["waze_alertas"]
coleccion = db["eventos"]



# Limpiar la colección al inicio

result = coleccion.delete_many({})
print(f"Documentos eliminados al inicio: {result.deleted_count}", flush=True)



if "uuid_1" not in coleccion.index_information():
    coleccion.create_index([("uuid", ASCENDING)], unique=True, sparse=True)


def job():
    try:
        print("Descargando y procesando datos...", flush=True)

        url = (
            "https://www.waze.com/live-map/api/georss?"
            "top=-33.3464&bottom=-33.5121&"
            "left=-70.7404&right=-70.5459&"
            "env=row&types=alerts,traffic"
        )

        resp = requests.get(url)
        if resp.status_code != 200:
            print(f"Error HTTP {resp.status_code}", flush=True)
            return  

        data = resp.json()
        alerts = data.get("alerts", [])
        print(f"Eventos descargados: {len(alerts)}", flush=True)

        insertados = 0
        for alert in alerts:
            alert["timestamp"] = datetime.utcnow()
            try:
                coleccion.insert_one(alert)
                insertados += 1
            except errors.DuplicateKeyError:
                pass

  
        cache.setex("latest_alerts", 10, json.dumps(alerts, default=str))
        print("Caché en latest_alerts de Redis por 10s", flush=True)

    except Exception as e:
        print(f"Error en la iteración: {e}", flush=True)


@app.route('/ingest', methods=['POST'])
def ingest_alert():
    """Endpoint para recibir alertas del generador de tráfico"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        # Agregar timestamp si no existe
        if 'timestamp' not in data:
            data['timestamp'] = datetime.utcnow()
        
        # Insertar en MongoDB
        coleccion.insert_one(data)
        
        # Actualizar caché con las alertas más recientes
        recent_alerts = list(coleccion.find({}).sort("timestamp", -1).limit(100))
        cache.setex("recent_alerts", 30, json.dumps(recent_alerts, default=str))
        
        print(f"Alert ingested: {data.get('type', 'unknown')} - UUID: {data.get('uuid', 'N/A')}", flush=True)
        return jsonify({"status": "success", "message": "Alert ingested"}), 200
        
    except errors.DuplicateKeyError:
        return jsonify({"status": "duplicate", "message": "Alert already exists"}), 409
    except Exception as e:
        print(f"Error ingesting alert: {e}", flush=True)
        return jsonify({"error": str(e)}), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint para verificar el estado del servicio"""
    try:
        # Verificar conexión a MongoDB
        client.admin.command('ping')
        # Verificar conexión a Redis
        cache.ping()
        
        # Contar documentos en MongoDB
        total_docs = coleccion.count_documents({})
        
        return jsonify({
            "status": "healthy",
            "mongodb": "connected",
            "redis": "connected",
            "total_events": total_docs
        }), 200
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), 500


@app.route('/stats', methods=['GET'])
def get_stats():
    """Endpoint para obtener estadísticas de los datos"""
    try:
        total_events = coleccion.count_documents({})
        recent_events = coleccion.count_documents({
            "timestamp": {"$gte": datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)}
        })
        
        # Obtener tipos de eventos más comunes
        pipeline = [
            {"$group": {"_id": "$type", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        event_types = list(coleccion.aggregate(pipeline))
        
        return jsonify({
            "total_events": total_events,
            "recent_events": recent_events,
            "event_types": event_types
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def scraper_worker():
    """Función que ejecuta el scraper en un hilo separado"""
    while True:
        job()
        print("Esperando 1 segundo para más eventos...\n", flush=True)
        time.sleep(1)


if __name__ == '__main__':
    print("Iniciando Waze Scraper con API Flask...", flush=True)
    
    # Iniciar el scraper en un hilo separado
    scraper_thread = threading.Thread(target=scraper_worker, daemon=True)
    scraper_thread.start()
    
    # Iniciar la aplicación Flask
    app.run(host='0.0.0.0', port=5000, debug=False)
