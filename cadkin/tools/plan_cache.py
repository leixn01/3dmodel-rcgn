"""Bounded process-local replay cache; revalidate every source before each use."""
from collections import OrderedDict
from copy import deepcopy
import hashlib
import threading

from cadkin.templates.catalog import ROOT
from cadkin.tools.files import json_path
from cadkin.tools.chain_sources import require
from cadkin.tools.matching import recheck


def reference_fingerprint():
    # Include metadata and all pinned assets: changed reference selection is also a change.
    paths = [ROOT / 'catalog.json', *sorted(ROOT.rglob('*.usda'))]
    return [(str(p), hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths]


class PlanReplayCache:
    def __init__(self, capacity=4):
        self.capacity = capacity
        self.entries = OrderedDict()
        self.lock = threading.RLock()

    def load(self, root, name):
        from cadkin.tools.followup import replay_plan
        path = json_path(root, name)
        key = (str(root), str(path))
        with self.lock:
            if key in self.entries:
                loaded, references = self.entries[key]
                try:
                    recheck(root, loaded[0]['input_files'] + [loaded[3]])
                    require(reference_fingerprint() == references,
                            'Reference assets changed after plan replay.', 'EVIDENCE_MISMATCH')
                except Exception:
                    del self.entries[key]
                    raise
                self.entries.move_to_end(key)
                return deepcopy(loaded)
            references = reference_fingerprint()
            loaded = replay_plan(root, str(path))
            require(reference_fingerprint() == references,
                    'Reference assets changed during replay.', 'EVIDENCE_MISMATCH')
            self.entries[key] = (deepcopy(loaded), references)
            while len(self.entries) > self.capacity:
                self.entries.popitem(last=False)
            return loaded
