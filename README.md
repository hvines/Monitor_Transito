# Sistema de Procesamiento de Eventos de Tráfico Waze

## Descripción General

Este proyecto despliega un procesamiento de eventos de tráfico extraídos de la API de Waze para la zona de Santiago, Chile. El sistema consta de los siguientes componentes:

1. **Scraper**: Obtiene eventos de tráfico en tiempo real de la API de Waze y los almacena en MongoDB
2. **MongoDB**: Base de datos NoSQL que almacena los eventos capturados del scraper
3. **Mongo-Elastic-Puente**: Sincroniza datos brutos desde MongoDB hacia Elasticsearch
4. **PIG**: Servicio de filtrado y procesamiento de datos desde MongoDB hacia Elasticsearch
5. **Elasticsearch**: Motor de búsqueda con dos índices: `waze_bruto` (datos sin procesar) y `waze_procesados` (datos filtrados)
6. **Redis**: Sistema de caché para optimizar consultas
7. **Kibana**: Interfaz web para visualización y análisis comparativo de datos brutos vs procesados

## Instrucciones de Arranque

### Iniciar el Sistema
1. Descargar el repositorio
2. Ejecutar desde la raíz del proyecto:

```bash

docker-compose up -d --build

docker-compose ps
```

### Acceso a los Servicios
- **Kibana** → http://localhost:5601 (Visualización de datos)
- **Mongo Express** → http://localhost:8081 (Administrador de MongoDB)
- **Redis Commander** → http://localhost:8082 (Administrador de Redis)


**Nota**: Elasticsearch tarda 30 segundos en inicializar completamente.

## Detener el Sistema

```bash
docker-compose down

docker-compose down --volumes
docker-compose down --volumes --remove-orphans
```



    
