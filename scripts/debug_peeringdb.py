"""Debug PeeringDB raw data."""
import json

with open("data/raw/peeringdb/facilities_raw.json", encoding="utf-8") as f:
    raw = json.load(f)
print(f"Raw records: {len(raw)}")

ids = [f.get("id") for f in raw if f.get("id") is not None]
print(f"ID range: {min(ids)} to {max(ids)}")

from collections import Counter
id_counts = Counter(ids)
dupes = {k: v for k, v in id_counts.items() if v > 1}
print(f"Duplicate IDs: {len(dupes)}")

seen = set()
count = 0
for fac in raw:
    fid = fac.get("id")
    if fid is None:
        continue
    fid = int(fid)
    if fid in seen:
        continue
    seen.add(fid)
    count += 1
print(f"Expected unique: {count}, seen size: {len(seen)}")

# Now check why process_facilities returns 100
# Maybe the org field parsing is failing
for fac in raw[:5]:
    print(f'  id={fac["id"]} org_type={type(fac.get("org"))} org_id={fac.get("org_id")} org_name={fac.get("org_name")}')
