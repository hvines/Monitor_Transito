import os
import csv
from pymongo import MongoClient
import sys

def filter_by_type(event_type):
    print(f"=== FILTRADO POR TIPO: {event_type} ===")
    
    # Variables de entorno
    mongo_uri = os.environ.get("MONGO_URI", "mongodb://root:example@mongodb:27017/?authSource=admin")
    db_name = os.environ.get("MONGO_DBNAME", "waze_alertas")
    coll_name = os.environ.get("MONGO_COLLNAME", "eventos")
    
    print(f"Conectando a MongoDB...")
    print(f"URI: {mongo_uri}")
    print(f"Database: {db_name}")
    print(f"Collection: {coll_name}")

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

        # Buscar por tipo (case insensitive)
        query = {"type": {"$regex": f"^{event_type}$", "$options": "i"}}
        
        # Contar documentos que coinciden
        matching_docs = collection.count_documents(query)
        print(f"Documentos de tipo '{event_type}': {matching_docs}")
        
        if matching_docs == 0:
            print(f"ADVERTENCIA: No se encontraron eventos de tipo '{event_type}'")
            # Mostrar algunos tipos de ejemplo
            sample_docs = collection.find({}, {"type": 1}).limit(10)
            print("Ejemplos de tipos en la base de datos:")
            types_found = set()
            for doc in sample_docs:
                event_type_found = doc.get('type', 'Sin tipo')
                if event_type_found not in types_found:
                    types_found.add(event_type_found)
                    print(f"  - {event_type_found}")
            return

        # Crear archivo CSV
        output_path = f"/scripts/eventos_tipo_{event_type.lower()}.csv"
        
        print(f"Exportando a: {output_path}")
        
        with open(output_path, mode="w", newline="", encoding="utf-8") as csvfile:
            fieldnames = ["uuid", "type", "city", "location", "timestamp", "description"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            cursor = collection.find(query)
            count = 0
            
            for doc in cursor:
                row = {
                    "uuid": doc.get("uuid", ""),
                    "type": doc.get("type", ""), 
                    "city": str(doc.get("city", "")),
                    "location": str(doc.get("location", "")),
                    "timestamp": str(doc.get("timestamp", "")),
                    "description": str(doc.get("description", ""))
                }
                writer.writerow(row)
                count += 1
                
                # Mostrar progreso cada 50 registros
                if count % 50 == 0:
                    print(f"  Procesados: {count} eventos...")

        print(f"CSV exportado exitosamente: {output_path}")
        print(f"Total eventos filtrados: {count}")
        
        # Mostrar primeros eventos como muestra
        print(f"\n=== MUESTRA DE EVENTOS TIPO {event_type} ===")
        sample_cursor = collection.find(query).limit(3)
        for i, doc in enumerate(sample_cursor, 1):
            print(f"{i}. UUID: {doc.get('uuid', 'N/A')}")
            print(f"   Tipo: {doc.get('type', 'N/A')}")
            print(f"   Ciudad: {doc.get('city', 'N/A')}")
            print(f"   Timestamp: {doc.get('timestamp', 'N/A')}")
            print()
        
        return count
        
    except Exception as e:
        print(f"ERROR: {e}")
        return 0

def get_all_types():
    """Función para obtener todos los tipos únicos de eventos"""
    print("=== OBTENIENDO TODOS LOS TIPOS DE EVENTOS ===")
    
    mongo_uri = os.environ.get("MONGO_URI", "mongodb://root:example@mongodb:27017/?authSource=admin")
    db_name = os.environ.get("MONGO_DBNAME", "waze_alertas")
    coll_name = os.environ.get("MONGO_COLLNAME", "eventos")
    
    try:
        client = MongoClient(mongo_uri)
        db = client[db_name]
        collection = db[coll_name]
        
        # Obtener tipos únicos usando aggregation
        pipeline = [
            {"$group": {"_id": "$type", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        
        results = collection.aggregate(pipeline)
        
        print("Tipos de eventos disponibles:")
        print("-" * 40)
        for result in results:
            event_type = result["_id"]
            count = result["count"]
            print(f"  {event_type}: {count} eventos")
        
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def export_all_types_unified():
    """Función para exportar todos los eventos separados por tipo en un solo CSV"""
    print("=== EXPORTANDO TODOS LOS TIPOS EN UN SOLO CSV ===")
    
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

        # Obtener todos los tipos únicos primero
        types_pipeline = [
            {"$group": {"_id": "$type", "count": {"$sum": 1}}},
            {"$sort": {"_id": 1}}  # Ordenar alfabéticamente
        ]
        
        types_result = list(collection.aggregate(types_pipeline))
        print(f"Tipos encontrados: {len(types_result)}")
        
        # Crear archivo CSV unificado
        output_path = "/scripts/eventos_todos_los_tipos.csv"
        
        print(f"Exportando todos los tipos a: {output_path}")
        
        with open(output_path, mode="w", newline="", encoding="utf-8") as csvfile:
            fieldnames = ["uuid", "type", "city", "location", "timestamp", "description"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            total_exported = 0
            
            # Procesar cada tipo por separado para mantener orden
            for type_info in types_result:
                event_type = type_info["_id"]
                type_count = type_info["count"]
                
                print(f"  Procesando tipo: {event_type} ({type_count} eventos)")
                
                # Consulta para este tipo específico
                query = {"type": event_type}
                cursor = collection.find(query).sort("timestamp", 1)  # Ordenar por timestamp
                
                type_exported = 0
                for doc in cursor:
                    row = {
                        "uuid": doc.get("uuid", ""),
                        "type": doc.get("type", ""), 
                        "city": str(doc.get("city", "")),
                        "location": str(doc.get("location", "")),
                        "timestamp": str(doc.get("timestamp", "")),
                        "description": str(doc.get("description", ""))
                    }
                    writer.writerow(row)
                    type_exported += 1
                    total_exported += 1
                
                print(f"    {type_exported} eventos de tipo {event_type} exportados")

        print(f"\nCSV unificado exportado exitosamente: {output_path}")
        print(f"Total eventos exportados: {total_exported}")
        
        # Resumen por tipo
        print(f"\n=== RESUMEN POR TIPO ===")
        for type_info in types_result:
            event_type = type_info["_id"]
            count = type_info["count"]
            percentage = (count / total_exported) * 100
            print(f"  {event_type}: {count} eventos ({percentage:.1f}%)")
        
        return total_exported
        
    except Exception as e:
        print(f"ERROR: {e}")
        return 0

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--list":
            get_all_types()
        elif sys.argv[1] == "--all":
            export_all_types_unified()
        else:
            event_type = sys.argv[1]
            filter_by_type(event_type)
    else:
        print("Uso:")
        print("  python3 filter_by_type.py JAM          # Filtrar por tipo específico")
        print("  python3 filter_by_type.py --list       # Ver todos los tipos disponibles")
        print("  python3 filter_by_type.py --all        # Exportar todos los tipos en un solo CSV")
        print("")
        print("Tipos comunes: HAZARD, JAM, POLICE, ACCIDENT, CHIT_CHAT")