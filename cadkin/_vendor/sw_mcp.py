# Copyright 2026 JIALE LIU
# Modifications Copyright 2026 Christian Dengler (d-veloping)
# Licensed under the Apache License, Version 2.0.
# See licenses/SW_MCP.LICENSE and licenses/SW_MCP.NOTICE.
# Adapted for 3DModel-RCGN on 2026-11-10 from d-veloping/SW_MCP
# commit 6ea475b14924f4bc85298fc17bd1f873024e8f6b, sw_core.py / sw_inspect.py.
# Changes: extracted value()/method flagging/view IDs; failed flagging now raises;
# no logging setup, global state, MCP registration, automatic startup or COM imports.
"""SOLIDWORKS late-binding helpers; usable with plain test doubles too."""

NAMED_VIEWS = {"front": 1, "back": 2, "left": 3, "right": 4,
               "top": 5, "bottom": 6, "isometric": 7, "trimetric": 8, "dimetric": 9}


def value(obj, member):
    member_value = getattr(obj, member)
    # Dispatch objects can be callable: never invoke their default member here.
    if callable(member_value) and not hasattr(member_value, "_oleobj_"):
        return member_value()
    return member_value


def call(obj, member, *args):
    # SOLIDWORKS sometimes declares argument-taking methods as property getters.
    # Flag BEFORE accessing the attribute, or access can invoke it without args.
    if hasattr(obj, "_oleobj_"):
        try:
            obj._FlagAsMethod(member)
        except Exception as exc:
            raise RuntimeError(f"Cannot safely bind SOLIDWORKS method {member}: {exc}") from exc
    return getattr(obj, member)(*args)
