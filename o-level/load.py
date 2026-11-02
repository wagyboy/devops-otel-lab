"""Generate traffic against shop-frontend: mixed SKUs, quantities and user tiers.

  python load.py [seconds]
"""
import random
import sys
import time
from collections import Counter

import requests

URL = "http://localhost:8080/buy/{sku}"
SKUS = ["SKU-100"] * 5 + ["SKU-200"] * 3 + ["SKU-300"] * 2 + ["SKU-999"]  # SKU-999 does not exist

duration = float(sys.argv[1]) if len(sys.argv) > 1 else 60
results = Counter()
end = time.time() + duration
while time.time() < end:
    sku = random.choice(SKUS)
    tier = random.choice(["free", "free", "premium"])
    resp = requests.get(URL.format(sku=sku), params={"qty": random.randint(1, 4)},
                        headers={"X-User-Tier": tier}, timeout=10)
    results[resp.status_code] += 1
    time.sleep(random.uniform(0.05, 0.2))

print("requests by status:", dict(sorted(results.items())))
