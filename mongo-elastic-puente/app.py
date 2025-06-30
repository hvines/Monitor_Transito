#!/usr/bin/env python3
"""
MongoDB to Elasticsearch Connector - Datos Brutos
Conecta directamente MongoDB con Elasticsearch para sincronizar datos brutos
"""

import time
import json
import logging
import os
from datetime import datetime, timezone
from pymongo import MongoClient, ASCENDING
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
import signal
import sys
from bson import ObjectId

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MongoElasticsearchConnector:
    def __init__(self):
        # Configuración
        self.MONGO_URI = os.environ.get("MONGO_URI", "mongodb://root:example@mongodb:27017/?authSource=admin")
        self.ES_HOST = os.environ.get("ES_HOST", "elasticsearch:9200")
        self.RAW_INDEX = "waze_bruto"
        self.POLL_INTERVAL = 15  # segundos entre revisiones para datos brutos
        self.BATCH_SIZE = 100    # mayor batch size para datos brutos (sin procesamiento)
        
        # Estado del servicio
        self.running = True
        self.last_synced_id = None
        
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
        """Configurar el índice de Elasticsearch para datos brutos"""
        try:
            # Mapping para el índice bruto (preserva estructura original)
            mapping = {
                "mappings": {
                    "properties": {
                        "mongo_id": {"type": "keyword"},
                        "country": {"type": "keyword"},
                        "city": {"type": "keyword"},
                        "street": {"type": "text"},
                        "type": {"type": "keyword"},
                        "subtype": {"type": "keyword"},
                        "pubMillis": {"type": "date"},
                        "location": {
                            "type": "geo_point"
                        },
                        "roadType": {"type": "keyword"},
                        "speed": {"type": "float"},
                        "length": {"type": "float"},
                        "delay": {"type": "integer"},
                        "severity": {"type": "integer"},
                        "reportRating": {"type": "integer"},
                        "confidence": {"type": "integer"},
                        "reliability": {"type": "integer"},
                        "jamLevel": {"type": "integer"},
                        "turnType": {"type": "keyword"},
                        "alertsCount": {"type": "integer"},
                        "irregularities": {"type": "integer"},
                        "driversCount": {"type": "integer"},
                        "level": {"type": "integer"},
                        "endNode": {"type": "keyword"},
                        "alertType": {"type": "keyword"},
                        "reportDescription": {"type": "text"},
                        "uuid": {"type": "keyword"},
                        "source_timestamp": {"type": "date"},
                        "ingestion_timestamp": {"type": "date", "format": "strict_date_optional_time||epoch_millis"}
                    }
                }
            }
            
            # Crear índice si no existe
            if not self.es_client.indices.exists(index=self.RAW_INDEX):
                self.es_client.indices.create(
                    index=self.RAW_INDEX,
                    body=mapping
                )
                logger.info(f"Índice {self.RAW_INDEX} creado con mapping optimizado")
            else:
                logger.info(f"Índice {self.RAW_INDEX} ya existe")
                
        except Exception as e:
            logger.error(f"Error configurando índice Elasticsearch: {e}")
            raise

    def setup_signal_handlers(self):
        """Configurar manejadores de señales para shutdown graceful"""
        def signal_handler(signum, frame):
            logger.info(f"Recibida señal {signum}, iniciando shutdown graceful...")
            self.running = False
            
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def convert_mongo_doc_to_es_raw(self, mongo_doc):
        """Convertir documento de MongoDB a formato Elasticsearch (datos brutos)"""
        try:
            # Conversión mínima, preservando estructura original
            es_doc = {
                "mongo_id": str(mongo_doc['_id']),
                "ingestion_timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            # Copiar campos directamente (sin procesamiento)
            fields_to_copy = [
                'country', 'city', 'street', 'type', 'subtype', 'pubMillis',
                'roadType', 'speed', 'length', 'delay', 'severity', 'reportRating',
                'confidence', 'reliability', 'jamLevel', 'turnType', 'alertsCount',
                'irregularities', 'driversCount', 'level', 'endNode', 'alertType',
                'reportDescription', 'uuid'
            ]
            
            for field in fields_to_copy:
                if field in mongo_doc:
                    es_doc[field] = mongo_doc[field]
            
            # Procesar ubicación geográfica si existe
            if 'location' in mongo_doc and mongo_doc['location']:
                location = mongo_doc['location']
                if 'x' in location and 'y' in location:
                    try:
                        # Convertir a formato geo_point de Elasticsearch
                        es_doc['location'] = {
                            "lat": float(location['y']),
                            "lon": float(location['x'])
                        }
                    except (ValueError, TypeError):
                        logger.warning(f"Coordenadas inválidas en documento {mongo_doc['_id']}")
            
            # Convertir timestamp si existe
            if 'pubMillis' in mongo_doc and mongo_doc['pubMillis']:
                try:
                    # Convertir milisegundos a formato ISO
                    timestamp = datetime.fromtimestamp(
                        mongo_doc['pubMillis'] / 1000,
                        tz=timezone.utc
                    )
                    es_doc['source_timestamp'] = timestamp.isoformat()
                except (ValueError, TypeError, OSError):
                    logger.warning(f"Timestamp inválido en documento {mongo_doc['_id']}")
            
            return es_doc
            
        except Exception as e:
            logger.error(f"Error convirtiendo documento {mongo_doc.get('_id', 'unknown')}: {e}")
            return None

    def get_last_synced_id(self):
        """Obtener el último ID sincronizado desde Elasticsearch"""
        try:
            # Buscar el documento más reciente por mongo_id
            search_body = {
                "sort": [{"mongo_id": {"order": "desc"}}],
                "size": 1,
                "_source": ["mongo_id"]
            }
            
            result = self.es_client.search(
                index=self.RAW_INDEX,
                body=search_body
            )
            
            if result['hits']['total']['value'] > 0:
                mongo_id = result['hits']['hits'][0]['_source']['mongo_id']
                return ObjectId(mongo_id)
            
            return None
            
        except Exception as e:
            logger.warning(f"No se pudo obtener último ID sincronizado: {e}")
            return None

    def sync_documents(self):
        """Sincronizar nuevos documentos de MongoDB a Elasticsearch"""
        try:
            # Construir query para documentos nuevos
            query = {}
            if self.last_synced_id:
                query = {"_id": {"$gt": self.last_synced_id}}
            
            # Obtener documentos nuevos ordenados por _id
            cursor = self.collection.find(query).sort("_id", ASCENDING).limit(self.BATCH_SIZE)
            documents = list(cursor)
            
            if not documents:
                return 0
            
            logger.info(f"Sincronizando {len(documents)} documentos brutos...")
            
            # Preparar lote para Elasticsearch
            bulk_actions = []
            synced_count = 0
            
            for doc in documents:
                es_doc = self.convert_mongo_doc_to_es_raw(doc)
                if es_doc:
                    # Acción de indexación
                    action = {
                        "_index": self.RAW_INDEX,
                        "_id": es_doc['mongo_id'],  # Usar mongo_id como ID único
                        "_source": es_doc
                    }
                    bulk_actions.append(action)
                    synced_count += 1
                    
                    # Actualizar último ID sincronizado
                    self.last_synced_id = doc['_id']
            
            # Ejecutar bulk insert
            if bulk_actions:
                success_count, failed_items = bulk(
                    self.es_client,
                    bulk_actions,
                    index=self.RAW_INDEX,
                    chunk_size=self.BATCH_SIZE,
                    request_timeout=30
                )
                
                logger.info(f"Sincronizados {success_count} documentos brutos al índice {self.RAW_INDEX}")
                
                if failed_items:
                    logger.warning(f"Falló la sincronización de {len(failed_items)} documentos")
            
            return synced_count
            
        except Exception as e:
            logger.error(f"Error sincronizando documentos: {e}")
            return 0

    def run_sync_cycle(self):
        """Ejecutar un ciclo de sincronización"""
        start_time = time.time()
        
        try:
            # Inicializar último ID si es necesario
            if self.last_synced_id is None:
                self.last_synced_id = self.get_last_synced_id()
                if self.last_synced_id:
                    logger.info(f"Continuando sincronización desde ID: {self.last_synced_id}")
                else:
                    logger.info("Iniciando sincronización completa desde el principio")
            
            # Sincronizar documentos nuevos
            synced_count = self.sync_documents()
            
            cycle_time = time.time() - start_time
            
            if synced_count > 0:
                logger.info(f"Ciclo de sincronización completado: {synced_count} docs en {cycle_time:.2f}s")
            else:
                logger.debug(f"Sin documentos nuevos para sincronizar (verificado en {cycle_time:.2f}s)")
                
        except Exception as e:
            logger.error(f"Error en ciclo de sincronización: {e}")

    def run(self):
        """Ejecutar el servicio de sincronización en modo continuo"""
        logger.info("Iniciando MongoDB-Elasticsearch Connector...")
        logger.info(f"Sincronizando MongoDB → Elasticsearch (índice: {self.RAW_INDEX})")
        logger.info(f"Intervalo de polling: {self.POLL_INTERVAL}s")
        logger.info("Modo: Datos brutos (sin procesamiento)")
        
        while self.running:
            try:
                self.run_sync_cycle()
                
                if self.running:
                    time.sleep(self.POLL_INTERVAL)
                    
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Error en servicio principal: {e}")
                time.sleep(20)  # Esperar más tiempo antes de reintentar
        
        logger.info("MongoDB-Elasticsearch Connector detenido")

if __name__ == "__main__":
    connector = MongoElasticsearchConnector()
    connector.run()
