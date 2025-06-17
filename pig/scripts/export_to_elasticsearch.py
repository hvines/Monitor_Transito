#!/usr/bin/env python3
"""
Script para exportar datos de MongoDB a Elasticsearch
"""

import os
import sys
import json
from datetime import datetime, timezone
from pymongo import MongoClient
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

def export_to_elasticsearch():
    """Exporta datos de MongoDB a Elasticsearch"""
    
    # Configuración MongoDB
    mongo_uri = os.environ.get("MONGO_URI", "mongodb://root:example@mongodb:27017/?authSource=admin")
    db_name = os.environ.get("MONGO_DBNAME", "waze_alertas")
    coll_name = os.environ.get("MONGO_COLLNAME", "eventos")
    
    # Configuración Elasticsearch
    es_host = os.environ.get("ES_HOST", "elasticsearch:9200")
    es_index = f"waze-events-{datetime.now().strftime('%Y.%m.%d')}"
    
    print(f"=== EXPORTANDO A ELASTICSEARCH ===")
    print(f"MongoDB URI: {mongo_uri}")
    print(f"ES Host: {es_host}")
    print(f"ES Index: {es_index}")
    
    try:
        # Conectar a MongoDB
        mongo_client = MongoClient(mongo_uri)
        db = mongo_client[db_name]
        collection = db[coll_name]
        
        # Conectar a Elasticsearch
        es = Elasticsearch([f"http://{es_host}"])
        
        # Verificar conexiones
        total_docs = collection.count_documents({})
        print(f"Total documentos en MongoDB: {total_docs}")
        
        try:
            # Verificar conexión obteniendo info del cluster
            cluster_info = es.cluster.health()
            print(f"✅ Conexión a Elasticsearch exitosa. Estado: {cluster_info['status']}")
        except Exception as ping_error:
            print(f"❌ Error al conectar a Elasticsearch: {ping_error}")
            return False
        
        print("✅ Conexiones establecidas")
        
        # Preparar documentos para bulk insert
        def generate_docs():
            for doc in collection.find():
                # Convertir ObjectId a string y guardarlo separadamente
                original_id = str(doc['_id'])
                
                # Remover el _id del documento fuente (no permitido en ES)
                doc_source = {k: v for k, v in doc.items() if k != '_id'}
                
                # Agregar el ID original como campo regular
                doc_source['mongodb_id'] = original_id
                
                # Normalizar timestamp
                if 'timestamp' in doc_source:
                    if isinstance(doc_source['timestamp'], str):
                        try:
                            doc_source['@timestamp'] = datetime.fromisoformat(doc_source['timestamp'].replace('Z', '+00:00'))
                        except:
                            doc_source['@timestamp'] = datetime.now(timezone.utc)
                    else:
                        doc_source['@timestamp'] = doc_source['timestamp']
                else:
                    doc_source['@timestamp'] = datetime.now(timezone.utc)
                
                # Parsear ubicación para geo_point
                if 'location' in doc_source and isinstance(doc_source['location'], dict):
                    if 'lat' in doc_source['location'] and 'lon' in doc_source['location']:
                        doc_source['geo_location'] = {
                            "lat": doc_source['location']['lat'],
                            "lon": doc_source['location']['lon']
                        }
                
                # Usar UUID como ID del documento si existe, sino usar el ID de MongoDB
                doc_id = doc_source.get('uuid', original_id)
                
                yield {
                    "_index": es_index,
                    "_id": doc_id,
                    "_source": doc_source
                }
        
        # Ejecutar bulk insert
        print("Iniciando exportación bulk...")
        try:
            from elasticsearch.helpers import BulkIndexError
            success_count, failed_items = bulk(es, generate_docs(), chunk_size=100, raise_on_error=False)
            
            print(f"✅ Exportación completada")
            print(f"Documentos exportados: {success_count}")
            
            if failed_items:
                print(f"⚠️  Documentos fallidos: {len(failed_items)}")
                # Mostrar algunos errores para debug
                for i, failed_item in enumerate(failed_items[:3]):
                    print(f"Error {i+1}: {failed_item}")
        except BulkIndexError as bulk_error:
            print(f"❌ Error en bulk insert: {bulk_error}")
            # Mostrar errores específicos
            for error in bulk_error.errors[:3]:
                print(f"Bulk error detail: {error}")
            return False
        except Exception as bulk_error:
            print(f"❌ Error general en bulk insert: {bulk_error}")
            return False
        
        # Verificar el índice en Elasticsearch
        if es.indices.exists(index=es_index):
            doc_count = es.count(index=es_index)['count']
            print(f"Documentos en ES index '{es_index}': {doc_count}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error durante la exportación: {e}")
        return False
    
    finally:
        if 'mongo_client' in locals():
            mongo_client.close()

if __name__ == "__main__":
    success = export_to_elasticsearch()
    sys.exit(0 if success else 1)
