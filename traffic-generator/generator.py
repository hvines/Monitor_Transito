import os
import time
import json
import random
import logging
from datetime import datetime
from pymongo import MongoClient
import redis

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TrafficGeneratorService:
    def __init__(self):
        # Configuración
        self.EVENTS_PER_SEC = float(os.environ.get("EVENTS_PER_SEC", 5))
        self.DISTRIBUTION = os.environ.get("DISTRIBUTION", "deterministic").lower()
        self.CACHE_TTL = 10  # TTL de 10 segundos igual que el scraper
        
        # Bbox de Santiago
        self.SANTIAGO_BBOX = {
            "top": -33.3464,
            "bottom": -33.5121,
            "left": -70.7404,
            "right": -70.5459
        }
        
        # Configurar conexiones
        self.setup_connections()

    def setup_connections(self):
        """Configurar conexiones a MongoDB y Redis"""
        try:
            # MongoDB
            mongo_uri = os.environ.get("MONGO_URI")
            if not mongo_uri:
                raise ValueError("MONGO_URI no está definida")
            
            self.mongo_client = MongoClient(mongo_uri)
            self.db = self.mongo_client.waze_db
            self.collection = self.db.events
            
            # Redis
            redis_host = os.environ.get("REDIS_HOST", "redis")
            self.redis_client = redis.Redis(host=redis_host, port=6379, decode_responses=True)
            
            logger.info("Conexiones establecidas correctamente")
        except Exception as e:
            logger.error(f"Error estableciendo conexiones: {e}")
            raise

    def make_random_alert(self):
        """Crear alerta aleatoria con estructura idéntica a eventos reales de Waze"""
        lat = random.uniform(self.SANTIAGO_BBOX["bottom"], self.SANTIAGO_BBOX["top"])
        lon = random.uniform(self.SANTIAGO_BBOX["left"], self.SANTIAGO_BBOX["right"])
        
        # Datos basados en eventos reales observados de Waze
        hazard_subtypes = ["HAZARD_ON_ROAD_POT_HOLE", "HAZARD_ON_ROAD_OBJECT", "HAZARD_ON_ROAD_ROAD_KILL", 
                          "HAZARD_ON_SHOULDER_CAR_STOPPED", "HAZARD_WEATHER_FOG", "HAZARD_ON_ROAD_CONSTRUCTION"]
        
        jam_subtypes = ["JAM_MODERATE_TRAFFIC", "JAM_HEAVY_TRAFFIC", "JAM_STAND_STILL_TRAFFIC"]
        
        accident_subtypes = ["ACCIDENT_MINOR", "ACCIDENT_MAJOR"]
        
        # Calles reales de Santiago observadas en eventos de Waze
        real_streets = ["Independencia", "Av. Libertador", "Av. Providencia", "Av. Las Condes", 
                       "Av. Apoquindo", "Av. Santa Rosa", "Gran Avenida", "Av. Vicuña Mackenna"]
        
        # Ciudades reales observadas en eventos de Waze
        real_cities = ["San Ramón", "Independencia", "Santiago", "Providencia", "Las Condes", 
                      "La Florida", "Ñuñoa", "Vitacura"]
        
        current_time = datetime.utcnow()
        current_millis = int(current_time.timestamp() * 1000)
        
        # Seleccionar tipo y subtipo basado en datos reales
        main_type = random.choice(["HAZARD", "JAM", "ACCIDENT"])
        if main_type == "HAZARD":
            subtype = random.choice(hazard_subtypes)
        elif main_type == "JAM":
            subtype = random.choice(jam_subtypes)
        else:
            subtype = random.choice(accident_subtypes)
        
        # Estructura IDÉNTICA a eventos reales de Waze
        alert = {
            'country': 'CI',  # Código de país observado en eventos reales
            'nThumbsUp': random.randint(0, 10),
            'city': random.choice(real_cities),
            'reportRating': random.randint(1, 5),
            'reportByMunicipalityUser': 'false',
            'reliability': random.randint(5, 10),
            'type': main_type,
            'fromNodeId': random.randint(100000000, 999999999),
            'uuid': f"gen_{random.randint(1000000, 9999999)}",
            'speed': random.randint(0, 120),
            'reportMood': random.randint(1, 5),
            'subtype': subtype,
            'street': random.choice(real_streets),
            'additionalInfo': '',
            'toNodeId': random.randint(100000000, 999999999),
            'id': f"alert-{random.randint(100000000, 999999999)}/gen_{random.randint(1000000, 9999999)}",
            'nComments': 0,  # Inicialmente sin comentarios
            'reportBy': f"generated_user_{random.randint(1000, 9999)}",
            'inscale': False,
            'comments': [],  # Array de comentarios (inicialmente vacío)
            'confidence': random.randint(1, 5),
            'roadType': random.randint(1, 6),
            'magvar': random.randint(180, 250),
            'wazeData': f"world,{lon},{lat},gen_{random.randint(1000000, 9999999)}",
            'location': {'x': lon, 'y': lat},  # Formato real de Waze (x, y)
            'pubMillis': current_millis,
            '_processed_at': current_time  # Marcador de que es evento generado
        }
        
        # Agregar algunos comentarios sintéticos ocasionalmente
        if random.random() < 0.3:  # 30% de probabilidad de tener comentarios
            num_comments = random.randint(1, 3)
            for _ in range(num_comments):
                comment_time = current_millis - random.randint(0, 3600000)  # Hasta 1 hora atrás
                alert['comments'].append({
                    'reportMillis': comment_time,
                    'text': '',
                    'isThumbsUp': random.choice([True, False])
                })
            alert['nComments'] = len(alert['comments'])
            alert['nThumbsUp'] = sum(1 for c in alert['comments'] if c.get('isThumbsUp'))
        
        return alert

    def store_event_mongodb(self, event):
        """Almacenar evento en MongoDB"""
        try:
            result = self.collection.insert_one(event)
            logger.info(f"Evento almacenado en MongoDB: {event['type']} - UUID: {event['uuid']}")
            return True
        except Exception as e:
            logger.error(f"Error almacenando en MongoDB: {e}")
            return False

    def update_redis_cache(self, event):
        """Actualizar caché Redis con el nuevo evento"""
        try:
            # Obtener eventos recientes desde MongoDB para mantener el caché actualizado
            recent_events = list(self.collection.find({}).sort("created_at", -1).limit(100))
            
            # Convertir ObjectId a string para JSON serialización
            for evt in recent_events:
                evt['_id'] = str(evt['_id'])
            
            latest_cache = {
                'events': recent_events,
                'count': len(recent_events),
                'last_updated': datetime.utcnow().isoformat(),
                'type': 'latest'
            }
            
            self.redis_client.setex(
                'latest_alerts', 
                self.CACHE_TTL, 
                json.dumps(latest_cache, default=str)
            )
            
            logger.info(f"Caché Redis actualizado: {len(recent_events)} eventos (TTL: {self.CACHE_TTL}s)")
            
        except Exception as e:
            logger.error(f"Error actualizando Redis: {e}")

    def run(self):
        """Ejecutar generador de tráfico"""
        logger.info(f"Iniciando Traffic Generator: rate={self.EVENTS_PER_SEC} evt/s, distribución={self.DISTRIBUTION}")
        
        interval = 1.0 / self.EVENTS_PER_SEC
        
        while True:
            try:
                # Generar evento
                alert = self.make_random_alert()
                
                # Almacenar en MongoDB
                if self.store_event_mongodb(alert):
                    # Actualizar caché Redis
                    self.update_redis_cache(alert)
                
                # Calcular próximo intervalo - con Poisson o determinístico
                if self.DISTRIBUTION == "poisson":
                    interval = random.expovariate(self.EVENTS_PER_SEC)
                else:
                    interval = 1.0 / self.EVENTS_PER_SEC
                
                time.sleep(interval)
                
            except KeyboardInterrupt:
                logger.info("Deteniendo Traffic Generator...")
                break
            except Exception as e:
                logger.error(f"Error en generación de tráfico: {e}")
                time.sleep(1)
        
        logger.info("Traffic Generator detenido")

if __name__ == "__main__":
    generator = TrafficGeneratorService()
    generator.run()