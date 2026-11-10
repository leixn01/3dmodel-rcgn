"""Stable errors shared by the CLI, tools and transports."""

class ToolFailure(RuntimeError):
    def __init__(self, code, message, **details):
        super().__init__(message)
        self.code = code
        self.details = details


def failure(exc):
    return {"schema_version": 1, "status": "error", "data": None,
            "errors": [{"code": getattr(exc, "code", "API_ERROR"),
                        "message": str(exc), "details": getattr(exc, "details", {})}]}


def success(data, errors=None):
    errors = errors or []
    return {"schema_version": 1, "status": "partial" if errors else "ok",
            "data": data, "errors": errors}
