# Sistema de Procesamiento de Eventos de Tráfico Waze - T3

## Descripción General

Este proyecto despliega un pipeline completo de procesamiento de eventos de tráfico de Waze con capacidades de análisis comparativo entre datos raw y procesados. El sistema consta de:

### Arquitectura del Pipeline

```
Waze API → Scraper → MongoDB → [Raw Exporter + PIG Processor] → Elasticsearch → Query Cache → Kibana
                                ↓                                    ↓
                            waze-raw-events              waze-processed-events
                                ↓                                    ↓
                            Redis Cache ← ← ← ← ← ← ← ← ← ← ← ← ← ← ←
```

### Componentes del Sistema

1. **Waze Scraper**: Extrae eventos de tráfico reales de la API de Waze para Santiago y los almacena en MongoDB
2. **MongoDB**: Base de datos NoSQL que almacena todos los eventos reales del scraper
3. **Raw Exporter**: Servicio que automáticamente exporta datos raw de MongoDB al índice `waze-raw-events` en Elasticsearch
4. **PIG Auto Processor**: Servicio que procesa automáticamente los datos aplicando filtros (tipo, zona, tiempo, frecuencia) y los exporta al índice `waze-processed-events`
5. **Elasticsearch**: Motor de búsqueda con dos índices separados para análisis comparativo
6. **Query Cache Service**: Proxy inteligente que cachea consultas a Elasticsearch en Redis (TTL: 10s) y enriquece respuestas
7. **Redis**: Sistema de caché para optimizar consultas repetitivas a Elasticsearch
8. **Kibana**: Interfaz web para visualización y análisis comparativo entre datos raw y procesados
9. **Herramientas de administración**: mongo-express (puerto 8081) y redis-commander (puerto 8082)

## Flujo de Datos

1. **Ingesta**: El scraper obtiene eventos en tiempo real de Waze → MongoDB
2. **Exportación Raw**: Raw exporter monitorea MongoDB y exporta automáticamente nuevos documentos a `waze-raw-events`
3. **Procesamiento**: PIG processor aplica filtros automáticos y exporta datos procesados a `waze-processed-events`
4. **Consulta**: Kibana consulta ambos índices a través del query cache service
5. **Cache**: Redis almacena resultados para optimizar consultas repetitivas
6. **Visualización**: Kibana permite comparar y analizar ambos conjuntos de datos

## Instrucciones de Arranque

### Opción 1: Usando el script de gestión (Recomendado)

```bash
# Inicia todos los servicios
./manage.sh up

# Para detener y limpiar completamente
./manage.sh down

# Para reiniciar todo
./manage.sh restart

# Para limpieza completa (contenedores, imágenes, volúmenes)
./manage.sh clean

# Para ver el estado de los servicios
./manage.sh status

# Para ver logs de todos los servicios o uno específico
./manage.sh logs [nombre_servicio]
```

### Opción 2: Usando Docker Compose directamente

```bash
# Limpia y detiene todos los contenedores
docker-compose down --remove-orphans

# Construye y arranca todos los servicios
docker-compose up -d

# Verificar servicios corriendo
docker-compose ps
```

## Acceso a los Servicios

- **Mongo Express** → http://localhost:8081 (Administrador de MongoDB)
- **Redis Commander** → http://localhost:8082 (Administrador de Redis)  
- **Elasticsearch** → http://localhost:9200 (API REST directa)
- **Query Cache Service** → http://localhost:9201 (Proxy con caché para Elasticsearch)
- **Kibana** → http://localhost:5601 (Visualización y análisis comparativo)

### Endpoints del Query Cache Service

- `GET http://localhost:9201/health` - Health check del proxy
- `GET/POST http://localhost:9201/waze-raw-events/_search` - Búsqueda en datos raw (con caché)
- `GET/POST http://localhost:9201/waze-processed-events/_search` - Búsqueda en datos procesados (con caché)
- `GET/POST http://localhost:9201/_all/_search` - Búsqueda en ambos índices

## Verificación del Pipeline

### 1. Verificar ingesta de datos
```bash
# Ver logs del scraper
docker-compose logs -f waze-scraper

# Verificar datos en MongoDB via mongo-express
curl -s http://localhost:8081
```

### 2. Verificar exportación raw
```bash
# Ver logs del raw exporter
docker-compose logs -f raw-exporter

# Verificar índice raw en Elasticsearch
curl -s "http://localhost:9200/waze-raw-events/_count" | jq .
```

