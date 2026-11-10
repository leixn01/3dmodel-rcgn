"""One COM apartment; no COM objects leave its worker thread."""
from concurrent.futures import Future, TimeoutError
import queue
import threading

from cadkin.errors import ToolFailure


class StaWorker:
    def __init__(self, factory, timeout=60.0):
        self.factory = factory
        self.timeout = timeout
        self._jobs = queue.Queue()
        self._gate = threading.Lock()
        self._state_lock = threading.Lock()
        self._uncertain = False
        self._closed = False
        self._thread = threading.Thread(target=self._run, name="cadkin-solidworks-sta", daemon=True)
        self._thread.start()

    def _run(self):
        adapter = None
        try:
            while True:
                job = self._jobs.get()
                if job is None:
                    break
                name, arguments, future = job
                try:
                    if adapter is None:
                        adapter = self.factory()  # COM initialisation happens here only.
                    future.set_result(getattr(adapter, name)(**arguments))
                except Exception as exc:
                    # Original tracebacks can retain COM locals. Send only plain error data.
                    future.set_exception(ToolFailure(getattr(exc, "code", "API_ERROR"), str(exc),
                                                     **getattr(exc, "details", {})))
        finally:
            if adapter is not None:
                adapter.close()  # Release COM references in their owning apartment.

    def mark_uncertain(self):
        with self._state_lock:
            self._uncertain = True

    def call(self, name, arguments):
        if not self._gate.acquire(blocking=False):
            raise ToolFailure("BUSY", "Another SOLIDWORKS operation is running; no call was queued.")
        try:
            with self._state_lock:
                if self._closed:
                    raise ToolFailure("CLOSED", "The SOLIDWORKS worker has shut down.")
                if self._uncertain:
                    raise ToolFailure("OUTCOME_UNKNOWN", "An earlier call timed out or was cancelled. Inspect SOLIDWORKS, then restart MCP; do not blindly repeat the operation.")
                future = Future()
                self._jobs.put((name, arguments, future))
            try:
                return future.result(timeout=self.timeout)
            except TimeoutError as exc:
                self.mark_uncertain()
                raise ToolFailure("TIMEOUT", "SOLIDWORKS did not respond in time. The call may still finish; inspect dialogs and model state, then restart MCP.", timeout_seconds=self.timeout) from exc
        finally:
            self._gate.release()

    def close(self):
        with self._state_lock:
            if self._closed:
                return
            self._closed = True
            self._jobs.put(None)
        self._thread.join(timeout=1.0)  # A blocked COM call must not hang server shutdown.
