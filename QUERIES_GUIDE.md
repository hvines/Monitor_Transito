# Guía de Consultas y Visualizaciones - Pipeline Waze

## Índices Disponibles

### waze-raw-events
Datos sin procesar directamente del scraper de Waze.

### waze-processed-events  
Datos procesados por PIG con filtros aplicados.

## Consultas de Ejemplo

### 1. Consultas Básicas via Query Cache Service

#### Contar eventos en cada índice
```bash
# Eventos raw
curl -X GET "http://localhost:9200/waze-raw-events/_count"

# Eventos procesados
curl -X GET "http://localhost:9200/waze-processed-events/_count"

# Todos los eventos
curl -X GET "http://localhost:9200/_all/_count"
```

#### Obtener eventos recientes
```bash
# Últimos 10 eventos raw
curl -X POST "http://localhost:9200/waze-raw-events/_search" \
  -H "Content-Type: application/json" \
  -d '{
    "size": 10,
    "sort": [{"pubTimestamp": {"order": "desc"}}]
  }'

# Últimos 10 eventos procesados
curl -X POST "http://localhost:9200/waze-processed-events/_search" \
  -H "Content-Type: application/json" \
  -d '{
    "size": 10,
    "sort": [{"pubTimestamp": {"order": "desc"}}]
  }'
```

### 2. Consultas Comparativas

#### Comparar distribución por tipo de evento
```bash
# Raw events por tipo
curl -X POST "http://localhost:9200/waze-raw-events/_search" \
  -H "Content-Type: application/json" \
  -d '{
    "size": 0,
    "aggs": {
      "types": {
        "terms": {
          "field": "type.keyword",
          "size": 20
        }
      }
    }
  }'

# Processed events por tipo
curl -X POST "http://localhost:9200/waze-processed-events/_search" \
  -H "Content-Type: application/json" \
  -d '{
    "size": 0,
    "aggs": {
      "types": {
        "terms": {
          "field": "type.keyword",
          "size": 20
        }
      }
    }
  }'
```

#### Comparar distribución temporal (por hora)
```bash
curl -X POST "http://localhost:9200/_all/_search" \
  -H "Content-Type: application/json" \
  -d '{
    "size": 0,
    "aggs": {
      "by_index": {
        "terms": {
          "field": "_index"
        },
        "aggs": {
          "over_time": {
            "date_histogram": {
              "field": "pubTimestamp",
              "calendar_interval": "hour"
            }
          }
        }
      }
    }
  }'
```

#### Buscar eventos específicos en ambos índices
```bash
# Buscar eventos de tipo JAM en ambos índices
curl -X POST "http://localhost:9200/_all/_search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": {
      "term": {
        "type.keyword": "JAM"
      }
    },
    "aggs": {
      "by_index": {
        "terms": {
          "field": "_index"
        }
      }
    }
  }'
```

### 3. Consultas Geográficas

#### Eventos por ubicación (raw vs procesados)
```bash
# Distribución geográfica en datos raw
curl -X POST "http://localhost:9200/waze-raw-events/_search" \
  -H "Content-Type: application/json" \
  -d '{
    "size": 0,
    "aggs": {
      "locations": {
        "geohash_grid": {
          "field": "location",
          "precision": 6
        }
      }
    }
  }'

# Distribución por comuna en datos procesados (si aplica)
curl -X POST "http://localhost:9200/waze-processed-events/_search" \
  -H "Content-Type: application/json" \
  -d '{
    "size": 0,
    "aggs": {
      "comunas": {
        "terms": {
          "field": "comuna.keyword",
          "size": 50
        }
      }
    }
  }'
```

### 4. Análisis de Rendimiento del Caché

#### Verificar estadísticas del cache
```bash
# Health check del query cache service
curl -X GET "http://localhost:9200/health"

# Realizar consulta para generar cache
curl -X POST "http://localhost:9200/waze-raw-events/_search" \
  -H "Content-Type: application/json" \
  -d '{"size": 1}'

# Repetir la misma consulta (debería usar cache)
curl -X POST "http://localhost:9200/waze-raw-events/_search" \
  -H "Content-Type: application/json" \
  -d '{"size": 1}'
```

## Configuración de Kibana

### 1. Crear Index Patterns

