"""FL21 compatibility route: saved FLP reads, MIDI, and self-contained Piano Roll scripts.

Uses PyFLP (GPL-3.0-or-later) for read-only parsing. Never saves a source FLP.
The generated scripts only use the FL21 native flpianoroll API.
"""
from collections import defaultdict
from pathlib import Path
import os
import hashlib
import json
import math
import re
import uuid

import mido
from inspect_project import inspect

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
SCRIPTS = Path(os.environ.get("FL_STUDIO_PIANO_ROLL_SCRIPTS", str(Path.home() / "Documents" / "Image-Line" / "FL Studio" / "Settings" / "Piano roll scripts")))


def validate_notes(notes):
    if not 1 <= len(notes) <= 10000:
        raise ValueError("Expected 1 to 10000 notes")
    result = []
    for row in notes:
        key, time, duration = row["key"], row["beat"], row["duration"]
        velocity = row.get("velocity", 0.78)
        if isinstance(key, bool) or not isinstance(key, int) or not 0 <= key <= 127:
            raise ValueError("key must be an integer MIDI number 0..127")
        if not all(isinstance(x, (float, int)) and math.isfinite(x) for x in (time, duration, velocity)):
            raise ValueError("Note timing and velocity must be finite")
        if time < 0 or duration <= 0 or not 0 < velocity <= 1:
            raise ValueError("Expected beat>=0, duration>0, and 0<velocity<=1")
        result.append({"key": key, "beat": float(time), "duration": float(duration),
                       "velocity": float(velocity)})
    return sorted(result, key=lambda n: (n["beat"], n["key"], n["duration"]))


def read_midi(path):
    midi = mido.MidiFile(path)
    if midi.type == 2:
        raise ValueError("Type 2 asynchronous MIDI is not supported")
    active = defaultdict(list)
    notes, unmatched = [], 0
    tick = 0
    for message in mido.merge_tracks(midi.tracks):
        tick += message.time
        if message.type == "note_on" and message.velocity:
            active[(message.channel, message.note)].append((tick, message.velocity))
        elif message.type == "note_off" or (message.type == "note_on" and not message.velocity):
            held = active[(message.channel, message.note)]
            if not held:
                unmatched += 1
                continue
            start, velocity = held.pop(0)
            notes.append({"key": message.note, "beat": start / midi.ticks_per_beat,
                          "duration": (tick - start) / midi.ticks_per_beat,
                          "velocity": velocity / 127, "midi_channel": message.channel})
    return {"notes": sorted(notes, key=lambda n: (n["beat"], n["key"])),
            "ppq": midi.ticks_per_beat, "unmatched_off": unmatched,
            "unclosed_notes": sum(map(len, active.values()))}


def export_midi(notes, name="composition", bpm=130.0):
    notes = validate_notes(notes)
    if not math.isfinite(bpm) or not 10 <= bpm <= 999:
        raise ValueError("bpm must be 10..999")
    OUTPUT.mkdir(exist_ok=True)
    tag = uuid.uuid4().hex[:10]
    stem = re.sub(r"[^A-Za-z0-9_-]", "_", name)[:40] or "composition"
    path = OUTPUT / (stem + "_" + tag + ".mid")
    midi = mido.MidiFile(ticks_per_beat=960)
    track = mido.MidiTrack()
    midi.tracks.append(track)
    track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm)))
    events = []
    for note in notes:
        start = round(note["beat"] * 960)
        stop = max(start + 1, round((note["beat"] + note["duration"]) * 960))
        events.append((start, 1, mido.Message("note_on", note=note["key"], velocity=max(1, round(note["velocity"] * 127)))))
        events.append((stop, 0, mido.Message("note_off", note=note["key"], velocity=0)))
    previous = 0
    for tick, _, event in sorted(events, key=lambda e: (e[0], e[1], e[2].note)):
        track.append(event.copy(time=tick - previous))
        previous = tick
    midi.save(path)
    actual = read_midi(path)
    expected = sorted((n["key"], round(n["beat"] * 960),
                       max(1, round((n["beat"] + n["duration"]) * 960) - round(n["beat"] * 960)),
                       max(1, round(n["velocity"] * 127))) for n in notes)
    got = sorted((n["key"], round(n["beat"] * 960), round(n["duration"] * 960),
                  round(n["velocity"] * 127)) for n in actual["notes"])
    if got != expected or actual["unclosed_notes"] or actual["unmatched_off"]:
        raise RuntimeError("MIDI round-trip verification failed")
    return {"path": str(path), "note_count": len(notes), "midi_roundtrip": "passed",
            "FL_execution": "not_tested"}


def prepare_script(notes, name="composition"):
    """Default target is an EMPTY Piano Roll; source data are embedded in the script."""
    notes = validate_notes(notes)
    OUTPUT.mkdir(exist_ok=True)
    tag = uuid.uuid4().hex[:10]
    script_name = "Codex_Compose_" + tag
    rows = [(n["key"], n["beat"], n["duration"], n["velocity"]) for n in notes]
    source = '''# Generated locally. Native FL21 API only. Empty Piano Roll required.
import flpianoroll as flp
_data = ROWS
_original_count = flp.score.noteCount
if _original_count:
    flp.Utils.ShowMessage("Refused: use an EMPTY Pattern/channel Piano Roll. Existing notes were preserved.")
else:
    _error = ""
    try:
        _expected = []
        for _key, _beat, _duration, _velocity in _data:
            _note = flp.Note()
            _note.number = _key
            _note.time = round(_beat * flp.score.PPQ)
            _note.length = max(1, round((_beat + _duration) * flp.score.PPQ) - _note.time)
            _note.velocity = _velocity
            flp.score.addNote(_note)
            _expected.append((_key, _note.time, _note.length, _velocity))
        _actual = []
        for _i in range(flp.score.noteCount):
            _n = flp.score.getNote(_i)
            _actual.append((_n.number, _n.time, _n.length, _n.velocity))
        _expected.sort()
        _actual.sort()
        if len(_actual) != len(_expected):
            raise RuntimeError("Note count read-back mismatch")
        for _a, _b in zip(_actual, _expected):
            if _a[:3] != _b[:3] or abs(_a[3] - _b[3]) > 0.02:
                raise RuntimeError("Pitch/time/length/velocity read-back mismatch")
    except Exception as _exc:
        _error = type(_exc).__name__ + ": " + str(_exc)
        for _i in range(flp.score.noteCount - 1, -1, -1):
            flp.score.deleteNote(_i)
    if _error:
        flp.Utils.ShowMessage("WRITE FAILED; temporary notes removed. " + _error)
    else:
        flp.Utils.ShowMessage("CODEX_COMPOSE_OK: " + str(flp.score.noteCount) + " notes written and read back. Project has NOT been saved.")
'''.replace("ROWS", repr(rows))
    compile(source, script_name, "exec")
    output_path = OUTPUT / (script_name + ".pyscript")
    output_path.write_text(source, encoding="utf-8")
    SCRIPTS.mkdir(parents=True, exist_ok=True)
    installed = SCRIPTS / output_path.name
    installed.write_text(source, encoding="utf-8")
    manifest = {"name": name, "script": str(installed), "notes": notes,
                "script_sha256": hashlib.sha256(source.encode()).hexdigest(),
                "state": "prepared_not_executed", "target": "empty Piano Roll only"}
    output_path.with_suffix(".json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


