"""3D 小企鹅偷鱼。

在一片可无限平铺的冰原上自由滑行。关卡开始时预生成一张
8x8 的平滑高度网格（smoothstep 双线性插值，坐标取模回绕），
冰原向任意方向都能延伸。

任务：从海豹旁边偷到 20 条鱼即过关。碰到巡逻的海豹会被抓回起点。

Controls:
    Up: accelerate
    Down: brake
    Left/Right: turn
    A: jump
    B: exit

Slow speed = waddle on feet; fast = belly slide.
"""

import math
import random
import time

from games.software3d import Software3D
from lib.hardware import Speaker


SCREEN_W = 160
SCREEN_H = 128
HORIZON_BASE = 44
GROUND_Y = 124

SKY_COLOR = 0x957F
HILL_COLOR = 0x7BEF
FAR_HILL_COLOR = 0xB5B8
SNOW_COLOR = 0xFFFF
PENGUIN_BODY = 0x0000
PENGUIN_ACCENT = 0xFD20
SEAL_COLOR = 0xB723
FISH_COLOR = 0xFFE0
FISH_TAIL = 0xF800
TEXT_COLOR = 0xFFFF

TILE_N = 8           # heightmap grid size (tileable via wrap)
TILE_SCALE = 0.12    # world units per grid cell
MAX_SPEED = 7.0
ACCEL = 3.2
BRAKE = 5.0
FRICTION = 1.2
TURN_RATE = 1.6
GRAVITY = 18.0
JUMP_VY = 6.5
FISH_COUNT = 20
FISH_PICKUP = 1.1
SEAL_TOUCH = 1.0
WALK_SPEED = 2.2     # below this = waddle, above = belly slide


# ---------------------------------------------------------------------------
# Mesh helpers
# ---------------------------------------------------------------------------

