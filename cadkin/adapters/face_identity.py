"""Read-only persistent face references; byte equality is never CAD identity proof."""
import base64
import binascii

from cadkin._vendor.sw_mcp import call, value
from cadkin.adapters.evidence import integer
from cadkin.errors import ToolFailure


def decode_reference(reference):
    if not isinstance(reference, dict) or reference.get('encoding') != 'base64' or reference.get('scope') != 'referenced_part_definition':
        raise ToolFailure('FACE_REFERENCE_UNAVAILABLE', 'Recollect cylinders with include_face_references=true.')
    encoded = reference.get('id')
    try:
        if not isinstance(encoded, str) or len(encoded) > 5464:
            raise ValueError('Invalid reference size.')
        raw = base64.b64decode(encoded, validate=True)
        if not 1 <= len(raw) <= 4096:
            raise ValueError('Invalid reference size.')
        return raw
    except (ValueError, binascii.Error) as exc:
        raise ToolFailure('INVALID_FACE_REFERENCE', 'Expected a bounded base64 persistent reference.') from exc


def same_object(app, left, right):
    code = integer(call(app, 'IsSame', left, right), 'IsSame')
    if code not in (0, 1):
        raise ToolFailure('FACE_IDENTITY_UNAVAILABLE', 'SOLIDWORKS cannot compare these entity objects.', equality_code=code)
    return code == 1


def resolve_face(part, reference, runtime):
    raw = decode_reference(reference)
    pythoncom, client = runtime
    encoded = client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_UI1, tuple(raw))
    state = client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    face = call(value(part, 'Extension'), 'GetObjectByPersistReference3', encoded, state)
    code = integer(state.value, 'swPersistReferencedObjectStates_e', 0)
    if code != 0 or face is None:
        raise ToolFailure('FACE_REFERENCE_UNRESOLVED', 'Persistent face reference is missing, invalid, deleted or suppressed.', reference_state=code)
    return face


def capture_face_reference(part, face, app, runtime):
    raw = call(value(part, 'Extension'), 'GetPersistReference3', face)
    if isinstance(raw, (tuple, list)):
        if not all(type(x) is int and 0 <= x <= 255 for x in raw):
            raise ToolFailure('INVALID_FACE_REFERENCE', 'Expected unsigned byte values.')
        raw = bytes(raw)
    if not isinstance(raw, bytes) or not 1 <= len(raw) <= 4096:
        raise ToolFailure('FACE_REFERENCE_UNAVAILABLE', 'SOLIDWORKS did not return a bounded persistent face ID.')
    reference = {'encoding': 'base64', 'scope': 'referenced_part_definition',
                 'id': base64.b64encode(raw).decode('ascii')}
    if not same_object(app, face, resolve_face(part, reference, runtime)):
        raise ToolFailure('FACE_IDENTITY_UNAVAILABLE', 'Persistent reference round-trip resolved a different object.')
    return reference
