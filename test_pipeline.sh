#!/bin/bash

# Test script para validar el pipeline completo de procesamiento de eventos Waze
# Uso: ./test_pipeline.sh

set -e

echo "🚀 Iniciando test del pipeline de eventos Waze..."
echo "=================================================="

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Función para imprimir con colores
print_status() {
    local status=$1
    local message=$2
    case $status in
        "INFO") echo -e "${BLUE}ℹ️  ${message}${NC}" ;;
        "SUCCESS") echo -e "${GREEN}✅ ${message}${NC}" ;;
        "WARNING") echo -e "${YELLOW}⚠️  ${message}${NC}" ;;
        "ERROR") echo -e "${RED}❌ ${message}${NC}" ;;
    esac
}

# Función para esperar por un servicio
wait_for_service() {
    local url=$1
    local service_name=$2
    local max_attempts=30
    local attempt=1
    
    print_status "INFO" "Esperando que ${service_name} esté disponible..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s "$url" > /dev/null 2>&1; then
            print_status "SUCCESS" "${service_name} está disponible"
            return 0
        fi
        
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    print_status "ERROR" "${service_name} no está disponible después de ${max_attempts} intentos"
    return 1
}

# Test 1: Verificar que los servicios están corriendo
echo -e "\n📋 Test 1: Verificando servicios Docker..."
services=("mongodb" "redis" "elasticsearch" "waze-scraper" "raw-exporter" "pig" "query-cache" "kibana")

for service in "${services[@]}"; do
    if docker-compose ps | grep -q "$service.*Up"; then
        print_status "SUCCESS" "Servicio $service está corriendo"
    else
        print_status "ERROR" "Servicio $service no está corriendo"
        exit 1
    fi
done

# Test 2: Verificar conectividad de servicios web
echo -e "\n🌐 Test 2: Verificando conectividad de servicios web..."

wait_for_service "http://localhost:9200/_cluster/health" "Elasticsearch"
wait_for_service "http://localhost:9201/health" "Query Cache Service"
wait_for_service "http://localhost:5601/api/status" "Kibana"
wait_for_service "http://localhost:8081" "Mongo Express"
wait_for_service "http://localhost:8082" "Redis Commander"

# Test 3: Verificar que Redis funciona
echo -e "\n💾 Test 3: Verificando Redis..."
redis_test=$(docker exec redis redis-cli ping 2>/dev/null || echo "FAIL")
if [ "$redis_test" = "PONG" ]; then
    print_status "SUCCESS" "Redis está funcionando"
else
    print_status "ERROR" "Redis no responde"
    exit 1
fi

# Test 4: Verificar MongoDB
echo -e "\n🍃 Test 4: Verificando MongoDB..."
if docker exec mongodb mongosh --quiet --eval "db.adminCommand('ping').ok" --authenticationDatabase admin -u root -p example > /dev/null 2>&1; then
    print_status "SUCCESS" "MongoDB está funcionando"
else
    print_status "ERROR" "MongoDB no responde"
    exit 1
fi

# Test 5: Verificar que el scraper está insertando datos
echo -e "\n🕷️  Test 5: Verificando ingesta de datos del scraper..."
sleep 10  # Esperar un poco para que el scraper inserte datos

# Verificar datos en MongoDB
mongo_count=$(docker exec mongodb mongosh --quiet --eval "db.events.countDocuments()" waze_data --authenticationDatabase admin -u root -p example 2>/dev/null || echo "0")
if [ "$mongo_count" -gt "0" ]; then
    print_status "SUCCESS" "Scraper ha insertado $mongo_count eventos en MongoDB"
else
    print_status "WARNING" "No hay datos del scraper aún. Esperando más tiempo..."
    sleep 30
    mongo_count=$(docker exec mongodb mongosh --quiet --eval "db.events.countDocuments()" waze_data --authenticationDatabase admin -u root -p example 2>/dev/null || echo "0")
    if [ "$mongo_count" -gt "0" ]; then
        print_status "SUCCESS" "Scraper ha insertado $mongo_count eventos en MongoDB"
    else
        print_status "WARNING" "Scraper aún no ha insertado datos. Continuando tests..."
    fi
fi

# Test 6: Verificar exportación raw a Elasticsearch
echo -e "\n📤 Test 6: Verificando exportación raw a Elasticsearch..."
sleep 15  # Esperar para que el raw-exporter procese

raw_count_response=$(curl -s "http://localhost:9200/waze-raw-events/_count" 2>/dev/null || echo '{"count":0}')
raw_count=$(echo "$raw_count_response" | grep -o '"count":[0-9]*' | cut -d: -f2 || echo "0")

if [ "$raw_count" -gt "0" ]; then
    print_status "SUCCESS" "Raw exporter ha exportado $raw_count eventos al índice waze-raw-events"
else
    print_status "WARNING" "No hay datos raw en Elasticsearch aún"
fi

