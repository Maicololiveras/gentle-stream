"""Display-only five-bar volume gauge for the Textual command strip."""

from rich.text import Text


# Each cell is one existing five-percentage-point step. Short bars fill first.
_BAR_STEPS = (2, 3, 4, 5, 6)
_BAR_HEIGHT = max(_BAR_STEPS)
_METER_WIDTH = len(_BAR_STEPS) * 4 - 1


def _levels(percent: int) -> tuple[int, tuple[int, ...]]:
    percent = max(0, min(100, round(percent)))
    remaining = percent // 5
    filled = []
    for capacity in _BAR_STEPS:
        portion = min(capacity, remaining)
        filled.append(portion)
        remaining -= portion
    return percent, tuple(filled)


def render_volume_meter(percent: int, accent: str) -> Text:
    """Return ascending outlined bars and a centered volume label, without changing audio."""
    percent, filled = _levels(percent)
    rows = []
    for row in range(_BAR_HEIGHT + 1):
        bars = []
        for capacity, portion in zip(_BAR_STEPS, filled):
            top = _BAR_HEIGHT - capacity
            if row < top:
                bars.append("   ")
            elif row == top:
                bars.append("╭─╮")
            else:
                bars.append("│█│" if row - top > capacity - portion else "│ │")
        rows.append(" ".join(bars))
    rows.append(f"{percent}%".center(_METER_WIDTH))
    return Text("\n".join(rows), style=accent, no_wrap=True)


def render_compact_volume_meter(percent: int, accent: str) -> Text:
    """Keep all twenty steps and the percentage visible in two terminal rows."""
    percent, filled = _levels(percent)
    blocks = "▁▂▃▄▅▆▇█"
    max_heights = (2, 3, 4, 6, 8)
    bars = " ".join(
        blocks[max(1, round(portion * height / capacity)) - 1] if portion else "▯"
        for portion, height, capacity in zip(filled, max_heights, _BAR_STEPS)
    )
    return Text(f"{bars}\n{f'{percent}%'.center(len(bars))}",
                style=accent, no_wrap=True)
