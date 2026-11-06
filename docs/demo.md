# Watch the playlist and mood demo

[Play the captioned MP4](assets/demo.mp4) · [Return to the README](../README.md)

This 2:35 Windows Terminal recording shows the *captured* version of gentle-stream: browsing the built-in and saved lists, entering an electrohouse mood, saving the audible style, and returning to its playlist. It does **not** demonstrate the later Appearance settings; use [Appearance](appearance.md) for those controls. The app generates a new composition from stored parameters; it does not save or replay an audio recording.

The soundtrack was synthesized specifically for this demo: original minor-key notes, kick, bass and percussion, with no third-party samples. Spanish captions carry the walkthrough; the public file has **no voiceover**. A short interval containing an unrelated terminal and a personal path was cut from the footage before publication. The source recording and the separate voiced draft remain local, not in the repository.

## Walkthrough and transcript

| Time | What you see | Caption text |
| :--- | :--- | :--- |
| 0:00 | Start and spectrum | Esto es gentle stream: música generativa en tiempo real, desde tu terminal. |
| 0:13 | Open `Playlist` | Con Playlist abro la biblioteca. La lista predeterminada trae estilos listos para escuchar. |
| 0:28 | Browse saved prompts | También puedo recorrer mis prompts guardados y elegir un tema sin volver a consultar al modelo. |
| 0:45 | Enter a mood while playing | Mientras suena, describo un mood nuevo. La música actual no se interrumpe durante la interpretación. |
| 1:02 | Request a dark electrohouse style | Probemos electrohouse épico y oscuro. La barra muestra el estado mientras se prepara la siguiente composición. |
| 1:23 | New style becomes audible | Cuando está listo, escuchamos el nuevo estilo. Las barras del espectro acompañan lo que se reproduce. |
| 1:39 | Playback and repeat controls | Los controles centrales permiten pausar, volver y avanzar. Repetir lista recorre los temas guardados. |
| 1:52 | Save the audible style | Para conservar el sonido actual, pulso Guardar, elijo un nombre y creo una playlist nueva. |
| 2:11 | Select the new playlist | Después, la biblioteca muestra el estilo guardado. Al seleccionarlo, vuelve a generarse música a partir de sus parámetros. |
| 2:23 | Closing guidance | Instalación y ajustes, en el README. ¡Disfrutá! |

Use `p` to open playlists, `s` to save the audible style, `/` to enter a mood, `c` to repeat the chosen list, and `Space` to pause or resume. The text shown in the recording includes model usage from that captured session; playing this MP4 does not call a model. For exact current keys, the model picker and the settings shortcut, see [Playlist controls](playlist-controls.md) and [Appearance](appearance.md).

## Install and verify

1. Follow the [README quick start](../README.md#get-started) for Linux/macOS or [WSL setup](windows-wsl.md) for the Windows-hosted path. PortAudio is needed for native audio; a Gentle Shell provider is needed only when interpreting a new mood.
2. Start the player without `--mood` to hear the default procedural composition without a model call.
3. Try `p`, `/`, `s` and `F2`. Saved styles are parameters, not WAV/MP3 files.
4. Before contributing, run `uv run pytest` in an isolated development environment; [CI coverage](ci.md) explains its platform checks and performance-test exclusion.
