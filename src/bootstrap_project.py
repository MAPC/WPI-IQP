"""Inventory root files before copying; preserve originals and input versions."""
import argparse
import csv
import html
from pathlib import Path
import shutil
from datetime import datetime, timezone
from .utils import sha256, html_page

PROJECT_FILES = {"README.md", "CHANGELOG.md", "requirements.txt", "pyproject.toml", "run_pipeline.bat", "run_pipeline.ps1", ".gitignore"}

def classify(path):
    n = path.name.lower()
    if n.endswith(".shp.zip") and "trans_" in n:
        return "raw GIS input", "input/gis", "Original MAPC zipped geometry"
    if n.endswith("_basecols.csv"):
        return "GIS reference", "input/gis_reference", "Attribute export paired with GIS"
    if "factcheck_audit" in n:
        return "previous audit reference", "reference/previous_audits", "Prior claims must be re-evaluated"
    if "processed" in n or path.suffix.lower() in (".py", ".html"):
        return "legacy output/code", "legacy", "Not an authoritative current source"
    if n.endswith(".csv"):
        with path.open(encoding="utf-8-sig", newline="") as f:
            cols = {x.strip().casefold() for x in next(csv.reader(f), [])}
        if cols & {"name of asset", "asset name", "asset_name"} and cols & {"attributes", "attributes_raw"}:
            return "raw asset input candidate", "input/assets", "Schema includes asset name and structured attributes"
    if "onboarding" in n:
        return "field guide reference", "reference/field_guides", "Collection procedures and definitions"
    if path.suffix.lower() in (".docx", ".pdf"):
        return "project document reference", "reference/project_docs", "Document context; no values auto-applied"
    return "unclassified/reference", "reference/unclassified", "Ambiguous role; requires review"

def bootstrap(root):
    root = Path(root).resolve()
    files = sorted((p for p in root.iterdir() if p.is_file() and p.name not in PROJECT_FILES), key=lambda p:p.name)
    rows = []
    for p in files:
        role, dest, reason = classify(p)
        rows.append(dict(filename=p.name, extension=p.suffix, size_bytes=p.stat().st_size, sha256=sha256(p), role=role, destination=f"{dest}/{p.name}", reason=reason, original_preserved=True))
    folder = root / "bootstrap"
    folder.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    inventory = folder / ("root_inventory.csv" if not (folder/"root_inventory.csv").exists() else f"root_inventory_{stamp}.csv")
    with inventory.open("w", newline="", encoding="utf-8-sig") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]) if rows else ["filename"]);writer.writeheader();writer.writerows(rows)
    for r in rows:
        src, target = root/r["filename"], root/r["destination"]
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and sha256(target) != r["sha256"]:
            archived=root/"cache/input_versions"/sha256(target)/target.name
            archived.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(target,archived)
            r["reason"] += f"; previous input preserved at {archived.relative_to(root)}"
        if not target.exists() or sha256(target)!=r["sha256"]: shutil.copy2(src,target)
        if sha256(target)!=r["sha256"]: raise RuntimeError(f"Copy checksum mismatch: {target}")
    import pandas as pd
    body="<p>Every original root file is preserved. Copies were verified by SHA-256. Multiple asset candidates require explicit configuration. Changes to same-named inputs archive the old bytes in cache/input_versions.</p>"+pd.DataFrame(rows).to_html(index=False,escape=True)
    (folder/"bootstrap_report.html").write_text(html_page("MAPC bootstrap report",body),encoding="utf-8")
    return rows

if __name__ == "__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[1]);args=parser.parse_args();bootstrap(args.root)
