# Tarea 3

# Descripción general

Este proyecto despliega, mediante Docker Compose, un flujo de procesamiento de eventos de tráfico extraídos de la API de Waze:
1.	Scraper: obtiene los últimos eventos de la zona de Santiago cada segundo y los almacena en MongoDB.
2.	MongoDB: base de datos NoSQL que almacena dichos eventos para luego pasar a su sistema de caché.
3.	Caché (Redis): almacena el último lote de eventos durante 10 segundos para consultas rápidas.
4.	Generador de tráfico: simula llegadas de eventos con dos distribuciones (determinista y Poisson).
5.	Apache PIG: filtrado y procesamiento de datos.
6.	Elasticsearch: motor de búsqueda y análisis para indexar eventos procesados.
7.	Kibana: interfaz web para visualización y análisis de datos en Elasticsearch.
8.	Visores para administración: mongo-express en el puerto 8081 y redis-commander en el 8082.


Cabe mencionar que el presente fue diseñado con vibe coding en un sistema con macOS 14.4.3.


# Instrucciones de arranque
1.	Clonar o descargar el repositorio.	
2.	Ejecutar:

    ```powershell
    
	docker-compose down --volumes  # limpia datos previos
	docker-compose up -d          # construye y arranca todos los servicios

    ```


3.	Verificar servicios corriendo:

    ```powershell

	docker-compose ps
	
 	```
 
4.	Acceder a los visores y servicios:

   
	Mongo Express → http://localhost:8081
	Redis Commander → http://localhost:8082
	Kibana → http://localhost:5601


5.	Tipos de consultas para Apache Pig

   	- Filtro de incidentes por comuna
    ```powershell

	docker exec -it pig_ds python3 /scripts/filter_by_comuna.py --list #para mostrar todas las comunas disponibles
    	docker exec -it pig_ds python3 /scripts/filter_by_comuna.py [nombre comuna]
	
 	```

   	- Filtro por intervalo de tiempo (AÑO-DIA-MES y hora, respectivamente) de eventos
    ```powershell
		
	docker exec -it pig_ds python3 /scripts/filter_by_time.py '2025-06-07 00:00:00' '2025-06-07 23:59:59'
	
 	```

   	- Filtro por tipo de evento			
    ```powershell

	docker exec -it pig_ds python3 /scripts/filter_by_type.py --list #reviso todos los eventos disponibles
    	docker exec -it pig_ds python3 /scripts/filter_by_type.py --all #todos los eventos ordenados por tipo
    	docker exec -it pig_ds python3 /scripts/filter_by_type.py JAM #ejemplo, selecciono el necesario
	
 	```

   	- Filtro por analisis de frecuencia	
    ```powershell

	docker exec -it pig_ds python3 /scripts/frequency_analysis.py #analisis general
   	docker exec -it pig_ds python3 /scripts/frequency_analysis.py JAM #por tipo de evento

	
 	```

6.	Exportación de datos a Elasticsearch

   	- Exportar eventos procesados de MongoDB a Elasticsearch
    ```powershell

	docker exec -it pig_ds python3 /scripts/export_to_elasticsearch.py
	
 	```

7.	Análisis y visualización

   	- Acceder a Kibana → http://localhost:5601
   	- Crear index patterns para visualizar los datos
   	- Generar dashboards y visualizaciones personalizadas




    
