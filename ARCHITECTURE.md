# Arquitectura del Pipeline de Eventos Waze - Documentación Técnica

## Resumen Ejecutivo

Este documento describe la arquitectura completa del sistema de procesamiento de eventos de tráfico Waze, diseñado para ingestar, procesar, almacenar y visualizar datos de tráfico en tiempo real con capacidades de análisis comparativo entre datos raw y procesados.

## Arquitectura General

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Waze API  │───▶│   Scraper   │───▶│   MongoDB   │
└─────────────┘    └─────────────┘    └─────────────┘
                                              │
                                              ├─────────────────┐
                                              ▼                 ▼
                                    ┌─────────────┐   ┌─────────────────┐
                                    │PIG Processor│   │ Mongo-ES        │
                                    └─────────────┘   │ Connector       │
                                              │       └─────────────────┘
                                              ▼                 │
                                    ┌─────────────────────────────────┐
                                    │        Elasticsearch            │
                                    │  ┌─────────────────────────────┐│
                                    │  │      waze_procesados        ││
                                    │  └─────────────────────────────┘│
                                    │  ┌─────────────────────────────┐│
                                    │  │        waze_bruto           ││
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

### 3. MongoDB-Elasticsearch Connector
**Función**: Sincronización directa de datos brutos
- **Tecnología**: Python con polling directo
- **Monitoreo**: Polling activo a MongoDB cada 15 segundos
- **Destino**: Índice `waze_bruto` en Elasticsearch
- **Características**:
  - Sincronización automática en tiempo real
  - Preservación completa de estructura original
  - Conversión mínima de tipos (geo-points, timestamps)
  - Manejo de errores y reintentos
  - Batch processing optimizado (100 docs/lote)

### 4. PIG Auto Processor
**Función**: Procesamiento inteligente y filtrado de datos
- **Tecnología**: Python con integración a scripts PIG
- **Monitoreo**: Polling activo a MongoDB cada 10 segundos
- **Destino**: Índice `waze_procesados` en Elasticsearch
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
  - `waze_bruto`: Datos sin procesar (sincronizados directamente desde MongoDB)
  - `waze_procesados`: Datos procesados y filtrados (procesados por PIG)
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
  - Dashboards para análisis comparativo entre datos brutos y procesados
  - Index patterns para `waze_bruto` y `waze_procesados`
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

### 2. Sincronización de Datos Brutos (MongoDB → Elasticsearch)
```
MongoDB (polling cada 15s)
    ↓ (Connector activo)
MongoDB-ES Connector
    ↓ (Conversión mínima + Mapping)
Elasticsearch (waze_bruto)
```

### 3. Procesamiento (MongoDB → Elasticsearch)
```
MongoDB (polling cada 10s)
    ↓ (Real-time monitoring)
PIG Auto Processor
    ↓ (Filters: Type + Zone + Time + Frequency)
Enhanced Events
    ↓ (Enrichment + Scoring)
Elasticsearch (waze_procesados)
```

### 4. Consulta y Visualización
```
Kibana (Frontend)
    ↓ (Elasticsearch API calls)
Elasticsearch (Backend:9200)
    ↓ (Results from waze_bruto and waze_procesados)
Response to Kibana
```

## Configuración y Variables

### Variables de Entorno Críticas

**Scraper**:
- `MONGO_URI`: Conexión a MongoDB
- `SCRAPE_INTERVAL`: Intervalo de scraping (default: 30s)

**MongoDB-ES Connector**:
- `MONGO_URI`: Conexión a MongoDB
- `ES_HOST`: Host de Elasticsearch
- `POLL_INTERVAL`: Intervalo de sincronización (default: 15s)

**PIG Processor**:
- `MONGO_URI`: Conexión a MongoDB
- `ES_HOST`: Host de Elasticsearch
- `FILTERS_CONFIG`: Configuración de filtros

### Configuraciones de Red

**Puertos Expuestos**:
- 5601: Kibana
- 8081: Mongo Express
- 8082: Redis Commander
- 9200: Elasticsearch (directo)

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
- Ratio de procesamiento (processed/total)

**Latencia**:
- Tiempo ingesta → procesamiento
- Tiempo de respuesta Elasticsearch

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
├── README.md                  # Documentación de usuario
├── QUERIES_GUIDE.md           # Guía de consultas
├── ARCHITECTURE.md            # Este documento
├── scraper/                   # Servicio scraper
├── mongo-elasticsearch-connector/ # Conector MongoDB-ES para datos brutos
├── pig/                       # Servicio procesador PIG
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
- Revisar logs del procesador PIG
- Verificar change streams activos

**Kibana no conecta**:
- Verificar Elasticsearch activo
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
