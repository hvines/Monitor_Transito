#!/usr/bin/env python3
"""
PIG Auto Processor Service - Procesamiento automático y exportación a Elasticsearch
Monitorea MongoDB, aplica filtros/procesamiento automático y exporta al índice waze-processed-events
"""

import time
import json
import logging
import os
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient, ASCENDING
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
import signal
import sys
from bson import ObjectId
import pytz

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PigAutoProcessorService:
    def __init__(self):
        # Configuración
        self.MONGO_URI = os.environ.get("MONGO_URI", "mongodb://root:example@mongodb:27017/?authSource=admin")
        self.ES_HOST = os.environ.get("ES_HOST", "elasticsearch:9200")
        self.PROCESSED_INDEX = "waze_procesados"
        self.POLL_INTERVAL = 10  # segundos entre revisiones (más largo para procesamiento)
        self.BATCH_SIZE = 50     # menor batch size por el procesamiento
        
        # Timezone de Chile
        self.chile_tz = pytz.timezone('America/Santiago')  # UTC-4 estándar, UTC-3 verano
        
        # Estado del servicio
        self.running = True
        self.last_processed_id = None
        
        # Configurar conexiones
        self.setup_connections()
        self.setup_elasticsearch_index()
        self.setup_signal_handlers()

    def setup_connections(self):
        """Establecer conexiones a MongoDB y Elasticsearch"""
        try:
            # MongoDB
            logger.info("Conectando a MongoDB...")
            self.mongo_client = MongoClient(self.MONGO_URI)
            self.db = self.mongo_client.waze_db
            self.collection = self.db.events
            
            # Elasticsearch
            logger.info("Conectando a Elasticsearch...")
            self.es_client = Elasticsearch([f"http://{self.ES_HOST}"])
            
            # Verificar conexiones
            self.mongo_client.admin.command('ping')
            if not self.es_client.ping():
                raise Exception("No se pudo conectar a Elasticsearch")
                
            logger.info("Conexiones establecidas correctamente")
            
        except Exception as e:
            logger.error(f"Error estableciendo conexiones: {e}")
            raise

    def setup_elasticsearch_index(self):
        """Configurar el índice de Elasticsearch para datos procesados"""
        try:
            # Mapping para el índice procesado con los 3 FILTROS PIG
            mapping = {
                "mappings": {
                    "properties": {
                        # Campos originales de MongoDB
                        "mongo_id": {"type": "keyword"},
                        "country": {"type": "keyword"},
                        "city": {"type": "keyword"},
                        "street": {"type": "text"},
                        "type": {"type": "keyword"},
                        "subtype": {"type": "keyword"},
                        "location": {"type": "geo_point"},
                        "pubMillis": {"type": "date"},
                        "source_timestamp": {"type": "date"},
                        "ingestion_timestamp": {"type": "date", "format": "strict_date_optional_time||epoch_millis"},
                        "reliability": {"type": "integer"},
                        "confidence": {"type": "integer"},
                        "nThumbsUp": {"type": "integer"},
                        "nComments": {"type": "integer"},
                        "reportBy": {"type": "keyword"},
                        "uuid": {"type": "keyword"},
                        "id": {"type": "keyword"},
                        
                        # ===== 3 FILTROS PIG =====
                        # FILTRO 1: EVENTOS
                        "pig_event_filter": {
                            "type": "object",
                            "properties": {
                                "tipo": {"type": "keyword"},
                                "subtipo": {"type": "keyword"},
                                "prioridad": {"type": "keyword"}
                            }
                        },
                        
                        # FILTRO 2: UBICACIÓN
                        "pig_location_filter": {
                            "type": "object",
                            "properties": {
                                "ciudad": {"type": "keyword"},
                                "zona": {"type": "keyword"}
                            }
                        },
                        
                        # FILTRO 3: TIEMPO
                        "pig_time_filter": {
                            "type": "object",
                            "properties": {
                                "categoria_dia": {"type": "keyword"},
                                "dia_semana": {"type": "keyword"},
                                "hora": {"type": "integer"},
                                "fecha": {"type": "date", "format": "yyyy-MM-dd"},
                                "timestamp_chile": {"type": "date"}
                            }
                        }
                    }
                },
                "settings": {
                    "number_of_shards": 1,
                    "number_of_replicas": 0
                }
            }
            
            # Crear índice si no existe O recrearlo si cambió la estructura
            index_exists = self.es_client.indices.exists(index=self.PROCESSED_INDEX)
            
            if index_exists:
                logger.info(f"Índice {self.PROCESSED_INDEX} ya existe - verificando estructura...")
                # Obtener mapping actual
                try:
                    current_mapping = self.es_client.indices.get_mapping(index=self.PROCESSED_INDEX)
                    current_props = current_mapping[self.PROCESSED_INDEX]['mappings'].get('properties', {})
                    
                    # Verificar si tiene la nueva estructura de filtros PIG
                    if 'pig_event_filter' not in current_props:
                        logger.info(f"Recreando índice {self.PROCESSED_INDEX} con nueva estructura de filtros PIG...")
                        self.es_client.indices.delete(index=self.PROCESSED_INDEX)
                        self.es_client.indices.create(index=self.PROCESSED_INDEX, body=mapping)
                        logger.info(f"Índice {self.PROCESSED_INDEX} recreado con nueva estructura")
                    else:
                        logger.info(f"Índice {self.PROCESSED_INDEX} ya tiene la estructura correcta")
                        
                except Exception as e:
                    logger.warning(f"Error verificando estructura del índice: {e}")
                    logger.info(f"Índice {self.PROCESSED_INDEX} existe pero usaremos estructura actual")
            else:
                self.es_client.indices.create(index=self.PROCESSED_INDEX, body=mapping)
                logger.info(f"Índice {self.PROCESSED_INDEX} creado correctamente")
                
        except Exception as e:
            logger.error(f"Error configurando índice Elasticsearch: {e}")
            raise

    def setup_signal_handlers(self):
        """Configurar manejadores de señales para shutdown limpio"""
        signal.signal(signal.SIGTERM, self.shutdown)
        signal.signal(signal.SIGINT, self.shutdown)

    def shutdown(self, signum, frame):
        """Shutdown limpio del servicio"""
        logger.info("Iniciando shutdown del PIG auto processor...")
        self.running = False

    def get_chile_timestamp(self, utc_datetime=None):
        """Convertir timestamp a hora de Chile"""
        if utc_datetime is None:
            utc_datetime = datetime.now(timezone.utc)
        
        if utc_datetime.tzinfo is None:
            utc_datetime = utc_datetime.replace(tzinfo=timezone.utc)
        
        chile_time = utc_datetime.astimezone(self.chile_tz)
        return chile_time

    def apply_pig_filters(self, mongo_doc):
        """Aplicar filtros y procesamiento tipo PIG al documento - 3 FILTROS PRINCIPALES"""
        try:
            # IMPORTANTE: Crear copia LIMPIA del documento raw de MongoDB
            # NO modificamos el documento original de MongoDB, solo creamos una copia procesada
            processed_doc = dict(mongo_doc)
            
            # VERIFICACIÓN: El documento de MongoDB debe ser RAW (sin campos procesados)
            raw_fields_check = [
                'pig_event_filter', 'pig_location_filter', 'pig_time_filter'
            ]
            for field in raw_fields_check:
                if field in mongo_doc:
                    logger.warning(f"ATENCIÓN: Campo procesado '{field}' encontrado en documento RAW de MongoDB. ID: {mongo_doc.get('_id', 'Unknown')}")
            
            # LOG para debug: mostrar que estamos procesando datos RAW
            logger.debug(f"Procesando documento RAW desde MongoDB. Campos originales: {list(mongo_doc.keys())}")
            
            # =================================================================
            # FILTRO 1: EVENTOS (tipo + subtipo + prioridad)
            # =================================================================
            event_type = processed_doc.get('type', '').upper()
            subtype = processed_doc.get('subtype', '').upper()
            
            # Mapeo de prioridades basado en tipo
            priority_map = {
                'ACCIDENT': 'ALTA',
                'HAZARD': 'MEDIA', 
                'JAM': 'BAJA',
                'ROAD_CLOSED': 'ALTA',
                'CONSTRUCTION': 'MEDIA',
                'POLICE': 'MEDIA',
                'WEATHERHAZARD': 'ALTA'
            }
            
            processed_doc['pig_event_filter'] = {
                'tipo': event_type,
                'subtipo': subtype,
                'prioridad': priority_map.get(event_type, 'BAJA')
            }
            
            # =================================================================
            # FILTRO 2: UBICACIÓN (ciudad + zona)
            # =================================================================
            city = processed_doc.get('city', 'UNKNOWN')
            
            location_filter = {
                'ciudad': city,
                'zona': 'UNKNOWN'
            }
            
            if 'location' in processed_doc:
                location = processed_doc['location']
                if isinstance(location, dict) and 'y' in location and 'x' in location:
                    lat, lon = location['y'], location['x']
                    
                    # Zonificación de Santiago (más específica)
                    if city.upper() == 'SANTIAGO' or city.upper() == 'CHILE':
                        if lat > -33.42:
                            zona = "Santiago-Norte"
                        elif lat < -33.58:
                            zona = "Santiago-Sur" 
                        else:
                            zona = "Santiago-Centro"
                            
                        if lon < -70.68:
                            zona += "-Oeste"
                        elif lon > -70.55:
                            zona += "-Este"
                        else:
                            zona += "-Centro"
                    else:
                        zona = f"{city}-Nearby"
                        
                    location_filter['zona'] = zona
            
            processed_doc['pig_location_filter'] = location_filter
            
            # =================================================================
            # FILTRO 3: TIEMPO (categoría + intervalos)
            # =================================================================
            now_chile = self.get_chile_timestamp()
            
            # Subcategoría 1: Categorización del día
            hour = now_chile.hour
            if 6 <= hour < 10:
                time_cat = "Mañana"
            elif 10 <= hour < 16:
                time_cat = "Día"
            elif 16 <= hour < 20:
                time_cat = "Tarde"
            elif 20 <= hour < 24:
                time_cat = "Noche"
            else:
                time_cat = "Madrugada"
            
            # Subcategoría 2: Intervalos para filtrado
            weekday = now_chile.strftime('%A')  # Monday, Tuesday, etc.
            day_name_spanish = {
                'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miércoles',
                'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'Sábado', 'Sunday': 'Domingo'
            }
            
            processed_doc['pig_time_filter'] = {
                'categoria_dia': time_cat,
                'dia_semana': day_name_spanish.get(weekday, weekday),
                'hora': hour,
                'fecha': now_chile.strftime('%Y-%m-%d'),
                'timestamp_chile': now_chile.isoformat()
            }
            
            # LOG para debug: confirmar que agregamos campos procesados solo a la copia
            added_fields = ['pig_event_filter', 'pig_location_filter', 'pig_time_filter']
            logger.debug(f"Campos PIG agregados: {added_fields}")
            
            return processed_doc
            
        except Exception as e:
            logger.error(f"Error aplicando filtros PIG: {e}")
            return None

    def convert_mongo_doc_to_es(self, mongo_doc):
        """Convertir documento de MongoDB a formato para Elasticsearch con procesamiento PIG"""
        try:
            # Aplicar filtros PIG primero
            processed_doc = self.apply_pig_filters(mongo_doc)
            if not processed_doc:
                return None
            
            # Convertir a formato ES
            es_doc = dict(processed_doc)
            
            # Convertir ObjectId a string
            es_doc['mongo_id'] = str(mongo_doc['_id'])
            del es_doc['_id']
            
            # Convertir location a formato geo_point
            if 'location' in es_doc and isinstance(es_doc['location'], dict):
                if 'x' in es_doc['location'] and 'y' in es_doc['location']:
                    es_doc['location'] = {
                        'lat': es_doc['location']['y'],
                        'lon': es_doc['location']['x']
                    }
            
            # ===== TIMESTAMPS (3 opciones como en MongoDB-ES Connector) =====
            # 1. pubMillis - Mantener original para referencia
            # (ya está copiado desde processed_doc)
            
            # 2. source_timestamp - Conversión de pubMillis a formato ISO UTC
            if 'pubMillis' in es_doc and es_doc['pubMillis']:
                try:
                    # Convertir milisegundos a formato ISO (igual que connector)
                    timestamp = datetime.fromtimestamp(
                        es_doc['pubMillis'] / 1000,
                        tz=timezone.utc
                    )
                    es_doc['source_timestamp'] = timestamp.isoformat()
                except (ValueError, TypeError, OSError):
                    logger.warning(f"Timestamp inválido en documento {mongo_doc['_id']}")
            
            # 3. ingestion_timestamp - Timestamp de procesamiento PIG
            es_doc['ingestion_timestamp'] = datetime.now(timezone.utc).isoformat()
            
            return es_doc
            
        except Exception as e:
            logger.error(f"Error convirtiendo documento: {e}")
            return None

    def get_last_processed_id(self):
        """Obtener el último ID procesado desde Elasticsearch"""
        try:
            query = {
                "size": 1,
                "sort": [
                    {"ingestion_timestamp": {"order": "desc"}}
                ],
                "_source": ["mongo_id"]
            }
            
            result = self.es_client.search(index=self.PROCESSED_INDEX, body=query)
            
            if result['hits']['hits']:
                mongo_id = result['hits']['hits'][0]['_source']['mongo_id']
                return ObjectId(mongo_id)
            
            return None
            
        except Exception as e:
            logger.warning(f"No se pudo obtener último ID procesado: {e}")
            return None

    def process_and_export_documents(self):
        """Procesar nuevos documentos de MongoDB y exportar a Elasticsearch"""
        try:
            # Construir query para documentos nuevos
            query = {}
            if self.last_processed_id:
                query = {"_id": {"$gt": self.last_processed_id}}
            
            # Obtener documentos nuevos ordenados por _id
            cursor = self.collection.find(query).sort("_id", ASCENDING).limit(self.BATCH_SIZE)
            documents = list(cursor)
            
            if not documents:
                return 0
            
            logger.info(f"Procesando {len(documents)} documentos nuevos con filtros PIG...")
            
            # Preparar lote para Elasticsearch
            bulk_actions = []
            processed_count = 0
            
            for doc in documents:
                es_doc = self.convert_mongo_doc_to_es(doc)
                if es_doc:
                    # Acción de indexación
                    action = {
                        "_index": self.PROCESSED_INDEX,
                        "_id": es_doc['mongo_id'],  # Usar mongo_id como ID único
                        "_source": es_doc
                    }
                    bulk_actions.append(action)
                    processed_count += 1
                    
                    # Actualizar último ID procesado
                    self.last_processed_id = doc['_id']
            
            # Ejecutar bulk insert
            if bulk_actions:
                success_count, failed_items = bulk(
                    self.es_client,
                    bulk_actions,
                    index=self.PROCESSED_INDEX,
                    chunk_size=self.BATCH_SIZE,
                    request_timeout=30
                )
                
                logger.info(f"Exportados {success_count} documentos procesados al índice {self.PROCESSED_INDEX}")
                
                if failed_items:
                    logger.warning(f"Falló la exportación de {len(failed_items)} documentos")
            
            return processed_count
            
        except Exception as e:
            logger.error(f"Error procesando documentos: {e}")
            return 0

    def validate_mongodb_raw_data(self):
        """Validar que MongoDB contenga solo datos RAW (sin campos procesados)"""
        try:
            logger.info("Validando que MongoDB contenga solo datos RAW...")
            
            # Campos PIG nuevos (3 filtros principales)
            processed_fields = [
                'pig_event_filter', 'pig_location_filter', 'pig_time_filter'
            ]
            
            # Buscar documentos que contengan campos procesados
            for field in processed_fields:
                count = self.collection.count_documents({field: {"$exists": True}})
                if count > 0:
                    logger.error(f"¡PROBLEMA! MongoDB contiene {count} documentos con campo procesado '{field}'")
                    logger.error("MongoDB debe contener SOLO datos RAW. Los campos procesados van únicamente a Elasticsearch.")
                    return False
                    
            logger.info("MongoDB contiene solo datos RAW (correcto)")
            
            # Mostrar ejemplo de documento RAW de MongoDB
            sample_doc = self.collection.find_one()
            if sample_doc:
                sample_fields = list(sample_doc.keys())
                logger.info(f"Campos en documento RAW de ejemplo: {sample_fields}")
                
            return True
            
        except Exception as e:
            logger.error(f"Error validando datos RAW en MongoDB: {e}")
            return False

    def run_processing_cycle(self):
        """Ejecutar un ciclo de procesamiento"""
        start_time = time.time()
        
        try:
            # Inicializar último ID si es necesario
            if self.last_processed_id is None:
                self.last_processed_id = self.get_last_processed_id()
                if self.last_processed_id:
                    logger.info(f"Continuando procesamiento desde ID: {self.last_processed_id}")
                else:
                    logger.info("Iniciando procesamiento desde el principio")
            
            # Validar datos RAW en MongoDB
            if not self.validate_mongodb_raw_data():
                logger.error("Deteniendo procesamiento por datos NO RAW en MongoDB")
                return
            
            # Procesar y exportar documentos nuevos
            processed_count = self.process_and_export_documents()
            
            cycle_time = time.time() - start_time
            
            if processed_count > 0:
                logger.info(f"Ciclo PIG completado: {processed_count} docs procesados en {cycle_time:.2f}s")
            else:
                logger.debug(f"Sin documentos nuevos para procesar (verificado en {cycle_time:.2f}s)")
                
        except Exception as e:
            logger.error(f"Error en ciclo de procesamiento PIG: {e}")

    def run(self):
        """Ejecutar el servicio de procesamiento en modo continuo"""
        logger.info("Iniciando PIG Auto Processor Service...")
        logger.info("=" * 80)
        logger.info("ARQUITECTURA DEL SISTEMA:")
        logger.info("1. Scraper → MongoDB (datos RAW sin procesar)")
        logger.info("2. MongoDB → Elasticsearch (índice 'waze_bruto' - datos RAW)")
        logger.info("3. PIG Processor → Elasticsearch (índice 'waze_procesados' - datos con 3 filtros)")
        logger.info("")
        logger.info("FILTROS PIG APLICADOS:")
        logger.info("   1. EVENTOS: tipo + subtipo + prioridad")
        logger.info("   2. UBICACIÓN: ciudad + zona geográfica")
        logger.info("   3. TIEMPO: categoría del día + intervalos (día, hora, fecha)")
        logger.info("=" * 80)
        logger.info(f"MongoDB → Procesamiento PIG → Elasticsearch ({self.PROCESSED_INDEX})")
        logger.info(f"Intervalo de polling: {self.POLL_INTERVAL}s")
        logger.info(f"Timezone: Chile (UTC-4/UTC-3)")
        logger.info("NOTA: PIG solo LEE de MongoDB y ESCRIBE a Elasticsearch. NO modifica MongoDB.")
        
        while self.running:
            try:
                self.run_processing_cycle()
                
                if self.running:
                    time.sleep(self.POLL_INTERVAL)
                    
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Error en servicio principal PIG: {e}")
                time.sleep(15)  # Esperar más tiempo antes de reintentar
        
        logger.info("PIG Auto Processor Service detenido")

if __name__ == "__main__":
    processor = PigAutoProcessorService()
    processor.run()
