"""Matplotlib chart rendering from worker chart specs (headless)."""

from __future__ import annotations

import io
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

PALETTE = ["#0E7C86", "#F2A541", "#C8553D", "#5B8E7D", "#6C5B7B", "#2E86AB", "#A23B72"]


def render(spec: dict[str, Any]) -> bytes | None:
    kind = spec.get("kind")
    fig, ax = plt.subplots(figsize=(6.4, 3.2), dpi=130)
    try:
        if kind == "bar":
            ax.barh(spec["x"][::-1], spec["y"][::-1], color=PALETTE[0])
            ax.set_xlabel("USD mn")
        elif kind == "line":
            ax.plot(spec["x"], spec["y"], marker="o", color=PALETTE[0], lw=2)
        elif kind == "line2":
            ax.plot(spec["x"], spec["y"], marker="o", color=PALETTE[0], lw=2, label=spec["labels"][0])
            ax.plot(spec["x"], spec["y2"], marker="s", color=PALETTE[1], lw=2, label=spec["labels"][1])
            ax.legend(frameon=False, fontsize=8)
        elif kind == "pie":
            ax.pie(spec["values"], labels=spec["labels"], colors=PALETTE, autopct="%1.0f%%",
                   textprops={"fontsize": 7}, wedgeprops={"linewidth": 1, "edgecolor": "white"})
            ax.axis("equal")
        elif kind == "heatmap":
            im = ax.imshow(spec["values"], cmap="YlGnBu", aspect="auto")
            ax.set_yticks(range(len(spec["rows"])), spec["rows"], fontsize=7)
            ax.set_xticks(range(len(spec["cols"])), spec["cols"], fontsize=7, rotation=30, ha="right")
            fig.colorbar(im, ax=ax, shrink=0.8)
        else:
            return None
        ax.set_title(spec.get("title", ""), fontsize=9, loc="left")
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        ax.tick_params(labelsize=7)
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png")
        return buf.getvalue()
    finally:
        plt.close(fig)
