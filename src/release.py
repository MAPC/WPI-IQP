"""Versioned release package. Original data are excluded conservatively."""
from pathlib import Path
import zipfile
from datetime import datetime, timezone
from . import __version__
from .utils import sha256, write_json

def create_release(root):
    root=Path(root);directory=root/"releases";directory.mkdir(exist_ok=True)
    date=datetime.now(timezone.utc).strftime("%Y-%m-%d")
    target=directory/f"MAPC_Recreation_Analysis_{date}_{__version__}.zip"
    if target.exists():
        # Retain earlier releases from the same day, never silently destroy a release.
        suffix=datetime.now(timezone.utc).strftime("%H%M%S%f")
        target=directory/f"MAPC_Recreation_Analysis_{date}_{__version__}_{suffix}.zip"
        counter=1
        while target.exists():
            target=directory/f"MAPC_Recreation_Analysis_{date}_{__version__}_{suffix}_{counter}.zip";counter+=1
    include=[]
    for name in ["README.md","CHANGELOG.md","requirements.txt","pyproject.toml","run_pipeline.bat","run_pipeline.ps1",".gitignore"]:
        p=root/name
        if p.exists():include.append(p)
    for folder in ["src","config","tests","output","bootstrap","notes"]:
        include.extend(p for p in (root/folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix!=".pyc")
    exclusions="Raw MAPC asset CSV, original GIS ZIPs/basecols, onboarding documents, prior audits, and MBTA GTFS snapshot are excluded from the distributable release because redistribution permissions were not supplied. They remain unchanged in the working project. Rebuild requires the exact inputs identified by SHA-256 in the manifest; retain input/, reference/, and cache/transit/ together with this release for institutional archival reproduction. The bundled map contains derived MAPC geometry and asset data; confirm permission before public distribution. No public publishing is performed by this pipeline.\n"
    with zipfile.ZipFile(target,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(set(include)):z.write(p,p.relative_to(root).as_posix())
        z.writestr("RAW_DATA_EXCLUSIONS.txt",exclusions)
    write_json(directory/"release_index.json",{"latest_release":target.name,"sha256":sha256(target),"size_bytes":target.stat().st_size,"raw_data_exclusions":exclusions})
    return target
