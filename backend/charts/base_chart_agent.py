from __future__ import annotations

from abc import ABC, abstractmethod

import matplotlib.pyplot as plt
import pandas as pd


plt.rcParams["font.family"] = "DejaVu Sans"


class BaseChartAgent(ABC):
    artifact_id: str = ""
    display_name: str = ""

    def _figure(self, title: str):
        fig, ax = plt.subplots(figsize=(12, 7), facecolor="white")
        ax.set_facecolor("white")
        ax.set_title(title, fontsize=18, fontweight="bold", pad=16)
        return fig, ax

    def _require_rows(self, df: pd.DataFrame, message: str = "Grafik olusturmak icin yeterli veri bulunamadi."):
        if df is None or df.empty:
            raise ValueError(message)

    @abstractmethod
    def build_figure(self, df: pd.DataFrame, user_prompt: str | None = None):
        raise NotImplementedError
