import argparse
import json
from pathlib import Path
from urllib.error import URLError
import zipfile

from .tools.intake import fetch_asset, inspect_path


def main():
    parser = argparse.ArgumentParser(description="CAD asset intake; no motion inference")
    commands = parser.add_subparsers(dest="command", required=True)
    fetch = commands.add_parser("fetch", help="Download a pinned, checksummed asset")
    fetch.add_argument("--source", required=True)
    fetch.add_argument("--output", required=True)
    inspect = commands.add_parser("inspect", help="Inventory STEP text or ZIP contents")
    inspect.add_argument("path")
    inspect.add_argument("--output")
    sw = commands.add_parser("sw", help="Call a SOLIDWORKS tool through the same implementation as MCP")
    sw.add_argument("tool")
    sw.add_argument("--arguments", default="{}", help="Tool arguments as a JSON object")
    sw.add_argument("--output", help="Save JSON to a new file")
    spatial = commands.add_parser("spatial-export", help="Collect all spatial pages sequentially into a new JSON file")
    spatial.add_argument("--output", required=True)
    spatial.add_argument("--page-size", type=int, default=20)
    spatial.add_argument("--max-components", type=int, default=5000)
    spatial.add_argument("--max-depth", type=int, default=64)
    spatial.add_argument("--without-boxes", action="store_true", help="Skip slow GetBox calls; geometry remains explicitly absent")
    group = commands.add_parser("group", help="Group exported leaf occurrences into reviewable role candidates")
    group.add_argument("inventory_path")
    group.add_argument("--output", required=True)
    group.add_argument("--scope", dest="scope_occurrence_path")
    group.add_argument("--review", dest="review_path")
    args = parser.parse_args()
    try:
        if args.command in {"sw", "spatial-export", "group"}:
            from .tools.solidworks import SolidWorksTools
            service = SolidWorksTools()
            try:
                if args.command == "sw":
                    result = service.call(args.tool, json.loads(args.arguments))
                elif args.command == "spatial-export":
                    from .tools.spatial import collect_spatial
                    # Check destination before spending time reading the assembly.
                    from .tools.files import json_path
                    json_path(Path.cwd(), args.output, output=True)
                    result = collect_spatial(service, args.page_size, args.max_components, args.max_depth, not args.without_boxes)
                else:
                    arguments = {"inventory_path": args.inventory_path, "output_path": args.output}
                    if args.scope_occurrence_path is not None:
                        arguments["scope_occurrence_path"] = args.scope_occurrence_path
                    if args.review_path is not None:
                        arguments["review_path"] = args.review_path
                    result = service.call("cad_group_components", arguments)
            finally:
                service.close()
        else:
            result = fetch_asset(args.source, args.output) if args.command == "fetch" else inspect_path(args.path)
        payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.command in {"inspect", "sw", "spatial-export"} and args.output:
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open("x", encoding="utf-8") as stream:
                stream.write(payload)
            print(str(output))
        else:
            print(payload, end="")
        if args.command in {"sw", "spatial-export", "group"} and result["status"] == "error":
            raise SystemExit(2)
    except (RuntimeError, OSError, ValueError, KeyError, zipfile.BadZipFile, URLError) as exc:
        parser.exit(2, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
