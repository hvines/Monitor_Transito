# Arquitectura del Pipeline de Eventos Waze - Documentación Técnica

## Resumen Ejecutivo

Este documento describe la arquitectura completa del sistema de procesamiento de eventos de tráfico Waze, diseñado para ingestar, procesar, almacenar y visualizar datos de tráfico en tiempo real con capacidades de análisis comparativo entre datos raw y procesados.

## Arquitectura General

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Waze API  │───▶│   Scraper   │───▶│   MongoDB   │───▶│Raw Exporter │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                                              │                    │
                                              ▼                    │
                                    ┌─────────────┐               │
                                    │PIG Processor│               │
                                    └─────────────┘               │
                                              │                    │
                                              ▼                    ▼
                                    ┌─────────────────────────────────┐
                                    │        Elasticsearch            │
                                    │  ┌─────────────────────────────┐│
                                    │  │    waze-processed-events    ││
                                    │  └─────────────────────────────┘│
                                    │  ┌─────────────────────────────┐│
                                    │  │      waze-raw-events        ││
                                    │  └─────────────────────────────┘│
                                    └─────────────────────────────────┘
                                                    │
                                                    ▼
                                    ┌─────────────────────────────────┐
                                    │      Query Cache Service        │
                                    │         (Proxy + Cache)         │
                                    └─────────────────────────────────┘
                                              │           ▲
                                              ▼           │
                                    ┌─────────────┐   ┌─────────────┐
                                    │   Kibana    │   │    Redis    │
                                    │(Visualización)│   │   (Cache)   │
                                    └─────────────┘   └─────────────┘
```

## Componentes del Sistema

### 1. Waze Scraper
**Función**: Ingesta de datos en tiempo real
- **Tecnología**: Python Flask
- **Fuente**: API pública de Waze para Santiago, Chile
- **Frecuencia**: Continua (cada 30-60 segundos)
- **Salida**: Eventos raw almacenados en MongoDB
- **Características**:
  - Manejo de errores y reconexión automática
  - Normalización básica de timestamps (UTC-4)
  - Validación de estructura de datos
  - Logging detallado para monitoreo

### 2. MongoDB
**Función**: Almacenamiento primario de datos raw
- **Tecnología**: MongoDB 6.0
- **Base de datos**: `waze_data`
- **Colección**: `events`
- **Características**:
  - Persistencia en volúmenes Docker
  - Autenticación configurada
  - Índices optimizados para consultas temporales y geográficas

### 3. Raw Exporter
**Función**: Exportación automática de datos sin procesar
- **Tecnología**: Python con MongoWatch
- **Monitoreo**: Change streams de MongoDB
- **Destino**: Índice `waze-raw-events` en Elasticsearch
- **Características**:
  - Exportación en tiempo real
  - Conversión de tipos (geo-points, timestamps)
  - Preservación de estructura original
  - Manejo de errores y reintentos

### 4. PIG Auto Processor
**Función**: Procesamiento inteligente y filtrado de datos
- **Tecnología**: Python con integración a scripts PIG
- **Monitoreo**: Change streams de MongoDB
- **Destino**: Índice `waze-processed-events` en Elasticsearch
- **Filtros aplicados**:
  - **Por tipo**: Filtra tipos de eventos relevantes
  - **Por zona**: Filtra por comunas de Santiago
  - **Por tiempo**: Filtros temporales configurables
  - **Por frecuencia**: Análisis de score y relevancia
- **Características**:
  - Procesamiento automático en tiempo real
  - Enriquecimiento de datos (score, metadata)
  - Normalización geográfica
  - Logging de transformaciones

### 5. Elasticsearch
**Función**: Motor de búsqueda y almacenamiento analítico
- **Tecnología**: Elasticsearch 8.x
- **Índices**:
  - `waze-raw-events`: Datos sin procesar
  - `waze-processed-events`: Datos procesados y filtrados
- **Características**:
  - Mappings optimizados para geo-búsquedas
  - Configuración de single-node
  - Health monitoring integrado
  - API REST completa

### 6. Redis
**Función**: Sistema de caché para optimización de consultas
- **Tecnología**: Redis 7.0
- **Puerto**: 6379
- **Características**:
  - Caché de datos para optimización de consultas
  - Configuración persistente
  - Health monitoring integrado
  - Soporte para clustering si es necesario

### 7. Kibana
**Función**: Interfaz de visualización y análisis
- **Tecnología**: Kibana 8.x
- **Conexión**: Directamente a Elasticsearch (puerto 9200)
- **Características**:
  - Dashboards comparativos
  - Index patterns para ambos índices
  - Geo-visualizaciones
  - Time-series analysis
  - Alerting capabilities

### 8. Herramientas de Administración
**Mongo Express**: Interfaz web para MongoDB (puerto 8081)
**Redis Commander**: Interfaz web para Redis (puerto 8082)

## Flujo de Datos Detallado

### 1. Ingesta (Waze API → MongoDB)
```
Waze API (REST) 
    ↓ (HTTP GET cada 30-60s)
