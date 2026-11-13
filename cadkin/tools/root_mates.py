"""Read-only source-bound root-mate associations, independent of cylinder scans."""
from cadkin.errors import success
from cadkin.tools.connections import review_connections
from cadkin.tools.files import json_path, read_json, replay_reads
from cadkin.tools.proximity import write_result


@replay_reads
def build_root_mate_review(root, inventory_path, mate_inventory_path):
    inv_path, mate_path = json_path(root, inventory_path), json_path(root, mate_inventory_path)
    inventory, ih = read_json(inv_path)
    mates, mh = read_json(mate_path)
    result = review_connections(None, mates, inventory, ih)
    result.update(sources={'inventory': {'path': str(inv_path), 'sha256': ih},
                          'mates': {'path': str(mate_path), 'sha256': mh}},
                  geometry_candidates_evaluated=False, requires_human_review=False)
    return result


def root_mate_review(root, inventory_path, mate_inventory_path, output_path):
    output = json_path(root, output_path, output=True)
    data = build_root_mate_review(root, inventory_path, mate_inventory_path)
    write_result(output, data)
    return success({'output_path': str(output), 'review_source': {'path': str(output), 'sha256': read_json(output)[1]},
        **{k: data[k] for k in ('counts', 'coverage', 'complete', 'geometry_candidates_evaluated',
            'requires_human_review', 'mechanical_relation_confirmed', 'solidworks_modified')},
        'detail_saved': True}, data['errors'])
