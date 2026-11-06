"""Validated UI-only preferences and native settings flows."""
from dataclasses import replace

import pytest
from textual.widgets import Input, Switch

from gentle_stream.appearance import Preferences, PreferenceError, PreferenceStore


@pytest.mark.parametrize("key,value", [("refresh_hz", 4), ("refresh_hz", 31), ("bands", 7),
    ("bands", 129), pytest.param("bands", 10 ** 400, id="oversized-integer"),
    ("height", 4), ("height", 31), ("smoothing", -1), ("smoothing", float('nan')),
    ("smoothing", 1.1), ("peak_hold", 4), ("accent", "red; color: blue"),
    ("background", "#xyzxyz"), ("style", "unknown"), ("show_controls", 1),
    ("icon_gap", 0), ("theme", "terminal")])
def test_rejected_preferences_leave_bytes_unchanged(tmp_path, key, value):
    store = PreferenceStore(tmp_path / "appearance.json")
    store.save(Preferences())
    before = store.path.read_bytes()
    with pytest.raises(PreferenceError, match=f"Invalid {key}\\."):
        store.save(replace(Preferences(), **{key: value}))
    assert store.path.read_bytes() == before
    assert store.load() == Preferences()


def test_roundtrip_defaults_bounds_and_corrupt_record(tmp_path):
    store = PreferenceStore(tmp_path / "appearance.json")
    assert store.load() == Preferences() and not store.path.exists()
    for hz in (5, 30):
        prefs = replace(Preferences(), refresh_hz=hz, bands=128, height=30,
                        smoothing=1., peak_hold=3., icon_gap=3)
        store.save(prefs)
        assert store.load() == prefs
    store.path.write_text('{oops')
    assert store.load() == Preferences()
    assert store.error.startswith("Cannot read appearance preferences:")
    with pytest.raises(PreferenceError, match="Cannot read appearance preferences:"):
        store.save(Preferences())
    assert store.path.read_text() == '{oops'


@pytest.mark.parametrize('record', ['{}', '{"version": 2, "preferences": {}}',
    '{"version": 1, "preferences": {"refresh_hz": 200}}', '[]'])
def test_invalid_record_is_not_rewritten(tmp_path, record):
    store = PreferenceStore(tmp_path / 'appearance.json')
    store.path.write_text(record)
    assert store.load() == Preferences() and store.error
    with pytest.raises(PreferenceError):
        store.save(Preferences())
    assert store.path.read_text() == record


def test_atomic_write_failure_keeps_previous_record(tmp_path, monkeypatch):
    import gentle_stream.appearance as appearance
    store = PreferenceStore(tmp_path / 'appearance.json')
    store.save(Preferences())
    before = store.path.read_bytes()
    def refuse(*args):
        raise OSError('test replacement refused')
    monkeypatch.setattr(appearance.os, 'replace', refuse)
    with pytest.raises(PreferenceError, match='Cannot write appearance preferences: test replacement refused'):
        store.save(replace(Preferences(), bands=8))
    assert store.path.read_bytes() == before
    assert store.load() == Preferences()