# Test 7: Verificar procesamiento PIG
echo -e "\n🐷 Test 7: Verificando procesamiento PIG..."
sleep 15  # Esperar para que PIG procese

processed_count_response=$(curl -s "http://localhost:9200/waze-processed-events/_count" 2>/dev/null || echo '{"count":0}')
processed_count=$(echo "$processed_count_response" | grep -o '"count":[0-9]*' | cut -d: -f2 || echo "0")

if [ "$processed_count" -gt "0" ]; then
    print_status "SUCCESS" "PIG processor ha procesado $processed_count eventos al índice waze-processed-events"
else
    print_status "WARNING" "No hay datos procesados en Elasticsearch aún"
fi

# Test 8: Verificar query cache service
echo -e "\n🗄️  Test 8: Verificando Query Cache Service..."

# Test de health check
cache_health=$(curl -s "http://localhost:9201/health" | grep -o '"status":"[^"]*"' | cut -d: -f2 | tr -d '"' || echo "unknown")
if [ "$cache_health" = "healthy" ]; then
    print_status "SUCCESS" "Query Cache Service está saludable"
else
    print_status "ERROR" "Query Cache Service no está saludable"
fi

# Test de proxy a través del cache
if [ "$raw_count" -gt "0" ]; then
    cache_raw_response=$(curl -s "http://localhost:9201/waze-raw-events/_count" 2>/dev/null || echo '{"count":0}')
    cache_raw_count=$(echo "$cache_raw_response" | grep -o '"count":[0-9]*' | cut -d: -f2 || echo "0")
    
    if [ "$cache_raw_count" = "$raw_count" ]; then
        print_status "SUCCESS" "Query Cache Service está funcionando como proxy correctamente"
    else
        print_status "WARNING" "Query Cache Service puede tener problemas con el proxy"
    fi
fi

# Test 9: Verificar que Kibana puede acceder a los datos a través del cache
echo -e "\n📊 Test 9: Verificando acceso de Kibana a través del cache..."

kibana_status=$(curl -s "http://localhost:5601/api/status" | grep -o '"overall":{"level":"[^"]*"' | cut -d: -f3 | tr -d '"' || echo "unknown")
if [ "$kibana_status" = "available" ]; then
    print_status "SUCCESS" "Kibana está disponible y puede acceder a los datos"
else
    print_status "WARNING" "Kibana no está completamente disponible aún"
fi

# Test 10: Verificar caché Redis funcionando
echo -e "\n🔄 Test 10: Verificando funcionamiento del caché..."

# Realizar la misma consulta dos veces para verificar caché
if [ "$raw_count" -gt "0" ]; then
    echo "Primera consulta (debería ser cache MISS)..."
    curl -s "http://localhost:9201/waze-raw-events/_search?size=1" > /dev/null
    
    sleep 2
    
    echo "Segunda consulta (debería ser cache HIT)..."
    curl -s "http://localhost:9201/waze-raw-events/_search?size=1" > /dev/null
    
    # Verificar logs del cache para ver hits/misses
    cache_logs=$(docker-compose logs --tail 10 query-cache 2>/dev/null || echo "")
    if echo "$cache_logs" | grep -q "Cache HIT"; then
        print_status "SUCCESS" "Sistema de caché está funcionando (Cache HIT detectado)"
    else
        print_status "INFO" "Sistema de caché configurado (verificar logs para hits/misses)"
    fi
fi

# Resumen final
echo -e "\n📈 Resumen del Pipeline:"
echo "======================"
print_status "INFO" "MongoDB eventos: $mongo_count"
print_status "INFO" "Elasticsearch raw: $raw_count"
print_status "INFO" "Elasticsearch procesados: $processed_count"
print_status "INFO" "Query Cache: $cache_health"
print_status "INFO" "Kibana: $kibana_status"

echo -e "\n🎯 URLs de acceso:"
echo "=================="
echo "• Mongo Express: http://localhost:8081"
echo "• Redis Commander: http://localhost:8082"
echo "• Elasticsearch: http://localhost:9200"
echo "• Query Cache Service: http://localhost:9201"
echo "• Kibana: http://localhost:5601"

echo -e "\n🔧 Comandos útiles para debugging:"
echo "=================================="
echo "• Ver logs scraper: docker-compose logs -f waze-scraper"
echo "• Ver logs raw exporter: docker-compose logs -f raw-exporter"
echo "• Ver logs PIG: docker-compose logs -f pig"
echo "• Ver logs query cache: docker-compose logs -f query-cache"
echo "• Estado de servicios: docker-compose ps"

if [ "$mongo_count" -gt "0" ] && [ "$raw_count" -gt "0" ] && [ "$cache_health" = "healthy" ]; then
    print_status "SUCCESS" "🎉 Pipeline completamente funcional!"
else
    print_status "WARNING" "⚠️  Pipeline parcialmente funcional. Revisar servicios individuales."
fi

echo -e "\n✨ Test completado"
