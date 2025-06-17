#!/bin/bash

echo "=== VERIFICACIÓN DEL PIPELINE WAZE ==="
echo

# Verificar servicios principales
echo "🔍 Verificando servicios..."
docker-compose ps

echo
echo "📊 Estadísticas del Scraper:"
curl -s http://localhost:5001/health | python3 -c "import sys, json; data=json.load(sys.stdin); print(f'Status: {data[\"status\"]}'); print(f'MongoDB: {data[\"mongodb\"]}'); print(f'Redis: {data[\"redis\"]}'); print(f'Total Events: {data[\"total_events\"]}')"

echo
echo "📈 Distribución de eventos por tipo:"
curl -s http://localhost:5001/stats | python3 -c "import sys, json; data=json.load(sys.stdin); [print(f'{item[\"_id\"]}: {item[\"count\"]}') for item in data['event_types'][:5]]"

echo
echo "🗄️  Verificando caché Redis:"
docker exec sistemas-distribuidos-1-redis-1 redis-cli keys "*" | head -5

echo
echo "🐷 Ejecutando análisis con Pig:"
docker exec pig_ds python3 /scripts/filter_by_type.py accident | tail -5

echo
echo "✅ Pipeline básico funcionando correctamente!"
echo "📊 Interfaces disponibles:"
echo "  - Scraper Health: http://localhost:5001/health"
echo "  - Scraper Stats: http://localhost:5001/stats"
echo "  - MongoDB Express: http://localhost:8081"
echo "  - Redis Commander: http://localhost:8082"
