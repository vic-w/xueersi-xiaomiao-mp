"""Check that Software3D still renders when the optional c3d module is absent."""

import runpy
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
sys.modules["c3d"] = None
Software3D = runpy.run_path(str(ROOT / "src" / "games" / "software3d.py"))[
    "Software3D"
]


class Display:
    def __init__(self):
        self.buffer = bytearray(160 * 128 * 2)
        self.fill_color = None
        self.horizontal_lines = 0
        self.lines = 0
        self.shows = 0

    def fill(self, color):
        self.fill_color = color

    def hline(self, x, y, width, color):
        assert 0 <= x < 160 and 0 <= y < 128
        assert 0 < width <= 160 - x
        assert 0 <= color <= 0xFFFF
        self.horizontal_lines += 1

    def line(self, x1, y1, x2, y2, color):
        assert 0 <= color <= 0xFFFF
        self.lines += 1

    def show(self):
        self.shows += 1


display = Display()
renderer = Software3D(display)
assert renderer.backend == "Python"
renderer.clear(0x001F)
assert display.fill_color == 0x001F
mesh = renderer.prepare_mesh(
    ((-1, -1, 0), (1, -1, 0), (0, 1, 0)),
    (((0, 1, 2), 0xF800),),
)
projection = renderer.draw_prepared_mesh(mesh, edge_color=0xFFFF)
assert len(projection) == 3
assert display.horizontal_lines > 0 and display.lines == 3
assert renderer.draw_prepared_mesh(mesh, return_projection=False) is None
renderer.show()
assert display.shows == 1
print("Software3D Python fallback tests passed")
