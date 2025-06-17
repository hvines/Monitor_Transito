#!/usr/bin/env python3
"""
Script para configurar índices y visualizaciones básicas en Kibana
"""

import requests
import json
import time

def setup_kibana():
    """Configura índices y dashboards básicos en Kibana"""
    
    kibana_url = "http://localhost:5601"
    es_url = "http://localhost:9200"
    
    print("🔧 Configurando Kibana...")
    
    # Esperar a que Kibana esté listo
    for i in range(30):
        try:
            response = requests.get(f"{kibana_url}/api/status")
            if response.status_code == 200:
                print("✅ Kibana está listo")
                break
        except:
            pass
        print(f"⏳ Esperando Kibana ({i+1}/30)...")
        time.sleep(2)
    else:
        print("❌ Kibana no está disponible")
        return False
    
    # Crear índice pattern para waze-events
    index_pattern = {
        "attributes": {
            "title": "waze-events-*",
            "timeFieldName": "@timestamp"
        }
    }
    
    headers = {
        "Content-Type": "application/json",
        "kbn-xsrf": "true"
    }
    
    try:
        # Crear el data view
        response = requests.post(
            f"{kibana_url}/api/data_views/data_view",
            headers=headers,
            json={
                "data_view": {
                    "title": "waze-events-*",
                    "timeFieldName": "@timestamp",
                    "name": "Waze Traffic Events"
                }
            }
        )
        
        if response.status_code in [200, 201]:
            print("✅ Data view 'waze-events-*' creado exitosamente")
        else:
            print(f"⚠️  Data view ya existe o error: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error al crear data view: {e}")
    
    print("\n🎯 CONFIGURACIÓN COMPLETADA:")
    print("-----------------------------")
    print("1. Ve a Kibana: http://localhost:5601")
    print("2. Ve a Analytics > Discover")
    print("3. Selecciona el data view 'Waze Traffic Events'")
    print("4. Explora tus datos de tráfico")
    print("\n📊 VISUALIZACIONES SUGERIDAS:")
    print("- Eventos por tipo (type)")
    print("- Eventos por ciudad (city)")
    print("- Evolución temporal (@timestamp)")
    print("- Mapa de ubicaciones (geo_location)")
    print("- Confiabilidad por tipo (confidence vs type)")
    
    return True

if __name__ == "__main__":
    setup_kibana()
