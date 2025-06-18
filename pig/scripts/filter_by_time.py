import os
import csv
from pymongo import MongoClient
import sys
from datetime import datetime, timedelta
import re

def parse_timestamp(timestamp_str):
    """Función para parsear diferentes formatos de timestamp"""
    if not timestamp_str:
        return None
    
    # Formatos comunes de timestamp
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%d/%m/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M:%S"
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(str(timestamp_str), fmt)
        except ValueError:
            continue
    
    # Si no funciona ningún formato, tratar como timestamp unix
    try:
        timestamp_num = float(str(timestamp_str))
        if timestamp_num > 1000000000000:  # Timestamp en milisegundos
            timestamp_num = timestamp_num / 1000
        return datetime.fromtimestamp(timestamp_num)
    except (ValueError, OSError):
        return None

def filter_by_time_interval(start_time, end_time, event_type=None, city=None):
    """Función para filtrar eventos por intervalo de tiempo"""
    print(f"=== FILTRADO POR INTERVALO DE TIEMPO ===")
    print(f"Desde: {start_time}")
    print(f"Hasta: {end_time}")
    if event_type:
        print(f"Tipo: {event_type}")
    if city:
        print(f"Ciudad: {city}")
    
    mongo_uri = os.environ.get("MONGO_URI", "mongodb://root:example@mongodb:27017/?authSource=admin")
    db_name = os.environ.get("MONGO_DBNAME", "waze_alertas")
    coll_name = os.environ.get("MONGO_COLLNAME", "eventos")
    
    try:
        client = MongoClient(mongo_uri)
        db = client[db_name]
        collection = db[coll_name]
        
        # Verificar conexión total
        total_docs = collection.count_documents({})
        print(f"Total documentos en la colección: {total_docs}")
        
        if total_docs == 0:
            print("ADVERTENCIA: No hay documentos en la coleccion")
            return

        # Construir query
        query = {}
        
        # Filtro temporal - necesitamos buscar en diferentes formatos
        time_query = {
            "$or": [
                {"timestamp": {"$gte": start_time, "$lte": end_time}},
                {"timestamp": {"$gte": start_time.isoformat(), "$lte": end_time.isoformat()}},
                {"timestamp": {"$gte": str(start_time), "$lte": str(end_time)}}
            ]
        }
        query.update(time_query)
        
        # Filtros adicionales
        if event_type:
            query["type"] = {"$regex": f"^{event_type}$", "$options": "i"}
        
        if city:
            query["city"] = {"$regex": city, "$options": "i"}
        
        print(f"Query construido: {query}")
        
        # Contar documentos que coinciden
        matching_docs = collection.count_documents(query)
        print(f"Documentos encontrados en el intervalo: {matching_docs}")
        
        if matching_docs == 0:
            print("ADVERTENCIA: No se encontraron eventos en el intervalo especificado")
            
            # Mostrar algunos timestamps de ejemplo para debugging
            sample_docs = collection.find({}, {"timestamp": 1}).limit(5)
            print("Ejemplos de timestamps en la base de datos:")
            for doc in sample_docs:
                timestamp = doc.get('timestamp', 'Sin timestamp')
                print(f"  - {timestamp} (tipo: {type(timestamp)})")
            return

        # Crear nombre de archivo
        start_str = start_time.strftime("%Y%m%d_%H%M")
        end_str = end_time.strftime("%Y%m%d_%H%M")
        filename = f"eventos_{start_str}_a_{end_str}"
        
        if event_type:
            filename += f"_tipo_{event_type.lower()}"
        if city:
            filename += f"_ciudad_{city.lower().replace(' ', '_')}"
        
        output_path = f"/scripts/{filename}.csv"
        
        print(f"Exportando a: {output_path}")
        
        with open(output_path, mode="w", newline="", encoding="utf-8") as csvfile:
            fieldnames = ["uuid", "type", "city", "location", "timestamp", "description", "parsed_timestamp"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            cursor = collection.find(query).sort("timestamp", 1)
            count = 0
            
            for doc in cursor:
                # Parsear timestamp para verificación
                timestamp_str = doc.get("timestamp", "")
                parsed_ts = parse_timestamp(timestamp_str)
                
                row = {
                    "uuid": doc.get("uuid", ""),
                    "type": doc.get("type", ""), 
                    "city": str(doc.get("city", "")),
                    "location": str(doc.get("location", "")),
                    "timestamp": str(timestamp_str),
                    "description": str(doc.get("description", "")),
                    "parsed_timestamp": str(parsed_ts) if parsed_ts else ""
                }
                writer.writerow(row)
                count += 1
                
                # Mostrar progreso cada 50 registros
                if count % 50 == 0:
                    print(f"  Procesados: {count} eventos...")

        print(f"CSV exportado exitosamente: {output_path}")
        print(f"Total eventos filtrados: {count}")
        
        # Mostrar estadísticas del intervalo
        print(f"\n=== ESTADÍSTICAS DEL INTERVALO ===")
        
        # Análisis por tipo en el intervalo
        type_pipeline = [
            {"$match": query},
            {"$group": {"_id": "$type", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        
        type_results = list(collection.aggregate(type_pipeline))
        
        print("Tipos de eventos en el intervalo:")
        for result in type_results:
            event_type_found = result["_id"]
            count_found = result["count"]
            percentage = (count_found / matching_docs) * 100
            print(f"  - {event_type_found}: {count_found} eventos ({percentage:.1f}%)")
        
        return count
        
    except Exception as e:
        print(f"ERROR: {e}")
        return 0

def show_time_range():
    """Función para mostrar el rango de tiempo de todos los eventos"""
    print("=== RANGO TEMPORAL DE EVENTOS ===")
    
    mongo_uri = os.environ.get("MONGO_URI", "mongodb://root:example@mongodb:27017/?authSource=admin")
    db_name = os.environ.get("MONGO_DBNAME", "waze_alertas")
    coll_name = os.environ.get("MONGO_COLLNAME", "eventos")
    
    try:
        client = MongoClient(mongo_uri)
        db = client[db_name]
        collection = db[coll_name]
        
        # Obtener algunos timestamps para analizar el formato
        sample_docs = list(collection.find({}, {"timestamp": 1}).limit(10))
        
        print("Muestra de timestamps en la base de datos:")
        timestamps = []
        for i, doc in enumerate(sample_docs, 1):
            timestamp = doc.get('timestamp', 'Sin timestamp')
            parsed = parse_timestamp(timestamp)
            timestamps.append(parsed)
            print(f"  {i}. Original: {timestamp}")
            print(f"     Parseado: {parsed}")
            print()
        
        # Filtrar timestamps válidos
        valid_timestamps = [ts for ts in timestamps if ts is not None]
        
        if valid_timestamps:
            min_time = min(valid_timestamps)
            max_time = max(valid_timestamps)
            
            print(f"RANGO TEMPORAL DETECTADO:")
            print(f"  Evento más antiguo: {min_time}")
            print(f"  Evento más reciente: {max_time}")
            print(f"  Duración total: {max_time - min_time}")
            
            # Sugerir algunos intervalos de ejemplo
            print(f"\nEJEMPLOS DE INTERVALOS PARA FILTRAR:")
            print(f"  1 hora desde el primer evento:")
            print(f"    python3 filter_by_time.py '{min_time}' '{min_time + timedelta(hours=1)}'")
            print(f"  1 día desde el primer evento:")
            print(f"    python3 filter_by_time.py '{min_time}' '{min_time + timedelta(days=1)}'")
        else:
            print("ADVERTENCIA: No se pudieron parsear los timestamps")
        
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("Uso:")
        print("  python3 filter_by_time.py --range                                    # Ver rango temporal")
        print("  python3 filter_by_time.py 'YYYY-MM-DD HH:MM:SS' 'YYYY-MM-DD HH:MM:SS'    # Filtrar por intervalo")
        print("  python3 filter_by_time.py 'YYYY-MM-DD HH:MM:SS' 'YYYY-MM-DD HH:MM:SS' JAM # Con tipo específico")
        print("  python3 filter_by_time.py 'YYYY-MM-DD HH:MM:SS' 'YYYY-MM-DD HH:MM:SS' JAM Santiago # Con tipo y ciudad")
        print("")
        print("Ejemplos:")
        print("  python3 filter_by_time.py '2024-01-01 00:00:00' '2024-01-01 23:59:59'")
        print("  python3 filter_by_time.py '2024-01-01 08:00:00' '2024-01-01 18:00:00' JAM")
        
        # Mostrar rango por defecto
        show_time_range()
    
    elif sys.argv[1] == "--range":
        show_time_range()
    
    elif len(sys.argv) >= 3:
        try:
            start_time = datetime.strptime(sys.argv[1], "%Y-%m-%d %H:%M:%S")
            end_time = datetime.strptime(sys.argv[2], "%Y-%m-%d %H:%M:%S")
            
            event_type = sys.argv[3] if len(sys.argv) > 3 else None
            city = sys.argv[4] if len(sys.argv) > 4 else None
            
            filter_by_time_interval(start_time, end_time, event_type, city)
            
        except ValueError as e:
            print(f"ERROR en formato de fecha: {e}")
            print("Formato requerido: 'YYYY-MM-DD HH:MM:SS'")
    
    else:
        print("ERROR: Parametros insuficientes")
        print("Usa --help para ver ejemplos de uso")