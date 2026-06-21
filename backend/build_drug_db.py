import requests
import json

print("Fetching drug data from openFDA...")

all_drugs = {}
skip = 0
limit = 100

while skip < 1000:
    url = f"https://api.fda.gov/drug/label.json?limit={limit}&skip={skip}"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code != 200:
            print(f"Status {res.status_code} at skip={skip}, stopping.")
            break
        data = res.json()
        results = data.get("results", [])
        if not results:
            break

        for item in results:
            generic = item.get("openfda", {}).get("generic_name", [])
            brand = item.get("openfda", {}).get("brand_name", [])

            if not generic:
                continue

            generic_name = generic[0].lower().strip()

            for b in brand:
                b_clean = b.lower().strip()
                if b_clean != generic_name:
                    all_drugs[b_clean] = generic_name

        skip += limit
        print(f"Fetched {skip} records, {len(all_drugs)} mappings so far...")

    except Exception as e:
        print(f"Error at skip={skip}: {e}")
        break

with open("/workspaces/232680061/cabinet_clear/backend/drug_db.json", "w") as f:
    json.dump(all_drugs, f)

print(f"Done! Saved {len(all_drugs)} brand-to-generic mappings.")
