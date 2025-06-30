#!/usr/bin/env python3
"""
Waze Processed Events - Procesador de datos de MongoDB a Elasticsearch
Filtra y procesa eventos según configuración definida
"""

import os
import sys
import json
import time
import logging
from datetime import datetime, timezone
from pymongo import MongoClient
from elasticsearch import Elasticsearch

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURACIÓN DE FILTROS
# ============================================================================
# Descomenta los campos que QUIERES MANTENER en el procesamiento
# Los campos comentados serán FILTRADOS/ELIMINADOS

FIELDS_TO_KEEP = [
    # CAMPOS CORE (Identificación básica)
    '_id',           # ObjectId - identificador único
    'type',          # str - tipo de evento (JAM, ACCIDENT, etc.)
    'subtype',       # str - subtipo específico
    
    # CAMPOS DE UBICACIÓN  
    'location',      # dict - coordenadas geográficas
    'street',        # str - nombre de la calle
    # 'nearBy',      # str - descripción de ubicación cercana
    
    # CAMPOS TEMPORALES
    'pubMillis',     # int - timestamp en milisegundos
    'pubTimestamp',  # datetime - timestamp convertido
    
    # CAMPOS WAZE (Datos de tráfico)
    'roadType',      # int - tipo de carretera
    'speed',         # float - velocidad
    'length',        # float - longitud del evento
    'level',         # int - nivel de severidad
    'reportRating',  # int - rating del reporte
    'confidence',    # int - confianza del dato
    'reliability',   # int - confiabilidad
    
    # CAMPOS METADATA (comentados por defecto)
    # '_pubMillis_santiago',  # Timestamp local Santiago
    # 'wazeData',            # Datos adicionales Waze
    # 'reportBy',            # Reportado por
    # 'magvar',              # Variación magnética
    # 'reportMood',          # Estado de ánimo del reporte
    # 'nComments',           # Número de comentarios
    # 'nThumbsUp',           # Número de likes
]

