import os
import csv
from pymongo import MongoClient
import sys

def filter_by_comuna(comuna_name):
    print(f"=== FILTRADO POR COMUNA: {comuna_name} ===")
    
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

        # CORRECCIÓN: Usar "city" (minúscula) consistentemente
        query = {"city": {"$regex": comuna_name, "$options": "i"}}
        
        # Contar documentos que coinciden
        matching_docs = collection.count_documents(query)
        print(f"Documentos que contienen '{comuna_name}' en city: {matching_docs}")
        
        if matching_docs == 0:
            print(f"ADVERTENCIA: No se encontraron eventos para la comuna '{comuna_name}'")
            # CORRECCIÓN: Usar "city" (minúscula)
            sample_docs = collection.find({}, {"city": 1}).limit(5)
            print("Ejemplos de ciudades en la base de datos:")
            for doc in sample_docs:
                # CORRECCIÓN: Usar "city" (minúscula)
                print(f"  - {doc.get('city', 'Sin ciudad')}")
            return

        # Crear archivo CSV
        output_path = f"/scripts/eventos_{comuna_name.lower().replace(' ', '_')}.csv"
        
        print(f"Exportando a: {output_path}")
        
        with open(output_path, mode="w", newline="", encoding="utf-8") as csvfile:
            # CORRECCIÓN: Usar "city" (minúscula) en fieldnames
            fieldnames = ["uuid", "type", "city", "location", "timestamp", "description"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            cursor = collection.find(query)
            count = 0
            
            for doc in cursor:
                row = {
                    "uuid": doc.get("uuid", ""),
                    "type": doc.get("type", ""), 
                    # CORRECCIÓN: Usar "city" (minúscula)
                    "city": str(doc.get("city", "")),
                    "location": str(doc.get("location", "")),
                    "timestamp": str(doc.get("timestamp", "")),
                    "description": str(doc.get("description", ""))
                }
                writer.writerow(row)
                count += 1
                
                # Mostrar progreso cada 100 registros
                if count % 100 == 0:
                    print(f"  Procesados: {count} eventos...")

        print(f"CSV exportado exitosamente: {output_path}")
        print(f"Total eventos filtrados: {count}")
        
        # Mostrar primeros eventos como muestra
        print("\n=== MUESTRA DE EVENTOS FILTRADOS ===")
        sample_cursor = collection.find(query).limit(3)
        for i, doc in enumerate(sample_cursor, 1):
            print(f"{i}. Tipo: {doc.get('type', 'N/A')}")
            # CORRECCIÓN: Usar "city" (minúscula)
            print(f"   Ciudad: {doc.get('city', 'N/A')}")
            print(f"   Ubicación: {doc.get('location', 'N/A')}")
            print(f"   Timestamp: {doc.get('timestamp', 'N/A')}")
            print(f"   UUID: {doc.get('uuid', 'N/A')}")
            print()
        
        return count
        
    except Exception as e:
        print(f"ERROR: {e}")
        return 0

def get_all_cities():
    """Función para obtener todas las ciudades únicas de eventos"""
    print("=== OBTENIENDO TODAS LAS CIUDADES DISPONIBLES ===")
    
    mongo_uri = os.environ.get("MONGO_URI", "mongodb://root:example@mongodb:27017/?authSource=admin")
    db_name = os.environ.get("MONGO_DBNAME", "waze_alertas")
    coll_name = os.environ.get("MONGO_COLLNAME", "eventos")
    
    try:
        client = MongoClient(mongo_uri)
        db = client[db_name]
        collection = db[coll_name]
        
        # Obtener ciudades únicas usando aggregation
        pipeline = [
            {"$group": {"_id": "$city", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        
        results = collection.aggregate(pipeline)
        
        print("Ciudades disponibles:")
        print("-" * 40)
        for result in results:
            city = result["_id"]
            count = result["count"]
            print(f"  {city}: {count} eventos")
        
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--list":
            get_all_cities()
        else:
            comuna = sys.argv[1]
            filter_by_comuna(comuna)
    else:
        print("Uso:")
        print("  python3 filter_by_comuna.py Santiago     # Filtrar por comuna específica")
        print("  python3 filter_by_comuna.py --list       # Ver todas las ciudades disponibles")
        print("")
        print("Ciudades comunes: Santiago, Providencia, Las Condes, Ñuñoa")