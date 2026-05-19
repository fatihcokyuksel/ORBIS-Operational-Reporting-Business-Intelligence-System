from __future__ import annotations

from pathlib import Path

from matplotlib.figure import Figure


MIN_WIDTH_PX = 1600
MIN_HEIGHT_PX = 900
DEFAULT_DPI = 180


def save_chart_figure(fig: Figure, output_dir: str | Path, file_name: str = "chart.jpg", dpi: int = DEFAULT_DPI) -> str:
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    output_path = target_dir / file_name

    width, height = fig.get_size_inches()
    if width * dpi < MIN_WIDTH_PX or height * dpi < MIN_HEIGHT_PX:
        fig.set_size_inches(max(width, 10), max(height, 6), forward=True)

    fig.patch.set_facecolor("white")
    fig.savefig(output_path, format="jpg", dpi=max(dpi, 150), bbox_inches="tight", facecolor="white")
    return str(output_path)
