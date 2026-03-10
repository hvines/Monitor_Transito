#!/bin/bash
set -e

echo "Iniciando Elasticsearch para proyecto Waze..."

# Iniciar Elasticsearch en background
/usr/local/bin/docker-entrypoint.sh elasticsearch &
ES_PID=$!

# Esperar a que Elasticsearch este disponible
echo "Esperando que Elasticsearch este listo..."
until curl -sf http://localhost:9200/_cluster/health > /dev/null 2>&1; do
    sleep 3
done
echo "Elasticsearch listo. Configurando templates para modo single-node..."

# Deshabilitar disk watermark (entorno de desarrollo - disco puede estar casi lleno)
curl -sf -X PUT "http://localhost:9200/_cluster/settings" \
  -H "Content-Type: application/json" \
  -d '{"persistent":{"cluster.routing.allocation.disk.threshold_enabled":false}}' \
  && echo "Disk watermark deshabilitado." \
  || echo "Advertencia: no se pudo deshabilitar disk watermark."

# Aplicar legacy index template para que todos los indices de Kibana
# se creen con replicas=0 (obligatorio en cluster single-node).
curl -sf -X PUT "http://localhost:9200/_template/kibana_single_node_template" \
  -H "Content-Type: application/json" \
  -d '{"index_patterns":["kibana*",".kibana*",".reporting*",".apm*",".fleet*",".security*",".siem*",".alerts*"],"settings":{"number_of_replicas":0}}' \
  && echo "Template Kibana configurado con replicas=0." \
  || echo "Advertencia: no se pudo aplicar template Kibana (puede que ya exista)."

wait $ES_PID
