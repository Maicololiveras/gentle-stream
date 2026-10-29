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
