"""Conservative FL21 composition MCP; does not claim a live DAW connection."""
from fastmcp import FastMCP
from compose_bridge import inspect, export_midi, prepare_script, read_midi
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'collab'))
from prepare_append import prepare as prepare_append, prepare_from_snapshot

mcp = FastMCP("fl21-compose", instructions="""FL Studio 21 compatibility mode.
Read saved FLP files via PyFLP, read/write MIDI, prepare native Piano Roll scripts.
Saved-file state excludes unsaved DAW changes. Generated scripts are PREPARED only;
the legacy generator needs an EMPTY Pattern/channel and CODEX_COMPOSE_OK.
The fixed-entry append tool uses a current MIDI snapshot, accepts an existing roll,
and requires CODEX_APPLY_OK to confirm execution. Never claim a live connection or
successful in-FL note write based on script creation or MIDI export alone.
Never overwrite original FLP files. This server intentionally has no mixing tools.
Pitch key is the numeric note number, beats are quarter notes; FL names middle C C5.
""")

@mcp.tool()
def fl21_status() -> dict:
    """Report actual route capabilities, not MIDI-port availability."""
    return {"live_connected": False, "mode": "saved FLP / MIDI / manual or agent-assisted Piano Roll scripts", "verified_FL_version": "21.2.3.4004", "snapshot_transport": "FL script dialog title, read by a separate UI agent"}

@mcp.tool()
def fl21_read_project(path: str) -> dict:
    """Read all saved patterns, notes, channels and arrangement clips without changing the FLP."""
    return inspect(path)

@mcp.tool()
def fl21_read_midi(path: str) -> dict:
    """Read note_on/off events from a type 0/1 MIDI file; excludes pedal/expression interpretation."""
    return read_midi(path)

@mcp.tool()
def fl21_write_midi(notes: list[dict], name: str = "composition", bpm: float = 130.0) -> dict:
    """Write a NEW MIDI and verify read-back. Notes: key 0..127, beat, duration, velocity 0..1."""
    return export_midi(notes, name, bpm)

@mcp.tool()
def fl21_prepare_piano_roll(notes: list[dict], name: str = "composition") -> dict:
    """Install a self-contained composition script for an EMPTY Piano Roll. Preparation is not execution."""
    return prepare_script(notes, name)

@mcp.tool()
def fl21_prepare_current_append(source_midi: str, notes: list[dict], description: str) -> dict:
    """Prepare fixed Codex_Collab entry to append to a captured CURRENT Piano Roll.

    source_midi must be a fresh MIDI clipboard capture or user-exported current score.
    notes use absolute quarter-beat positions after the captured score's end.
    Stores baseline and candidate, keeps original notes in place, prevents duplicate
    append, and supports removing this candidate. Preparation is NOT FL execution.
    Select Codex_Collab once after FL restart; Ctrl+Alt+Y then reruns that entry.
    """
    return prepare_append(source_midi, notes, description)

@mcp.tool()
def fl21_read_native_snapshot(path: str) -> dict:
    """Read a captured native Piano Roll snapshot, including FL note properties."""
    result = json.loads(Path(path).read_text(encoding='utf-8'))
    if result.get('schema') != 1 or result.get('source') != 'native_piano_roll_message':
        raise ValueError('Expected a validated native Piano Roll snapshot')
    return result

@mcp.tool()
def fl21_prepare_snapshot_append(snapshot_path: str, notes: list[dict], description: str) -> dict:
    """Prepare appended notes from a fresh native snapshot; does not execute in FL."""
    return prepare_from_snapshot(snapshot_path, notes, description)

if __name__ == "__main__":
    mcp.run()
