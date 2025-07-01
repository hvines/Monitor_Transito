#!/usr/bin/env python3
"""
MongoDB Data Inspector - Muestra todos los parámetros disponibles en MongoDB
Permite seleccionar cuáles filtrar o mantener para el procesamiento
"""

import os
import sys
import json
import time
import logging
from datetime import datetime, timezone
from pymongo import MongoClient
from collections import defaultdict

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MongoDataInspector:
    def __init__(self):
        # Configuración desde variables de entorno
        self.mongo_uri = os.getenv('MONGO_URI', 'mongodb://root:example@mongodb:27017/?authSource=admin')
        self.db_name = 'waze_data'
        self.collection_name = 'events'
        
        # Conectar a MongoDB
        self.setup_mongo_connection()
        
    def setup_mongo_connection(self):
        """Establecer conexión a MongoDB"""
        try:
            self.mongo_client = MongoClient(self.mongo_uri)
            self.db = self.mongo_client[self.db_name]
            self.collection = self.db[self.collection_name]
            
            # Verificar conexión
            self.mongo_client.admin.command('ismaster')
            logger.info("Conexión a MongoDB establecida correctamente")
            
        except Exception as e:
            logger.error(f"Error conectando a MongoDB: {e}")
            sys.exit(1)
    
    def get_sample_documents(self, limit=100):
        """Obtener documentos de muestra para analizar estructura"""
        try:
            # Obtener documentos más recientes
            documents = list(self.collection.find().sort("_id", -1).limit(limit))
            logger.info(f"Obtenidos {len(documents)} documentos para análisis")
            return documents
        except Exception as e:
            logger.error(f"Error obteniendo documentos: {e}")
            return []
    
    def analyze_field_structure(self, documents):
        """Analizar la estructura de campos en los documentos"""
        field_stats = defaultdict(lambda: {
            'count': 0,
            'types': set(),
            'sample_values': [],
            'null_count': 0
        })
        
        def traverse_document(doc, prefix=""):
            """Recorrer documento recursivamente"""
            for key, value in doc.items():
                field_name = f"{prefix}.{key}" if prefix else key
                
                # Contar apariciones
                field_stats[field_name]['count'] += 1
                
                # Registrar tipo
                field_stats[field_name]['types'].add(type(value).__name__)
                
                # Manejar valores nulos
                if value is None:
                    field_stats[field_name]['null_count'] += 1
                else:
                    # Guardar valores de muestra (máximo 5)
                    if len(field_stats[field_name]['sample_values']) < 5:
                        if isinstance(value, (dict, list)):
                            # Para objetos complejos, guardar tipo y tamaño
                            if isinstance(value, dict):
                                sample = f"dict({len(value)} keys)"
                            else:
                                sample = f"list({len(value)} items)"
                        else:
                            sample = str(value)[:100]  # Limitar longitud
                        
                        field_stats[field_name]['sample_values'].append(sample)
                
                # Recorrer recursivamente si es diccionario
                if isinstance(value, dict):
                    traverse_document(value, field_name)
                elif isinstance(value, list) and value and isinstance(value[0], dict):
                    # Recorrer primer elemento de lista si contiene diccionarios
                    traverse_document(value[0], f"{field_name}[0]")
        
        # Analizar todos los documentos
        for doc in documents:
            traverse_document(doc)
        
        return field_stats
    
    def print_field_analysis(self, field_stats, total_docs):
        """Imprimir análisis de campos de forma organizada"""
        print("\n" + "="*80)
        print("ANÁLISIS DE ESTRUCTURA DE DATOS MONGODB")
        print("="*80)
        print(f"Total de documentos analizados: {total_docs}")
        print(f"Campos únicos encontrados: {len(field_stats)}")
        print("\n")
        
        # Ordenar campos por frecuencia
        sorted_fields = sorted(field_stats.items(), key=lambda x: x[1]['count'], reverse=True)
        
        print("LISTA DE CAMPOS DISPONIBLES:")
        print("-" * 80)
        
        for field_name, stats in sorted_fields:
            # Calcular porcentaje de aparición
            percentage = (stats['count'] / total_docs) * 100
            
            # Información básica del campo
            types_str = ", ".join(stats['types'])
            
            print(f"\n• Campo: {field_name}")
            print(f"   Frecuencia: {stats['count']}/{total_docs} ({percentage:.1f}%)")
            print(f"   Tipo(s): {types_str}")
            
            if stats['null_count'] > 0:
                null_percentage = (stats['null_count'] / stats['count']) * 100
                print(f"   Valores nulos: {stats['null_count']} ({null_percentage:.1f}%)")
            
            # Mostrar valores de muestra
            if stats['sample_values']:
                print(f"   Valores de muestra:")
                for i, sample in enumerate(stats['sample_values'][:3], 1):
                    print(f"      {i}. {sample}")
            
            print("   " + "-" * 60)
    
    def generate_filter_template(self, field_stats):
        """Generar plantilla de configuración de filtros"""
        print("\n" + "="*80)
        print("PLANTILLA DE CONFIGURACIÓN DE FILTROS")
        print("="*80)
        print("# Descomenta los campos que QUIERES MANTENER en el procesamiento")
        print("# Los campos comentados serán FILTRADOS/ELIMINADOS")
        print("\n")
        
        # Agrupar campos por categorías comunes
        core_fields = []
        waze_fields = []
        location_fields = []
        time_fields = []
        metadata_fields = []
        
        for field_name in field_stats.keys():
            if field_name in ['_id', 'type', 'subtype']:
                core_fields.append(field_name)
            elif 'location' in field_name.lower() or 'coord' in field_name.lower():
                location_fields.append(field_name)
            elif 'time' in field_name.lower() or 'pub' in field_name.lower() or 'date' in field_name.lower():
                time_fields.append(field_name)
            elif field_name.startswith('_') or 'id' in field_name.lower():
                metadata_fields.append(field_name)
            else:
                waze_fields.append(field_name)
        
        categories = [
            ("CAMPOS CORE (Identificación básica)", core_fields),
            ("CAMPOS DE UBICACIÓN", location_fields),
            ("CAMPOS TEMPORALES", time_fields),
            ("CAMPOS WAZE (Datos de tráfico)", waze_fields),
            ("CAMPOS METADATA", metadata_fields)
        ]
        
        filter_config = []
        
        for category_name, fields in categories:
            if fields:
                filter_config.append(f"\n# {category_name}")
                for field in sorted(fields):
                    freq = field_stats[field]['count']
                    types = ", ".join(field_stats[field]['types'])
                    # Por defecto, mantener campos core y ubicación, comentar metadata
                    if 'metadata' in category_name.lower() or field.startswith('_') and field != '_id':
                        filter_config.append(f"# '{field}',  # {types} - aparece {freq} veces")
                    else:
                        filter_config.append(f"'{field}',  # {types} - aparece {freq} veces")
        
        print("FIELDS_TO_KEEP = [")
        for line in filter_config:
            print(f"    {line}")
        print("]\n")
        
        print("# Ejemplo de uso en waze-processed-events.py:")
        print("# filtered_doc = {field: doc[field] for field in FIELDS_TO_KEEP if field in doc}")
    
    def run_interactive_analysis(self):
        """Ejecutar análisis interactivo"""
        print("Iniciando análisis de estructura de datos MongoDB...")
        
        # Verificar que hay datos
        total_count = self.collection.count_documents({})
        if total_count == 0:
            print("No hay documentos en la colección. Asegúrate de que el scraper esté funcionando.")
            return
        
        print(f"Total de documentos en la colección: {total_count}")
        
        # Obtener muestra
        sample_size = min(100, total_count)
        print(f"Analizando muestra de {sample_size} documentos...")
        
        documents = self.get_sample_documents(sample_size)
        if not documents:
            print("No se pudieron obtener documentos para análisis")
            return
        
        # Analizar estructura
        field_stats = self.analyze_field_structure(documents)
        
        # Mostrar resultados
        self.print_field_analysis(field_stats, len(documents))
        self.generate_filter_template(field_stats)
        
        print("\n" + "="*80)
        print("Análisis completado. Usa la plantilla anterior para configurar filtros.")
        print("="*80)

if __name__ == "__main__":
    inspector = MongoDataInspector()
    inspector.run_interactive_analysis()
