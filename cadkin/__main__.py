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
    args = parser.parse_args()
    try:
        result = fetch_asset(args.source, args.output) if args.command == "fetch" else inspect_path(args.path)
        payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.command == "inspect" and args.output:
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open("x", encoding="utf-8") as stream:
                stream.write(payload)
            print(str(output))
        else:
            print(payload, end="")
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, URLError) as exc:
        parser.exit(2, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