### 3. Verificar procesamiento
```bash
# Ver logs del procesador PIG
docker-compose logs -f pig

# Verificar índice procesado
curl -s "http://localhost:9200/waze-processed-events/_count" | jq .
```

### 4. Verificar caché
```bash
# Ver logs del query cache
docker-compose logs -f query-cache

# Verificar estado del caché
curl -s "http://localhost:9201/health" | jq .
```

### 5. Comparar datos en Kibana
1. Acceder a Kibana → http://localhost:5601
2. Crear index patterns para ambos índices:
   - `waze-raw-events`
   - `waze-processed-events`
3. Usar Discover para explorar las diferencias
4. Crear visualizaciones comparativas

## Análisis Comparativo

### Datos Raw vs Procesados

**Datos Raw (`waze-raw-events`)**:
- Eventos originales sin filtrar de Waze
- Incluye todos los tipos de eventos
- Timestamps originales
- Ubicaciones exactas sin procesamiento

**Datos Procesados (`waze-processed-events`)**:
- Filtros aplicados por tipo de evento
- Filtros por zona geográfica (comunas de Santiago)
- Filtros temporales
- Análisis de frecuencia y score calculado
- Datos normalizados y enriquecidos

### Ejemplos de Consultas Comparativas

```bash
# Contar eventos por tipo en datos raw
curl -X POST "http://localhost:9201/waze-raw-events/_search" \
  -H "Content-Type: application/json" \
  -d '{"size": 0, "aggs": {"types": {"terms": {"field": "type.keyword"}}}}'

# Contar eventos por tipo en datos procesados  
curl -X POST "http://localhost:9201/waze-processed-events/_search" \
  -H "Content-Type: application/json" \
  -d '{"size": 0, "aggs": {"types": {"terms": {"field": "type.keyword"}}}}'

# Comparar distribución temporal
curl -X POST "http://localhost:9201/_all/_search" \
  -H "Content-Type: application/json" \
  -d '{"size": 0, "aggs": {"by_index": {"terms": {"field": "_index"}, "aggs": {"over_time": {"date_histogram": {"field": "pubTimestamp", "calendar_interval": "hour"}}}}}}'
```

## Configuración y Personalización

### Variables de Entorno

**Raw Exporter**:
- `MONGO_URI`: URI de conexión a MongoDB
- `ES_HOST`: Host de Elasticsearch

**PIG Processor**:
- `MONGO_URI`: URI de conexión a MongoDB  
- `ES_HOST`: Host de Elasticsearch

**Query Cache Service**:
- `ES_HOST`: Host de Elasticsearch (elasticsearch:9200)
- `REDIS_HOST`: Host de Redis (redis:6379)

### Configuración de Filtros PIG

Los filtros se aplican automáticamente, pero pueden ser personalizados modificando:
- `pig/scripts/filter_by_type.py`
- `pig/scripts/filter_by_comuna.py`
- `pig/scripts/filter_by_time.py`
- `pig/scripts/frequency_analysis.py`

## Monitoreo y Logs

```bash
# Ver logs de todos los servicios
docker-compose logs -f

# Ver logs de un servicio específico
docker-compose logs -f [waze-scraper|raw-exporter|pig|query-cache]

# Ver estado de todos los contenedores
docker-compose ps

# Ver uso de recursos
docker stats
```

## Troubleshooting

### Elasticsearch no inicia
- Verificar que tiene suficiente memoria (mínimo 4GB recomendado)
- Esperar hasta 60 segundos para inicialización completa

### Kibana no puede conectar
- Verificar que Elasticsearch esté saludable
- Verificar que el query cache service esté funcionando en puerto 9201

### Sin datos en los índices
- Verificar que el scraper esté corriendo y obteniendo datos
- Verificar logs del raw-exporter y pig processor
- Verificar conectividad con MongoDB y Elasticsearch

### Caché no funciona
- Verificar conectividad entre query-cache y Redis
- Verificar logs del query cache service

## Detener el Sistema

```bash
# Usando el script de gestión
./manage.sh down

# O usando Docker Compose directamente
docker-compose down --remove-orphans

# Para limpieza completa (incluyendo volúmenes)
docker-compose down --remove-orphans --volumes
```

**Nota**: El sistema mantiene persistencia de datos en volúmenes Docker. Para reinicializar completamente, usar la opción `--volumes`.




    
