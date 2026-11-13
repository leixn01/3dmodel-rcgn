"""Exclusive workflow outputs and per-call journals; no CAD or inference logic."""
import time
from pathlib import Path

from cadkin.errors import ToolFailure
from cadkin.tools.files import json_path, read_json
from cadkin.tools.proximity import write_result


def binding(root, name):
    path = json_path(root, name)
    return {'path': str(path), 'sha256': read_json(path)[1]}


class WorkflowLog:
    def __init__(self, root, output_path, call):
        self.root, self.call = root, call
        self.output = json_path(root, output_path, output=True)
        self.folder = self.output.parent / (self.output.stem + '-files')
        if self.folder.exists():
            raise ToolFailure('OUTPUT_EXISTS', 'Workflow directory exists; retain it and resume from its receipts.')
        self.output.parent.mkdir(parents=True, exist_ok=True)
        # Reserve both names before work; a crash must never silently restart a capture.
        with self.output.open('x', encoding='utf-8'):
            self.folder.mkdir(exist_ok=False)
        self.steps = []
        self.started = time.perf_counter()

    def path(self, name):
        return str(self.folder / (name + '.json'))

    def run(self, tool, arguments):
        start = time.perf_counter()
        result = self.call(tool, arguments)
        number = len(self.steps) + 1
        path = self.path(f'call-{number:03d}')
        write_result(Path(path), result)
        self.steps.append({'tool': tool, 'arguments': arguments, 'status': result['status'],
            'elapsed_seconds': max(0., time.perf_counter() - start),
            'response_source': binding(self.root, path), 'errors': result['errors']})
        if result['status'] == 'error':
            error = result['errors'][0]
            raise ToolFailure(error['code'], error['message'])
        return result['data']

    def finish(self, data):
        from collections import defaultdict
        totals = defaultdict(lambda: {'calls': 0, 'elapsed_seconds': 0.})
        for step in self.steps:
            row = totals[step['tool']]
            row['calls'] += 1
            row['elapsed_seconds'] += step['elapsed_seconds']
        data.update(steps=self.steps, performance={
            'elapsed_seconds': max(0., time.perf_counter() - self.started),
            'stage_tool_timings': sorted(({'tool': k, **v} for k, v in totals.items()),
                                        key=lambda r: (-r['elapsed_seconds'], r['tool']))})
        # Only this reserved report is finalized; all evidence files remain exclusive writes.
        import json
        with self.output.open('w', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write('\n')
        return binding(self.root, str(self.output))
