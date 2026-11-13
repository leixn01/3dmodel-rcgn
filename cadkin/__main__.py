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
    chain = commands.add_parser('chain-evidence', help='Build an offline scoped chain evidence dossier')
    chain.add_argument('inventory_path')
    chain.add_argument('--occurrences', dest='occurrence_paths', nargs='+', required=True)
    chain.add_argument('--name', dest='chain_name', required=True)
    chain.add_argument('--evidence', dest='evidence_paths', nargs='+')
    chain.add_argument('--grouping', dest='grouping_path')
    chain.add_argument('--grouping-review', dest='grouping_review_path')
    chain.add_argument('--output', required=True)
    chain_review = commands.add_parser('review-chain', help='Legacy optional human declarations; not part of automatic decomposition')
    chain_review.add_argument('chain_path')
    chain_review.add_argument('review_path')
    chain_review.add_argument('--output', required=True)
    templates = commands.add_parser('templates', help='List bundled mechanism reference excerpts')
    templates.add_argument('--query', default='')
    templates.add_argument('--include-heldout', action='store_true')
    extract = commands.add_parser('template-extract', help='Extract authored USD reference structure offline')
    choice = extract.add_mutually_exclusive_group(required=True)
    choice.add_argument('--template-id')
    choice.add_argument('--asset-path')
    extract.add_argument('--output', required=True)
    compare = commands.add_parser('template-compare', help='Compare graph topology with explicit hash-bound body correspondence')
    compare.add_argument('reference_path')
    compare.add_argument('candidate_path')
    compare.add_argument('--correspondence', dest='correspondence_path', required=True)
    compare.add_argument('--output', required=True)
    target = commands.add_parser('target-graph', help='Replay a chain dossier into an occurrence evidence graph')
    target.add_argument('chain_path')
    target.add_argument('--relations', dest='relation_paths', nargs='+')
    target.add_argument('--output', required=True)
    batch = commands.add_parser('execute-evidence-batch', help='Execute a bounded serial plan prefix and return a compact handoff')
    batch.add_argument('plan_path')
    batch.add_argument('--output', required=True)
    batch.add_argument('--previous-execution', dest='previous_execution_path')
    batch.add_argument('--max-steps', type=int, default=12)
    batch.add_argument('--time-budget-seconds', type=float, default=30)
    chain = commands.add_parser('solve-chain-constraints', help='Solve source-bound multi-component instantaneous constraints offline')
    chain.add_argument('constraint_analysis_path')
    chain.add_argument('--output', required=True)
    chain.add_argument('--reference-occurrence-path', required=True)
    chain.add_argument('--characteristic-length-mm', type=float, required=True)
    chain.add_argument('--relative-rank-tolerance', type=float, default=1e-8)
    chain.add_argument('--max-constraints-per-pair', type=int, default=200)
    local = commands.add_parser('solve-local-constraints', help='Solve a source-bound local instantaneous constraint model offline')
    local.add_argument('constraint_analysis_path')
    local.add_argument('--output', required=True)
    local.add_argument('--characteristic-length-mm', type=float, required=True)
    local.add_argument('--relative-rank-tolerance', type=float, default=1e-8)
    local.add_argument('--max-pairs', type=int, default=200)
    local.add_argument('--max-constraints-per-snapshot', type=int, default=200)
    constraint = commands.add_parser('analyze-constraints', help='Combine source-bound local mate constraints; no DOF solving')
    constraint.add_argument('target_graph_path')
    constraint.add_argument('--output', required=True)
    constraint.add_argument('--distance-tolerance-mm', type=float, required=True)
    constraint.add_argument('--angle-tolerance-deg', type=float, required=True)
    constraint.add_argument('--max-pairs', type=int, default=200)
    constraint.add_argument('--evidence-index', dest='evidence_index_path')
    match = commands.add_parser('match-templates', help='Rank bounded reference subgraph hypotheses against a target graph')
    match.add_argument('target_graph_path')
    match.add_argument('--template-ids', nargs='+')
    match.add_argument('--include-heldout', action='store_true')
    match.add_argument('--pattern-size', type=int, default=3)
    match.add_argument('--max-candidates', type=int, default=5)
    match.add_argument('--max-states', type=int, default=20000)
    match.add_argument('--beam-width', type=int, default=50)
    match.add_argument('--angle-tolerance-deg', type=float, default=10)
    match.add_argument('--output', required=True)
    rigid = commands.add_parser('rigid-candidates', help='Build conditional multi-occurrence body partitions')
    rigid.add_argument('target_graph_path')
    rigid.add_argument('--max-group-size', type=int, default=8)
    rigid.add_argument('--max-partitions', type=int, default=8)
    rigid.add_argument('--without-contact-hypotheses', action='store_true')
    rigid.add_argument('--output', required=True)
    draft = commands.add_parser('draft-joints', help='Draft target evidence; templates are optional explicit analogies')
    draft.add_argument('rigid_candidates_path')
    draft.add_argument('--template-ids', nargs='+')
    draft.add_argument('--include-heldout', action='store_true')
    draft.add_argument('--pattern-size', type=int, default=3)
    draft.add_argument('--max-candidates', type=int, default=5)
    draft.add_argument('--max-states', type=int, default=20000)
    draft.add_argument('--beam-width', type=int, default=50)
    draft.add_argument('--angle-tolerance-deg', type=float, default=10)
    draft.add_argument('--axis-distance-tolerance-mm', type=float, default=0.1)
    draft.add_argument('--axis-angle-tolerance-deg', type=float, default=1)
    draft.add_argument('--max-target-pairs', type=int, default=200)
    draft.add_argument('--output', required=True)
    check = commands.add_parser('check-joints', help='Replay and check a joint draft for conflicts and uncertainty')
    check.add_argument('joint_draft_path')
    check.add_argument('--max-findings', type=int, default=200)
    check.add_argument('--output', required=True)
    plan = commands.add_parser('plan-evidence', help='Plan bounded read-only evidence tasks; does not execute them')
    plan.add_argument('draft_check_path')
    plan.add_argument('--max-tasks', type=int, default=20)
    plan.add_argument('--evidence-index', dest='evidence_index_path')
    plan.add_argument('--constraint-analysis', dest='constraint_analysis_path')
    plan.add_argument('--output', required=True)
    face_plan = commands.add_parser('plan-face-probes', help='Plan witness-guided finite-face probes from a current check and latest index')
    face_plan.add_argument('draft_check_path')
    face_plan.add_argument('--evidence-index', dest='evidence_index_path', required=True)
    face_plan.add_argument('--max-component-gap-mm', type=float, required=True)
    face_plan.add_argument('--surface-tolerance-mm', type=float, required=True)
    face_plan.add_argument('--max-component-pairs', type=int, default=20)
    face_plan.add_argument('--max-face-candidates', type=int, default=20)
    face_plan.add_argument('--max-face-pairs', type=int, default=100)
    face_plan.add_argument('--max-tasks', type=int, default=20)
    face_plan.add_argument('--max-iterations', type=int, default=20)
    face_plan.add_argument('--convergence-tolerance-mm', type=float, default=0.001)
    face_plan.add_argument('--output', required=True)
    execute = commands.add_parser('execute-evidence', help='Execute a bounded read-only plan serially, saving every receipt')
    execute.add_argument('plan_path')
    execute.add_argument('--output', required=True)
    reintegrate = commands.add_parser('reintegrate-evidence', help='Recompute compatible evidence after passed execution guards')
    reintegrate.add_argument('execution_path')
    reintegrate.add_argument('--face-review', dest='face_review_path')
    reintegrate.add_argument('--output', required=True)
    compare = commands.add_parser('compare-checks', help='Compare source-replayed draft checks without asserting resolution')
    compare.add_argument('before_check_path')
    compare.add_argument('after_check_path')
    compare.add_argument('--output', required=True)
    index = commands.add_parser('index-evidence', help='Associate guarded observations and preserve attempted captures for bounded follow-up')
    index.add_argument('draft_check_path')
    index.add_argument('execution_path')
    index.add_argument('--max-contexts', type=int, default=200)
    index.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        if args.command in {"sw", "spatial-export", "group", "relations", "review-connections", 'proximity', 'review-proximity', 'review-face-contacts', 'chain-evidence', 'review-chain', 'templates', 'template-extract', 'template-compare', 'target-graph', 'match-templates', 'rigid-candidates', 'draft-joints', 'check-joints', 'plan-evidence', 'execute-evidence', 'reintegrate-evidence', 'compare-checks', 'index-evidence', 'plan-face-probes', 'analyze-constraints', 'solve-local-constraints', 'solve-chain-constraints', 'execute-evidence-batch'}:
            from .tools.solidworks import SolidWorksTools
            service = SolidWorksTools()
            try:
                if args.command == "sw":
                    result = service.call(args.tool, json.loads(args.arguments))
                elif args.command == 'execute-evidence':
                    from .tools.execution import run_plan
                    result = run_plan(service,args.plan_path,args.output)
                elif args.command == 'reintegrate-evidence':
                    arguments = {'execution_path': args.execution_path, 'output_path': args.output}
                    if args.face_review_path is not None: arguments['face_review_path'] = args.face_review_path
                    result = service.call('cad_reintegrate_evidence', arguments)
                elif args.command == 'compare-checks':
                    result = service.call('cad_compare_draft_checks',{'before_check_path':args.before_check_path,
                        'after_check_path':args.after_check_path,'output_path':args.output})
                elif args.command == 'check-joints':
                    result = service.call('cad_check_joint_draft', {'joint_draft_path':args.joint_draft_path,
                        'output_path':args.output, 'max_findings':args.max_findings})
                elif args.command == 'plan-evidence':
                    arguments = {'draft_check_path':args.draft_check_path, 'output_path':args.output, 'max_tasks':args.max_tasks}
                    if args.evidence_index_path is not None: arguments['evidence_index_path'] = args.evidence_index_path
                    if args.constraint_analysis_path is not None: arguments['constraint_analysis_path'] = args.constraint_analysis_path
                    result = service.call('cad_plan_evidence_tasks', arguments)
                elif args.command == 'index-evidence':
                    result = service.call('cad_index_evidence', {'draft_check_path':args.draft_check_path,
                        'execution_path':args.execution_path, 'output_path':args.output, 'max_contexts':args.max_contexts})
                elif args.command == 'plan-face-probes':
                    arguments = {k: v for k, v in vars(args).items() if k not in ('command', 'output')}
                    result = service.call('cad_plan_face_probes', {**arguments, 'output_path': args.output})
                elif args.command == 'rigid-candidates':
                    result = service.call('cad_build_rigid_candidates', {
                        'target_graph_path':args.target_graph_path, 'output_path':args.output,
                        'max_group_size':args.max_group_size, 'max_partitions':args.max_partitions,
                        'include_contact_hypotheses':not args.without_contact_hypotheses})
                elif args.command == 'draft-joints':
                    arguments = {k:getattr(args,k) for k in ('rigid_candidates_path','include_heldout','pattern_size',
                        'max_candidates','max_states','beam_width','angle_tolerance_deg','axis_distance_tolerance_mm','axis_angle_tolerance_deg','max_target_pairs')}
                    if args.template_ids is not None:arguments['template_ids']=args.template_ids
                    result = service.call('cad_draft_joints',{**arguments,'output_path':args.output})
                elif args.command in ('solve-chain-constraints','execute-evidence-batch'):
                    arguments = {k:v for k,v in vars(args).items() if k not in ('command','output') and v is not None}
                    tool = 'cad_solve_chain_constraints' if args.command=='solve-chain-constraints' else 'sw_execute_evidence_batch'
                    result = service.call(tool, {**arguments,'output_path':args.output})
                elif args.command == 'solve-local-constraints':
                    arguments = {k: v for k, v in vars(args).items() if k not in ('command', 'output')}
                    result = service.call('cad_solve_local_constraints', {**arguments, 'output_path':args.output})
                elif args.command == 'analyze-constraints':
                    arguments = {k: v for k, v in vars(args).items() if k not in ('command', 'output') and v is not None}
                    result = service.call('cad_analyze_constraints', {**arguments, 'output_path': args.output})
                elif args.command == 'target-graph':
                    arguments = {'chain_path':args.chain_path,'output_path':args.output}
                    if args.relation_paths is not None:arguments['relation_paths']=args.relation_paths
                    result = service.call('cad_build_target_graph',arguments)
                elif args.command == 'match-templates':
                    arguments = {k:getattr(args,k) for k in ('target_graph_path','include_heldout','pattern_size','max_candidates','max_states','beam_width','angle_tolerance_deg')}
                    if args.template_ids is not None:arguments['template_ids']=args.template_ids
                    result = service.call('cad_match_mechanism_templates',{**arguments,'output_path':args.output})
                elif args.command == 'templates':
                    result = service.call('cad_list_mechanism_templates', {'query':args.query,'include_heldout':args.include_heldout})
                elif args.command == 'template-extract':
                    arguments = {k:getattr(args,k) for k in ('template_id','asset_path') if getattr(args,k) is not None}
                    result = service.call('cad_extract_mechanism_template', {**arguments,'output_path':args.output})
                elif args.command == 'template-compare':
                    result = service.call('cad_compare_mechanism_graphs', {k:getattr(args,k) for k in ('reference_path','candidate_path','correspondence_path')} | {'output_path':args.output})
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
                elif args.command == 'chain-evidence':
                    arguments = {k: getattr(args, k) for k in ('inventory_path', 'occurrence_paths', 'chain_name', 'evidence_paths', 'grouping_path', 'grouping_review_path') if getattr(args, k) is not None}
                    arguments['output_path'] = args.output
                    result = service.call('cad_build_chain_evidence', arguments)
                elif args.command == 'review-chain':
                    result = service.call('cad_apply_chain_review', {'chain_path': args.chain_path, 'review_path': args.review_path, 'output_path': args.output})
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
        if args.command in {"sw", "spatial-export", "group", "relations", "review-connections", 'proximity', 'review-proximity', 'review-face-contacts', 'chain-evidence', 'review-chain', 'templates', 'template-extract', 'template-compare', 'target-graph', 'match-templates', 'rigid-candidates', 'draft-joints', 'check-joints', 'plan-evidence', 'execute-evidence', 'reintegrate-evidence', 'compare-checks', 'index-evidence', 'plan-face-probes'} and result["status"] == "error":
            raise SystemExit(2)
    except (RuntimeError, OSError, ValueError, KeyError, zipfile.BadZipFile, URLError) as exc:
        parser.exit(2, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