Scraper (Python)
    ↓ (Validation + Normalization)
MongoDB (waze_data.events)
```

### 2. Exportación Raw (MongoDB → Elasticsearch Raw)
```
MongoDB Change Stream
    ↓ (Real-time monitoring)
Raw Exporter (Python)
    ↓ (Type conversion + Mapping)
Elasticsearch (waze-raw-events)
```

### 3. Procesamiento (MongoDB → Elasticsearch Processed)
```
MongoDB Change Stream
    ↓ (Real-time monitoring)
PIG Auto Processor
    ↓ (Filters: Type + Zone + Time + Frequency)
Enhanced Events
    ↓ (Enrichment + Scoring)
Elasticsearch (waze-processed-events)
```

### 4. Consulta y Visualización
```
Kibana (Frontend)
    ↓ (Elasticsearch API calls)
Query Cache Service (Proxy:9200)
    ↓ (Cache check in Redis)
Redis Cache ←→ Elasticsearch (Backend:9200)
    ↓ (Results with enhancement)
Response to Kibana
```

## Configuración y Variables

### Variables de Entorno Críticas

**Scraper**:
- `MONGO_URI`: Conexión a MongoDB
- `SCRAPE_INTERVAL`: Intervalo de scraping (default: 30s)

**Raw Exporter**:
- `MONGO_URI`: Conexión a MongoDB
- `ES_HOST`: Host de Elasticsearch
- `INDEX_NAME`: Nombre del índice raw

**PIG Processor**:
- `MONGO_URI`: Conexión a MongoDB
- `ES_HOST`: Host de Elasticsearch
- `FILTERS_CONFIG`: Configuración de filtros

**Query Cache**:
- `ES_HOST`: Backend Elasticsearch
- `REDIS_HOST`: Host de Redis
- `CACHE_TTL`: Time-to-live del caché

### Configuraciones de Red

**Puertos Expuestos**:
- 5601: Kibana
- 8081: Mongo Express
- 8082: Redis Commander
- 9200: Elasticsearch (directo)
- 9200: Query Cache Service

**Red Interna**: `my-network` (bridge)

## Monitoreo y Observabilidad

### Health Checks Implementados

1. **Elasticsearch**: `/_cluster/health`
2. **Query Cache**: `/health`
3. **Kibana**: `/api/status`
4. **Redis**: `PING` command
5. **MongoDB**: `db.adminCommand('ping')`

### Métricas Clave

**Throughput**:
- Eventos/minuto ingresados
- Ratio de exportación (raw/total)
- Ratio de procesamiento (processed/raw)

**Latencia**:
- Tiempo ingesta → raw export
- Tiempo raw → processed
- Tiempo de respuesta cache

**Calidad**:
- Eventos con coordenadas válidas
- Eventos con timestamps válidos
- Distribución geográfica

### Logging

Todos los servicios implementan logging estructurado:
- Nivel INFO para operaciones normales
- Nivel WARNING para problemas no críticos
- Nivel ERROR para fallos que requieren atención
- Timestamps en UTC
- Formato JSON para agregación

## Escalabilidad y Performance

### Escalabilidad Horizontal

**MongoDB**: Sharding ready
**Elasticsearch**: Cluster ready (multi-node)
**Redis**: Clustering support
**Query Cache**: Stateless (múltiples instancias)

### Optimizaciones Implementadas

1. **Caché inteligente** con TTL ajustable
2. **Índices optimizados** en MongoDB y Elasticsearch
3. **Change streams** para procesamiento en tiempo real
4. **Conexiones persistentes** entre servicios
5. **Batch processing** para operaciones bulk

### Límites y Consideraciones

**MongoDB**: Limitado por I/O de disco
**Elasticsearch**: Requiere mínimo 4GB RAM
**Redis**: Limitado por memoria disponible
**Scraper**: Limitado por rate limits de Waze API

## Seguridad

### Configuraciones de Seguridad

1. **Autenticación MongoDB** con credenciales
2. **Red interna aislada** para comunicación entre servicios
3. **Usuarios no-root** en contenedores
4. **Configuración XPack deshabilitada** (desarrollo)

### Consideraciones para Producción

1. **HTTPS/TLS** en todos los endpoints
2. **Autenticación OAuth** para Kibana
3. **Cifrado** de datos en reposo
4. **Rate limiting** en APIs públicas
5. **Firewall** y network policies

## Deployment y DevOps

### Estructura de Archivos
```
├── docker-compose.yml          # Orquestación principal
├── manage.sh                   # Script de gestión
├── test_pipeline.sh           # Tests automatizados
├── README.md                  # Documentación de usuario
├── QUERIES_GUIDE.md           # Guía de consultas
├── ARCHITECTURE.md            # Este documento
├── scraper/                   # Servicio scraper
├── raw-exporter/              # Servicio exportador raw
├── pig/                       # Servicio procesador PIG
├── query-cache/               # Servicio caché
├── elasticsearch/             # Configuración ES
├── kibana/                    # Configuración Kibana
├── mongodb/                   # Configuración MongoDB
└── redis/                     # Configuración Redis
```

### Comandos de Gestión
```bash
./manage.sh up       # Iniciar sistema completo
./manage.sh down     # Detener sistema
./manage.sh test     # Ejecutar tests
./manage.sh status   # Verificar estado
./manage.sh clean    # Limpieza completa
```

## Troubleshooting

### Problemas Comunes y Soluciones

**Elasticsearch no inicia**:
- Verificar memoria disponible (>4GB)
- Revisar permisos de volúmenes
- Verificar configuración de VM

**Sin datos en índices**:
- Verificar conectividad Scraper → MongoDB
- Revisar logs de exportadores
- Verificar change streams activos

**Caché no funciona**:
- Verificar conectividad Redis
- Revisar TTL configuration
- Verificar logs del proxy

**Kibana no conecta**:
- Verificar Query Cache Service activo
- Verificar configuración elasticsearch.hosts
- Revisar health checks

## Roadmap y Mejoras Futuras

### Corto Plazo
1. **Alerting** automatizado en Kibana
2. **Métricas** de performance más detalladas
3. **Tests** de integración automatizados
4. **Documentación** de APIs

### Mediano Plazo
1. **Machine Learning** para predicción de tráfico
2. **Stream processing** con Kafka
3. **Multi-región** deployment
4. **API Gateway** para acceso externo

### Largo Plazo
1. **Real-time** dashboard con WebSockets
2. **Mobile app** para visualización
3. **Integration** con sistemas de transporte público
4. **AI-powered** traffic optimization

---

Este documento proporciona una visión completa de la arquitectura del sistema. Para preguntas específicas o detalles de implementación, consultar el código fuente y documentación adicional.
