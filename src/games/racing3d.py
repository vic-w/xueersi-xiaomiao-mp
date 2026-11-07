"""汽车在无限棋盘格地面上行驶。

统一坐标系：相机在 (0, 3, 0) 朝 +z 看，center=(80,64) 是地平线。
棋盘格在 y=-3 平面（相机下方），车在 (0, -3, 5)（相机前方 5 米）。
两者用同一套 c3d 投影，不再各自为政。

Controls:
    A: 前进
    Left/Right: 转前轮
"""

import json
import math
import time

from games.software3d import Software3D
from lib.hardware import Speaker


SCREEN_W = 160
SCREEN_H = 128

# Camera params (must match Software3D defaults: distance=4, focal=111)
CAM_DISTANCE = 4.0
CAM_FOCAL = 111.0
HORIZON_Y = 64.0      # screen center = horizon
CAM_HEIGHT = 3.0      # camera height above ground

MAX_STEER = 0.6
STEER_SPEED = 1.5
MAX_SPEED = 12.0
ACCEL = 8.0
FRICTION = 3.0
WHEEL_BASE = 2.5


def load_car_mesh(gl, path="/games/car_model.json"):
    try:
        with open(path) as f:
            data = json.load(f)
    except OSError:
        return None
    # Offset car into camera space: (0, -CAM_HEIGHT, 5) = ground, 5m ahead.
    verts = [(v[0], v[1] - CAM_HEIGHT, v[2] + 5.0) for v in data["vertices"]]
    faces = []
    for indices, color_name in data["faces"]:
        c = {"body": 0xF800, "glass": 0x29BF, "wheel": 0x0000,
             "taillight": 0xFC00, "headlight": 0xFFE0}.get(color_name, 0xFFFF)
        faces.append((tuple(indices), c))
    return gl.prepare_mesh(verts, faces)


def build_checker_mesh(gl):
    """8x8 checkerboard on the ground plane (y=-CAM_HEIGHT).
    z=0 is near (under camera), z=80 is far (toward horizon)."""
    CELL = 10.0
    N = 8
    verts = []
    for iz in range(N + 1):
        for ix in range(N + 1):
            x = (ix - N / 2) * CELL
            z = iz * CELL
            verts.append((x, -CAM_HEIGHT, z))
    faces = []
    for iz in range(N):
        for ix in range(N):
            a = iz * (N + 1) + ix
            b = a + 1
            c = a + (N + 1) + 1
            d = a + (N + 1)
            color = 0x4B47 if (ix + iz) % 2 == 0 else 0x3AC5
            faces.append(((a, b, c, d), color))
    return gl.prepare_mesh(verts, faces)


