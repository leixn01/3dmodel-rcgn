"""Run the production CLI with an explicitly synthetic service; tests only."""
import argparse
import json
from pathlib import Path
import sys
from unittest.mock import patch

from tests.chain_session_fakes import session_fixture


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--mode', choices=['chain_closed', 'no_mates'], default='chain_closed')
    parser.add_argument('--profile', choices=['geometry_and_mates', 'root_mates'], default='geometry_and_mates')
    args = parser.parse_args()
    service, _, _, config = session_fixture(args.root, args.mode)
    config['capture_profile'] = args.profile
    (args.root/'config.json').write_text(json.dumps(config), encoding='utf-8')
    from cadkin.__main__ import main
    with patch('cadkin.tools.solidworks.SolidWorksTools', return_value=service), patch.object(
            sys, 'argv', ['cadkin', 'chain-session', 'config.json', '--output', 'outputs/session.json']):
        main()
