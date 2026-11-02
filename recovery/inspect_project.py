"""Read a saved FLP without modifying it. Private PyFLP dependencies live beside this file."""
from pathlib import Path
import hashlib
import json
import math
import sys
import warnings

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "deps"))
import pyflp
from pyflp._events import EventEnum

# PyFLP #183: CPython refuses a value lookup on the memberless base enum.
# Delegate only that lookup to PyFLP's existing subclass/unknown-ID resolver.
_event_meta = type(EventEnum)
_enum_call = _event_meta.__call__
def _event_call(cls, value, *args, **kwargs):
    if cls is EventEnum and not args and not kwargs:
        found = cls._missing_(value)
        if found is None:
            raise ValueError("Invalid FLP event ID: " + repr(value))
        return found
    return _enum_call(cls, value, *args, **kwargs)
_event_meta.__call__ = _event_call


def inspect(path):
    path = Path(path).resolve()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        project = pyflp.parse(path)
        channels = [{"id": c.iid, "name": c.name, "type": type(c).__name__}
                    for c in project.channels]
        patterns = []
        for p in project.patterns:
            notes = [{"key": n["key"], "fl_name": n.key,
                      "time_ticks": n.position, "length_ticks": n.length,
                      "channel_id": n.rack_channel, "velocity_raw": n.velocity,
                      "color": n.midi_channel, "slide": n.slide}
                     for n in p.notes]
            patterns.append({"id": p.iid, "name": p.name, "notes": notes})
        arrangements = []
        for a in project.arrangements:
            tracks = []
            for track in a.tracks:
                clips = []
                for clip in track:
                    row = {"type": type(clip).__name__, "time_ticks": clip.position,
                           "length_ticks": clip.length,
                           "offsets": [v if math.isfinite(v) else None for v in clip.offsets]}
                    if hasattr(clip, "pattern"):
                        row["pattern_id"] = clip.pattern.iid
                    if hasattr(clip, "channel"):
                        row["channel_id"] = clip.channel.iid
                    clips.append(row)
                if clips:
                    tracks.append({"name": track.name, "clips": clips})
            arrangements.append({"name": a.name, "tracks": tracks})
    return {"source": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "mode": "saved_file_read_only", "version": str(project.version),
            "ppq": project.ppq, "tempo": project.tempo, "channels": channels,
            "patterns": patterns, "arrangements": arrangements,
            "warnings": sorted({str(w.message) for w in caught})}


if __name__ == "__main__":
    result = inspect(sys.argv[1])
    output = ROOT / "project_snapshot.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"snapshot": str(output), "version": result["version"],
                      "ppq": result["ppq"], "tempo": result["tempo"],
                      "channels": result["channels"],
                      "patterns": [{"id": p["id"], "name": p["name"], "notes": len(p["notes"])}
                                   for p in result["patterns"]],
                      "arrangements": result["arrangements"], "warnings": result["warnings"]},
                     ensure_ascii=True, indent=2))
