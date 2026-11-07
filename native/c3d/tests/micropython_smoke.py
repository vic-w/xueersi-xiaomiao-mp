"""Run with a MicroPython v1.28.0 build containing c3d and framebuf."""

import gc
import sys
import c3d
import framebuf

sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else "src")
from games.software3d import Software3D

WIDTH, HEIGHT = 160, 128
SIZE = WIDTH * HEIGHT * 2
VERTICES = (
    (-1.0, -1.0, -1.0), (1.0, -1.0, -1.0),
    (1.0, 1.0, -1.0), (-1.0, 1.0, -1.0),
    (-1.0, -1.0, 1.0), (1.0, -1.0, 1.0),
    (1.0, 1.0, 1.0), (-1.0, 1.0, 1.0),
)
FACES = (
    ((0, 1, 2, 3), 0xE8A2), ((4, 5, 6, 7), 0xFD20),
    ((0, 4, 7, 3), 0x4DFF), ((1, 2, 6, 5), 0x07E0),
    ((3, 7, 6, 2), 0xF81F), ((0, 1, 5, 4), 0xFFE0),
)


class Display:
    def __init__(self):
        self.storage = bytearray(b"\xa5" * (SIZE + 32))
        self.buffer = memoryview(self.storage)[16:16 + SIZE]
        self.fb = framebuf.FrameBuffer(self.buffer, WIDTH, HEIGHT, framebuf.RGB565)
        self.fill = self.fb.fill
        self.hline = self.fb.hline
        self.line = self.fb.line

    def show(self):
        pass

    def check_guards(self):
        assert self.storage[:16] == b"\xa5" * 16
        assert self.storage[-16:] == b"\xa5" * 16


def expect_error(exception, function, *args):
    try:
        function(*args)
    except exception:
        return
    raise AssertionError("expected " + str(exception))


native_display = Display()
python_display = Display()
native = Software3D(native_display)
reference = Software3D(python_display, use_native=False)
assert native.backend == "C"
assert reference.backend == "Python"
mesh = native.prepare_mesh(VERTICES, FACES)
assert isinstance(mesh, c3d.Mesh)

for color in (0, 0xF800, 0x07E0, 0x001F, 0xFFFF):
    native.clear(color)
    reference.clear(color)
    assert native_display.buffer == python_display.buffer

for angles in ((0.0, 0.0, 0.0), (0.45, 0.0, 0.2),
               (0.5, 0.75, 0.25), (1.3, 2.1, -0.3)):
    for center in (None, (-10, 64), (165, 128)):
        for renderer in (native, reference):
            renderer.set_camera(4.2, 60)
            renderer.clear()
        actual = native.draw_prepared_mesh(mesh, angles, 1.18, center)
        expected = reference.draw_mesh(VERTICES, FACES, angles, 1.18, center)
        assert len(actual) == len(expected)
        for a, b in zip(actual, expected):
            assert abs(a[0] - b[0]) <= 1 and abs(a[1] - b[1]) <= 1
            assert abs(a[2] - b[2]) < 0.00001
        differences = sum(
            1 for index in range(0, SIZE, 2)
            if native_display.buffer[index:index + 2] !=
            python_display.buffer[index:index + 2]
        )
        assert differences <= 20, (angles, center, differences)
        native_display.check_guards()

# Near-plane rejection and out-of-range projections must remain bounded.
for distance in (0.13, 0.5, 1.0):
    native.set_camera(distance)
    native.clear()
    native.draw_prepared_mesh(mesh, (0.3, 0.2, 0.1), edge_color=0)
    native_display.check_guards()
native.set_camera(4.2)
native.clear()
native.draw_prepared_mesh(mesh, scale=1e30, return_projection=False)
native_display.check_guards()

# Empty meshes and the legacy draw_mesh entry point are supported.
empty = native.prepare_mesh((), ())
assert native.draw_prepared_mesh(empty) == []
assert reference.draw_prepared_mesh(reference.prepare_mesh((), ())) == []
assert reference.draw_mesh(VERTICES, FACES, return_projection=False) is None
assert native.draw_mesh(VERTICES, FACES, return_projection=False) is None

# Discarded projection results should allocate no per-vertex Python objects.
gc.collect()
before = gc.mem_free()
for _ in range(100):
    assert native.draw_prepared_mesh(mesh, return_projection=False) is None
gc.collect()
assert gc.mem_free() >= before - 256

expect_error(ValueError, c3d.clear, bytearray(1), WIDTH, HEIGHT, 0)
expect_error(TypeError, c3d.clear, bytes(SIZE), WIDTH, HEIGHT, 0)
expect_error(ValueError, c3d.clear, bytearray(8), -1, 1, 0)
expect_error(ValueError, c3d.clear, bytearray(8), 2, 2, -1)
expect_error(ValueError, c3d.clear, bytearray(8), 2, 2, 65536)
expect_error(ValueError, c3d.Mesh, VERTICES, (((0, 1, 8), 0),))
expect_error(ValueError, c3d.Mesh, VERTICES, (((0, 1), 0),))
expect_error(ValueError, c3d.Mesh, VERTICES * 17, ())
expect_error(ValueError, c3d.Mesh, VERTICES, FACES * 11)
expect_error(ValueError, c3d.Mesh, ((float("nan"), 0, 0),), ())
expect_error(ValueError, native.draw_prepared_mesh, mesh, (float("inf"), 0, 0))

# Prepared native meshes own their copied data across collection and mutation.
mutable = [list(vertex) for vertex in VERTICES]
owned = c3d.Mesh(mutable, FACES)
expected = native.draw_prepared_mesh(owned)
mutable[0][0] = 999
del mutable
gc.collect()
assert native.draw_prepared_mesh(owned) == expected
native_display.check_guards()
print("c3d MicroPython integration tests passed")
