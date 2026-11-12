"""Bound recursive plan/index provenance replay before reading nested inputs."""
from contextvars import ContextVar
from functools import wraps
from cadkin.tools.files import json_path
from cadkin.tools.chain_sources import require

_STACK = ContextVar('cadkin_provenance_replay', default=())


def bounded_replay(function):
    @wraps(function)
    def wrapped(root, name, *args, **kwargs):
        key = str(json_path(root, name))
        stack = _STACK.get()
        require(key not in stack, 'Cyclic evidence provenance.', 'EVIDENCE_CYCLE')
        require(len(stack) < 12, 'Evidence provenance exceeds replay depth.', 'EVIDENCE_DEPTH_LIMIT')
        token = _STACK.set(stack + (key,))
        try:
            return function(root, name, *args, **kwargs)
        finally:
            _STACK.reset(token)
    return wrapped