def _box(verts, faces, cx, cy, cz, sx, sy, sz, color):
    x0, x1 = cx - sx / 2, cx + sx / 2
    y0, y1 = cy - sy / 2, cy + sy / 2
    z0, z1 = cz - sz / 2, cz + sz / 2
    base = len(verts)
    verts.extend([
        (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
        (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
    ])
    faces.extend([
        ((base + 0, base + 1, base + 5, base + 4), color),
        ((base + 3, base + 2, base + 6, base + 7), color),
        ((base + 0, base + 1, base + 2, base + 3), color),
        ((base + 4, base + 5, base + 6, base + 7), color),
        ((base + 0, base + 4, base + 7, base + 3), color),
        ((base + 1, base + 2, base + 6, base + 5), color),
    ])


def _build_penguin():
    v, f = [], []
    # Tapered body (frustum): wide shoulders, narrow waist.
    v.extend([
        (-0.42, 1.25, -0.26), (0.42, 1.25, -0.26),
        (0.42, 1.25, 0.26), (-0.42, 1.25, 0.26),
        (-0.26, 0.4, -0.18), (0.26, 0.4, -0.18),
        (0.26, 0.4, 0.18), (-0.26, 0.4, 0.18),
    ])
    f.extend([
        ((0, 3, 2, 1), PENGUIN_BODY),
        ((4, 5, 6, 7), PENGUIN_BODY),
        ((0, 1, 5, 4), PENGUIN_BODY),
        ((3, 7, 6, 2), 0xFFFF),     # white belly
        ((0, 4, 7, 3), PENGUIN_BODY),
        ((1, 2, 6, 5), PENGUIN_BODY),
    ])
    # Head
    base = len(v)
    v.extend([
        (-0.30, 1.25, -0.22), (0.30, 1.25, -0.22),
        (0.30, 1.25, 0.22), (-0.30, 1.25, 0.22),
        (-0.26, 1.85, -0.20), (0.26, 1.85, -0.20),
        (0.26, 1.85, 0.20), (-0.26, 1.85, 0.20),
    ])
    f.extend([
        ((base + 0, base + 3, base + 2, base + 1), PENGUIN_BODY),
        ((base + 4, base + 5, base + 6, base + 7), PENGUIN_BODY),
        ((base + 0, base + 1, base + 5, base + 4), PENGUIN_BODY),
        ((base + 3, base + 7, base + 6, base + 2), 0xFFFF),
        ((base + 0, base + 4, base + 7, base + 3), PENGUIN_BODY),
        ((base + 1, base + 2, base + 6, base + 5), PENGUIN_BODY),
    ])
    # Beak wedge
    base = len(v)
    v.extend([
        (-0.09, 1.62, -0.20), (0.09, 1.62, -0.20),
        (0.07, 1.52, -0.20), (-0.07, 1.52, -0.20),
        (0.0, 1.57, -0.42),
    ])
    f.extend([
        ((base + 0, base + 1, base + 4), PENGUIN_ACCENT),
        ((base + 1, base + 2, base + 4), PENGUIN_ACCENT),
        ((base + 2, base + 3, base + 4), PENGUIN_ACCENT),
        ((base + 3, base + 0, base + 4), PENGUIN_ACCENT),
    ])
    # Flippers (thin frusta)
    for side in (-1, 1):
        base = len(v)
        sx = 0.40 * side
        v.extend([
            (sx, 1.15, -0.12), (sx + 0.12 * side, 1.05, -0.08),
            (sx + 0.10 * side, 0.55, -0.04), (sx, 0.65, -0.08),
            (sx, 1.15, 0.12), (sx + 0.12 * side, 1.05, 0.08),
            (sx + 0.10 * side, 0.55, 0.04), (sx, 0.65, 0.08),
        ])
        f.extend([
            ((base + 0, base + 1, base + 2, base + 3), PENGUIN_BODY),
            ((base + 4, base + 7, base + 6, base + 5), PENGUIN_BODY),
            ((base + 0, base + 4, base + 5, base + 1), PENGUIN_BODY),
            ((base + 3, base + 2, base + 6, base + 7), PENGUIN_BODY),
        ])
    # Feet + scarf
    _box(v, f, -0.15, 0.12, 0.05, 0.20, 0.14, 0.30, PENGUIN_ACCENT)
    _box(v, f, 0.15, 0.12, 0.05, 0.20, 0.14, 0.30, PENGUIN_ACCENT)
    _box(v, f, 0.0, 1.22, 0.0, 0.58, 0.14, 0.36, 0xF800)
    return v, f


def _build_seal():
    v, f = [], []
    _box(v, f, 0, 0.28, 0.0, 0.95, 0.5, 1.25, SEAL_COLOR)
    _box(v, f, 0, 0.42, -0.62, 0.55, 0.45, 0.5, SEAL_COLOR)
    _box(v, f, 0, 0.3, -0.9, 0.3, 0.2, 0.25, 0xDEFB)
    return v, f


def _build_fish():
    v, f = [], []
    _box(v, f, 0, 0, 0, 0.18, 0.12, 0.4, FISH_COLOR)
    _box(v, f, 0, 0, 0.28, 0.12, 0.08, 0.16, FISH_TAIL)
    return v, f


# ---------------------------------------------------------------------------
# Tileable heightmap
# ---------------------------------------------------------------------------

class Heightmap:
    def __init__(self):
        self.grid = [
            [random.uniform(-1.0, 1.0) for _ in range(TILE_N)]
            for _ in range(TILE_N)
        ]

    def _smooth(self, t):
        return t * t * (3.0 - 2.0 * t)

    def sample(self, x, z):
        gx = x * TILE_SCALE
        gz = z * TILE_SCALE
        x0 = math.floor(gx)
        z0 = math.floor(gz)
        fx = self._smooth(gx - x0)
        fz = self._smooth(gz - z0)
        ix0 = x0 % TILE_N
        iz0 = z0 % TILE_N
        ix1 = (ix0 + 1) % TILE_N
        iz1 = (iz0 + 1) % TILE_N
        h00 = self.grid[iz0][ix0]
        h01 = self.grid[iz0][ix1]
        h10 = self.grid[iz1][ix0]
        h11 = self.grid[iz1][ix1]
        return (h00 * (1 - fx) * (1 - fz) + h01 * fx * (1 - fz)
                + h10 * (1 - fx) * fz + h11 * fx * fz)


# ---------------------------------------------------------------------------
# Game
# ---------------------------------------------------------------------------

class PenguinSki:
    def __init__(self, ctx):
        self.ctx = ctx
        self.disp = ctx.ed.display
        self.gl = Software3D(self.disp, SCREEN_W, SCREEN_H)
        self.gl.set_camera(4.2, 60.0)

        v, f = _build_penguin()
        self.mesh_penguin = self.gl.prepare_mesh(v, f)
        v, f = _build_seal()
        self.mesh_seal = self.gl.prepare_mesh(v, f)
        v, f = _build_fish()
        self.mesh_fish = self.gl.prepare_mesh(v, f)

        try:
            self.sound = Speaker()
        except Exception:
            self.sound = None
        self.should_exit = False

    def _beep(self, freq, duration):
        if self.sound is None:
            return
        try:
            self.sound.beep(freq, duration)
        except Exception:
            pass

    def _read_buttons(self, previous):
        pins = (
            self.ctx.k_u.button, self.ctx.k_d.button,
            self.ctx.k_l.button, self.ctx.k_r.button,
            self.ctx.k_a.button, self.ctx.k_b.button,
        )
        current = [pin.value() == 0 for pin in pins]
        pressed = [current[i] and not previous[i] for i in range(6)]
        return current, pressed

    # Perspective: world offset (dx, dz) ahead-of-camera -> (sx, sy, scale).
    def _project(self, dx, dz, height):
        if dz < 0.4:
            return None
        p = 4.0 / (4.0 + dz * 1.5)
        sx = 80.0 + dx * 32.0 * p
        sy = HORIZON_BASE + (GROUND_Y - HORIZON_BASE) * p - height * 28.0 * p
        if sx < -40 or sx > SCREEN_W + 40:
            return None
        return sx, sy, p

    def _draw_sky_and_hills(self, heading, px, pz):
        # Sky
        self.disp.fill_rect(0, 0, SCREEN_W, HORIZON_BASE + 6, SKY_COLOR)
        # Two hill layers sampled from the heightmap at different depths.
        for depth, color, base_y, amp in (
            (18.0, FAR_HILL_COLOR, HORIZON_BASE + 4, 14),
            (8.0, HILL_COLOR, HORIZON_BASE + 8, 10),
        ):
            pts = []
            for col in range(0, SCREEN_W + 4, 4):
                angle = heading + (col - 80.0) / 80.0 * 0.7
                wx = px + math.sin(angle) * depth
                wz = pz + math.cos(angle) * depth
                h = self.hills.sample(wx, wz)
                y = base_y - int(h * amp)
                pts.append((col, y))
            # Fill polygon from base_y down to ground.
            self.disp.line(pts[0][0], pts[0][1], pts[1][0], pts[1][1], color)
            for i in range(1, len(pts) - 1):
                self.disp.line(pts[i][0], pts[i][1],
                               pts[i + 1][0], pts[i + 1][1], color)
            # Solid band below the silhouette.
            self.disp.fill_rect(0, base_y + 2, SCREEN_W,
                                GROUND_Y - base_y - 2, SNOW_COLOR)

    def _place_object(self, mesh, wx, wz, height, angles, scale_base, edge=0):
        dx = (wx - self.px) * math.cos(self.heading) - (wz - self.pz) * math.sin(self.heading)
        dz = (wx - self.px) * math.sin(self.heading) + (wz - self.pz) * math.cos(self.heading)
        proj = self._project(dx, dz, height)
        if proj is None:
            return
        sx, sy, p = proj
        self.gl.draw_prepared_mesh(
            mesh, angles, scale_base * p, (sx, sy), edge,
            return_projection=False,
        )

    def play(self):
        buttons = (
            self.ctx.k_u, self.ctx.k_d, self.ctx.k_l,
            self.ctx.k_r, self.ctx.k_a, self.ctx.k_b,
        )
        saved = [b.down_func for b in buttons]
        for b in buttons:
            b.down_func = None

        previous = [True] * 6

        # --- level generation (once) ---
        self.hills = Heightmap()
        self.px = 0.0
        self.pz = 0.0
        self.heading = 0.0
        self.speed = 0.0
        self.height = 0.0
        self.vy = 0.0
        self.airborne = False

        # Fish scattered in a ring around start.
        self.fish = []
        for _ in range(FISH_COUNT):
            a = random.uniform(0, math.tau)
            r = random.uniform(4.0, 22.0)
            self.fish.append((math.sin(a) * r, math.cos(a) * r, False))

        # Seals patrol on small loops around a fixed center.
        # Each entry: [center_x, center_z, angle, angular_speed, patrol_radius]
        self.seals = []
        for _ in range(5):
            a = random.uniform(0, math.tau)
            r = random.uniform(7.0, 22.0)
            cx = math.sin(a) * r
            cz = math.cos(a) * r
            self.seals.append([cx, cz, random.uniform(0, math.tau),
                               random.uniform(0.4, 1.0),
                               random.uniform(1.5, 2.5)])

        collected = 0
        message = ""
        message_until = 0
        won = False
        walk_phase = 0.0
        last_time = time.ticks_ms()

        try:
            while not self.should_exit:
                now = time.ticks_ms()
                delta = min(0.05, time.ticks_diff(now, last_time) / 1000.0)
                last_time = now

                current, pressed = self._read_buttons(previous)
                if pressed[5]:
                    self.should_exit = True
                    break

                if message == "" and not won:
                    # --- steering (level-triggered: hold to turn) ---
                    turn = (1.0 if current[3] else 0.0) - (1.0 if current[2] else 0.0)
                    self.heading += turn * TURN_RATE * delta * (0.4 + 0.6 * min(1.0, self.speed / MAX_SPEED))

                    # --- speed (level-triggered: hold up to accelerate) ---
                    if current[0]:
                        self.speed = min(MAX_SPEED, self.speed + ACCEL * delta)
                    elif current[1]:
                        self.speed = max(0.0, self.speed - BRAKE * delta)
                    else:
                        self.speed = max(0.0, self.speed - FRICTION * delta)

                    # --- jump (edge-triggered: one hop per press) ---
                    if pressed[4] and not self.airborne:
                        self.vy = JUMP_VY
                        self.airborne = True
                        self._beep(500, 40)

                    # --- integrate ---
                    ax = math.sin(self.heading)
                    az = math.cos(self.heading)
                    self.px += ax * self.speed * delta
                    self.pz += az * self.speed * delta

                    if self.airborne:
                        self.height += self.vy * delta
                        self.vy -= GRAVITY * delta
                        if self.height <= 0.0 and self.vy < 0.0:
                            self.height = 0.0
                            self.vy = 0.0
                            self.airborne = False

                    walk_phase += self.speed * delta * 4.0

                    # --- fish pickup ---
                    for i, (fx, fz, taken) in enumerate(self.fish):
                        if taken:
                            continue
                        dx = fx - self.px
                        dz = fz - self.pz
                        if dx * dx + dz * dz < FISH_PICKUP * FISH_PICKUP:
                            self.fish[i] = (fx, fz, True)
                            collected += 1
                            self._beep(700 + collected * 20, 30)
                            if collected >= FISH_COUNT:
                                won = True
                                message = "偷够20条鱼! 过关"
                                message_until = time.ticks_add(now, 3000)
                                self._beep(880, 400)

                    # --- seals patrol & collision ---
                    for seal in self.seals:
                        cx, cz, angle, ang_speed, radius = seal
                        seal[2] = angle + delta * ang_speed
                        angle = seal[2]
                        sx = cx + math.sin(angle) * radius
                        sz = cz + math.cos(angle) * radius
                        dx = sx - self.px
                        dz = sz - self.pz
                        if dx * dx + dz * dz < SEAL_TOUCH * SEAL_TOUCH and self.height < 1.0:
                            message = "被海豹抓住! 回起点"
                            message_until = time.ticks_add(now, 1600)
                            self.speed = 0.0
                            self._beep(200, 200)

                # --- reset after message ---
                if message and time.ticks_diff(message_until, now) <= 0:
                    if won:
                        self.should_exit = True
                        break
                    self.px = 0.0
                    self.pz = 0.0
                    self.heading = 0.0
                    self.speed = 0.0
                    self.height = 0.0
                    self.vy = 0.0
                    self.airborne = False
                    message = ""

                # --- render ---
                self._draw_sky_and_hills(self.heading, self.px, self.pz)

                # Collect visible objects, sort far -> near.
                items = []
                for fx, fz, taken in self.fish:
                    if not taken:
                        items.append((fz - self.pz, "fish", fx, fz))
                for seal in self.seals:
                    cx, cz, angle, ang_speed, radius = seal
                    sx = cx + math.sin(angle) * radius
                    sz = cz + math.cos(angle) * radius
                    items.append((sz - self.pz, "seal", sx, sz))
                items.sort(key=lambda e: -e[0])

                for _, kind, ox, oz in items:
                    if kind == "fish":
                        bob = 0.3 + 0.1 * math.sin(walk_phase * 2.0)
                        self._place_object(self.mesh_fish, ox, oz, bob,
                                           (0, walk_phase, 0), 0.7)
                    else:
                        self._place_object(self.mesh_seal, ox, oz, 0.3,
                                           (0, 0, 0), 0.9)

                # --- penguin (bottom center) ---
                if self.speed < WALK_SPEED:
                    # Waddle: bob up/down, slight rock.
                    bob = abs(math.sin(walk_phase * 2.0)) * 0.15
                    tilt_z = math.sin(walk_phase * 2.0) * 0.18
                    tilt_x = 0.0
                else:
                    # Belly slide: lean forward, flatten.
                    bob = 0.0
                    tilt_z = 0.0
                    tilt_x = min(0.9, 0.3 + self.speed * 0.08)
                sy = 116.0 - self.height * 26.0 + bob
                self.gl.draw_prepared_mesh(
                    self.mesh_penguin,
                    (tilt_x, 0.0, tilt_z), 0.95,
                    (80.0, sy), 0xFFFF, return_projection=False,
                )

                # HUD
                self.disp.text("FISH %d/%d" % (collected, FISH_COUNT), 2, 2, TEXT_COLOR)
                self.disp.text("SPD %d" % int(self.speed), 110, 2, TEXT_COLOR)
                self.disp.text("A JUMP  B EXIT", 16, 119, 0x8410)
                if message:
                    self.disp.fill_rect(18, 52, 124, 24, 0x0000)
                    self.disp.rect(18, 52, 124, 24, 0xFFFF)
                    self.disp.text(message, 24, 60, 0xFD20)

                self.gl.show()
                time.sleep_ms(16)
                previous = current
        finally:
            for i, b in enumerate(buttons):
                b.down_func = saved[i]
            if self.sound is not None:
                try:
                    self.sound.pin.deinit()
                except Exception:
                    pass


def run(ctx):
    PenguinSki(ctx).play()
