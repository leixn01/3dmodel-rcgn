"""Bounded JSON input and new evidence-file destinations shared by tools."""
import hashlib
import json
import math
from pathlib import Path

from cadkin.errors import ToolFailure


def json_path(root, name, output=False):
    root = Path(root).resolve()
    path = Path(name)
    path = (path if path.is_absolute() else root / path).resolve()
    boundary = root / "outputs" if output else root
    if not path.is_relative_to(boundary) or path == boundary or path.suffix.lower() != ".json":
        raise ToolFailure("INVALID_PATH", "Use a JSON file inside the project; new results must be under outputs/.")
    if output and path.exists():
        raise ToolFailure("OUTPUT_EXISTS", "Choose a new output filename; existing evidence is never overwritten.")
    return path


def read_json(path):
    try:
        with path.open("rb") as stream:
            raw = stream.read(64 * 1024 * 1024 + 1)
        if len(raw) > 64 * 1024 * 1024:
            raise ValueError("JSON exceeds 64 MiB")
        def reject(value):
            raise ValueError(f"Non-finite JSON value: {value}")
        def finite_float(value):
            result = float(value)
            if not math.isfinite(result):
                reject(value)
            return result
        return json.loads(raw.decode("utf-8-sig"), parse_constant=reject, parse_float=finite_float), hashlib.sha256(raw).hexdigest()
    except (OSError, ValueError) as exc:
        raise ToolFailure("INVALID_INPUT", "Cannot read the requested JSON input.", reason=str(exc)) from exc
