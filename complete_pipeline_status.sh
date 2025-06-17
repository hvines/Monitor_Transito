#!/bin/bash

echo "======================================="
echo "🚀 SISTEMA DE ANÁLISIS DE TRÁFICO WAZE"
echo "======================================="
echo
echo "📊 ESTADO DE SERVICIOS:"
echo "-------------------------"

# Check all containers
echo "🐳 Contenedores Docker:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "(elasticsearch|kibana|logstash|pig|waze-scraper|traffic|mongo|redis)"

echo
echo "📊 ESTADÍSTICAS DEL PIPELINE:"
echo "-----------------------------"

# Scraper statistics
echo "🤖 Scraper (Puerto 5001):"
curl -s http://localhost:5001/stats 2>/dev/null | head -3 || echo "  ❌ Scraper no disponible"

echo

# MongoDB statistics
echo "📦 MongoDB:"
MONGO_COUNT=$(docker exec sistemas-distribuidos-1-mongodb-1 mongosh --quiet --eval "db.getSiblingDB('waze_alertas').eventos.countDocuments({})" 2>/dev/null)
echo "  📄 Documentos: $MONGO_COUNT"

# Redis statistics
echo "🔄 Redis Cache:"
REDIS_LATEST=$(docker exec sistemas-distribuidos-1-redis-1 redis-cli EXISTS latest_alerts 2>/dev/null)
REDIS_RECENT=$(docker exec sistemas-distribuidos-1-redis-1 redis-cli EXISTS recent_alerts 2>/dev/null)
echo "  🗂️  latest_alerts: $([ "$REDIS_LATEST" = "1" ] && echo "✅ Disponible" || echo "❌ No disponible")"
echo "  🗂️  recent_alerts: $([ "$REDIS_RECENT" = "1" ] && echo "✅ Disponible" || echo "❌ No disponible")"

# Elasticsearch statistics
echo "🔍 Elasticsearch:"
ES_HEALTH=$(curl -s http://localhost:9200/_cluster/health | python3 -c "import sys, json; data = json.load(sys.stdin); print(data['status'])" 2>/dev/null)
ES_COUNT=$(curl -s "http://localhost:9200/waze-events-*/_count" | python3 -c "import sys, json; data = json.load(sys.stdin); print(data['count'])" 2>/dev/null)
echo "  🔍 Estado: $ES_HEALTH"
echo "  📄 Documentos: $ES_COUNT"

# Kibana status
echo "📈 Kibana:"
KIBANA_STATUS=$(curl -s http://localhost:5601/api/status | python3 -c "import sys, json; data = json.load(sys.stdin); print(data['status']['overall']['level'])" 2>/dev/null)
echo "  📊 Estado: $KIBANA_STATUS"

echo
echo "🌐 ACCESO A SERVICIOS:"
echo "----------------------"
echo "📊 Kibana Dashboard:     http://localhost:5601"
echo "🔍 Elasticsearch API:    http://localhost:9200"
echo "📦 MongoDB Express:      http://localhost:8081"
echo "🔄 Redis Commander:      http://localhost:8082"
echo "🤖 Scraper API:          http://localhost:5001"
echo "  └─ Health:             http://localhost:5001/health"
echo "  └─ Stats:              http://localhost:5001/stats"
echo "  └─ Manual Ingest:      http://localhost:5001/ingest"

echo
echo "⚙️  COMANDOS ÚTILES:"
echo "-------------------"
echo "🔄 Exportar datos a Elasticsearch:"
echo "   docker exec pig_ds python3 /scripts/export_to_elasticsearch.py"
echo
echo "📊 Análisis con Pig:"
echo "   docker exec pig_ds python3 /scripts/filter_by_type.py"
echo "   docker exec pig_ds python3 /scripts/frequency_analysis.py"
echo
echo "🔍 Consultar Elasticsearch:"
echo "   curl -X GET \"localhost:9200/waze-events-*/_search?size=5&pretty\""
echo
echo "📦 Consultar MongoDB:"
echo "   docker exec sistemas-distribuidos-1-mongodb-1 mongosh --eval \"db.getSiblingDB('waze_alertas').eventos.find().limit(5)\""

echo
echo "✅ Pipeline completo operativo. ¡Comienza tu análisis!"
echo "📊 Abre Kibana en http://localhost:5601 para crear dashboards"
echo
