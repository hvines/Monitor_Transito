FROM docker.elastic.co/kibana/kibana:8.11.0

# Configuración para conectar con Elasticsearch
ENV ELASTICSEARCH_HOSTS=http://elasticsearch:9200
ENV ELASTICSEARCH_USERNAME=""
ENV ELASTICSEARCH_PASSWORD=""
ENV XPACK_SECURITY_ENABLED=false
ENV XPACK_ENCRYPTEDSAVEDOBJECTS_ENCRYPTIONKEY="a7a6311933d3503b89bc2dbc36572c33a6c10925682e591bffcab6911c06786d"

# Configurar Kibana
COPY kibana.yml /usr/share/kibana/config/

# Crear script de inicialización directamente en el Dockerfile
USER root
RUN echo '#!/bin/bash' > /usr/local/bin/init-kibana.sh && \
    echo 'set -e' >> /usr/local/bin/init-kibana.sh && \
    echo '' >> /usr/local/bin/init-kibana.sh && \
    echo 'echo "📊 Iniciando Kibana para proyecto Waze..."' >> /usr/local/bin/init-kibana.sh && \
    echo '' >> /usr/local/bin/init-kibana.sh && \
    echo '# Esperar a que Elasticsearch esté disponible' >> /usr/local/bin/init-kibana.sh && \
    echo 'echo "⏳ Esperando Elasticsearch..."' >> /usr/local/bin/init-kibana.sh && \
    echo 'until curl -s http://elasticsearch:9200/_cluster/health > /dev/null; do' >> /usr/local/bin/init-kibana.sh && \
    echo '    echo "Esperando Elasticsearch..."' >> /usr/local/bin/init-kibana.sh && \
    echo '    sleep 5' >> /usr/local/bin/init-kibana.sh && \
    echo 'done' >> /usr/local/bin/init-kibana.sh && \
    echo '' >> /usr/local/bin/init-kibana.sh && \
    echo 'echo "✅ Elasticsearch disponible, iniciando Kibana..."' >> /usr/local/bin/init-kibana.sh && \
    echo '' >> /usr/local/bin/init-kibana.sh && \
    echo '# Iniciar Kibana' >> /usr/local/bin/init-kibana.sh && \
    echo 'exec /usr/local/bin/kibana-docker' >> /usr/local/bin/init-kibana.sh && \
    chmod +x /usr/local/bin/init-kibana.sh

USER kibana

EXPOSE 5601

ENTRYPOINT ["/usr/local/bin/init-kibana.sh"]
