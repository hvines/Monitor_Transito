#!/bin/bash

# Script de gestión para el pipeline de eventos Waze
# Uso: ./manage.sh [comando]

set -e

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Función para imprimir con colores
print_colored() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

print_header() {
    echo
    print_colored $BLUE "🚀 Pipeline de Eventos Waze - Sistema de Gestión"
    print_colored $BLUE "================================================="
    echo
}

print_usage() {
    print_header
    echo "Uso: $0 [comando]"
    echo
    echo "Comandos disponibles:"
    echo "  up          - Iniciar todos los servicios"
    echo "  down        - Detener todos los servicios"
    echo "  restart     - Reiniciar todos los servicios"
    echo "  status      - Mostrar estado de los servicios"
    echo "  logs        - Mostrar logs de todos los servicios"
    echo "  logs [srv]  - Mostrar logs de un servicio específico"
    echo "  clean       - Limpieza completa (contenedores, imágenes, volúmenes)"
    echo "  test        - Ejecutar tests del pipeline"
    echo "  build       - Reconstruir imágenes"
    echo "  urls        - Mostrar URLs de acceso"
    echo "  help        - Mostrar esta ayuda"
    echo
    echo "Servicios disponibles para logs:"
    echo "  waze-scraper, raw-exporter, pig, query-cache, kibana,"
    echo "  elasticsearch, mongodb, redis"
    echo
}

check_dependencies() {
    if ! command -v docker &> /dev/null; then
        print_colored $RED "❌ Docker no está instalado"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        print_colored $RED "❌ Docker Compose no está instalado"
        exit 1
    fi
}

wait_for_services() {
    print_colored $YELLOW "⏳ Esperando que los servicios estén listos..."
    
    # Esperar a Elasticsearch
    echo -n "Esperando Elasticsearch"
    for i in {1..60}; do
        if curl -s http://localhost:9200/_cluster/health &>/dev/null; then
            echo " ✅"
            break
        fi
        echo -n "."
        sleep 2
    done
    
    # Esperar a Query Cache
    echo -n "Esperando Query Cache Service"
    for i in {1..30}; do
        if curl -s http://localhost:9201/health &>/dev/null; then
            echo " ✅"
            break
        fi
        echo -n "."
        sleep 2
    done
    
    # Esperar a Kibana
    echo -n "Esperando Kibana"
    for i in {1..60}; do
        if curl -s http://localhost:5601/api/status &>/dev/null; then
            echo " ✅"
            break
        fi
        echo -n "."
        sleep 2
    done
    
    print_colored $GREEN "✅ Servicios listos!"
}

cmd_up() {
    print_header
    print_colored $GREEN "🚀 Iniciando pipeline de eventos Waze..."
    
    # Detener servicios existentes
    docker-compose down --remove-orphans 2>/dev/null || true
    
    # Iniciar servicios
    print_colored $YELLOW "📦 Construyendo e iniciando servicios..."
    docker-compose up -d --build
    
    # Esperar que estén listos
    wait_for_services
    
    print_colored $GREEN "✅ Pipeline iniciado correctamente!"
    cmd_urls
}

cmd_down() {
    print_header
    print_colored $YELLOW "🛑 Deteniendo pipeline de eventos Waze..."
    
    docker-compose down --remove-orphans
    
    print_colored $GREEN "✅ Pipeline detenido"
}

cmd_restart() {
    print_header
    print_colored $YELLOW "🔄 Reiniciando pipeline de eventos Waze..."
    
    cmd_down
    sleep 2
    cmd_up
}