En Kibana (http://localhost:5601):

1. Ir a **Stack Management > Index Patterns**
2. Crear pattern para `waze-raw-events*`
   - Time field: `pubTimestamp`
3. Crear pattern para `waze-processed-events*`
   - Time field: `pubTimestamp`

### 2. Visualizaciones Recomendadas

#### Dashboard Comparativo

**Gráfico 1: Volumen de Eventos por Tiempo**
- Tipo: Line Chart
- X-axis: `pubTimestamp` (Date Histogram, 1 hour interval)
- Y-axis: Count
- Split Series: `_index.keyword`

**Gráfico 2: Distribución por Tipo de Evento**
- Tipo: Pie Chart  
- Buckets: `type.keyword`
- Filtros: Comparar entre índices

**Gráfico 3: Mapa de Calor Geográfico**
- Tipo: Maps
- Data source: Raw events
- Geo field: `location`

**Gráfico 4: Top Ubicaciones Procesadas**
- Tipo: Data Table
- Rows: `comuna.keyword` (para eventos procesados)
- Metrics: Count

**Gráfico 5: Eventos en Tiempo Real**
- Tipo: Metric
- Aggregation: Count
- Time range: Last 15 minutes

#### Dashboard de Monitoreo del Pipeline

**Métricas Clave:**
- Total eventos raw vs procesados
- Ratio de procesamiento (procesados/raw)
- Eventos por minuto en tiempo real
- Tipos de evento más frecuentes
- Distribución geográfica

### 3. Searches Guardados

#### Eventos Críticos
```json
{
  "query": {
    "bool": {
      "should": [
        {"term": {"type.keyword": "ACCIDENT"}},
        {"term": {"type.keyword": "ROAD_CLOSED"}},
        {"term": {"subtype.keyword": "ACCIDENT_MAJOR"}}
      ]
    }
  }
}
```

#### Comparación Temporal
```json
{
  "query": {
    "range": {
      "pubTimestamp": {
        "gte": "now-1h",
        "lte": "now"
      }
    }
  },
  "aggs": {
    "by_index": {
      "terms": {"field": "_index"},
      "aggs": {
        "timeline": {
          "date_histogram": {
            "field": "pubTimestamp",
            "calendar_interval": "5m"
          }
        }
      }
    }
  }
}
```

## Monitoreo y Alertas

### 1. KPIs del Pipeline

#### Throughput
- Eventos/minuto ingresados por scraper
- Ratio de exportación raw (raw_events/mongo_events)
- Ratio de procesamiento (processed_events/raw_events)

#### Latencia
- Tiempo desde ingesta hasta raw export
- Tiempo desde raw hasta processed
- Tiempo de respuesta del cache

#### Calidad de Datos
- Eventos con coordenadas válidas
- Eventos con timestamps válidos
- Distribución geográfica esperada

### 2. Alertas Recomendadas

#### Alertas de Sistema
- Pipeline detenido (no nuevos eventos en 10 min)
- Cache hit ratio < 30%
- Elasticsearch storage > 80%
- MongoDB connections > límite

#### Alertas de Negocio
- Eventos críticos (accidentes) > threshold
- Cambio significativo en distribución geográfica
- Tipos de evento no reconocidos

## Troubleshooting

### Problemas Comunes

#### No hay datos en índices
1. Verificar scraper: `docker-compose logs waze-scraper`
2. Verificar MongoDB: acceder via mongo-express
3. Verificar exporters: `docker-compose logs raw-exporter pig`

#### Cache no funciona
1. Verificar Redis: `docker exec redis redis-cli ping`
2. Verificar query-cache: `curl http://localhost:9200/health`
3. Revisar logs: `docker-compose logs query-cache`

#### Kibana no muestra datos
1. Verificar index patterns están creados
2. Verificar time range en Discover
3. Verificar conectividad a query-cache

### Comandos de Debugging

```bash
# Ver logs en tiempo real
docker-compose logs -f [servicio]

# Ver estado de todos los contenedores
docker-compose ps

# Reiniciar servicio específico
docker-compose restart [servicio]

# Ver uso de recursos
docker stats

# Acceso directo a contenedor
docker exec -it [contenedor] /bin/bash

# Test de conectividad
curl -v http://localhost:[puerto]/[endpoint]
```

## Optimización

### 1. Performance del Cache

- TTL actual: 10 segundos
- Para aumentar: modificar `CACHE_TTL` en query-cache service
- Para consultas complejas, considerar TTL más largo

### 2. Elasticsearch

- Aumentar heap size si hay muchos datos
- Configurar índice templates para optimizar mapping
- Implementar ILM (Index Lifecycle Management)

### 3. Pipeline

- Ajustar frecuencia de scraping según necesidades
- Optimizar filtros PIG para reducir procesamiento
- Implementar particionado por fecha en índices

Este archivo proporciona una guía completa para usar y monitorear el pipeline de eventos Waze.
