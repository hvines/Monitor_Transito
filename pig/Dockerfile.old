# pig/Dockerfile

FROM ubuntu:20.04

# Evitar prompts interactivos durante la instalación
ENV DEBIAN_FRONTEND=noninteractive

# Instalar Java y dependencias
RUN apt-get update && \
    apt-get install -y openjdk-8-jdk python3 python3-pip wget curl && \
    apt-get clean

# Configurar JAVA_HOME
ENV JAVA_HOME=/usr/lib/jvm/java-8-openjdk-amd64
ENV PATH=$PATH:$JAVA_HOME/bin

# Instalar Apache Pig
RUN wget https://archive.apache.org/dist/pig/pig-0.17.0/pig-0.17.0.tar.gz && \
    tar -xzf pig-0.17.0.tar.gz && \
    mv pig-0.17.0 /opt/pig && \
    rm pig-0.17.0.tar.gz

# Configurar PIG_HOME
ENV PIG_HOME=/opt/pig
ENV PATH=$PATH:$PIG_HOME/bin

FROM openjdk:8-jdk-slim

# Instalar dependencias
RUN apt-get update && \
    apt-get install -y python3 python3-pip wget curl && \
    apt-get clean

# JAVA_HOME ya está configurado en esta imagen base
ENV JAVA_HOME=/usr/local/openjdk-8

# Instalar Apache Pig
RUN wget https://archive.apache.org/dist/pig/pig-0.17.0/pig-0.17.0.tar.gz && \
    tar -xzf pig-0.17.0.tar.gz && \
    mv pig-0.17.0 /opt/pig && \
    rm pig-0.17.0.tar.gz

ENV PIG_HOME=/opt/pig
ENV PATH=$PATH:$PIG_HOME/bin

# Instalar dependencias de Python
COPY requirements.txt /scripts/
RUN pip3 install -r /scripts/requirements.txt

# Crear directorios
RUN mkdir -p /data/raw /data/processed /scripts

# Copiar scripts
COPY scripts/ /scripts/

WORKDIR /scripts