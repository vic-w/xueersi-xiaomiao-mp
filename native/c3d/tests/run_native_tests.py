"""Compile and run the standalone C renderer tests with the host C compiler."""

import os
import pathlib
import subprocess
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[3]
SOURCE = ROOT / "native" / "c3d" / "c3d_render.c"
TEST = ROOT / "native" / "c3d" / "tests" / "test_c3d.c"
OUTPUT_NAME = "test_c3d.exe" if os.name == "nt" else "test_c3d"

with tempfile.TemporaryDirectory(prefix="xiaomiao-c3d-") as temporary_dir:
    executable = pathlib.Path(temporary_dir) / OUTPUT_NAME
    subprocess.run(
        [
            os.environ.get("CC", "gcc"),
            "-std=c99",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-pedantic",
            "-O2",
            str(SOURCE),
            str(TEST),
            "-lm",
            "-o",
            str(executable),
        ],
        check=True,
    )
    subprocess.run([str(executable)], check=True)
