"""Store native Piano Roll snapshots read from the script's visible message."""
import ast
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def store_snapshot(message):
    if message.startswith('CODEX_SNAPSHOT_V3 '):
        if len(message) > 4_000_000 or not message.endswith(' CODEX_END'):
            raise ValueError('Truncated native snapshot')
        ppq, count, dictionaries, packed = ast.literal_eval(message[len('CODEX_SNAPSHOT_V3 '):-len(' CODEX_END')])
        packed = packed.split(';') if packed else []
        if not isinstance(ppq, int) or ppq <= 0 or not 0 <= count <= 10000 or count != len(packed) or len(dictionaries) != 12:
            raise ValueError('Invalid snapshot header')
        fields = ('number', 'time', 'length', 'velocity', 'pan', 'release', 'color', 'group', 'fcut', 'fres', 'pitchofs', 'slide', 'porta', 'muted', 'selected')
        rows = []
        for encoded in packed:
            row = encoded.split(',')
            if len(row) != 4 or len(row[3]) % 2:
                raise ValueError('Invalid packed note')
            indexes = [0] * len(dictionaries)
            for offset in range(0, len(row[3]), 2):
                field, value = int(row[3][offset], 36), int(row[3][offset + 1], 36)
                if field >= len(indexes) or indexes[field] or not value:
                    raise ValueError('Invalid field index')
                indexes[field] = value
            values = []
            for index, dictionary in zip(indexes, dictionaries):
                if index >= len(dictionary):
                    raise ValueError('Invalid dictionary index')
                values.append(dictionary[index])
            rows.append(tuple(int(v, 36) for v in row[:3]) + tuple(values))
        message = 'CODEX_SNAPSHOT_V1\n' + repr((ppq, fields, rows))
    if message.startswith('CODEX_SNAPSHOT_V2 '):
        if len(message) > 4_000_000 or not message.endswith(' CODEX_END'):
            raise ValueError('Truncated native snapshot')
        ppq, count, defaults, packed = ast.literal_eval(message[len('CODEX_SNAPSHOT_V2 '):-len(' CODEX_END')])
        fields = ('number', 'time', 'length', 'velocity', 'pan', 'release',
                  'color', 'group', 'fcut', 'fres', 'pitchofs', 'slide', 'porta', 'muted', 'selected')
        if not isinstance(ppq, int) or ppq <= 0 or not 0 <= count <= 10000 or count != len(packed):
            raise ValueError('Invalid snapshot header or note count')
        if count and len(defaults) != len(fields) - 3:
            raise ValueError('Invalid default attributes')
        rows = []
        for row in packed:
            if len(row) != 4:
                raise ValueError('Invalid packed note')
            values = list(defaults)
            indices = set()
            for index, value in row[3]:
                if not isinstance(index, int) or index < 0 or index >= len(values) or index in indices:
                    raise ValueError('Invalid or repeated attribute index')
                indices.add(index)
                values[index] = value
            rows.append(tuple(row[:3]) + tuple(values))
        message = 'CODEX_SNAPSHOT_V1\n' + repr((ppq, fields, rows))
    prefix = 'CODEX_SNAPSHOT_V1\n'
    if not message.startswith(prefix) or len(message) > 4_000_000:
        raise ValueError('Expected bounded CODEX_SNAPSHOT_V1 message')
    ppq, fields, rows = ast.literal_eval(message[len(prefix):].strip())
    if not isinstance(ppq, int) or ppq <= 0 or len(rows) > 10000:
        raise ValueError('Invalid snapshot header')
    expected = ('number', 'time', 'length', 'velocity', 'pan', 'release',
                'color', 'group', 'fcut', 'fres', 'pitchofs', 'slide', 'porta', 'muted', 'selected')
    if tuple(fields) != expected or any(len(row) != len(fields) for row in rows):
        raise ValueError('Snapshot fields incomplete')
    result = {'schema': 1, 'source': 'native_piano_roll_message', 'ppq': ppq,
              'captured_at_ns': time.time_ns(), 'notes': [dict(zip(fields, row)) for row in rows]}
    (ROOT / 'state').mkdir(exist_ok=True)
    path = ROOT / 'state' / ('native_snapshot_' + str(result['captured_at_ns']) + '.json')
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    return {'path': str(path), 'note_count': len(rows), 'ppq': ppq, 'snapshot': result}
