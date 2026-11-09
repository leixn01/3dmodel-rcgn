"""Conservative STEP text inventory, not a CAD parser or motion solver."""

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import tempfile
from urllib.request import urlopen
import zipfile

MAX_BYTES = 256 * 1024 * 1024
# Preserve strings while removing comments; quoted semicolons are not records.
TOKEN = re.compile(r"'(?:[^']|'')*'|/\*.*?\*/|;|[^'/;]+|.", re.S)
ENTITY = re.compile(r"#\d+\s*=\s*([A-Z][A-Z0-9_]*)\s*\(", re.I)
STRING = re.compile(r"'((?:[^']|'')*)'")


def records(text):
    parts = []
    for match in TOKEN.finditer(text):
        token = match.group()
        if token.startswith("/*"):
            parts.append(" ")
        elif token == ";":
            yield "".join(parts).strip()
            parts = []
        else:
            parts.append(token)
    if "".join(parts).strip():
        raise ValueError("Unterminated STEP record")


def inspect_step(data):
    if len(data) > MAX_BYTES:
        raise ValueError("STEP exceeds the intake size limit")
    text = data.decode("latin1")
    statements = list(records(text))
    if not statements or statements[0].upper() != "ISO-10303-21":
        raise ValueError("Not a STEP Part 21 file")
    if statements[-1].upper() != "END-ISO-10303-21":
        raise ValueError("Incomplete STEP Part 21 file")
    counts, products, schemas, units, kinematic = Counter(), [], [], set(), set()
    for statement in statements:
        match = ENTITY.match(statement)
        if match:
            kind = match[1].upper()
            counts[kind] += 1
            if kind == "PRODUCT":
                values = STRING.findall(statement)
                products.append({"entity_id": statement.split("=")[0].strip(),
                                 "name": values[1].replace("''", "'") if len(values) > 1 else None})
            if any(word in kind for word in ("KINEMATIC", "PAIR", "ACTUATION")):
                kinematic.add(kind)
        if re.match(r"FILE_SCHEMA\s*\(", statement, re.I):
            schemas.extend(STRING.findall(statement))
        if statement.startswith("#"):
            # Strip string contents before inspecting complex entity signatures.
            code = STRING.sub("''", statement)
            units.update(re.findall(r"SI_UNIT\s*\([^)]*\)", code, re.I))
    return {
        "inspection_level": "step_text_inventory_only",
        "sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data),
        "schemas": schemas, "simple_entity_counts": dict(sorted(counts.items())),
        "product_definitions": products, "si_unit_declarations": sorted(units),
        "kinematic_simple_entity_types": sorted(kinematic),
        "limitations": [
            "No B-Rep loading, geometric validity or transform verification performed.",
            "PRODUCT and NAUO record counts are not expanded assembly occurrence counts.",
            "Simple entity counts exclude complex entity components.",
            "STEP encoded product strings are retained; only doubled apostrophes are decoded.",
            "No native SolidWorks mates, rigid groups, joints or limits inferred.",
            "An empty kinematic-type list is a text-scan result, not a full semantic proof."
        ]
    }


def inspect_path(path):
    path = Path(path)
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            if any(i.flag_bits & 1 for i in members):
                raise ValueError("Encrypted archives are not supported")
            if sum(i.file_size for i in members) > MAX_BYTES:
                raise ValueError("Archive exceeds the expanded size limit")
            results = []
            for item in members:
                if Path(item.filename).suffix.lower() in {".step", ".stp"}:
                    results.append({"member": item.filename, **inspect_step(archive.read(item))})
            if not results:
                raise ValueError("No STEP file found in archive")
            return {"archive_name": path.name,
                    "members": [{"path": i.filename, "size_bytes": i.file_size} for i in members],
                    "step_files": results}
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("Input exceeds the intake size limit")
    return inspect_step(path.read_bytes())


def fetch_asset(source, output):
    spec = json.loads(Path(source).read_text(encoding="utf-8"))
    output = Path(output)
    if output.exists():
        raise ValueError("Output already exists; choose a new path")
    if not spec["download_url"].startswith("https://"):
        raise ValueError("Asset URL must use HTTPS")
    expected = spec["sha256"]
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ValueError("Expected SHA-256 is invalid")
    output.parent.mkdir(parents=True, exist_ok=True)
    digest, total, temporary = hashlib.sha256(), 0, None
    try:
        with tempfile.NamedTemporaryFile(dir=output.parent, delete=False) as stream:
            temporary = Path(stream.name)
            with urlopen(spec["download_url"], timeout=60) as response:
                while chunk := response.read(1024 * 1024):
                    total += len(chunk)
                    if total > MAX_BYTES:
                        raise ValueError("Download exceeds the intake size limit")
                    digest.update(chunk)
                    stream.write(chunk)
        if digest.hexdigest() != expected or total != spec["size_bytes"]:
            raise ValueError("Asset checksum or size mismatch; download discarded")
        # Exclusive create prevents overwriting a file produced during download.
        with output.open("xb") as target, temporary.open("rb") as source_stream:
            while chunk := source_stream.read(1024 * 1024):
                target.write(chunk)
        return {"output": str(output), "sha256": expected, "size_bytes": total}
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
