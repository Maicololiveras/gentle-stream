"""Five-bar volume feedback, rendered without a player or personal records."""

import pytest

from gentle_stream.volume_meter import render_volume_meter


@pytest.mark.parametrize("percent", range(0, 101, 5))
def test_five_ascending_bars_fill_one_step_per_five_percent(percent):
    meter = render_volume_meter(percent, "#f095c8")
    rows = meter.plain.splitlines()
    assert len(rows) == 8
    assert all(len(row) == 19 for row in rows)
    assert [row.count("╭─╮") for row in rows[:7]] == [1, 1, 1, 1, 1, 0, 0]
    assert rows[7].strip() == f"{percent}%"
    assert abs((rows[7].index(f"{percent}%") * 2 + len(f"{percent}%")) - 19) <= 1
    capacities = (2, 3, 4, 5, 6)
    remaining = percent // 5
    for index, capacity in enumerate(capacities):
        column = 4 * index + 1
        filled = sum(row[column] == "█" for row in rows[:7])
        assert filled == min(capacity, max(0, remaining)), (percent, index)
        remaining -= capacity
    assert sum(row.count("█") for row in rows[:7]) == percent // 5
    assert meter.style == "#f095c8"  # Empty outlines and filled cells retain the selected pink accent.


def test_zero_is_outlines_only_and_full_volume_fills_every_bar():
    empty = render_volume_meter(0, "#f095c8").plain.splitlines()
    full = render_volume_meter(100, "#f095c8").plain.splitlines()
    assert empty[0] == full[0] == "                ╭─╮"
    assert empty[4].startswith("╭─╮") and full[4].startswith("╭─╮")
    assert "█" not in "".join(empty[:7])
    for index, capacity in enumerate((2, 3, 4, 5, 6)):
        assert all(full[row][4 * index + 1] == "█" for row in range(7 - capacity, 7))
    assert full[7].strip() == "100%"
