"""Convenience runner for segment_geotiff.py.

Edit the paths and prompt below, then run this file with:

    uv run python run_segment_geotiff.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
IMAGE = Path(r"C:\Data\clay\wellington\imagery\wellington\hutt-city_2025_0.075m\rgb\2193\BQ32_500_027026_0.3m.tiff")
OUTPUT = Path(r"C:\Temp\imagery\class_test\class3.tiff")
CHECKPOINT = ROOT / ".models" / "sam2.1_s.pt"
PROMPT_POINT = "476,783"
PROMPT_POINT = "405,779"
PROMPT_POINT = "532,779"
DEVICE = "cpu"


def main() -> None:
    command = [
        sys.executable,
        str(ROOT / "segment_geotiff.py"),
        str(IMAGE),
        str(OUTPUT),
        "--checkpoint",
        str(CHECKPOINT),
        "--prompt-point",
        PROMPT_POINT,
        "--device",
        DEVICE,
    ]
    subprocess.run(command, check=True, cwd=ROOT)


if __name__ == "__main__":
    main()