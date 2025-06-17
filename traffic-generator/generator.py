import os, time, json, random
import requests
from datetime import datetime, timezone


API_URL = os.environ["GENERATOR_API_URL"]  


BBOX = {
  "top":    -33.3464,
  "bottom": -33.5121,
  "left":   -70.7404,
  "right":  -70.5459
}

def make_random_alert():
    return {
      "uuid":      str(random.randint(1_000_000, 9_999_999)),
      "type":      random.choice(["jam", "closure", "accident"]),
      "location":  {
          "lat": random.uniform(BBOX["bottom"], BBOX["top"]),
          "lon": random.uniform(BBOX["left"],  BBOX["right"]),
      },
      "timestamp": datetime.now(timezone.utc).isoformat()
    }


if __name__ == "__main__":
    rate = float(os.environ.get("EVENTS_PER_SEC", 5))
    dist = os.environ.get("DISTRIBUTION", "deterministic").lower() #por defecto "deterministic", cambiar por "poisson" para probar otra distribución
    interval = 1.0 / rate

    print(f"Generador funcionando a: rate={rate} evt/s, con una distribución={dist}")

    while True:
        alert = make_random_alert()
        
        try:
            r = requests.post(API_URL, json=alert, timeout=2)
            print(f"Sent {alert['type']} – {r.status_code}")

        except Exception as e:
            print("Error al enviar", e)
        
        if dist == "poisson":
            interval = random.expovariate(rate)
        else:
            interval = 1.0 / rate

        time.sleep(interval) 