class Racing3D:
    def __init__(self, ctx):
        self.ctx = ctx
        self.disp = ctx.ed.display
        self.gl = Software3D(self.disp, SCREEN_W, SCREEN_H)
        self.gl.set_camera(CAM_DISTANCE, 60.0)
        self.car_mesh = load_car_mesh(self.gl)
        self.checker_mesh = build_checker_mesh(self.gl)
        try:
            self.sound = Speaker()
        except Exception:
            self.sound = None
        self.should_exit = False

    def _read_buttons(self, prev):
        pins = (self.ctx.k_u.button, self.ctx.k_d.button,
                self.ctx.k_l.button, self.ctx.k_r.button,
                self.ctx.k_a.button, self.ctx.k_b.button)
        cur = [p.value() == 0 for p in pins]
        pressed = [cur[i] and not prev[i] for i in range(6)]
        return cur, pressed

    def play(self):
        buttons = (self.ctx.k_u, self.ctx.k_d, self.ctx.k_l,
                   self.ctx.k_r, self.ctx.k_a, self.ctx.k_b)
        saved = [b.down_func for b in buttons]
        for b in buttons: b.down_func = None
        prev = [True] * 6

        heading = 0.0
        steer = 0.0
        speed = 0.0
        car_x = 0.0
        car_z = 0.0

        # Load car model vertices once (we offset per-frame below).
        try:
            with open("/games/car_model.json") as f:
                import json as _json
                _data = _json.load(f)
            _car_verts = [(v[0], v[1] - CAM_HEIGHT, v[2])
                          for v in _data["vertices"]]
            _car_faces_raw = _data["faces"]
        except OSError:
            _car_verts = None
            _car_faces_raw = []

        last = time.ticks_ms()
        try:
            while not self.should_exit:
                now = time.ticks_ms()
                dt = min(0.05, time.ticks_diff(now, last) / 1000.0)
                last = now

                cur, pressed = self._read_buttons(prev)

                # Steering
                steer_target = 0.0
                if cur[2]: steer_target = -MAX_STEER
                if cur[3]: steer_target = MAX_STEER
                steer += (steer_target - steer) * min(1.0, STEER_SPEED * dt)

                # Speed
                if cur[4]:
                    speed = min(MAX_SPEED, speed + ACCEL * dt)
                else:
                    speed = max(0.0, speed - FRICTION * dt)

                # Bicycle model: car moves in world space
                heading += (speed / WHEEL_BASE) * math.tan(steer) * dt
                car_x += math.sin(heading) * speed * dt
                car_z += math.cos(heading) * speed * dt

                # --- render: top-down view from 100m above origin ---
                # Camera pitched -90 (looking down). World y becomes screen depth.
                PITCH = -math.pi / 2   # look straight down
                CELL = 10.0
                N = 8     # 9x9=81 verts (c3d limit 128)
                verts = []
                for iz in range(N + 1):
                    for ix in range(N + 1):
                        x = (ix - N / 2) * CELL
                        z = (iz - N / 2) * CELL
                        verts.append((x, -CAM_HEIGHT, z))
                faces = []
                for iz in range(N):
                    for ix in range(N):
                        a = iz * (N + 1) + ix
                        b = a + 1
                        c = a + (N + 1) + 1
                        d = a + (N + 1)
                        color = 0x4B47 if (ix + iz) % 2 == 0 else 0x3AC5
                        faces.append(((a, b, c, d), color))
                ground_mesh = self.gl.prepare_mesh(verts, faces)
                if ground_mesh is not None:
                    self.gl.draw_prepared_mesh(
                        ground_mesh,
                        (PITCH, 0.0, 0.0),
                        1.0,
                        (SCREEN_W / 2, SCREEN_H / 2),
                        0,
                        return_projection=False,
                    )

                # Car mesh: bake yaw around car center, then translate to
                # world (car_x, car_z). c3d applies only pitch=-90 (shared
                # camera pitch), no yaw (already baked).
                if _car_verts is not None:
                    ch = math.cos(heading)
                    sh = math.sin(heading)
                    car_verts = []
                    for (vx, vy, vz) in _car_verts:
                        # Rotate around Y axis (car center = origin of mesh).
                        rx = vx * ch - vz * sh
                        rz = vx * sh + vz * ch
                        car_verts.append((rx + car_x, vy, rz + car_z))
                    car_faces = []
                    for indices, cn in _car_faces_raw:
                        c = {"body": 0xF800, "glass": 0x29BF, "wheel": 0x0000,
                             "taillight": 0xFC00, "headlight": 0xFFE0}.get(cn, 0xFFFF)
                        car_faces.append((tuple(indices), c))
                    car_mesh = self.gl.prepare_mesh(car_verts, car_faces)
                    if car_mesh is not None:
                        self.gl.draw_prepared_mesh(
                            car_mesh,
                            (PITCH, 0.0, 0.0),   # shared camera pitch only
                            0.5,
                            (SCREEN_W / 2, SCREEN_H / 2),
                            0xFFFF,
                            return_projection=False,
                        )

                # HUD
                self.disp.text("A GAS L/R", 30, 119, 0xFFFF)
                self.disp.text("SPD %02d" % int(speed * 3.6), 2, 2, 0xFFFF)
                wheel_pct = int(steer / MAX_STEER * 100)
                self.disp.text("WHL %+03d" % wheel_pct, 60, 2, 0xFFFF)

                self.gl.show()
                time.sleep_ms(16)
                prev = cur
        finally:
            for i, b in enumerate(buttons): b.down_func = saved[i]
            if self.sound:
                try: self.sound.pin.deinit()
                except Exception: pass


def run(ctx):
    Racing3D(ctx).play()
