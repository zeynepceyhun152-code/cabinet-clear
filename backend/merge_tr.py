"""merge_tr.py - adds the new Turkish messages to frontend/tr.json WITHOUT overwriting wording you have already edited."""
import json, sys
path = sys.argv[1] if len(sys.argv) > 1 else "frontend/tr.json"
new = json.load(open(sys.argv[2] if len(sys.argv) > 2 else "backend/tr_security_strings.json", encoding="utf-8"))
tr = json.load(open(path, encoding="utf-8"))
added = 0
for k, v in new["strings"].items():
    if k not in tr["strings"]:
        tr["strings"][k] = v; added += 1
upgraded = 0
for up in new["pattern_upgrades"]:
    for p in tr["patterns"]:
        if p["re"] == up["re"] and p["tr"] == up["old"]:     # only if you have not changed it yourself
            p["tr"] = up["new"]; upgraded += 1
json.dump(tr, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"tr.json: {added} messages added, {upgraded} patterns upgraded")
