"""Maintainer utility: cache authoritative MAPC domains; never run implicitly."""
from pathlib import Path
import datetime, hashlib, json, urllib.request

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "bicycle_facilities": "https://geo.mapc.org/server/rest/services/MapcTrails/MapServer/0?f=pjson",
    "shared_use_paths": "https://geo.mapc.org/server/rest/services/Transportation/AllTrails/FeatureServer/8?f=pjson",
    "walking_trails": "https://geo.mapc.org/server/rest/services/Transportation/AllTrails/FeatureServer/4?f=pjson",
    "land_line_systems": "https://geo.mapc.org/server/rest/services/transportation/landlines/FeatureServer/0?f=pjson",
}

def main():
    target = ROOT / "reference/gis_metadata"
    target.mkdir(parents=True, exist_ok=True)
    config = {"metadata_version": 1, "sources": {}, "layers": {}}
    for layer, url in SOURCES.items():
        raw = urllib.request.urlopen(url, timeout=60).read()
        data = json.loads(raw)
        if "fields" not in data:
            raise ValueError(f"No field metadata at {url}")
        sha = hashlib.sha256(raw).hexdigest()
        filename = f"{layer}_{sha[:12]}.json"
        (target / filename).write_bytes(raw)
        config["sources"][layer] = {
            "url": url, "retrieved_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "sha256": sha, "cached_file": f"reference/gis_metadata/{filename}",
            "layer_name": data.get("name"),
        }
        fields = {}
        for field in data["fields"]:
            if field.get("domain") and field["domain"].get("codedValues"):
                fields[field["name"]] = {str(v["code"]): v["name"] for v in field["domain"]["codedValues"]}
        config["layers"][layer] = {"domains": fields}
        print(layer, json.dumps(fields, ensure_ascii=True))
    # JSON is valid YAML and removes a dependency from this acquisition utility.
    (ROOT / "config").mkdir(exist_ok=True)
    (ROOT / "config/mapc_gis_codes.yaml").write_text(json.dumps(config, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
