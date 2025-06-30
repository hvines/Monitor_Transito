#!/usr/bin/env python3
"""
Query Cache Service - Proxy con caché Redis para consultas a Elasticsearch
Intercepta consultas de Kibana, cachea resultados combinados de ambos índices en Redis
"""

import time
import json
import logging
import hashlib
from datetime import datetime, timezone
from flask import Flask, request, jsonify, Response
import requests
import redis
import signal
import sys
import threading

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class QueryCacheService:
    def __init__(self):
        # Configuración
        self.ES_HOST = "elasticsearch:9200"
        self.REDIS_HOST = "redis:6379"
        self.CACHE_TTL = 10  # segundos
        self.PORT = 9201  # Puerto del proxy
        
        # Índices a monitorear
        self.RAW_INDEX = "waze-raw-events"
        self.PROCESSED_INDEX = "waze-processed-events"
        
        # Estado del servicio
        self.running = True
        
        # Configurar conexiones
        self.setup_connections()
        self.setup_flask_app()
        self.setup_signal_handlers()

    def setup_connections(self):
        """Establecer conexiones a Redis y Elasticsearch"""
        try:
            # Redis
            logger.info("Conectando a Redis...")
            self.redis_client = redis.Redis(
                host=self.REDIS_HOST.split(':')[0], 
                port=int(self.REDIS_HOST.split(':')[1]), 
                decode_responses=True
            )
            self.redis_client.ping()
            
            # Elasticsearch (para verificar conexión)
            logger.info("Verificando conexión a Elasticsearch...")
            es_response = requests.get(f"http://{self.ES_HOST}")
            if es_response.status_code != 200:
                raise Exception("Elasticsearch no responde")
                
            logger.info("Conexiones establecidas correctamente")
            
        except Exception as e:
            logger.error(f"Error estableciendo conexiones: {e}")
            raise

    def setup_flask_app(self):
        """Configurar aplicación Flask como proxy"""
        self.app = Flask(__name__)
        self.app.logger.setLevel(logging.INFO)
        
        # Ruta principal para interceptar todas las consultas
        @self.app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
        def proxy_request(path):
            return self.handle_proxy_request(path)
        
        # Ruta raíz
        @self.app.route('/', methods=['GET'])
        def root():
            return self.handle_proxy_request('')
        
        # Endpoint de health check
        @self.app.route('/health', methods=['GET'])
        def health():
            return jsonify({
                "status": "healthy",
                "service": "query-cache-proxy",
                "elasticsearch": f"http://{self.ES_HOST}",
                "redis": self.REDIS_HOST,
                "cache_ttl": self.CACHE_TTL
            })

    def setup_signal_handlers(self):
        """Configurar manejadores de señales para shutdown limpio"""
        signal.signal(signal.SIGTERM, self.shutdown)
        signal.signal(signal.SIGINT, self.shutdown)

    def shutdown(self, signum, frame):
        """Shutdown limpio del servicio"""
        logger.info("Iniciando shutdown del query cache service...")
        self.running = False

    def generate_cache_key(self, method, path, query_params, body):
        """Generar clave única para caché basada en la consulta"""
        try:
            # Crear string único de la consulta
            cache_data = {
                'method': method,
                'path': path,
                'params': sorted(query_params.items()) if query_params else [],
                'body': body if body else ''
            }
            
            cache_string = json.dumps(cache_data, sort_keys=True)
            cache_hash = hashlib.md5(cache_string.encode()).hexdigest()
            
            return f"es_query:{cache_hash}"
            
        except Exception as e:
            logger.warning(f"Error generando clave de caché: {e}")
            return None

    def is_search_query(self, path, method):
        """Determinar si la consulta es de búsqueda y debe ser cacheada"""
        search_paths = [
            '_search',
            '_msearch',
            '_count'
        ]
        
        return (
            method in ['GET', 'POST'] and
            any(search_path in path for search_path in search_paths) and
            (self.RAW_INDEX in path or self.PROCESSED_INDEX in path or '_all' in path)
        )

    def get_cached_result(self, cache_key):
        """Obtener resultado desde caché Redis"""
        try:
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                logger.info(f"Cache HIT: {cache_key[:20]}...")
                return json.loads(cached_data)
            return None
            
        except Exception as e:
            logger.warning(f"Error obteniendo caché: {e}")
            return None

    def set_cached_result(self, cache_key, result_data):
        """Guardar resultado en caché Redis"""
        try:
            # Agregar metadata de caché
            cached_result = {
                'data': result_data,
                'cached_at': datetime.now(timezone.utc).isoformat(),
                'ttl': self.CACHE_TTL
            }
            
            self.redis_client.setex(
                cache_key,
                self.CACHE_TTL,
                json.dumps(cached_result)
            )
            
            logger.info(f"Cache SET: {cache_key[:20]}... (TTL: {self.CACHE_TTL}s)")
            
        except Exception as e:
            logger.warning(f"Error guardando en caché: {e}")

    def enhance_search_results(self, es_response, path):
        """Enriquecer resultados de búsqueda con información comparativa"""
        try:
            if 'hits' not in es_response:
                return es_response
            
            # Agregar metadata de índices consultados
            enhancement = {
                'query_cache_info': {
                    'cached_at': datetime.now(timezone.utc).isoformat(),
                    'indices_available': [self.RAW_INDEX, self.PROCESSED_INDEX],
                    'current_query_path': path,
                    'enhancement_applied': True
                }
            }
            
            # Si es una consulta a un índice específico, agregar info del otro
            if self.RAW_INDEX in path:
                enhancement['query_cache_info']['queried_index'] = 'raw'
                enhancement['query_cache_info']['companion_index'] = self.PROCESSED_INDEX
            elif self.PROCESSED_INDEX in path:
                enhancement['query_cache_info']['queried_index'] = 'processed'
                enhancement['query_cache_info']['companion_index'] = self.RAW_INDEX
            else:
                enhancement['query_cache_info']['queried_index'] = 'multiple'
            
            # Agregar enhancement a la respuesta
            es_response.update(enhancement)
            
            return es_response
            
        except Exception as e:
            logger.warning(f"Error enriqueciendo resultados: {e}")
            return es_response

    def handle_proxy_request(self, path):
        """Manejar request proxy con caché inteligente"""
        try:
            method = request.method
            query_params = request.args.to_dict()
            
            # Obtener body si existe
            body = None
            if request.content_length and request.content_length > 0:
                try:
                    body = request.get_json(silent=True)
                    if body is None:
                        body = request.get_data(as_text=True)
                except:
                    body = request.get_data(as_text=True)
            
            # Construir URL de Elasticsearch
            es_url = f"http://{self.ES_HOST}/{path}"
            if query_params:
                es_url += '?' + '&'.join([f"{k}={v}" for k, v in query_params.items()])
            
            logger.info(f"{method} {path} - Proxy request")
            
            # Verificar si debe usar caché
            if self.is_search_query(path, method):
                cache_key = self.generate_cache_key(method, path, query_params, body)
                
                if cache_key:
                    # Intentar obtener desde caché
                    cached_result = self.get_cached_result(cache_key)
                    if cached_result:
                        return jsonify(cached_result['data'])
            
            # Realizar consulta a Elasticsearch
            es_headers = {
                'Content-Type': request.content_type or 'application/json'
            }
            
            if body and isinstance(body, (dict, list)):
                es_response = requests.request(
                    method=method,
                    url=es_url,
                    json=body,
                    headers=es_headers,
                    timeout=30
                )
            else:
                es_response = requests.request(
                    method=method,
                    url=es_url,
                    data=body,
                    headers=es_headers,
                    timeout=30
                )
            
            # Procesar respuesta
            if es_response.status_code == 200:
                try:
                    response_data = es_response.json()
                    
                    # Enriquecer resultados de búsqueda
                    if self.is_search_query(path, method):
                        response_data = self.enhance_search_results(response_data, path)
                        
                        # Guardar en caché si es consulta de búsqueda
                        if cache_key:
                            self.set_cached_result(cache_key, response_data)
                    
                    return jsonify(response_data)
                    
                except json.JSONDecodeError:
                    return Response(
                        es_response.content,
                        status=es_response.status_code,
                        headers=dict(es_response.headers)
                    )
            else:
                return Response(
                    es_response.content,
                    status=es_response.status_code,
                    headers=dict(es_response.headers)
                )
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error en request a Elasticsearch: {e}")
            return jsonify({
                'error': 'Elasticsearch connection error',
                'message': str(e)
            }), 500
            
        except Exception as e:
            logger.error(f"Error en proxy request: {e}")
            return jsonify({
                'error': 'Internal proxy error',
                'message': str(e)
            }), 500

    def run_cache_cleanup(self):
        """Limpiar caché periódicamente"""
        while self.running:
            try:
                # Obtener estadísticas de caché
                cache_keys = self.redis_client.keys("es_query:*")
                logger.info(f"Caché activo: {len(cache_keys)} consultas almacenadas")
                
                # Dormir por 60 segundos
                time.sleep(60)
                
            except Exception as e:
                logger.warning(f"Error en limpieza de caché: {e}")
                time.sleep(60)

    def run(self):
        """Ejecutar el servicio proxy con caché"""
        logger.info("Iniciando Query Cache Service (Elasticsearch Proxy)...")
        logger.info(f"Proxy escuchando en puerto {self.PORT}")
        logger.info(f"Elasticsearch backend: http://{self.ES_HOST}")
        logger.info(f"Redis cache: {self.REDIS_HOST} (TTL: {self.CACHE_TTL}s)")
        logger.info(f"Índices monitoreados: {self.RAW_INDEX}, {self.PROCESSED_INDEX}")
        
        # Iniciar limpieza de caché en background
        cleanup_thread = threading.Thread(target=self.run_cache_cleanup, daemon=True)
        cleanup_thread.start()
        
        try:
            # Ejecutar Flask app
            self.app.run(
                host='0.0.0.0',
                port=self.PORT,
                debug=False,
                threaded=True
            )
        except KeyboardInterrupt:
            logger.info("Query Cache Service detenido por usuario")
        except Exception as e:
            logger.error(f"Error ejecutando servicio: {e}")
        finally:
            self.running = False
            logger.info("Query Cache Service detenido")

if __name__ == "__main__":
    cache_service = QueryCacheService()
    cache_service.run()
