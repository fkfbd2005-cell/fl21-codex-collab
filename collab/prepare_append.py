"""Prepare a fixed-entry append candidate from a captured current Piano Roll."""
from pathlib import Path
import sys
import json
import time
import shutil
import os

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / 'recovery'))
from compose_bridge import read_midi, validate_notes

SCRIPTS = Path(os.environ.get('FL_STUDIO_PIANO_ROLL_SCRIPTS', str(Path.home() / 'Documents' / 'Image-Line' / 'FL Studio' / 'Settings' / 'Piano roll scripts')))

def prepare(midi_path, notes, description):
    captured = read_midi(midi_path)
    if captured['unclosed_notes'] or captured['unmatched_off']:
        raise ValueError('Incomplete MIDI capture')
    ppq = captured['ppq']
    baseline = [(n['key'], round(n['beat'] * ppq), round(n['duration'] * ppq)) for n in captured['notes']]
    return _prepare(ppq, baseline, notes, description, {'source_midi': str(midi_path)})

def prepare_from_snapshot(snapshot_path, notes, description):
    snapshot = json.loads(Path(snapshot_path).read_text(encoding='utf-8'))
    if snapshot.get('schema') != 1 or snapshot.get('source') != 'native_piano_roll_message':
        raise ValueError('Expected a validated native Piano Roll snapshot')
    ppq = snapshot['ppq']
    baseline = [(n['number'], n['time'], n['length']) for n in snapshot['notes']]
    return _prepare(ppq, baseline, notes, description, {'source_snapshot': str(snapshot_path)})

def _prepare(ppq, baseline, notes, description, source):
    (ROOT / 'state').mkdir(exist_ok=True)
    (ROOT / 'backups').mkdir(exist_ok=True)
    SCRIPTS.mkdir(parents=True, exist_ok=True)
    notes = validate_notes(notes)
    rows = [(n['key'], round(n['beat'] * ppq), max(1, round(n['duration'] * ppq)), n['velocity']) for n in notes]
    end = max((t + length for _, t, length in baseline), default=0)
    if any(row[1] < end for row in rows):
        raise ValueError('Append candidate must start after all current notes')
    tag = str(time.time_ns())
    manifest = {'id': tag, 'state': 'prepared_not_executed', **source,
                'ppq': ppq, 'baseline': baseline, 'additions': rows, 'description': description}
    (ROOT / 'state' / ('candidate_' + tag + '.json')).write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    source = 'PPQ = ' + repr(ppq) + '\nBASELINE = ' + repr(baseline) + '\nADDITIONS = ' + repr(rows) + '\nDESCRIPTION = ' + repr(description) + '\n'
    compile(source, 'CodexCollabCommand.py', 'exec')
    for filename in ('Codex_Collab.pyscript', 'CodexCollabRuntime.py'):
        dest = SCRIPTS / filename
        if dest.exists():
            shutil.copy2(dest, ROOT / 'backups' / (tag + '_' + filename))
        if filename == 'Codex_Collab.pyscript':
            entry = (ROOT / filename).read_text(encoding='utf-8').replace('SCRIPT_DIRECTORY_PLACEHOLDER', repr(str(SCRIPTS.resolve())))
            compile(entry, filename, 'exec')
            dest.write_text(entry, encoding='utf-8')
        else:
            shutil.copy2(ROOT / filename, dest)
    dest = SCRIPTS / 'CodexCollabCommand.py'
    if dest.exists():
        shutil.copy2(dest, ROOT / 'backups' / (tag + '_' + dest.name))
    temp = dest.with_suffix('.tmp')
    temp.write_text(source, encoding='utf-8')
    temp.replace(dest)
    return manifest

