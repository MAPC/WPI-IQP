"""Shared serialization, hashing, and HTML helpers."""
import hashlib
import json
from pathlib import Path
import datetime
import html
import numpy as np
import pandas as pd

def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def json_default(value):
    if isinstance(value, Path): return str(value)
    if isinstance(value, (datetime.datetime, datetime.date)): return value.isoformat()
    if isinstance(value, np.generic): return value.item()
    if isinstance(value, (set, tuple)): return list(value)
    if value is pd.NA: return None
    raise TypeError(type(value).__name__)

def write_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False, default=json_default), encoding="utf-8")

def csv_frame(df):
    result = df.copy()
    for col in result:
        result[col] = result[col].map(lambda v: json.dumps(v, ensure_ascii=False, sort_keys=True, default=json_default) if isinstance(v, (list,dict,tuple)) else v)
    return result

def write_csv(df, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    csv_frame(df).to_csv(path, index=False, encoding="utf-8-sig", lineterminator="\n")

def html_page(title, body):
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'''+html.escape(title)+'''</title><style>body{font:16px/1.5 system-ui;margin:36px auto;padding:0 28px;max-width:1350px;color:#173344;background:#f5f7f9}h1,h2{color:#153d55}table{border-collapse:collapse;width:100%;background:white;font-size:13px;margin:18px 0}th,td{text-align:left;vertical-align:top;padding:9px;border-bottom:1px solid #d6e0e6;overflow-wrap:anywhere}th{background:#173f56;color:white}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:white;padding:18px}.warning{padding:18px;background:#fff0d2;border-left:5px solid #c47c12}a{color:#006c9b}details{margin:12px 0}h1{font-size:32px}</style><h1>'''+html.escape(title)+"</h1>"+body+"</html>"
