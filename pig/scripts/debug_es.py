#!/usr/bin/env python3
import sys
import requests
from elasticsearch import Elasticsearch

print("=== DEBUGGING ELASTICSEARCH CONNECTION ===")

# Test 1: Manual HTTP request
try:
    response = requests.get("http://elasticsearch:9200/_cluster/health", timeout=10)
    print(f"✅ Manual HTTP request successful: {response.status_code}")
    print(f"Response: {response.text[:200]}...")
except Exception as e:
    print(f"❌ Manual HTTP request failed: {e}")

# Test 2: Elasticsearch client
try:
    es = Elasticsearch([{"host": "elasticsearch", "port": 9200, "scheme": "http"}])
    print(f"✅ ES client created")
    
    # Try ping
    if es.ping():
        print("✅ ES ping successful")
    else:
        print("❌ ES ping failed")
        
except Exception as e:
    print(f"❌ ES client error: {e}")

# Test 3: Different ES connection format
try:
    es2 = Elasticsearch(["http://elasticsearch:9200"])
    print(f"✅ ES client 2 created")
    
    if es2.ping():
        print("✅ ES ping 2 successful")
    else:
        print("❌ ES ping 2 failed")
        
except Exception as e:
    print(f"❌ ES client 2 error: {e}")
