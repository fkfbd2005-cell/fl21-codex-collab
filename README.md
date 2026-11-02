# FL21 Codex Collab (experimental)

An experimental Windows Piano Roll collaboration adapter for FL Studio 21. It combines a small MCP server, native Piano Roll scripts, and an optional separate UI agent. It was developed after investigating [Zierax/fl-studio-mcp](https://github.com/Zierax/fl-studio-mcp) and is an independent implementation, not an official fix or a drop-in replacement for that project.

**Scope:** read saved FLP patterns/channels/arrangements with PyFLP; read/write MIDI; prepare a Piano Roll script; capture a current Piano Roll through a native script dialog; append notes to the current Piano Roll. This is not a persistent or real-time DAW connection. The MCP server itself does not operate FL's UI or automatically extract dialog titles. A capable UI agent and suitable desktop access are separate requirements.

## Evidence and limits

- Observed on Windows 10 and FL Studio **21.2.3.4004**: 104 native notes read, a 33-note script written/read back; and 137 notes captured, a further 33 appended, 170 read back. A separate UI agent triggered the latter operations. This is one machine, not a compatibility guarantee.
- Snapshot titles can be truncated by the accessibility interface. The decoder rejects missing terminators and inconsistent note counts. The current encoding supports up to 36 distinct values per attribute and has no pagination. A dialog title can expose note data to local accessibility clients.
- The append command compares pitch, start and length against the snapshot before applying. It preserves existing notes on successful append; rollback and undo have not been exhaustively verified. Apply readback checks pitch/time/length, not all expressive attributes.
- Snapshot mode includes 15 native note attributes; MIDI alone cannot represent every FL-specific property. Saved FLP inspection only reflects saved state and uses an unofficial parser. Read warnings returned by that tool.
- No playback, tempo, mixer, master, or virtual MIDI clock setup is required. The original community project's JSON/MIDI bridge is not used.

## Installation

Python 3.12 and FL Studio 21.2.3.4004 were used for development. From this repository in PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe install.py --scripts-dir 'C:\YOUR_FL_USER_DATA\Settings\Piano roll scripts'
```

Find your actual user data folder in FL Studio's File settings. Existing files of the same names are copied to `collab/backups/` before replacement. Do not point the installer at FL's system script directory. Files in `collab/state/` and `collab/backups/` may contain music: keep them private.

Register `recovery/mcp_server.py` with your MCP client, setting its Python command to this repository's `.venv\Scripts\python.exe`, its working directory to `recovery`, and the environment variable `FL_STUDIO_PIANO_ROLL_SCRIPTS` to the **same** script directory. For Codex, an example user `config.toml` entry (replace both paths) is:

```toml
[mcp_servers.fl21_collab]
command = 'C:\YOUR_REPOSITORY\.venv\Scripts\python.exe'
args = ['C:\YOUR_REPOSITORY\recovery\mcp_server.py']
cwd = 'C:\YOUR_REPOSITORY\recovery'
env = { FL_STUDIO_PIANO_ROLL_SCRIPTS = 'C:\YOUR_FL_USER_DATA\Settings\Piano roll scripts' }
```

Restart the client if necessary. This package does not install or configure a UI automation plugin and does not guarantee your client has one.

## Manual workflow

1. Open the target Pattern/channel Piano Roll. Select **Tools → Scripts → Codex_Collab**. The initial command displays a compressed read-only snapshot in its dialog title. A separately configured UI agent can read that title and pass the complete `CODEX_SNAPSHOT_V3 ... CODEX_END` text to `collab.snapshot_store.store_snapshot`. Cancel or accept the dialog to close it. `Ctrl+Alt+Y` reruns the last script; ensure it is `Codex_Collab` before using it.
2. `fl21_read_native_snapshot(path)` reads a stored snapshot. `fl21_prepare_snapshot_append(snapshot_path, notes, description)` installs an append command; note objects use `key`, `beat`, `duration`, `velocity`, with beats in quarter notes. Positions must begin at or after the current score's end. Alternatively capture via FL's **File → Copy to MIDI clipboard**, save the standard MIDI to a file, and use `fl21_prepare_current_append`.
3. Run `Codex_Collab` again and accept. A successful native script reports `CODEX_APPLY_OK`; prepared command files alone do not demonstrate an edit. Review the result and save to a separate project copy. The script offers an undo checkbox for the prepared candidate, but this undo path has not been independently verified on FL.

The agent must obtain and decode the title itself: this repository contains no automatic UI bridge. Actual note writing needs execution inside FL. For larger patterns use MIDI export or a saved project until snapshot pagination exists.

## Attribution and license

Code in this repository is released under GPL-3.0-or-later; see [LICENSE](LICENSE). [PyFLP](https://github.com/demberto/PyFLP) is GPL-3.0-or-later and is installed as a dependency, not bundled. [Zierax/fl-studio-mcp](https://github.com/Zierax/fl-studio-mcp) is MIT licensed and informed the investigation; its code is not included in this distribution. FL Studio is a product of Image-Line; this project is unaffiliated.
