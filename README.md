# Sistema de Procesamiento de Eventos de Tráfico Waze

## Descripción General

Este proyecto despliega un pipeline de procesamiento de eventos de tráfico extraídos de la API de Waze para la zona de Santiago, Chile. El sistema consta de los siguientes componentes:

1. **Scraper**: Obtiene eventos de tráfico en tiempo real de la API de Waze y los almacena en MongoDB
2. **MongoDB**: Base de datos NoSQL que almacena los eventos capturados del scraper
3. **MongoDB-ES Connector**: Sincroniza datos brutos desde MongoDB hacia Elasticsearch
4. **PIG**: Servicio de filtrado y procesamiento de datos desde MongoDB hacia Elasticsearch
5. **Elasticsearch**: Motor de búsqueda con dos índices: `waze_bruto` (datos sin procesar) y `waze_procesados` (datos filtrados)
6. **Redis**: Sistema de caché para optimizar consultas
7. **Kibana**: Interfaz web para visualización y análisis comparativo de datos brutos vs procesados

## Instrucciones de Arranque

### Requisitos Previos
- Docker y Docker Compose instalados
- Mínimo 4GB de RAM disponible

### Iniciar el Sistema
1. Clonar o descargar el repositorio
2. Ejecutar desde la raíz del proyecto:

```bash
# Construir e iniciar todos los servicios
docker-compose up -d --build

# Verificar que los servicios estén corriendo
docker-compose ps
```

### Acceso a los Servicios
- **Kibana** → http://localhost:5601 (Visualización de datos)
- **Mongo Express** → http://localhost:8081 (Administrador de MongoDB)
- **Redis Commander** → http://localhost:8082 (Administrador de Redis)
- **Elasticsearch** → http://localhost:9200 (API REST)

**Nota**: Elasticsearch puede tardar 30-60 segundos en inicializar completamente.

## Detener el Sistema

```bash
# Detener todos los servicios
docker-compose down

# Detener y eliminar volúmenes (limpieza completa)
docker-compose down --volumes
```

## Troubleshooting

### Problemas Comunes

**Elasticsearch no inicia**:
- Verificar que hay suficiente memoria disponible (>4GB)
- Esperar hasta 60 segundos para la inicialización completa

**Sin datos en los servicios**:
- Verificar logs del scraper: `docker-compose logs waze-scraper`
- Verificar conectividad a MongoDB: acceder a http://localhost:8081

**Servicios no responden**:
- Verificar estado: `docker-compose ps`
- Reiniciar servicios: `docker-compose restart [nombre-servicio]`
- Ver logs: `docker-compose logs [nombre-servicio]`

**Problemas de red**:
- Verificar que los puertos 5601, 8081, 8082, 9200 estén disponibles
- Reiniciar Docker si es necesario

### Comandos Útiles

```bash
# Ver logs en tiempo real
docker-compose logs -f [nombre-servicio]

# Reiniciar un servicio específico
docker-compose restart [nombre-servicio]

# Ver estado de recursos
docker stats

# Limpiar sistema completo
docker-compose down --volumes --remove-orphans
docker system prune -a
```




    
