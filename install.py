"""Install the fixed Piano Roll entry into an explicitly chosen FL user folder."""
import argparse
from pathlib import Path
import shutil
import time

root = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--scripts-dir', type=Path, required=True,
                    help='FL user data folder / Settings / Piano roll scripts')
args = parser.parse_args()
dest = args.scripts_dir.expanduser().resolve()
dest.mkdir(parents=True, exist_ok=True)
entry = (root / 'collab' / 'Codex_Collab.pyscript').read_text(encoding='utf-8')
entry = entry.replace('SCRIPT_DIRECTORY_PLACEHOLDER', repr(str(dest)))
compile(entry, 'Codex_Collab.pyscript', 'exec')
files = {
    'Codex_Collab.pyscript': entry,
    'CodexCollabRuntime.py': (root / 'collab' / 'CodexCollabRuntime.py').read_text(encoding='utf-8'),
    'CodexCollabCommand.py': "MODE = 'snapshot'\n",
}
for name, data in files.items():
    path = dest / name
    if path.exists():
        backup = root / 'collab' / 'backups' / (str(time.time_ns()) + '_' + name)
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup)
    path.write_text(data, encoding='utf-8')
print('Installed to:', dest)
print('Set FL_STUDIO_PIANO_ROLL_SCRIPTS to this path in the MCP client environment.')
