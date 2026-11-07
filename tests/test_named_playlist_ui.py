"""Public Textual flows; no audio devices, generators, or live player."""
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest
from textual.widgets import Button, Input, OptionList, Select

from gentle_stream.app import ModelPicker, PresetPicker, SaveDialog, StreamApp
from gentle_stream.appearance_ui import SettingsScreen
from gentle_stream.client import PlayerError
from gentle_stream.playlist_library import PlaylistLibrary
from gentle_stream.presets import PresetStore
from gentle_stream.style import DEFAULT, Style


@pytest.fixture
def ui(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    store = PresetStore(tmp_path / "presets.json")
    library = PlaylistLibrary(tmp_path / "playlist-library.json")
    player = Mock(now=SimpleNamespace(style=DEFAULT, piece=1, bar=0,
                                     playlist_name="Audible", playlist_index=1),
                  playing=True, volume=.8, continuous=False,
                  playlist_name="Future", playlist_index=9)
    player.spectrum.side_effect = lambda width: np.zeros(width)
    player.set_volume.side_effect = lambda value: setattr(player, "volume", value)
    player.toggle.side_effect = lambda: setattr(player, "playing", not player.playing)
    player.set_continuous.side_effect = lambda value: setattr(player, "continuous", value)
    shell = Mock(model=None)
    shell.list_models.return_value = ["provider/chosen-model"]
    app = StreamApp(player, shell, presets=store)
    app.library = library
    return app, player, shell, store, library


def shown(app, selector):
    return str(app.screen.query_one(selector).render())


@pytest.mark.asyncio
async def test_pause_resume_focus_does_not_invert_button_background(ui):
    app, player, shell, _, _ = ui
    async with app.run_test(size=(80, 24)) as pilot:
        button = app.query_one("#play", Button)
        assert await pilot.click("#play")
        await pilot.hover("#spectrum")
        await pilot.pause(button.active_effect_duration + .05)
        await pilot.wait_for_scheduled_animations()
        assert app.focused is button and button.can_focus
        assert player.playing is False and str(button.label) == "▶"
        assert not button.styles.text_style.reverse
        assert not button.styles.text_style.underline
        assert button.styles.text_style.bold
        assert button.styles.border_left[0] in ("", "none")
        assert button.styles.border_right[0] in ("", "none")
        await pilot.press("enter")
        await pilot.pause(button.active_effect_duration + .05)
        await pilot.wait_for_scheduled_animations()
        assert player.playing is True and str(button.label) == "⏸"
        assert app.focused is button
        assert not button.styles.text_style.reverse
        assert not button.styles.text_style.underline
        assert button.styles.border_left[0] in ("", "none")
        assert button.styles.border_right[0] in ("", "none")
        assert player.toggle.call_count == 2
        shell.interpret_with_usage.assert_not_called()


@pytest.mark.asyncio
async def test_transport_double_clicks_are_not_debounced(ui):
    app, player, shell, store, library = ui
    async with app.run_test(size=(80, 24)) as pilot:
        assert await pilot.click("#play", times=2)
        await pilot.pause()
        assert player.toggle.call_count == 2 and player.playing is True
        assert str(app.query_one("#play", Button).label) == "⏸"
        assert await pilot.click("#next", times=2)
        await pilot.pause()
        assert player.next.call_count == 2
        assert await pilot.click("#previous", times=2)
        await pilot.pause()
        assert player.previous.call_count == 2
        assert not store.path.exists() and not library.path.exists()
        shell.interpret_with_usage.assert_not_called()


@pytest.mark.asyncio
async def test_toolbar_background_is_black_with_and_without_keyboard_focus(ui):
    app, player, shell, _, _ = ui
    async with app.run_test(size=(80, 24)) as pilot:
        for button in app.query("#commands Button"):
            assert button.styles.background.hex == "#000000", button.id
            button.focus()
            await pilot.pause()
            assert app.focused is button
            assert button.styles.background.hex == "#000000", button.id
            assert not button.styles.text_style.reverse
            assert not button.styles.text_style.underline
            assert button.styles.border_left[0] in ("", "none")
            assert button.styles.border_right[0] in ("", "none")
        player.toggle.assert_not_called()
        shell.interpret_with_usage.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("size", [(60, 20), (80, 24)])
async def test_toolbar_clicks_keyboard_and_geometry(ui, size):
    app, p, shell, store, _ = ui
    async with app.run_test(size=size) as pilot:
        panel, strip, mood = [app.query_one(s) for s in ("#panel", "#commands", "#mood")]
        assert panel.region.bottom <= strip.region.y < strip.region.bottom <= mood.region.y
        assert app.query_one("#spectrum").region.height >= 5
        for selector in ("#state", "#model", "#status"):
            assert app.query_one(selector).region.bottom <= panel.content_region.bottom
        for id, icon in {"previous": "⏮", "play": "⏸", "next": "⏭", "mood-command": "✎",
                         "save-command": "💾", "playlist-command": "☷", "continuous": "↻  off"}.items():
            assert str(app.query_one(f"#{id}", Button).label) == icon
        for id in ("previous", "play", "next", "mood-command", "model-command", "save-command", "playlist-command",
                   "continuous", "quieter", "louder"):
            button = app.query_one(f"#{id}", Button)
            assert button.can_focus and button.tooltip
            await pilot.wait_for_scheduled_animations()  # finish focus scrolling from the previous click
            button.scroll_visible(animate=False, immediate=True)
            await pilot.pause()
            assert await pilot.click(f"#{id}", offset=(button.size.width // 2, 0)), id
            await pilot.pause()
            if id == "model-command":
                assert isinstance(app.screen, SettingsScreen)
                await app.screen.submit('model')
                assert isinstance(app.screen, ModelPicker)
                await pilot.pause()
                await pilot.press("down", "enter")
                await pilot.pause()
                await pilot.press("escape")
                await pilot.pause()
                assert "chosen-model" in str(app.query_one("#model-command", Button).label)
                model_button = app.query_one("#model-command", Button)
                assert model_button.content_region.width >= len(str(model_button.label))
                assert "provider/chosen-model" in str(app.query_one("#model-command").tooltip)
            elif id == "save-command":
                assert isinstance(app.screen, SaveDialog)
                await pilot.press("escape")
            elif id == "playlist-command":
                assert isinstance(app.screen, PresetPicker)
                await pilot.press("escape")
        p.toggle.assert_called_once()
        p.next.assert_called_once()
        p.previous.assert_called_once()
        assert p.set_volume.call_count == 2 and p.volume == .8
        p.set_playlist.assert_not_called()
        assert "Select a song" in shown(app, "#status")
        await pilot.press("escape", "space", "n", "minus", "plus")
        assert p.toggle.call_count == 2 and p.next.call_count == 2
        await pilot.press("escape", "tab")
        assert isinstance(app.focused, Button)
        (store.path.parent / f"toolbar-{size[0]}x{size[1]}.svg").write_text(app.export_screenshot())
        shell.interpret_with_usage.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("size", [(60, 20), (80, 24), (100, 30), (200, 46)])
async def test_volume_meter_lives_between_controls_without_moving_transport(ui, size):
    app, player, shell, store, library = ui
    player.volume = 0
    async with app.run_test(size=size) as pilot:
        await pilot.pause()
        strip = app.query_one("#commands")
        center = app.query_one("#transport")
        right = app.query_one("#commands-right")
        meter = app.query_one("#volume-meter")
        assert strip.styles.background.hex == "#000000"
        assert strip.region.height == 1
        assert strip.region.contains_region(center.region)
        assert abs((center.region.x * 2 + center.region.width) -
                   (strip.region.x * 2 + strip.region.width)) <= 1
        assert [child.id for child in right.children] == ["quieter", "volume-meter", "louder", "model-command"]
        assert meter.region.width == 13 and meter.region.height == 1
        model = app.query_one('#model-command', Button)
        assert meter.region.right <= model.region.x
        if size[0] >= 100:
            assert model.region.width <= 14  # Default label must not push the gauge left.
        assert strip.region.contains_region(meter.region)
        assert meter.render().plain == "▱" * 8 + " 0%"
        at_zero = meter.render().plain
        state = shown(app, "#state")
        assert "Playing" in state and "piece 1" in state and "bar 1" in state
        assert "Audible #2" in state and "vol " not in state
        assert "Gentle Shell default" in shown(app, "#model")
        for selector in ("#details", "#mood-line"):
            assert str(app.query_one(selector).tooltip) == shown(app, selector)
        assert app.query_one("#spectrum").region.height >= 5
        for selector in ("#state", "#model", "#status"):
            assert app.query_one(selector).region.bottom <= app.query_one("#panel").content_region.bottom
        louder = app.query_one("#louder", Button)
        louder.scroll_visible(animate=False, immediate=True)
        await pilot.pause()
        assert await pilot.click("#louder")
        await pilot.pause()
        assert player.volume == .05 and meter.render().plain == "▱" * 8 + " 5%"
        assert meter.render().plain != at_zero
        await pilot.press("plus", "minus", "down", "up")
        await pilot.pause()
        assert player.volume == .05 and meter.render().plain == "▱" * 8 + " 5%"
        assert player.set_volume.call_count == 5
        player.toggle.assert_not_called()
        player.next.assert_not_called()
        player.previous.assert_not_called()
        shell.interpret_with_usage.assert_not_called()
        assert not store.path.exists() and not library.path.exists()


@pytest.mark.asyncio
async def test_wide_window_keeps_transport_visible_and_fills_spectrum(ui):
    app, player, shell, _, _ = ui
    player.spectrum.side_effect = lambda count: np.ones(count)
    async with app.run_test(size=(200, 46)) as pilot:
        await pilot.pause()
        strip = app.query_one("#commands")
        center = app.query_one("#transport")
        spectrum = app.query_one("#spectrum")
        assert 0 <= strip.region.y < strip.region.bottom <= app.screen.size.height
        assert center.region.width == 15 and strip.region.contains_region(center.region)
        assert abs((center.region.x * 2 + center.region.width) - (strip.region.x * 2 + strip.region.width)) <= 1
        assert spectrum.region.width > 100
        assert all(len(line) == spectrum.region.width for line in spectrum.render().plain.splitlines())
        assert not app.query_one("#mood").region.y >= app.screen.size.height
        shell.interpret_with_usage.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("size", [(60, 20), (80, 24), (120, 30)])
async def test_centered_transport_and_independent_side_groups(ui, size):
    app, p, shell, store, _ = ui
    shell.model = "provider/" + "long-model-" * 20
    p.playlist_index = None
    async with app.run_test(size=size) as pilot:
        await pilot.pause()
        strip = app.query_one("#commands").content_region
        left = app.query_one("#commands-left")
        center = app.query_one("#transport")
        right = app.query_one("#commands-right")
        assert [b.id for b in left.query(Button)] == ["save-command", "continuous", "mood-command", "playlist-command"]
        assert [b.id for b in center.query(Button)] == ["previous", "play", "next"]
        assert [b.id for b in right.query(Button)] == ["quieter", "louder", "model-command"]
        assert abs((center.region.x * 2 + center.region.width) - (strip.x * 2 + strip.width)) <= 1
        assert left.region.right <= center.region.x < center.region.right <= right.region.x
        assert all(center.region.contains_region(b.region) for b in center.query(Button))
        assert str(app.query_one("#previous", Button).label) == "⏮"
        assert "previous" in str(app.query_one("#previous").tooltip).lower()
        assert "long-model" in str(app.query_one("#model-command", Button).label)
        assert shell.model in str(app.query_one("#model-command").tooltip)
        await pilot.click("#previous")
        p.previous.assert_not_called()
        assert "Select a song in Playlist" in shown(app, "#status")
        assert app.is_running
        if size[0] in (80, 120):
            (store.path.parent / f"centered-{size[0]}.svg").write_text(app.export_screenshot())


@pytest.mark.asyncio
@pytest.mark.parametrize("size", [(60, 20), (80, 24), (120, 30)])
async def test_paused_play_is_blue_without_shifting_centered_transport(ui, size):
    app, player, shell, store, library = ui
    async with app.run_test(size=size) as pilot:
        strip = app.query_one("#commands")
        transport = app.query_one("#transport")
        play = app.query_one("#play", Button)
        before = transport.region
        assert await pilot.click("#play")
        await pilot.pause()
        assert player.playing is False and str(play.label) == "▶"
        assert play.styles.color.hex.lower() == "#00a6ed"
        assert play.styles.background.hex == strip.styles.background.hex == "#000000"
        assert play.region.width == 5 and transport.region == before
        play.focus()
        await pilot.pause()
        assert play.styles.color.hex.lower() == "#00a6ed"
        assert await pilot.click("#play")
        await pilot.pause()
        assert player.playing is True and str(play.label) == "⏸"
        assert play.styles.background.hex == "#000000"
        assert play.region.width == 5 and transport.region == before
        assert player.toggle.call_count == 2
        assert not store.path.exists() and not library.path.exists()
        shell.interpret_with_usage.assert_not_called()


@pytest.mark.asyncio
async def test_save_new_existing_and_legacy_snapshot_replacement(ui):
    app, p, shell, store, library = ui
    async with app.run_test() as pilot:
        await pilot.press("s")
        await pilot.pause()
        app.screen.query_one("#save-name", Input).value = "Same"
        await pilot.press("enter")
        legacy = store.path.read_bytes()
        await pilot.press("s")
        await pilot.pause()
        app.screen.query_one("#save-destination", Select).value = "new"
        await pilot.pause()
        app.screen.query_one("#save-playlist", Input).value = "[rose] Night"
        app.screen.query_one("#save-name", Input).value = "Same"
        p.now.style = Style(name="Future")  # save uses snapshot from opening dialog
        await pilot.click("#save-submit")
        await pilot.pause()
        assert library.get("[rose] Night", "Same").style == store.get("Same").style
        assert store.path.read_bytes() == legacy
        await pilot.press("s")
        await pilot.pause()
        await pilot.click("#save-destination")  # SelectCurrent is the actual mouse target
        await pilot.press("end", "enter")
        await pilot.pause()
        assert not app.screen.query_one("#save-playlist").display
        app.screen.query_one("#save-name", Input).value = "same"
        await pilot.click("#save-submit")
        await pilot.pause()
        assert len(library.list()) == 1
        assert library.get("[rose] Night", "same").style.name == "same"
        assert library.get("[rose] Night", "same").style.bpm == p.now.style.bpm
        assert "Replaced" in shown(app, "#status")
        assert store.path.read_bytes() == legacy
        shell.interpret_with_usage.assert_not_called()
        shell.list_models.assert_not_called()


@pytest.mark.asyncio
async def test_enter_after_selecting_existing_playlist_saves_the_song(ui):
    app, player, shell, store, library = ui
    library.save("Night", "Existing", DEFAULT)
    before = library.path.read_bytes()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("s")
        await pilot.pause()
        app.screen.query_one("#save-name", Input).value = "Fresh"
        await pilot.click("#save-destination")  # SelectCurrent receives the pointer event
        await pilot.press("end", "enter")  # select the existing group using the public picker
        await pilot.pause()
        assert app.screen.query_one("#save-destination", Select).value == "group-0"
        await pilot.press("enter")  # dialog says Enter saves, even after a Select choice
        await pilot.pause()
        assert library.get("Night", "Fresh") is not None
        assert library.get("Night", "Existing") is not None
        assert library.path.read_bytes() != before
        assert not store.path.exists()
        assert "Saved" in shown(app, "#status")
        player.toggle.assert_not_called()
        shell.interpret_with_usage.assert_not_called()


@pytest.mark.asyncio
async def test_keyboard_only_existing_playlist_selection_and_enter_save(ui):
    app, player, shell, store, library = ui
    library.save("Night", "Existing", DEFAULT)
    before = library.path.read_bytes()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("s")
        await pilot.pause()
        app.screen.query_one("#save-name", Input).value = "Keyboard"
        await pilot.press("tab")
        destination = app.screen.query_one("#save-destination", Select)
        assert destination.has_focus_within
        assert "Enter opens" in shown(app, "#save-status")
        assert "Enter again saves" in shown(app, "#save-status")
        await pilot.press("enter", "down", "down", "enter")
        await pilot.pause()
        assert destination.value == "group-0"
        await pilot.press("enter")
        await pilot.pause()
        assert library.get("Night", "Keyboard") is not None
        assert library.get("Night", "Existing") is not None
        assert library.path.read_bytes() != before
        assert not store.path.exists()
        assert "Saved" in shown(app, "#status")
        player.toggle.assert_not_called()
        shell.interpret_with_usage.assert_not_called()


@pytest.mark.asyncio
async def test_save_corrupt_and_validation_errors_keep_fields(ui):
    app, p, shell, store, library = ui
    library.path.write_text("{oops")
    async with app.run_test() as pilot:
        await pilot.press("s")
        await pilot.pause()
        app.screen.query_one("#save-destination", Select).value = "new"
        await pilot.pause()
        app.screen.query_one("#save-name", Input).value = "Keep me"
        app.screen.query_one("#save-playlist", Input).value = "   "
        await pilot.click("#save-submit")
        assert "empty" in shown(app, "#save-status").lower()
        app.screen.query_one("#save-playlist", Input).value = "Night"
        app.screen.query_one("#save-playlist", Input).focus()
        await pilot.press("enter")
        assert "playlist-library.json" in shown(app, "#save-status")
        assert app.screen.query_one("#save-name", Input).value == "Keep me"
        assert app.screen.query_one("#save-playlist", Input).value == "Night"
        assert library.path.read_text() == "{oops" and not store.path.exists()
        shell.interpret_with_usage.assert_not_called()


@pytest.mark.asyncio
async def test_groups_back_delete_scope_and_continuous_selected(ui):
    app, p, shell, store, library = ui
    store.save("Shared", DEFAULT)
    library.save("Night", "Zulu", Style(bpm=80))
    library.save("Night", "Alpha", Style(bpm=70))
    library.save("Other", "Zulu", Style(bpm=90))
    before = store.path.read_bytes()
    async with app.run_test() as pilot:
        await pilot.press("p")
        await pilot.pause()
        options = app.screen.query_one("#presets", OptionList)
        assert options.option_count == 3
        assert "Saved prompts" in str(options.get_option_at_index(0).prompt)
        await pilot.press("down", "enter")
        await pilot.pause()
        assert "Night" in shown(app, "#presets-breadcrumb")
        assert "Alpha" in str(options.get_option_at_index(0).prompt)
        await pilot.press("down")
        assert await pilot.click("#playlist-loop")
        await pilot.pause()
        songs = library.list_songs("Night")
        p.set_playlist.assert_called_once_with([s.style for s in songs], start_index=1,
                                              name="Night", continuous=True)
        p.play.assert_called_once()
        p.set_style.assert_not_called()
        p.continuous = True
        await pilot.click("#continuous")
        p.set_continuous.assert_called_once_with(False)
        assert p.play.call_count == 1
        await pilot.press("p")
        await pilot.pause()
        await pilot.press("down", "enter")
        await pilot.pause()
        await pilot.press("down", "d")
        assert library.get("Night", "Zulu") is None
        assert library.get("Other", "Zulu") is not None
        assert store.path.read_bytes() == before
        assert await pilot.click("#playlist-back")
        await pilot.pause()
        assert options is not None
        assert app.screen.query_one("#presets", OptionList).option_count == 3
        shell.interpret_with_usage.assert_not_called()
        shell.list_models.assert_not_called()


@pytest.mark.asyncio
async def test_normal_selection_remembers_full_list_for_toolbar_and_errors(ui):
    app, p, shell, store, library = ui
    library.save("[bold]", "[x]", DEFAULT)
    library.save("[bold]", "Z", Style(bpm=90))
    async with app.run_test() as pilot:
        await pilot.press("p")
        await pilot.pause()
        await pilot.press("down", "enter")
        await pilot.pause()
        await pilot.press("down", "enter")
        await pilot.pause()
        p.set_style.assert_called_once_with(library.get("[bold]", "Z").style)
        p.set_playlist.side_effect = PlayerError("old daemon: unknown command")
        await pilot.click("#continuous")
        await pilot.pause()
        assert "old daemon: unknown command" in shown(app, "#status")
        p.play.assert_not_called()
        assert "off" in str(app.query_one("#continuous", Button).label)
        assert "Future" not in shown(app, "#state")
        assert "Audible" in shown(app, "#state")
        p.set_playlist.side_effect = None
        await pilot.press("c")
        p.set_playlist.assert_called_with([s.style for s in library.list_songs("[bold]")],
                                        start_index=1, name="[bold]", continuous=True)
        p.play.assert_called_once()
        shell.interpret_with_usage.assert_not_called()


@pytest.mark.asyncio
async def test_default_continuous_starts_highlighted_and_is_read_only(ui):
    app, p, shell, store, library = ui
    async with app.run_test(size=(60, 20)) as pilot:
        await pilot.press("p")
        await pilot.pause()
        await pilot.press("right", "down", "d")
        assert await pilot.click("#playlist-loop")
        await pilot.pause()
        from gentle_stream.playlists import default_playlist
        styles = sorted(default_playlist(), key=lambda s: s.name.casefold())
        p.set_playlist.assert_called_once_with(styles, start_index=1, name="Default playlist", continuous=True)
        p.play.assert_called_once()
        assert not store.path.exists() and not library.path.exists()
        shell.interpret_with_usage.assert_not_called()


@pytest.mark.asyncio
async def test_flower_marks_existing_and_new_songs_in_all_playlist_views(ui):
    app, player, shell, store, library = ui
    store.save("Legacy", DEFAULT)
    library.save("Test Group", "Before", DEFAULT)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("p", "enter")
        await pilot.pause()
        options = app.screen.query_one("#presets", OptionList)
        assert str(options.get_option_at_index(0).prompt).startswith("🌸  Legacy")
        await pilot.press("backspace", "down", "enter")
        await pilot.pause()
        assert str(options.get_option_at_index(0).prompt).startswith("🌸  Before")
        await pilot.press("escape")
        await pilot.pause()  # Wait for the first modal to dismiss before reopening it.
        library.save("Test Group", "After", Style(bpm=90))
        stored = (store.path.read_bytes(), library.path.read_bytes())
        await pilot.press("p", "down", "enter")
        await pilot.pause()
        options = app.screen.query_one("#presets", OptionList)  # New modal, not the dismissed one.
        assert options.option_count == 2
        assert all(str(options.get_option_at_index(i).prompt).startswith("🌸  ") for i in range(2))
        assert [song.name for song in library.list_songs("Test Group")] == ["After", "Before"]
        await pilot.press("right")
        await pilot.pause()
        assert options.option_count > 2
        assert all(str(options.get_option_at_index(i).prompt).startswith("🌸  ")
                   for i in range(options.option_count))
        assert (store.path.read_bytes(), library.path.read_bytes()) == stored
        player.set_style.assert_not_called()
        shell.interpret_with_usage.assert_not_called()


@pytest.mark.asyncio
async def test_wrapped_named_songs_leave_a_blank_row_between_options(ui):
    app, player, shell, store, library = ui
    mood = "Synthetic energetic rhythm with warm keys and many descriptive words that wrap on a narrow list"
    library.save("Test Group", "First", Style(mood=mood))
    library.save("Test Group", "Second", Style(mood=mood))
    stored = library.path.read_bytes()
    async with app.run_test(size=(80, 30)) as pilot:
        await pilot.press("p", "down", "enter")
        await pilot.pause()
        options = app.screen.query_one("#presets", OptionList)
        rows = [options.render_line(y).text for y in range(options.size.height)]
        first = next(i for i, row in enumerate(rows) if "First" in row)
        second = next(i for i, row in enumerate(rows) if "Second" in row)
        assert second > first + 2  # description spans multiple rows before the next song
        assert any(not row.strip() for row in rows[first + 1:second]), "No visible blank row between songs"
        assert options.option_count == 2
        await pilot.press("down", "enter")
        player.set_style.assert_called_once_with(library.list_songs("Test Group")[1].style)
        assert library.path.read_bytes() == stored and not store.path.exists()
        shell.interpret_with_usage.assert_not_called()


@pytest.mark.asyncio
async def test_default_playlist_songs_have_one_visual_gap_without_changing_selection(ui):
    app, player, shell, store, library = ui
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("p", "right")
        await pilot.pause()
        options = app.screen.query_one("#presets", OptionList)
        from gentle_stream.playlists import default_playlist
        styles = sorted(default_playlist(), key=lambda style: style.name.casefold())
        assert options.option_count == len(styles)
        lines = [options.render_line(y).text for y in range(options.size.height)]
        blank_rows = [line for line in lines if not line.strip()]
        assert blank_rows, "The visible song list has no blank row between adjacent options"
        assert all(options.get_option_at_index(index).id == f"song-{index}"
                   for index in range(options.option_count))
        await pilot.press("down")
        assert options.highlighted == 1
        await pilot.press("enter")
        player.set_style.assert_called_once_with(styles[1])
        assert not store.path.exists() and not library.path.exists()
        shell.interpret_with_usage.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("method,key,button", [("toggle", "space", "play"), ("next", "n", "next"),
                                             ("set_volume", "minus", "quieter")])
@pytest.mark.parametrize("via", ["keyboard", "click"])
async def test_transport_rejections_stay_actionable_without_crashing(ui, method, key, button, via):
    app, p, shell, store, library = ui
    getattr(p, method).side_effect = PlayerError("transport cut unavailable")
    async with app.run_test() as pilot:
        if via == "click":
            app.query_one(f"#{button}").scroll_visible(immediate=True)
            await pilot.pause()
            assert await pilot.click(f"#{button}")
        else:
            await pilot.press(key)
        await pilot.pause()
        assert "transport cut unavailable" in shown(app, "#status")
        assert app.is_running and p.playing and p.volume == .8
        p.close.assert_not_called()
        shell.interpret_with_usage.assert_not_called()


@pytest.mark.asyncio
async def test_empty_group_hint_and_mood_markup_are_literal(ui):
    app, p, shell, store, library = ui
    library.save("Empty", "Gone", DEFAULT)
    library.delete("Empty", "Gone")
    async with app.run_test(size=(60, 20)) as pilot:
        await pilot.press("p")
        await pilot.pause()
        await pilot.press("down", "enter")
        await pilot.pause()
        assert app.screen.query_one("#playlist-loop", Button).disabled
        await pilot.press("c")
        assert "Select a song" in shown(app, "#presets-status")
        p.set_playlist.assert_not_called()
        assert library.list_songs("Empty") == [] and len(library.list()) == 1
        await pilot.press("escape")
        # Keep interpretation pending so the status is observable before any result.
        import threading
        release = threading.Event()
        def interpret(*args):
            release.wait(5)
            return DEFAULT, None
        shell.interpret_with_usage.side_effect = interpret
        await pilot.press("slash")
        app.query_one("#mood", Input).value = "[bold]fog[/bold]"
        await pilot.press("enter")
        try:
            assert "[bold]fog[/bold]" in shown(app, "#status")
        finally:
            release.set()
            await app.workers.wait_for_complete()


@pytest.mark.asyncio
async def test_unwritable_library_keeps_save_and_long_model_is_elided(ui):
    app, p, shell, store, library = ui
    shell.model = "provider/" + "model-" * 20
    library.path.mkdir()
    async with app.run_test(size=(60, 20)) as pilot:
        label = str(app.query_one("#model-command", Button).label)
        assert len(label) <= 26 and "…" in label
        assert shell.model in str(app.query_one("#model-command").tooltip)
        await pilot.press("s")
        await pilot.pause()
        await pilot.click("#save-destination")
        await pilot.press("down", "enter")
        await pilot.pause()
        app.screen.query_one("#save-playlist", Input).value = "Night"
        app.screen.query_one("#save-playlist", Input).focus()
        await pilot.press("enter")
        assert isinstance(app.screen, SaveDialog)
        assert "Could not save" in shown(app, "#save-status")
        assert app.screen.query_one("#save-playlist", Input).value == "Night"
        assert library.path.is_dir() and not store.path.exists()
        shell.interpret_with_usage.assert_not_called()


@pytest.mark.asyncio
async def test_previous_click_ordinary_picker_real_audio_and_pause(ui, monkeypatch):
    from gentle_stream.player import Player
    from tests.test_continuous_playback import SONGS, engine
    from tests.test_player import FakeStream

    app, _, shell, store, library = ui
    p = Player(engine(), volume=.37)
    monkeypatch.setattr(p, "start", lambda: None)  # real queue, explicit fake callback; no device/producer
    app.player = p
    for s in SONGS:
        library.save("Evening", s.name, s)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("p")
        await pilot.pause()
        await pilot.press("down", "enter")
        await pilot.pause()
        await pilot.press("enter")  # ordinary One, no eager unrelated-cache preparation
        await pilot.pause()
        assert not p.continuous and p.playlist_index is None
        await pilot.click("#previous")
        await pilot.pause()
        # Displayed alphabetical order is One, Three, Two: previous from One is Two.
        assert p.style.name == "Two" and p.playlist_index == 2
        stream = FakeStream(callback=p._callback)
        stream.pull(128)
        app._tick()
        assert "Two" in shown(app, "#title") and "Evening #3" in shown(app, "#state")
        await pilot.press("escape", "space")
        stream.pull(1024)  # finish ordinary sounddevice fade
        held = p.position
        assert await pilot.click("#previous", times=2)
        await pilot.pause()
        assert p.style.name == "One" and p.playlist_index == 0
        assert not p.playing and not p.continuous and p.volume == .37 and p.position == held
        await pilot.press("escape", "space")
        stream.pull(128)
        app._tick()
        assert p.now.style.name == "One" and "One" in shown(app, "#title")
        shell.interpret_with_usage.assert_not_called()
        shell.list_models.assert_not_called()


@pytest.mark.asyncio
async def test_previous_old_daemon_error_visible_ui_alive(ui):
    import json
    from gentle_stream.client import PlayerClient
    from tests.test_continuous_playback import LocalConnection, engine
    from gentle_stream.player import Player

    app, _, shell, store, library = ui
    p = Player(engine())
    p.set_playlist((DEFAULT,), name="Old")
    class OldConnection(LocalConnection):
        def send_bytes(self, raw):
            if json.loads(raw)["cmd"] == "previous":
                self.answer = {"ok": False, "error": "bad request: unknown command 'previous'"}
            else:
                super().send_bytes(raw)
    client = PlayerClient(OldConnection(p))
    client.close = lambda: None  # no socket lifecycle in this in-memory transport
    app.player = client
    async with app.run_test() as pilot:
        before = p.playback_state()
        await pilot.click("#previous")
        await pilot.pause()
        assert "unknown command 'previous'" in shown(app, "#status")
        assert app.is_running and p.playback_state() == before
        await pilot.press("escape", "space")
        assert not p.playing
        shell.interpret_with_usage.assert_not_called()


@pytest.mark.asyncio
async def test_playlist_and_save_menus_keep_a_clear_keyboard_hierarchy(ui):
    app, player, shell, store, library = ui
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("p")
        await pilot.pause()
        picker = app.screen
        assert isinstance(picker, PresetPicker)
        assert "Playlists" in shown(app, ".heading")
        assert "Generative styles" in shown(app, "#picker-description")
        assert picker.query_one("#presets-status").region.y > picker.query_one("#presets").region.y
        assert picker.query_one("#presets", OptionList).has_focus
        await pilot.press("escape", "s")
        await pilot.pause()
        assert isinstance(app.screen, SaveDialog)
        assert "Song name" in shown(app, "#save-name-label")
        assert "Destination" in shown(app, "#save-destination-label")
        assert not app.screen.query_one("#save-playlist-label").display
        app.screen.query_one("#save-destination", Select).value = "new"
        await pilot.pause()
        assert app.screen.query_one("#save-playlist-label").display
        assert app.screen.query_one("#save-playlist", Input).display
        await pilot.press("escape")
        assert not store.path.exists() and not library.path.exists()
        player.toggle.assert_not_called()
        shell.interpret_with_usage.assert_not_called()
