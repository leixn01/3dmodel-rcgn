"""Run the production CLI with an explicitly synthetic service; tests only."""
import argparse
from pathlib import Path
import sys
from unittest.mock import patch

from tests.chain_session_fakes import session_fixture


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--mode', choices=['chain_closed', 'no_mates'], default='chain_closed')
    args = parser.parse_args()
    service, _, _, _ = session_fixture(args.root, args.mode)
    from cadkin.__main__ import main
    with patch('cadkin.tools.solidworks.SolidWorksTools', return_value=service), patch.object(
            sys, 'argv', ['cadkin', 'chain-session', 'config.json', '--output', 'outputs/session.json']):
        main()
