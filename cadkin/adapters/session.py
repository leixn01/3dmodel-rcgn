"""Explicit Windows application startup, separate from read-only attachment."""
import time

from cadkin._vendor.sw_mcp import value
from cadkin.errors import ToolFailure, success


def boolean_property(app, member):
    result = value(app, member)
    if not isinstance(result, (bool, int)) or result not in (False, True, -1):
        raise ToolFailure('STARTUP_READ_FAILED', f'{member} did not return a readable Boolean.')
    return bool(result)


class SessionOperations:
    def _resolve_application_clsid(self):
        import pywintypes
        return pywintypes.IID('SldWorks.Application')

    def sw_start_application(self, wait_seconds=120):
        deadline = time.monotonic() + wait_seconds
        pythoncom, client = self.runtime
        started = False
        try:
            # _connect distinguishes not running from a running-but-unavailable session.
            # Never create a second process to work around an attach or process-query error.
            try:
                app = self._connect()
            except ToolFailure as exc:
                if exc.code != 'NOT_RUNNING':
                    raise
                if self._launch_uncertain:
                    raise ToolFailure('START_OUTCOME_UNKNOWN', 'A previous launch failed after activation began. Inspect SOLIDWORKS and restart MCP before another launch attempt.') from exc
                # Resolve registration before marking activation as uncertain.
                try:
                    clsid = self._resolve_application_clsid()
                except Exception as registration_error:
                    raise ToolFailure('APPLICATION_NOT_REGISTERED', 'Windows could not resolve SldWorks.Application. Check the installed desktop SOLIDWORKS COM registration.', reason=str(registration_error)) from registration_error
                # Recheck after registration in case another user/client started the application.
                try:
                    app = self._connect()
                except ToolFailure as recheck:
                    if recheck.code != 'NOT_RUNNING':
                        raise
                    self._launch_uncertain = True
                    dispatch = pythoncom.CoCreateInstance(clsid, None, pythoncom.CLSCTX_LOCAL_SERVER, pythoncom.IID_IDispatch)
                    app = client.dynamic.Dispatch(dispatch)
                    self.app = app  # Keep the reference even if later readiness checks fail.
                    self.process_id = str(value(app, 'GetProcessID'))
                    started = True
            app.UserControl = True  # Keep the interactive application alive after MCP/CLI exits.
            app.Visible = True
            if not boolean_property(app, 'UserControl') or not boolean_property(app, 'Visible'):
                raise ToolFailure('STARTUP_STATE_MISMATCH', 'SOLIDWORKS did not confirm an interactive visible session.')
            while not boolean_property(app, 'StartupProcessCompleted'):
                if time.monotonic() >= deadline:
                    raise ToolFailure('STARTUP_PENDING', 'SOLIDWORKS is attached but startup/add-ins are not ready. Inspect licence, recovery or startup dialogs; a later start call will reuse the existing process.', process_id=self.process_id, started_by_call=started)
                pythoncom.PumpWaitingMessages()
                time.sleep(min(0.2, max(0, deadline - time.monotonic())))
            # Check the OS process list and attached object's PID again. Do not kill either
            # instance if an external launcher raced this call and created multiple sessions.
            verified = self._connect()
            if str(value(verified, 'GetProcessID')) != str(value(app, 'GetProcessID')):
                raise ToolFailure('SESSION_MISMATCH', 'The SOLIDWORKS session changed during startup.')
            revision = value(app, 'RevisionNumber')
            if not isinstance(revision, str) or not revision.strip():
                raise ToolFailure('STARTUP_READ_FAILED', 'SOLIDWORKS returned no readable revision.')
            self._launch_uncertain = False
            return success({'connected': True, 'started': started, 'reused_existing': not started,
                            'process_id': self.process_id, 'revision': revision,
                            'startup_completed': True, 'visible': True, 'user_control': True,
                            'has_active_document': value(app, 'ActiveDoc') is not None,
                            'verification': 'COM startup and visibility properties confirmed; licence/recovery dialogs and the actual window still require local inspection.'})
        except ToolFailure:
            raise
        except Exception as exc:
            raise ToolFailure('START_FAILED', 'SOLIDWORKS startup/attachment did not complete. A process may still be starting; inspect the window before retrying. No process was terminated.',
                              process_id=self.process_id, activation_attempted=self._launch_uncertain, reason=str(exc)) from exc
