"""Frozen selection already independently verified; no automatic binding application."""
import json,hashlib
from pathlib import Path
def verify(path,expected):
 raw=Path(path).read_bytes()
 if len(raw)>8000000 or hashlib.sha256(raw).hexdigest()!=expected:raise ValueError("closed_metadata_binding")
 return json.loads(raw)
