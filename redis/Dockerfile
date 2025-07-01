# Redis Service - Simplified
FROM redis:7.0-alpine

# Instalar curl para health checks
RUN apk add --no-cache curl

# Copiar configuración de Redis
COPY redis.conf /usr/local/etc/redis/redis.conf

# Exponer puerto estándar de Redis
EXPOSE 6379

# Health check simple
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD redis-cli ping || exit 1

# Comando por defecto
CMD ["redis-server", "/usr/local/etc/redis/redis.conf"]
