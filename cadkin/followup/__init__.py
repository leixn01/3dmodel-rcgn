"""Draft consistency and bounded evidence planning; no CAD calls or skill loading."""
import hashlib
import json


def stable_id(prefix, value):
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    return prefix + hashlib.sha256(data).hexdigest()[:24]
