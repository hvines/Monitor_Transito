# Reorganización del Proyecto - Resumen de Cambios

## ✅ Cambios Completados

### 🗂️ Estructura Final del Proyecto
```
Sistemas-Distribuidos/
├── 📄 README.md                  # Documentación simplificada
├── 📄 docker-compose.yml         # Configuración de servicios actualizada
├── 🗂️ scraper/                   # Servicio scraper (sin cambios)
├── 🗂️ pig/                       # Servicio procesamiento reorganizado
│   ├── 📄 data_inspector.py      # NUEVO: Inspector de datos MongoDB
│   ├── 📄 waze-processed-events.py # RENOMBRADO: procesador principal
│   ├── 📄 requirements.txt       # Dependencias Python
│   └── 🗂️ scripts/               # Solo filter_homogenize.pig
├── 🗂️ redis/                     # Servicio combinado Redis + Consultas Cache
│   ├── 📄 consultas_cache.py     # RENOMBRADO: servicio de caché
│   ├── 📄 requirements.txt       # Dependencias Python
│   └── 📄 Dockerfile             # MODIFICADO: Redis + Python
├── 🗂️ elasticsearch/             # Configuración Elasticsearch
├── 🗂️ kibana/                    # Configuración Kibana (actualizada)
└── 🗂️ mongodb/                   # Configuración MongoDB
```

### 🗑️ Archivos Eliminados
- ❌ `manage.sh` y `test_pipeline.sh` (scripts eliminados)
- ❌ `QUERIES_GUIDE.md`, `ARCHITECTURE.md`, `PIPELINE_SUMMARY.md` (documentación extra)
- ❌ `raw-exporter/` (directorio completo eliminado)
- ❌ `query-cache/` (contenido movido a redis/)
- ❌ Scripts PIG: `filter_by_comuna.py`, `filter_by_time.py`, `filter_by_type.py`, etc.

## 🔧 Cambios Principales

### 1. **README.md Simplificado**
- ✅ Solo instrucciones de arranque básicas
- ✅ Descripción general del proyecto
- ✅ Troubleshooting básico
- ❌ Eliminada documentación técnica extensa

### 2. **PIG Reorganizado**
- ✅ **data_inspector.py**: NUEVO script para mostrar todos los parámetros de MongoDB
- ✅ **waze-processed-events.py**: Renombrado desde `pig_auto_processor.py`
- ✅ **Configuración de filtros**: Lista `FIELDS_TO_KEEP` comentada para fácil selección
- ❌ Eliminados scripts individuales de filtrado (serán hechos en Elasticsearch/Kibana)

### 3. **Redis + Consultas Cache Combinados**
- ✅ **Servicio unificado**: Redis server + consultas cache en un solo contenedor
- ✅ **consultas_cache.py**: Renombrado desde `app.py`
- ✅ **Dockerfile actualizado**: Supervisor para manejar ambos servicios
- ✅ **Puertos expuestos**: 6379 (Redis) + 9201 (Cache service)

### 4. **Docker Compose Actualizado**
- ✅ **Servicios actuales**: scraper, mongodb, pig, redis (con cache), elasticsearch, kibana
- ❌ **Eliminado**: raw-exporter, query-cache separado
- ✅ **Dependencias corregidas**: Kibana → consultas_cache:9201

## 📊 Flujo Simplificado Actual

```
Waze API → Scraper → MongoDB → PIG (filtros) → Elasticsearch → Consultas Cache → Kibana
                                ↓                               ↑
                        Solo datos filtrados            Redis Cache (TTL: 10s)
```

## 🎯 Características del Sistema Reorganizado

### **Data Inspector (PIG)**
- 📊 Muestra TODOS los parámetros disponibles en MongoDB
- 🔧 Lista configurable `FIELDS_TO_KEEP` para filtrar campos
- 💡 Comentarios explicativos para fácil selección
- 🎛️ Agrupación por categorías (Core, Ubicación, Temporal, etc.)

### **Waze Processed Events**
- 🔄 Procesamiento automático desde MongoDB
- ✂️ Filtrado por configuración de campos seleccionados
- 📤 Exportación directa a Elasticsearch
- 🏷️ Metadata de procesamiento agregada

### **Consultas Cache (dentro de Redis)**
- 🔗 Proxy transparente hacia Elasticsearch
- ⚡ Caché Redis integrado (TTL: 10s)
- 📈 Métricas de hit/miss automáticas
- 🖥️ Un solo contenedor para Redis + Cache service

## 🚀 Comandos de Uso Actualizados

### Iniciar el Sistema
```bash
# Limpiar y construir
docker-compose down --remove-orphans
docker-compose up -d --build

# Verificar estado
docker-compose ps
```

### Inspeccionar Datos MongoDB
```bash
# Ejecutar inspector de datos
docker exec -it pig-auto-processor python3 data_inspector.py

# Ver logs del procesador
docker-compose logs -f pig
```

### Verificar Cache
```bash
# Health check del cache
curl http://localhost:9201/health

# Ver logs del cache
docker exec consultas_cache tail -f /var/log/consultas_cache.out.log
```

### Acceso a Servicios
- **Kibana**: http://localhost:5601 (→ consultas_cache:9201 → elasticsearch:9200)
- **Mongo Express**: http://localhost:8081
- **Redis Commander**: http://localhost:8082
- **Consultas Cache**: http://localhost:9201
- **Elasticsearch directo**: http://localhost:9200

## 🛠️ Próximos Pasos

### 1. **Configurar Filtros PIG**
- Ejecutar `data_inspector.py` para ver parámetros disponibles
- Modificar `FIELDS_TO_KEEP` en `waze-processed-events.py`
- Comentar/descomentar campos según necesidades

### 2. **Verificar Funcionamiento**
- Iniciar sistema con `docker-compose up -d --build`
- Verificar ingesta: logs scraper + mongo-express
- Verificar procesamiento: logs pig + elasticsearch count
- Verificar cache: curl health check + redis-commander

### 3. **Desarrollo en Elasticsearch/Kibana**
- Los filtros por tipo de evento se harán en Kibana
- Crear visualizaciones y dashboards
- Configurar index patterns para datos procesados

## ⚠️ Notas Importantes

1. **El sistema ahora es más simple**: un solo flujo de datos sin duplicación
2. **El cache está integrado**: no hay servicios separados, todo en redis/
3. **Los filtros son configurables**: fácil modificar qué campos mantener
4. **La documentación es mínima**: solo lo esencial en README.md
5. **El filtrado por tipo se hará después**: en Elasticsearch/Kibana, no en PIG

---

**✅ La reorganización está completa y lista para continuar con Elasticsearch/Kibana.**
