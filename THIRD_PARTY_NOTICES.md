# Third-party code

## SW_MCP (Apache-2.0)

- Source: https://github.com/d-veloping/SW_MCP
- Pinned commit: `6ea475b14924f4bc85298fc17bd1f873024e8f6b`
- Upstream files reviewed: `solidworks_mcp/sw_core.py`, `sw_binding.py`, `sw_file.py`, `sw_inspect.py`, `server.py`, `LICENSE`, `NOTICE`.
- Reused subset: zero-argument COM member access (`value`), argument-taking method flagging, and standard view IDs. The subset is in `cadkin/_vendor/sw_mcp.py`.
- Modifications: extracted helpers from the large shared module; removed application globals, logging setup and tool registration; failed method flagging raises instead of continuing. Only late binding is implemented here. The upstream server and its full tool catalogue are not bundled or enabled.
- Copyright 2026 JIALE LIU; modifications Copyright 2026 Christian Dengler (d-veloping).
- The unmodified upstream license and notice are distributed in `cadkin/_vendor/licenses/SW_MCP.LICENSE` and `SW_MCP.NOTICE`, including in the Python wheel.

The STA worker, typed tool catalogue, bounded occurrence traversal, document target checks, CLI and MCP integration in this repository are project code. Upstream test/version claims do not constitute validation of this integration.

The MCP transport uses the official `modelcontextprotocol/python-sdk` package, pinned to `mcp==1.29.0` (MIT) as an optional dependency. It is installed from the package index, not copied into the repository. Version 1.x is chosen deliberately for the reviewed API; upgrading to 2.x requires adapting its server API.

The bundled example CAD asset has separate provenance; see `examples/three_servo_lift/README.md`. SOLIDWORKS itself is proprietary and is not distributed here.
