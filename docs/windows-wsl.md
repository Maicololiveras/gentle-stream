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

Play/pause, volume, next, mood changes and detach keep their existing behavior.
A paced writer limits audio buffering; output-device latency may still delay a
control slightly. A Windows supervisor owns FFplay and closes it on input EOF or
failure. It does not use a Linux PID to kill a Windows process or kill other apps.
An output failure is reported in the player log and `ctl status`; no silent
fallback or automatic restart is performed.

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
