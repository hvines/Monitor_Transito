FROM docker.elastic.co/elasticsearch/elasticsearch:8.11.0

# Configuración básica para desarrollo
ENV discovery.type=single-node
ENV xpack.security.enabled=false
ENV xpack.security.enrollment.enabled=false
ENV xpack.security.http.ssl.enabled=false
ENV xpack.security.transport.ssl.enabled=false
ENV cluster.name=waze-cluster
ENV node.name=waze-node
ENV bootstrap.memory_lock=true
ENV ES_JAVA_OPTS="-Xms512m -Xmx512m"

EXPOSE 9200 9300

# Crear script de inicialización directamente en el Dockerfile
USER root
RUN echo '#!/bin/bash' > /usr/local/bin/init-elasticsearch.sh && \
    echo 'set -e' >> /usr/local/bin/init-elasticsearch.sh && \
    echo '' >> /usr/local/bin/init-elasticsearch.sh && \
    echo 'echo "Iniciando Elasticsearch para proyecto Waze..."' >> /usr/local/bin/init-elasticsearch.sh && \
    echo '' >> /usr/local/bin/init-elasticsearch.sh && \
    echo '# Configurar permisos' >> /usr/local/bin/init-elasticsearch.sh && \
    echo 'chown -R elasticsearch:elasticsearch /usr/share/elasticsearch/data' >> /usr/local/bin/init-elasticsearch.sh && \
    echo '' >> /usr/local/bin/init-elasticsearch.sh && \
    echo '# Iniciar Elasticsearch' >> /usr/local/bin/init-elasticsearch.sh && \
    echo 'exec /usr/local/bin/docker-entrypoint.sh elasticsearch' >> /usr/local/bin/init-elasticsearch.sh && \
    chmod +x /usr/local/bin/init-elasticsearch.sh

USER elasticsearch

ENTRYPOINT ["/usr/local/bin/init-elasticsearch.sh"]