class WazeProcessor:
    def __init__(self):
        # Configuración desde variables de entorno
        self.mongo_uri = os.getenv('MONGO_URI', 'mongodb://root:example@mongodb:27017/?authSource=admin')
        self.es_host = os.getenv('ES_HOST', 'elasticsearch:9200')
        self.db_name = 'waze_data'
        self.collection_name = 'events'
        self.es_index = 'waze-processed-events'
        
        # Estado del procesador
        self.running = True
        self.processed_count = 0
        
        # Configurar conexiones
        self.setup_connections()
        
    def setup_connections(self):
        """Establecer conexiones a MongoDB y Elasticsearch"""
        try:
            # MongoDB
            logger.info("Conectando a MongoDB...")
            self.mongo_client = MongoClient(self.mongo_uri)
            self.db = self.mongo_client[self.db_name]
            self.collection = self.db[self.collection_name]
            self.mongo_client.admin.command('ismaster')
            
            # Elasticsearch
            logger.info("Conectando a Elasticsearch...")
            self.es_client = Elasticsearch([f"http://{self.es_host}"])
            self.es_client.ping()
            
            logger.info("Conexiones establecidas correctamente")
            
        except Exception as e:
            logger.error(f"Error estableciendo conexiones: {e}")
            sys.exit(1)
    
    def filter_document(self, doc):
        """Filtrar documento según configuración de campos"""
        try:
            # Aplicar filtro de campos
            filtered_doc = {}
            
            for field in FIELDS_TO_KEEP:
                if field in doc:
                    filtered_doc[field] = doc[field]
            
            # Validaciones básicas
            if not filtered_doc.get('location'):
                return None  # Descartar eventos sin ubicación
            
            if not filtered_doc.get('type'):
                return None  # Descartar eventos sin tipo
            
            # Agregar metadata de procesamiento
            filtered_doc['processed_at'] = datetime.now(timezone.utc)
            filtered_doc['processor_version'] = '1.0'
            filtered_doc['fields_filtered'] = len(doc) - len(filtered_doc)
            
            return filtered_doc
            
        except Exception as e:
            logger.warning(f"Error filtrando documento: {e}")
            return None
    
    def ensure_index_mapping(self):
        """Crear mapping optimizado para el índice procesado"""
        mapping = {
            "mappings": {
                "properties": {
                    "location": {
                        "type": "geo_point"
                    },
                    "pubTimestamp": {
                        "type": "date"
                    },
                    "processed_at": {
                        "type": "date"
                    },
                    "type": {
                        "type": "keyword"
                    },
                    "subtype": {
                        "type": "keyword"
                    },
                    "street": {
                        "type": "text",
                        "fields": {
                            "keyword": {
                                "type": "keyword"
                            }
                        }
                    }
                }
            }
        }
        
        try:
            if not self.es_client.indices.exists(index=self.es_index):
                self.es_client.indices.create(index=self.es_index, body=mapping)
                logger.info(f"Índice {self.es_index} creado con mapping optimizado")
        except Exception as e:
            logger.warning(f"Error creando índice: {e}")
    
    def export_to_elasticsearch(self, filtered_doc):
        """Exportar documento filtrado a Elasticsearch"""
        try:
            # Usar el _id de MongoDB como ID en Elasticsearch
            doc_id = str(filtered_doc.get('_id'))
            
            # Remover _id del documento (Elasticsearch generará uno nuevo)
            es_doc = {k: v for k, v in filtered_doc.items() if k != '_id'}
            
            # Indexar en Elasticsearch
            self.es_client.index(
                index=self.es_index,
                id=doc_id,
                body=es_doc
            )
            
            self.processed_count += 1
            
            if self.processed_count % 10 == 0:
                logger.info(f"Procesados {self.processed_count} eventos")
                
        except Exception as e:
            logger.error(f"Error exportando a Elasticsearch: {e}")
    
    def process_existing_data(self):
        """Procesar datos existentes en MongoDB"""
        logger.info("Procesando datos existentes en MongoDB...")
        
        try:
            # Obtener todos los documentos
            total_docs = self.collection.count_documents({})
            logger.info(f"Total de documentos a procesar: {total_docs}")
            
            # Procesar en lotes
            batch_size = 100
            processed = 0
            
            for doc in self.collection.find().batch_size(batch_size):
                if not self.running:
                    break
                
                # Filtrar documento
                filtered_doc = self.filter_document(doc)
                
                if filtered_doc:
                    # Exportar a Elasticsearch
                    self.export_to_elasticsearch(filtered_doc)
                
                processed += 1
                
                if processed % 100 == 0:
                    percentage = (processed / total_docs) * 100
                    logger.info(f"Progreso: {processed}/{total_docs} ({percentage:.1f}%)")
            
            logger.info(f"Procesamiento inicial completado: {self.processed_count} eventos procesados")
            
        except Exception as e:
            logger.error(f"Error procesando datos existentes: {e}")
    
    def monitor_new_data(self):
        """Monitorear nuevos datos usando change streams"""
        logger.info("Iniciando monitoreo de nuevos datos...")
        
        try:
            # Usar change streams para monitorear inserts
            with self.collection.watch([{'$match': {'operationType': 'insert'}}]) as stream:
                for change in stream:
                    if not self.running:
                        break
                    
                    # Obtener el documento insertado
                    new_doc = change['fullDocument']
                    
                    # Filtrar y procesar
                    filtered_doc = self.filter_document(new_doc)
                    
                    if filtered_doc:
                        self.export_to_elasticsearch(filtered_doc)
                        logger.info("Nuevo evento procesado en tiempo real")
                        
        except Exception as e:
            logger.error(f"Error en monitoreo de datos: {e}")
            time.sleep(5)  # Esperar antes de reintentar
    
    def run(self):
        """Ejecutar el procesador"""
        logger.info("Iniciando Waze Processed Events Processor...")
        logger.info(f"MongoDB: {self.mongo_uri}")
        logger.info(f"Elasticsearch: http://{self.es_host}")
        logger.info(f"Índice de salida: {self.es_index}")
        logger.info(f"Campos a mantener: {len(FIELDS_TO_KEEP)}")
        
        # Configurar índice
        self.ensure_index_mapping()
        
        # Procesar datos existentes
        self.process_existing_data()
        
        # Monitorear nuevos datos
        while self.running:
            try:
                self.monitor_new_data()
            except KeyboardInterrupt:
                logger.info("Procesador detenido por usuario")
                break
            except Exception as e:
                logger.error(f"Error en procesador: {e}")
                time.sleep(10)
        
        logger.info(f"Procesador detenido. Total procesado: {self.processed_count} eventos")

if __name__ == "__main__":
    processor = WazeProcessor()
    processor.run()
