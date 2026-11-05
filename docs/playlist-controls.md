# Save and repeat a playlist from your selected song

Use the existing Textual Playlist panel and the rose command strip directly above the mood input. No browser or separate player is needed. All keyboard shortcuts remain available; Tab focuses buttons, and tooltips describe actions and shortcuts. `↻ off` / `↻ on` and play/pause glyphs show state without relying on color. Narrow terminals scroll the command strip horizontally; focusing a button brings it into view. At 24 rows or fewer, tighter panel spacing keeps the spectrum, state, model and status inside the panel. Long status/model lines have full hover tooltips.

## Quick path

1. Press **s** (or the **💾** button) to save the currently audible song. Enter a song name and choose **Saved prompts**, **New playlist…**, or an existing named playlist. New reveals the playlist name field. Enter or **Save** commits both the new group and song together.
2. Open **Playlist** (**p** or **☷**). Under **My playlist**, open **Saved prompts** or a named group. Songs appear in the same panel. **< My playlists** / Backspace returns to groups; Left/Right switches the My/Default tabs.
3. Highlight a song, then choose **Repeat from selection** or press **c**. Playback begins at that song, advances after each complete composition, and wraps in alphabetical display order. **Default playlist** works the same way but cannot be edited.
4. Click **↻ on** or press **c** outside the input to turn rotation off. Current audio is not cut or restarted. Already-buffered transitions may still be heard.

Clicking a song or pressing Enter normally applies only that style and exits continuous mode. That selection retains its full list snapshot and index, so the global **↻ off** button can start continuous playback predictably afterward. With no selection, it asks you to select a song first. An empty group cannot start rotation. A newly interpreted mood also exits rotation through ordinary style application.

## Saving safely

- Save captures `player.now.style` when the dialog opens, not render-ahead state or a pending mood.
- The same song title replaces only inside the chosen group. Identical titles in other groups remain independent.
- Saved prompts remain in `presets.json`. Named playlists use the separate versioned `playlist-library.json` beside it, under `$XDG_CONFIG_HOME/gentle-stream` (default `~/.config/gentle-stream`). Nothing is migrated.
- **d** / Delete removes only the highlighted saved song, never a whole group. Deleting the final song retains its named group. Built-in songs are read-only.
- Validation and unreadable-file errors remain visible; failed saves keep your entered fields and do not dismiss the dialog. Repair or move a corrupt file before saving to it again.

## Playback and model feedback

The strip mirrors existing play/pause, Next, mood, model, save, playlist, and volume actions, plus continuous playback. The model button shows the selected model, or the honest Gentle Shell default when none is selected; long IDs are elided with their full value in the tooltip. The model line retains session usage.

Audible playlist/song position is read from `player.now`, not the producer's future index. Continuous playback belongs to the daemon and continues after **b** detaches the UI. No model or speech-generation calls are made to apply saved styles or advance a playlist. **q** still stops playback. An older daemon rejecting continuous commands produces an error instead of an assumed success.

See [runtime semantics](continuous-playback.md) and [storage format](named-playlists.md) for API and buffering details.
