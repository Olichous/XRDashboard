import json
from datetime import datetime
from pathlib import Path

from .ssh_utils import run_commands
from .textfsm_utils import parse_output

SNAP_DIR = Path('uploads/snapshots')
SNAP_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_COMMANDS = [
    'show running-config',
    'show interfaces description'
]


def take_snapshot(ip: str, username: str, password: str):
    raw = run_commands(ip, username, password, DEFAULT_COMMANDS)
    parsed = {cmd: parse_output(cmd, out) for cmd, out in raw.items()}
    ts = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    path = SNAP_DIR / f'{ip}_{ts}.json'
    with open(path, 'w') as f:
        json.dump(parsed, f, indent=2)
    return path
