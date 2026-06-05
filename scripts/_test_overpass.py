"""Test Overpass API query."""
import json
import urllib.request

query = '[out:json][timeout:60];way["man_made"="submarine_cable"](1,1,180,80);out count;'
print(f"Query: {query}")

data = json.dumps({"data": query}).encode()
req = urllib.request.Request(
    "https://overpass-api.de/api/interpreter",
    data=data,
    headers={
        "Content-Type": "application/json",
        "User-Agent": "FUTURE-Infrastructure-Atlas/1.0",
    },
)
resp = urllib.request.urlopen(req, timeout=120)
result = json.loads(resp.read())
print(json.dumps(result, indent=2)[:1000])
