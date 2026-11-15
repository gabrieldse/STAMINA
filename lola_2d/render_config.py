"""Output image size shared by the plotting scripts.

Static renders are capped at 1080x720 px for now. Data is computed at the
resolution the image can show, so a bigger image means more detail (and
more memory). Interactive views will pick their own resolutions later.
"""

import argparse

import matplotlib.pyplot as plt

WIDTH_PX = 1080
HEIGHT_PX = 720
DPI = 100


def add_size_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--width", type=int, default=WIDTH_PX, help=f"image width in pixels (default {WIDTH_PX})")
    parser.add_argument("--height", type=int, default=HEIGHT_PX, help=f"image height in pixels (default {HEIGHT_PX})")


def new_figure(width: int, height: int, **kwargs) -> plt.Figure:
    """A figure that saves at exactly width x height pixels (with savefig(dpi=DPI))."""
    return plt.figure(figsize=(width / DPI, height / DPI), dpi=DPI, **kwargs)