cmd_status() {
    print_header
    print_colored $BLUE "📊 Estado de los servicios:"
    echo
    
    docker-compose ps
    
    echo
    print_colored $BLUE "🔍 Health checks:"
    
    # Elasticsearch
    if curl -s http://localhost:9200/_cluster/health &>/dev/null; then
        health=$(curl -s http://localhost:9200/_cluster/health | grep -o '"status":"[^"]*"' | cut -d: -f2 | tr -d '"')
        print_colored $GREEN "✅ Elasticsearch: $health"
    else
        print_colored $RED "❌ Elasticsearch: No disponible"
    fi
    
    # Query Cache
    if curl -s http://localhost:9201/health &>/dev/null; then
        print_colored $GREEN "✅ Query Cache Service: Disponible"
    else
        print_colored $RED "❌ Query Cache Service: No disponible"
    fi
    
    # Kibana
    if curl -s http://localhost:5601/api/status &>/dev/null; then
        print_colored $GREEN "✅ Kibana: Disponible"
    else
        print_colored $RED "❌ Kibana: No disponible"
    fi
    
    # Redis
    if docker exec redis redis-cli ping &>/dev/null | grep -q PONG; then
        print_colored $GREEN "✅ Redis: Disponible"
    else
        print_colored $RED "❌ Redis: No disponible"
    fi
    
    # MongoDB
    if docker exec mongodb mongosh --quiet --eval "db.adminCommand('ping').ok" --authenticationDatabase admin -u root -p example &>/dev/null; then
        print_colored $GREEN "✅ MongoDB: Disponible"
    else
        print_colored $RED "❌ MongoDB: No disponible"
    fi
}

cmd_logs() {
    local service=$1
    
    if [ -z "$service" ]; then
        print_header
        print_colored $BLUE "📋 Logs de todos los servicios (Ctrl+C para salir):"
        echo
        docker-compose logs -f
    else
        print_header
        print_colored $BLUE "📋 Logs del servicio: $service (Ctrl+C para salir):"
        echo
        docker-compose logs -f "$service"
    fi
}

cmd_clean() {
    print_header
    print_colored $YELLOW "🧹 Limpieza completa del sistema..."
    
    echo "⚠️  Esta operación eliminará:"
    echo "   - Todos los contenedores del proyecto"
    echo "   - Todas las imágenes del proyecto"
    echo "   - Todos los volúmenes de datos"
    echo "   - Redes del proyecto"
    echo
    read -p "¿Estás seguro? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Detener y eliminar contenedores
        docker-compose down --remove-orphans --volumes
        
        # Eliminar imágenes del proyecto
        print_colored $YELLOW "🗑️  Eliminando imágenes..."
        docker images | grep -E "(pig|scraper|raw-exporter|query-cache)" | awk '{print $3}' | xargs -r docker rmi -f 2>/dev/null || true
        
        # Eliminar imágenes huérfanas
        docker image prune -f
        
        # Eliminar volúmenes huérfanos
        docker volume prune -f
        
        print_colored $GREEN "✅ Limpieza completa finalizada"
    else
        print_colored $YELLOW "❌ Limpieza cancelada"
    fi
}

cmd_build() {
    print_header
    print_colored $YELLOW "🔨 Reconstruyendo imágenes..."
    
    docker-compose build --no-cache
    
    print_colored $GREEN "✅ Imágenes reconstruidas"
}

cmd_test() {
    print_header
    print_colored $BLUE "🧪 Ejecutando tests del pipeline..."
    
    if [ ! -f "./test_pipeline.sh" ]; then
        print_colored $RED "❌ Script de test no encontrado"
        exit 1
    fi
    
    chmod +x ./test_pipeline.sh
    ./test_pipeline.sh
}

cmd_urls() {
    print_header
    print_colored $PURPLE "🌐 URLs de acceso al sistema:"
    echo
    echo "📊 Interfaces de usuario:"
    echo "   • Kibana (Visualización):     http://localhost:5601"
    echo "   • Mongo Express (MongoDB):    http://localhost:8081"
    echo "   • Redis Commander (Redis):    http://localhost:8082"
    echo
    echo "🔧 APIs y servicios:"
    echo "   • Elasticsearch (directo):    http://localhost:9200"
    echo "   • Query Cache Service:        http://localhost:9201"
    echo "   • Health check cache:         http://localhost:9201/health"
    echo
    echo "📈 Ejemplos de consultas:"
    echo "   • Raw events count:           curl http://localhost:9201/waze-raw-events/_count"
    echo "   • Processed events count:     curl http://localhost:9201/waze-processed-events/_count"
    echo "   • Pipeline health:            curl http://localhost:9201/health"
    echo
    echo "📖 Documentación adicional:"
    echo "   • Guía de consultas:          QUERIES_GUIDE.md"
    echo "   • Documentación técnica:      README.md"
    echo
}

# Verificar dependencias
check_dependencies

# Procesar comando
case "${1:-help}" in
    "up")
        cmd_up
        ;;
    "down")
        cmd_down
        ;;
    "restart")
        cmd_restart
        ;;
    "status")
        cmd_status
        ;;
    "logs")
        cmd_logs $2
        ;;
    "clean")
        cmd_clean
        ;;
    "build")
        cmd_build
        ;;
    "test")
        cmd_test
        ;;
    "urls")
        cmd_urls
        ;;
    "help"|*)
        print_usage
        ;;
esac
