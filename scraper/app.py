import requests
import time
import json
import logging
from pymongo import MongoClient
import redis
from datetime import datetime, timedelta
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import signal
import sys

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WazeScraperService:
    def __init__(self):
        # Configuración
        self.WAZE_API_URL = "https://www.waze.com/row-RoutingManager/routingRequest"
        self.SANTIAGO_BBOX = {
            'left': -70.75,   # Área más pequeña, centrada en Santiago
            'bottom': -33.6,
            'right': -70.55,
            'top': -33.4
        }
        self.MAX_REQUESTS_PER_CYCLE = 5  # Reducir a 5 requests por ciclo
        self.SYNC_TIMEOUT = 30  # segundos
        self.CYCLE_INTERVAL = 30  # reducir a 30 segundos entre ciclos
        self.CACHE_TTL = 10  # TTL de 10 segundos para latest_alerts
        
        # Conexiones
        self.setup_connections()
        
        # Control de estado
        self.running = True
        self.setup_signal_handlers()

    def setup_connections(self):
        """Configurar conexiones a MongoDB y Redis"""
        try:
            # MongoDB con autenticación
            self.mongo_client = MongoClient('mongodb://root:example@mongodb:27017/?authSource=admin')
            self.db = self.mongo_client.waze_db
            self.collection = self.db.events
            
            # Redis
            self.redis_client = redis.Redis(host='redis', port=6379, decode_responses=True)
            
            logger.info("Conexiones establecidas correctamente")
        except Exception as e:
            logger.error(f"Error estableciendo conexiones: {e}")
            raise

    def setup_signal_handlers(self):
        """Configurar manejadores de señales para shutdown limpio"""
        signal.signal(signal.SIGTERM, self.shutdown)
        signal.signal(signal.SIGINT, self.shutdown)

    def shutdown(self, signum, frame):
        """Shutdown limpio del servicio"""
        logger.info("Iniciando shutdown del scraper...")
        self.running = False

    def scrape_waze_events(self):
        """Extraer eventos de Waze con límite conservador de requests"""
        events = []
        requests_made = 0
        
        try:
            # Headers para simular un navegador real
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Referer': 'https://www.waze.com/',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
            }
            
            # Endpoint simplificado de Waze
            alerts_url = "https://www.waze.com/live-map/api/georss"
            
            logger.info(f"Iniciando scraping de Waze (máximo {self.MAX_REQUESTS_PER_CYCLE} requests)")
            
            # Hacer solo unos pocos requests por ciclo para evitar rate limiting
            for attempt in range(self.MAX_REQUESTS_PER_CYCLE):
                if not self.running:
                    break
                    
                try:
                    # Parámetros más específicos para reducir carga
                    params = {
                        'left': self.SANTIAGO_BBOX['left'],
                        'bottom': self.SANTIAGO_BBOX['bottom'], 
                        'right': self.SANTIAGO_BBOX['right'],
                        'top': self.SANTIAGO_BBOX['top'],
                        'env': 'row',
                        'types': 'alerts'  # Solo alertas, no otras categorías
                    }
                    
                    response = requests.get(alerts_url, params=params, headers=headers, timeout=20)
                    requests_made += 1
                    
                    if response.status_code == 200:
                        try:
                            data = response.json()
                            if 'alerts' in data and data['alerts']:
                                # Almacenar eventos tal como los recibe la API
                                raw_events = data['alerts']
                                
                                # Solo agregar timestamp de procesamiento sin modificar estructura original
                                processed_events = []
                                for event in raw_events:
                                    # Crear copia del evento original
                                    processed_event = dict(event)
                                    # Solo agregar campo de procesamiento
                                    processed_event['_processed_at'] = datetime.utcnow()
                                    processed_events.append(processed_event)
                                
                                events.extend(processed_events)
                                logger.info(f"Request {requests_made}: {len(processed_events)} eventos obtenidos de Waze")
                                
                                # Log de estructura para análisis (solo el primer evento)
                                if processed_events and requests_made == 1:
                                    logger.info(f"Estructura original de evento Waze: {json.dumps(processed_events[0], indent=2, default=str)[:500]}...")
                                
                                # Si obtuvimos eventos, no necesitamos hacer más requests
                                if len(processed_events) > 0:
                                    break
                            else:
                                logger.info(f"Request {requests_made}: No hay alertas activas en este momento")
                                
                        except json.JSONDecodeError as e:
                            logger.warning(f"Request {requests_made}: Error parseando JSON: {e}")
                    
                    elif response.status_code == 429:
                        logger.warning(f"Rate limit alcanzado en request {requests_made}, terminando ciclo")
                        break
                    
                    elif response.status_code == 500:
                        logger.warning(f"Request {requests_made}: Server error 500, reintentando con pausa más larga")
                        time.sleep(10)  # Pausa más larga para server errors
                        
                    else:
                        logger.warning(f"Request {requests_made} falló con código: {response.status_code}")
                    
                    # Pausa más larga entre requests para ser más respetuosos
                    if attempt < self.MAX_REQUESTS_PER_CYCLE - 1:
                        time.sleep(5)
                    
                except requests.exceptions.Timeout:
                    logger.warning(f"Request {requests_made}: Timeout, continuando...")
                    time.sleep(3)
                    
                except requests.exceptions.RequestException as e:
                    logger.error(f"Request {requests_made}: Error de conexión: {e}")
                    time.sleep(5)
                    
        except Exception as e:
            logger.error(f"Error durante scraping: {e}")
        
        logger.info(f"Scraping completado: {len(events)} eventos totales, {requests_made} requests realizados")
        return events

    def store_events_mongodb(self, events):
        """Almacenar eventos en MongoDB con timeout"""
        if not events:
            return 0
            
        try:
            logger.info(f"Almacenando {len(events)} eventos en MongoDB...")
            start_time = time.time()
            
            # Inserción con timeout
            result = self.collection.insert_many(events, ordered=False)
            
            elapsed_time = time.time() - start_time
            if elapsed_time > self.SYNC_TIMEOUT:
                logger.warning(f"Almacenamiento en MongoDB tomó {elapsed_time:.2f}s (>{self.SYNC_TIMEOUT}s)")
            
            logger.info(f"MongoDB: {len(result.inserted_ids)} eventos almacenados en {elapsed_time:.2f}s")
            return len(result.inserted_ids)
            
        except Exception as e:
            logger.error(f"Error almacenando en MongoDB: {e}")
            return 0

    def update_redis_cache(self, events):
        """Actualizar caché Redis con TTL de 10 segundos"""
        if not events:
            return
            
        try:
            logger.info(f"Actualizando caché Redis con {len(events)} eventos...")
            start_time = time.time()
            
            # latest_alerts: TTL de 10 segundos para eventos ultra-frescos
            latest_cache = {
                'events': events,
                'count': len(events),
                'last_updated': datetime.utcnow().isoformat(),
                'type': 'latest'
            }
            
            self.redis_client.setex(
                'latest_alerts', 
                self.CACHE_TTL, 
                json.dumps(latest_cache, default=str)
            )
            
            elapsed_time = time.time() - start_time
            if elapsed_time > self.SYNC_TIMEOUT:
                logger.warning(f"Actualización Redis tomó {elapsed_time:.2f}s (>{self.SYNC_TIMEOUT}s)")
                
            logger.info(f"Redis: Caché actualizado en {elapsed_time:.2f}s (TTL: {self.CACHE_TTL}s)")
            
        except Exception as e:
            logger.error(f"Error actualizando Redis: {e}")

    def synchronized_data_pipeline(self, events):
        """Pipeline sincronizado con timeouts para MongoDB y Redis"""
        logger.info("Iniciando pipeline sincronizado...")
        
        with ThreadPoolExecutor(max_workers=2) as executor:
            # Ejecutar MongoDB y Redis en paralelo
            mongodb_future = executor.submit(self.store_events_mongodb, events)
            redis_future = executor.submit(self.update_redis_cache, events)
            
            # Esperar con timeout
            completed_tasks = 0
            for future in as_completed([mongodb_future, redis_future], timeout=self.SYNC_TIMEOUT):
                try:
                    result = future.result()
                    completed_tasks += 1
                except Exception as e:
                    logger.error(f"Error en pipeline: {e}")
            
            logger.info(f"Pipeline completado: {completed_tasks}/2 tareas exitosas")

    def run_scraping_cycle(self):
        """Ejecutar un ciclo completo de scraping"""
        logger.info("=== Iniciando ciclo de scraping ===")
        cycle_start = time.time()
        
        # 1. Scraping de Waze
        events = self.scrape_waze_events()
        
        if events:
            # 2. Pipeline sincronizado
            self.synchronized_data_pipeline(events)
        else:
            logger.warning("No se obtuvieron eventos en este ciclo")
        
        cycle_time = time.time() - cycle_start
        logger.info(f"=== Ciclo completado en {cycle_time:.2f}s ===")

    def run(self):
        """Ejecutar scraper en modo continuo"""
        logger.info("Iniciando Waze Scraper Service...")
        
        while self.running:
            try:
                self.run_scraping_cycle()
                
                if self.running:
                    logger.info(f"Esperando {self.CYCLE_INTERVAL}s para próximo ciclo...")
                    time.sleep(self.CYCLE_INTERVAL)
                    
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Error en ciclo principal: {e}")
                time.sleep(10)  # Esperar antes de reintentar
        
        logger.info("Scraper detenido")

if __name__ == "__main__":
    scraper = WazeScraperService()
    scraper.run()
