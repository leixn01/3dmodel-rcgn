"""Bounded JSON input and new evidence-file destinations shared by tools."""
import hashlib
import json
import math
from pathlib import Path
from contextvars import ContextVar
from functools import wraps

from cadkin.errors import ToolFailure

_REPLAY_READS = ContextVar('cadkin_replay_reads', default=None)


class ReplayReads:
    """One pure replay only. Recheck bytes and path resolutions before releasing results."""
    def __init__(self):
        self.paths, self.files, self.bytes = {}, {}, 0

    def verify(self):
        for (root, name), expected in self.paths.items():
            if _resolve_json_path(root, name) != expected:
                raise ToolFailure('EVIDENCE_MISMATCH', 'An input path changed during replay.')
        for path, (_, digest) in self.files.items():
            try:
                with path.open('rb') as stream: raw = stream.read(64 * 1024 * 1024 + 1)
            except OSError as exc:
                raise ToolFailure('EVIDENCE_MISMATCH', 'An input disappeared during replay.') from exc
            if hashlib.sha256(raw).hexdigest() != digest:
                raise ToolFailure('EVIDENCE_MISMATCH', 'An input changed during replay.')


def replay_reads(function):
    """Use only on read-only derivation/replay functions, never writers or CAD calls."""
    @wraps(function)
    def wrapped(*args, **kwargs):
        if _REPLAY_READS.get() is not None: return function(*args, **kwargs)
        state = ReplayReads(); token = _REPLAY_READS.set(state)
        try:
            result = function(*args, **kwargs)
            state.verify()
            return result
        finally: _REPLAY_READS.reset(token)
    return wrapped


def _resolve_json_path(root, name):
    root = Path(root).resolve(); path = Path(name)
    path = (path if path.is_absolute() else root / path).resolve()
    if not path.is_relative_to(root) or path == root or path.suffix.lower() != '.json':
        raise ToolFailure('INVALID_PATH', 'Use a JSON file inside the project; new results must be under outputs/.')
    return path


def json_path(root, name, output=False):
    state = _REPLAY_READS.get()
    if not output and state is not None:
        key = (str(root), str(name))
        if key in state.paths: return state.paths[key]
        path = _resolve_json_path(root, name)
        if len(state.paths) < 1024: state.paths[key] = path
        return path
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
    state = _REPLAY_READS.get()
    try:
        if state is not None and path in state.files:
            raw, digest = state.files[path]
        else:
            with path.open("rb") as stream:
                raw = stream.read(64 * 1024 * 1024 + 1)
            digest = hashlib.sha256(raw).hexdigest()
        if len(raw) > 64 * 1024 * 1024:
            raise ValueError("JSON exceeds 64 MiB")
        def reject(value):
            raise ValueError(f"Non-finite JSON value: {value}")
        def finite_float(value):
            result = float(value)
            if not math.isfinite(result):
                reject(value)
            return result
        data = json.loads(raw.decode("utf-8-sig"), parse_constant=reject, parse_float=finite_float)
        if state is not None and path not in state.files and len(state.files) < 512 and state.bytes + len(raw) <= 128 * 1024 * 1024:
            state.files[path] = (raw, digest); state.bytes += len(raw)
        return data, digest
    except (OSError, ValueError) as exc:
        raise ToolFailure("INVALID_INPUT", "Cannot read the requested JSON input.", reason=str(exc)) from exc
