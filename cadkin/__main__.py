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
    relations = commands.add_parser("relations", help="Compare saved cylinder axes offline; candidates require review")
    relations.add_argument("inventory_path")
    relations.add_argument("--cylinders", dest="cylinder_paths", nargs="+", required=True)
    relations.add_argument("--output", required=True)
    relations.add_argument("--distance-tolerance-mm", type=float, required=True)
    relations.add_argument("--angle-tolerance-deg", type=float, required=True)
    relations.add_argument("--max-pairs", type=int, default=10000)
    relations.add_argument("--max-candidates", type=int, default=1000)
    relations.add_argument("--grouping", dest="grouping_path")
    review = commands.add_parser("review-connections", help="Associate geometric candidates with root mate evidence offline")
    review.add_argument("relations_path")
    review.add_argument("mate_inventory_path")
    review.add_argument("--output", required=True)
    proximity = commands.add_parser('proximity', help='Create an approximate-box worklist for component distance measurements')
    proximity.add_argument('inventory_path')
    proximity.add_argument('--output', required=True)
    proximity.add_argument('--max-box-gap-mm', type=float, required=True)
    proximity.add_argument('--occurrences', dest='occurrence_paths', nargs='+')
    proximity.add_argument('--max-pairs', type=int, default=20000)
    proximity.add_argument('--max-candidates', type=int, default=200)
    near_review = commands.add_parser('review-proximity', help='Review saved distance evidence offline; contact remains a candidate')
    near_review.add_argument('proximity_path')
    near_review.add_argument('--distances', dest='distance_paths', nargs='+', required=True)
    near_review.add_argument('--output', required=True)
    near_review.add_argument('--contact-tolerance-mm', type=float, required=True)
    faces_review = commands.add_parser('review-face-contacts', help='Review local face probes offline, without global minimum/contact claims')
    faces_review.add_argument('--probes', dest='probe_paths', nargs='+', required=True)
    faces_review.add_argument('--output', required=True)
    faces_review.add_argument('--contact-tolerance-mm', type=float, required=True)
    faces_review.add_argument('--angle-tolerance-deg', type=float, required=True)
    args = parser.parse_args()
    try:
        if args.command in {"sw", "spatial-export", "group", "relations", "review-connections", 'proximity', 'review-proximity', 'review-face-contacts'}:
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
                elif args.command == "review-connections":
                    result = service.call("cad_review_connections", {"relations_path": args.relations_path,
                        "mate_inventory_path": args.mate_inventory_path, "output_path": args.output})
                elif args.command == "relations":
                    arguments = {key: getattr(args, key) for key in (
                        "inventory_path", "cylinder_paths", "distance_tolerance_mm", "angle_tolerance_deg",
                        "max_pairs", "max_candidates")}
                    arguments["output_path"] = args.output
                    if args.grouping_path is not None:
                        arguments["grouping_path"] = args.grouping_path
                    result = service.call("cad_component_relations", arguments)
                elif args.command == 'review-face-contacts':
                    result = service.call('cad_review_face_contacts', {'probe_paths': args.probe_paths,
                        'output_path': args.output, 'contact_tolerance_mm': args.contact_tolerance_mm, 'angle_tolerance_deg': args.angle_tolerance_deg})
                elif args.command == 'proximity':
                    arguments = {k: getattr(args, k) for k in ('inventory_path', 'max_box_gap_mm', 'max_pairs', 'max_candidates')}
                    arguments['output_path'] = args.output
                    if args.occurrence_paths is not None:
                        arguments['occurrence_paths'] = args.occurrence_paths
                    result = service.call('cad_proximity_candidates', arguments)
                elif args.command == 'review-proximity':
                    result = service.call('cad_review_proximity', {'proximity_path': args.proximity_path,
                        'distance_paths': args.distance_paths, 'contact_tolerance_mm': args.contact_tolerance_mm, 'output_path': args.output})
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
        if args.command in {"sw", "spatial-export", "group", "relations", "review-connections", 'proximity', 'review-proximity', 'review-face-contacts'} and result["status"] == "error":
            raise SystemExit(2)
    except (RuntimeError, OSError, ValueError, KeyError, zipfile.BadZipFile, URLError) as exc:
        parser.exit(2, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
