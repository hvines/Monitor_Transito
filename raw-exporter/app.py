#!/usr/bin/env python3
"""
Raw Exporter Service - Exporta datos raw de MongoDB a Elasticsearch
Monitorea cambios en MongoDB y los replica automáticamente al índice waze-raw-events
"""

import time
import json
import logging
from datetime import datetime, timezone
from pymongo import MongoClient, ASCENDING
from elasticsearch import Elasticsearch
import signal
import sys
import threading
from bson import ObjectId

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RawExporterService:
    def __init__(self):
        # Configuración
        self.MONGO_URI = "mongodb://root:example@mongodb:27017/?authSource=admin"
        self.ES_HOST = "elasticsearch:9200"
        self.RAW_INDEX = "waze-raw-events"
        self.POLL_INTERVAL = 5  # segundos entre revisiones
        self.BATCH_SIZE = 100   # documentos por lote
        
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
        """Configurar el índice de Elasticsearch para datos raw"""
        try:
            # Mapping para el índice raw
            mapping = {
                "mappings": {
                    "properties": {
                        "mongo_id": {"type": "keyword"},
                        "country": {"type": "keyword"},
                        "city": {"type": "keyword"},
                        "street": {"type": "text"},
                        "type": {"type": "keyword"},
                        "subtype": {"type": "keyword"},
                        "location": {
                            "type": "geo_point"
                        },
                        "pubMillis": {"type": "date"},
                        "pubMillis_santiago": {"type": "date"},
                        "_processed_at": {"type": "date"},
                        "raw_exported_at": {"type": "date"},
                        "reliability": {"type": "integer"},
                        "confidence": {"type": "integer"},
                        "nThumbsUp": {"type": "integer"},
                        "nComments": {"type": "integer"},
                        "reportBy": {"type": "keyword"},
                        "uuid": {"type": "keyword"},
                        "id": {"type": "keyword"}
                    }
                },
                "settings": {
                    "number_of_shards": 1,
                    "number_of_replicas": 0
                }
            }
            
            # Crear índice si no existe
            if not self.es_client.indices.exists(index=self.RAW_INDEX):
                self.es_client.indices.create(index=self.RAW_INDEX, body=mapping)
                logger.info(f"Índice {self.RAW_INDEX} creado correctamente")
            else:
                logger.info(f"Índice {self.RAW_INDEX} ya existe")
                
        except Exception as e:
            logger.error(f"Error configurando índice Elasticsearch: {e}")
            raise

    def setup_signal_handlers(self):
        """Configurar manejadores de señales para shutdown limpio"""
        signal.signal(signal.SIGTERM, self.shutdown)
        signal.signal(signal.SIGINT, self.shutdown)

    def shutdown(self, signum, frame):
        """Shutdown limpio del servicio"""
        logger.info("Iniciando shutdown del raw exporter...")
        self.running = False

    def convert_mongo_doc_to_es(self, mongo_doc):
        """Convertir documento de MongoDB a formato para Elasticsearch"""
        try:
            # Crear copia del documento
            es_doc = dict(mongo_doc)
            
            # Convertir ObjectId a string y guardarlo
            es_doc['mongo_id'] = str(mongo_doc['_id'])
            del es_doc['_id']
            
            # Agregar timestamp de exportación
            es_doc['raw_exported_at'] = datetime.now(timezone.utc).isoformat()
            
            # Convertir location a formato geo_point si existe
            if 'location' in es_doc and isinstance(es_doc['location'], dict):
                if 'x' in es_doc['location'] and 'y' in es_doc['location']:
                    es_doc['location'] = {
                        'lat': es_doc['location']['y'],
                        'lon': es_doc['location']['x']
                    }
            
            # Convertir timestamps si existen
            if 'pubMillis' in es_doc and isinstance(es_doc['pubMillis'], (int, float)):
                try:
                    es_doc['pubMillis'] = datetime.fromtimestamp(
                        es_doc['pubMillis'] / 1000, tz=timezone.utc
                    ).isoformat()
                except:
                    pass
            
            # Convertir _processed_at si es datetime
            if '_processed_at' in es_doc:
                if hasattr(es_doc['_processed_at'], 'isoformat'):
                    es_doc['_processed_at'] = es_doc['_processed_at'].isoformat()
                elif isinstance(es_doc['_processed_at'], str):
                    pass  # Ya es string
            
            return es_doc
            
        except Exception as e:
            logger.error(f"Error convirtiendo documento: {e}")
            return None

    def get_last_processed_id(self):
        """Obtener el último ID procesado desde Elasticsearch"""
        try:
            # Buscar el documento con el timestamp más reciente
            query = {
                "size": 1,
                "sort": [
                    {"raw_exported_at": {"order": "desc"}}
                ],
                "_source": ["mongo_id"]
            }
            
            result = self.es_client.search(index=self.RAW_INDEX, body=query)
            
            if result['hits']['hits']:
                mongo_id = result['hits']['hits'][0]['_source']['mongo_id']
                return ObjectId(mongo_id)
            
            return None
            
        except Exception as e:
            logger.warning(f"No se pudo obtener último ID procesado: {e}")
            return None

    def export_new_documents(self):
        """Exportar nuevos documentos de MongoDB a Elasticsearch"""
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
            
            logger.info(f"Procesando {len(documents)} documentos nuevos...")
            
            # Preparar lote para Elasticsearch
            bulk_actions = []
            processed_count = 0
            
            for doc in documents:
                es_doc = self.convert_mongo_doc_to_es(doc)
                if es_doc:
                    # Acción de indexación
                    action = {
                        "_index": self.RAW_INDEX,
                        "_id": es_doc['mongo_id'],  # Usar mongo_id como ID único
                        "_source": es_doc
                    }
                    bulk_actions.append(action)
                    processed_count += 1
                    
                    # Actualizar último ID procesado
                    self.last_processed_id = doc['_id']
            
            # Ejecutar bulk insert
            if bulk_actions:
                from elasticsearch.helpers import bulk
                success_count, failed_items = bulk(
                    self.es_client,
                    bulk_actions,
                    index=self.RAW_INDEX,
                    chunk_size=self.BATCH_SIZE,
                    request_timeout=30
                )
                
                logger.info(f"Exportados {success_count} documentos al índice {self.RAW_INDEX}")
                
                if failed_items:
                    logger.warning(f"Falló la exportación de {len(failed_items)} documentos")
            
            return processed_count
            
        except Exception as e:
            logger.error(f"Error exportando documentos: {e}")
            return 0

    def run_export_cycle(self):
        """Ejecutar un ciclo de exportación"""
        start_time = time.time()
        
        try:
            # Inicializar último ID si es necesario
            if self.last_processed_id is None:
                self.last_processed_id = self.get_last_processed_id()
                if self.last_processed_id:
                    logger.info(f"Continuando desde ID: {self.last_processed_id}")
                else:
                    logger.info("Iniciando exportación desde el principio")
            
            # Exportar documentos nuevos
            exported_count = self.export_new_documents()
            
            cycle_time = time.time() - start_time
            
            if exported_count > 0:
                logger.info(f"Ciclo completado: {exported_count} docs en {cycle_time:.2f}s")
            else:
                logger.debug(f"Sin documentos nuevos (verificado en {cycle_time:.2f}s)")
                
        except Exception as e:
            logger.error(f"Error en ciclo de exportación: {e}")

    def run(self):
        """Ejecutar el servicio de exportación en modo continuo"""
        logger.info("Iniciando Raw Exporter Service...")
        logger.info(f"Monitoreando MongoDB → Elasticsearch ({self.RAW_INDEX})")
        logger.info(f"Intervalo de polling: {self.POLL_INTERVAL}s")
        
        while self.running:
            try:
                self.run_export_cycle()
                
                if self.running:
                    time.sleep(self.POLL_INTERVAL)
                    
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Error en servicio principal: {e}")
                time.sleep(10)  # Esperar antes de reintentar
        
        logger.info("Raw Exporter Service detenido")

if __name__ == "__main__":
    exporter = RawExporterService()
    exporter.run()
