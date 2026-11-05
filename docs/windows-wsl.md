# Use Windows Gentle Shell from Ubuntu

This local adapter connects the Ubuntu gentle-stream installation to maicolj's
existing Windows Gentle Shell, using its Windows configuration. No Linux Gentle
Shell installation or credential copying is needed.

## Launch from Windows

```powershell
wsl -d Ubuntu -u maicolj -- /home/maicolj/.local/share/gentle-stream/venv/bin/gentle-stream --gentle-shell /mnt/d/Dev/Personal/gentle-stream/scripts/gentle-shell-windows
```

The adapter must be executable in WSL. If the checkout does not preserve its
executable bit, run once:

```powershell
wsl -d Ubuntu -u maicolj -- chmod +x /mnt/d/Dev/Personal/gentle-stream/scripts/gentle-shell-windows
```

Mood requests use the Windows installation's configured model/provider and can
incur normal model usage. Launching without a mood does not request a model.

## Optional native Windows audio

PortAudio/sounddevice remains the default. To bypass WSLg/PulseAudio for playback,
select `windows` when starting a **new** player. The music still generates live;
FFplay receives the same stereo PCM, including any requested integrated voice.
No prerecorded track, model call or speech tool is used by the output backend.

From Ubuntu (replace the executable paths with your own installed paths):

```bash
gentle-stream ctl stop
GENTLE_STREAM_AUDIO_OUTPUT=windows \
GENTLE_STREAM_WINDOWS_PYTHON='/mnt/c/path/to/python.exe' \
GENTLE_STREAM_WINDOWS_FFPLAY='/mnt/c/path/to/ffplay.exe' \
gentle-stream --gentle-shell /mnt/d/Dev/Personal/gentle-stream/scripts/gentle-shell-windows
```

Both executables must be **Windows** programs, not Linux Python/FFplay. No packages
are installed automatically. Native Python uses only its standard library; a
checkout's existing `.voice-venv/Scripts/python.exe` is tried automatically, then
`python.exe` on PATH (not the Microsoft Store alias). FFplay is discovered through
`ffplay.exe` on PATH or the explicit variable above. WSL interop must be enabled.
The isolated voice environment is optional; Windows audio does not import Edge TTS.

**Pause cuts the owned output queue before acknowledging success.** The Windows
supervisor terminates and waits for its own FFplay child, discarding that child's
queued PCM. While paused, the stream makes no callbacks or PCM submissions.
Play/toggle resumes with a fresh owned FFplay child and the next retained Player
samples, preserving volume, position and playlist selection. It does not restart
the music daemon, clear the playlist, replay discarded output, change system
volume, or control other audio applications. Resume may take time to open the
native device again; a hard output cut can click. The default sounddevice path
retains its existing short gain fade.

This is an **owned-process stop boundary, not zero speaker latency**: Windows,
device and hardware buffers may still have an audible tail. Player position and
`now` describe callback-consumed PCM, not a measurement at the speakers. Up to an
in-flight callback block can have been consumed before the cut and is not rewound.
Device-free tests prove the owned child stopped before acknowledgment, including
under pipe backpressure; they do not measure acoustic latency.

The private transport uses bounded frames (at most 8192 PCM bytes), one outstanding
PCM acknowledgment, and pause/resume acknowledgments. Each pipe write has a
two-second deadline and each acknowledgment a three-second deadline. Invalid or
truncated messages and output failures fail visibly through the control call,
player log and `ctl status`; no silent fallback or automatic recovery is performed.
All process operations run outside the audio callback. EOF/failure still cleans up
the owned native child, using its native Popen handle rather than a Linux PID,
global process search or taskkill. The protocol accepts no paths or commands.

`gentle-stream ctl status` adds `audio_output: "windows"` and
`audio_output_error` for this mode. `output_underflows` is **null**, because this
transport cannot measure Windows device underflows. `underruns` still measures
the application's sample queue, not speaker quality. `backend` in daemon state
continues to describe procedural/sampled synthesis, not the output device.

To return to the normal output, stop the player and launch with the output
variable unset (or set it to `sounddevice`). Selecting a different output while
an existing player runs returns an error instead of stopping/replacing it.
A clean pre-rendered Windows test alone does not prove a WSLg root cause or
real-time stability; verify long playback and pause/resume on your own device.

## Adapter details

- Requires WSL Windows executable interop and Python 3 on Ubuntu's PATH.
- Reads only the version pointer `C:\Users\maicolj\.gentle-shell-bundle\current`.
- Executes bundled `runtime/node-24.21.0/node.exe` with the selected version's
  `node_modules/gentle-pi/bin/gentle-shell.mjs` as a Windows path.
- Forwards all arguments (including `--`), standard streams, and exit status
  directly. Does not invoke `cmd`, `eval`, or the npm shell shim.
- Does not read or copy credentials, edit profiles, or replace global launchers.
- The home and Node version are local-machine-specific; if the runtime changes,
  update this adapter rather than installing another Gentle Shell in Linux.

**Cancellation limitation:** killing the Linux process/process group does not
guarantee that Windows descendant processes stop. A cancelled or timed-out mood
request may continue running on Windows; cancellation is not a billing guarantee.

## Verify without a model call

From Ubuntu, list models through the adapter:

```bash
/mnt/d/Dev/Personal/gentle-stream/scripts/gentle-shell-windows -- --no-mcp --no-skill-registry --list-models
```

The isolated stdlib test uses a fake Node, not the Windows installation:

```bash
/home/maicolj/.local/share/gentle-stream/venv/bin/python -B -m unittest discover -s /mnt/d/Dev/Personal/gentle-stream/tests -p test_windows_shell_adapter.py
```
