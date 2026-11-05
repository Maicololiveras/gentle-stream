# Play a selected playlist continuously

Continuous playback is opt-in and owned by the background player, not by UI polling. It starts **from the selected song**, plays one complete 44-bar composition per song, advances in list order, and wraps. Detaching a client leaves the sequence running; restarting the daemon does not restore it.

## UI integration (T3)

Both `Player` and `PlayerClient` expose:

```python
player.set_playlist(styles, start_index=selected_index, name=display_name, continuous=True)
player.play()
# Later:
player.set_continuous(False)
```

- `styles` is a nonempty `Sequence[Style]` snapshot, not a storage object or file. `start_index=0`, `name=""`, and `continuous=False` are the defaults. Indices are zero-based; booleans are not indices.
- Configuration preserves pause/play state. Explicitly call `play()` when enabling from the selected UI entry.
- Show audible song information from `player.now`, **not** `player.style` or the top-level playlist index. The latter describe selected/render-ahead state.
- `next()` advances exactly one entry in continuous mode, even when the producer has already buffered the next song. Repeated presses advance once each. Outside continuous mode, Next retains its existing same-mood variation behavior.
- Ordinary `set_style(style)` leaves playlist rotation and retains its existing buffered style-change behavior. A normal newly generated mood should use that method.
- Disable changes future scheduling without clearing buffered audio, stopping playback, or restarting the audible song. An already rendered song boundary may still be heard; subsequent forms no longer rotate. Re-enabling without reconfiguration continues the configured snapshot. To enable **from the UI selection**, call `set_playlist(..., continuous=True)` again instead.

Empty queues, invalid indices/styles/flags, and missing or corrupt voice caches reject the entire request before active state changes. All songs' saved voice caches are loaded before replacing the sequence. Advancement uses resident clips only; it does not call models, speech synthesis, storage, or cache loaders. The existing literal `agrega frases` opt-in remains unchanged.

## State and wire additions

Existing fields remain available. Additive fields default safely when connecting to an older daemon:

| Field | Meaning | Old daemon default |
| --- | --- | --- |
| `continuous` | Future automatic scheduling enabled | `False` |
| `playlist_name` | Configured display identity | `None` |
| `playlist_index` | Selected/render-ahead index | `None` |
| `now.playlist_name` | Identity attached to consumed PCM | `None` |
| `now.playlist_index` | Index attached to consumed PCM | `None` |

Top-level selection may change before `style` is rendered; `style` may change before `now.style` becomes audible. Buffered chunks retain their original metadata, including after a manual style change. Do not treat a display name as a durable storage identifier.

```json
{"cmd":"set_playlist","styles":[{"name":"Selected","bpm":90}],"start_index":0,"name":"Evening","continuous":true}
{"cmd":"set_continuous","enabled":false}
```

Success returns the existing `{"ok":true,"state":...}` envelope. Failure returns `{"ok":false,"error":"bad request: ..."}`; `PlayerClient` raises `PlayerError`. Playlist wire styles use the existing Style normalizer, but reject supplied fields that would require normalization instead of silently repairing them. Existing single-style wire normalization is unchanged. Old daemons reject the new commands normally; the UI should show the error rather than imply continuous playback was enabled.

## Audio boundary and pause diagnostics

The producer serializes rendering and controls with its existing render lock. The callback only consumes chunks, applies gain, and records audible metadata under the existing short queue lock; it performs no cache loading or synthesis. Natural transitions keep the engine accumulation/master-chain tails and smoothing. Manual Next retains the existing short crossfade. Paused callbacks stop consuming after the existing short de-click fade; elapsed time and UI polls do not advance audible selection.

S3 (delayed pause) is **not resolved by this sequencing change**. A deterministic device-free Windows output test demonstrates that a successful pause response and subsequent silent callbacks do not retract PCM already submitted downstream. `WindowsPCMStream` sends raw PCM; the Windows supervisor queues up to four 8192-byte chunks before FFplay, with additional pipe/player buffering possible. There is no pause/flush control channel. The test proves this pipeline mechanism, not real speaker latency. Follow-up work needs separately authorized edits to `windows_audio.py`, `_windows_output_host.py`, and their transport tests; do not promise zero hardware latency.

## Verification scope

`tests/test_continuous_playback.py` covers complete-form order/wrap, selection, atomic rejection/cache preparation, resident voice advancement, audible/render-ahead metadata, pause, Next at buffered boundaries, concurrent producer controls, old-daemon defaults, and unchanged off-mode audio. The daemon test covers isolated fake-output detach/reconnect. No real devices, speech/model calls, downloads, or production player interaction are required. Public CLI help and toolbar integration remain T3-owned.
