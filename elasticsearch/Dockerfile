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

USER root
COPY init-elasticsearch.sh /usr/local/bin/init-elasticsearch.sh
RUN chmod +x /usr/local/bin/init-elasticsearch.sh

USER elasticsearch

ENTRYPOINT ["/usr/local/bin/init-elasticsearch.sh"]
