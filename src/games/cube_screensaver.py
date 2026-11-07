"""MicroPython software-rendered rotating-cube screen saver.

Controls:
    Up/Down: change rotation speed
    A: pause or resume
    B: exit
"""

import time

from games.software3d import Software3D
from lib.hardware import Speaker


SCREEN_WIDTH = 160
SCREEN_HEIGHT = 128
ROTATION_SPEEDS = (0.45, 0.75, 1.1)

CUBE_VERTICES = (
    (-1.0, -1.0, -1.0),
    (1.0, -1.0, -1.0),
    (1.0, 1.0, -1.0),
    (-1.0, 1.0, -1.0),
    (-1.0, -1.0, 1.0),
    (1.0, -1.0, 1.0),
    (1.0, 1.0, 1.0),
    (-1.0, 1.0, 1.0),
)

CUBE_FACES = (
    ((0, 1, 2, 3), 0xE8A2),
    ((4, 5, 6, 7), 0xFD20),
    ((0, 4, 7, 3), 0x4DFF),
    ((1, 2, 6, 5), 0x07E0),
    ((3, 7, 6, 2), 0xF81F),
    ((0, 1, 5, 4), 0xFFE0),
)


class CubeScreensaver:
    def __init__(self, ctx):
        self.ctx = ctx
        self.disp = ctx.ed.display
        self.gl = Software3D(self.disp, SCREEN_WIDTH, SCREEN_HEIGHT)
        self.gl.set_camera(4.2, 60.0)
        self.mesh = self.gl.prepare_mesh(CUBE_VERTICES, CUBE_FACES)
        try:
            self.sound = Speaker()
        except Exception:
            self.sound = None
        self.should_exit = False

    def _beep(self, frequency, duration):
        if self.sound is None:
            return
        try:
            self.sound.beep(frequency, duration)
        except Exception:
            pass

    def _read_buttons(self, previous):
        pins = (
            self.ctx.k_u.button,
            self.ctx.k_d.button,
            self.ctx.k_l.button,
            self.ctx.k_r.button,
            self.ctx.k_a.button,
            self.ctx.k_b.button,
        )
        current = [pin.value() == 0 for pin in pins]
        pressed = [
            current[index] and not previous[index]
            for index in range(6)
        ]
        return current, pressed

    def _draw_overlay(self, paused, speed_index):
        self.disp.text(self.gl.backend + " 3D", 50, 1, 0x7BEF)
        speed = "SPD{}".format(speed_index + 1)
        self.disp.text(speed, 2, 1, 0x8410)
        self.disp.text("A PAUSE  B EXIT", 16, 119, 0x8410)
        if paused:
            self.disp.fill_rect(49, 53, 62, 22, 0x0000)
            self.disp.rect(49, 53, 62, 22, 0x4DFF)
            self.disp.text("PAUSED", 60, 60, 0xFFFFFF)

    def _draw(self, angle_x, angle_y, angle_z, paused, speed_index):
        self.gl.clear(0x0000)
        self.gl.draw_prepared_mesh(
            self.mesh,
            (angle_x, angle_y, angle_z),
            1.18,
            (80.0, 64.0),
            0x0000,
            return_projection=False,
        )
        self._draw_overlay(paused, speed_index)
        self.gl.show()

    def play(self):
        buttons = (
            self.ctx.k_u,
            self.ctx.k_d,
            self.ctx.k_l,
            self.ctx.k_r,
            self.ctx.k_a,
            self.ctx.k_b,
        )
        saved = [button.down_func for button in buttons]
        for button in buttons:
            button.down_func = None

        previous = [True] * 6
        angle_x = 0.45
        angle_y = 0.0
        angle_z = 0.2
        speed_index = 1
        paused = False
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
                if pressed[4]:
                    paused = not paused
                    self._beep(520 if not paused else 260, 30)
                if pressed[0] and speed_index < len(ROTATION_SPEEDS) - 1:
                    speed_index += 1
                    self._beep(620, 20)
                if pressed[1] and speed_index > 0:
                    speed_index -= 1
                    self._beep(420, 20)

                if not paused:
                    speed = ROTATION_SPEEDS[speed_index]
                    angle_x += 0.78 * speed * delta
                    angle_y += 1.12 * speed * delta
                    angle_z += 0.36 * speed * delta

                previous = current
                self._draw(angle_x, angle_y, angle_z, paused, speed_index)
                time.sleep_ms(12)
        finally:
            for index, button in enumerate(buttons):
                button.down_func = saved[index]
            if self.sound is not None:
                try:
                    self.sound.pin.deinit()
                except Exception:
                    pass


def run(ctx):
    CubeScreensaver(ctx).play()
