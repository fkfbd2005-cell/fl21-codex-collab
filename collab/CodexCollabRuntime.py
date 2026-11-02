"""Native FL runtime: imported anew through the fixed entry. No file/network IO."""
import flpianoroll as flp
import CodexCollabCommand as command

def core(note):
    return (note.number, note.time, note.length)

def current():
    return sorted(core(flp.score.getNote(i)) for i in range(flp.score.noteCount))

def run():
    if getattr(command, 'MODE', '') == 'snapshot':
        fields = ('number', 'time', 'length', 'velocity', 'pan', 'release',
                  'color', 'group', 'fcut', 'fres', 'pitchofs', 'slide', 'porta', 'muted', 'selected')
        rows = [tuple(getattr(flp.score.getNote(i), name) for name in fields)
                for i in range(flp.score.noteCount)]
        dictionaries = []
        for i in range(3, len(fields)):
            values = []
            for row in rows:
                if row[i] not in values:
                    values.append(row[i])
            if len(values) > 36:
                flp.Utils.ShowMessage('CODEX_SNAPSHOT_LIMIT: too many different attribute values.')
                return
            dictionaries.append(tuple(values))
        digits = '0123456789abcdefghijklmnopqrstuvwxyz'
        def base36(value):
            value = int(value)
            if value == 0:
                return '0'
            result = ''
            while value:
                result = digits[value % 36] + result
                value //= 36
            return result
        packed = ';'.join(','.join((base36(row[0]), base36(row[1]), base36(row[2]),
                          ''.join(base36(i) + base36(dictionaries[i].index(value))
                                  for i, value in enumerate(row[3:]) if dictionaries[i].index(value)))) for row in rows)
        message = 'CODEX_SNAPSHOT_V3 ' + repr((flp.score.PPQ, len(rows), dictionaries, packed)) + ' CODEX_END'
        flp.Utils.log(message)
        snapshot_dialog = flp.ScriptDialog(message, 'Read-only note snapshot. No notes are changed.')
        snapshot_dialog.Execute()
        return
    baseline = sorted(command.BASELINE)
    additions = command.ADDITIONS
    target = sorted(baseline + [tuple(row[:3]) for row in additions])
    if flp.score.PPQ != command.PPQ:
        flp.Utils.ShowMessage('CODEX: PPQ changed; capture current MIDI again.')
        return
    dialog = flp.ScriptDialog('Codex collaboration', command.DESCRIPTION)
    dialog.AddInputCheckbox('Undo this candidate', False)
    dialog.restoreFormValues = False
    if not dialog.Execute():
        return
    undo = dialog.GetInputValue('Undo this candidate')
    actual = current()
    source, desired = (target, baseline) if undo else (baseline, target)
    if actual == desired:
        flp.Utils.ShowMessage('CODEX_ALREADY_DONE: no duplicate notes added.')
        return
    if actual != source:
        flp.Utils.ShowMessage('CODEX_PATTERN_CHANGED: capture current MIDI to update this candidate.')
        return
    backup = [flp.score.getNote(i).clone() for i in range(flp.score.noteCount)]
    try:
        if undo:
            remaining = [tuple(row[:3]) for row in additions]
            for i in range(flp.score.noteCount - 1, -1, -1):
                value = core(flp.score.getNote(i))
                if value in remaining:
                    flp.score.deleteNote(i)
                    remaining.remove(value)
            if remaining:
                raise RuntimeError('Missing candidate notes')
        else:
            for key, tick, length, velocity in additions:
                note = flp.Note()
                note.number = key
                note.time = tick
                note.length = length
                note.velocity = velocity
                flp.score.addNote(note)
        if current() != desired:
            raise RuntimeError('Pitch/time/length readback mismatch')
        # Original notes are never recreated on successful append/undo.
        flp.Utils.ShowMessage(('CODEX_UNDO_OK: ' if undo else 'CODEX_APPLY_OK: ')
                              + str(flp.score.noteCount) + ' notes; readback PASS')
    except Exception as exc:
        for i in range(flp.score.noteCount - 1, -1, -1):
            flp.score.deleteNote(i)
        for note in backup:
            flp.score.addNote(note)
        flp.Utils.ShowMessage('CODEX_FAILED: restored pre-operation notes. ' + str(exc))
