"""Chrome 风格恐龙跑酷，小喵掌机 MicroPython 版。

操作：
    上键 / A：开始、跳跃、重新开始
    下键：下蹲
    B：暂停或继续；在开始和结束画面退出游戏
    A+B：游戏中直接退出
"""

import random
import time

from lib.hardware import Speaker


SCREEN_WIDTH = 160
SCREEN_HEIGHT = 128
GROUND_Y = 105
DINO_X = 18
HIGH_SCORE_FILE = "/dino_high_score.txt"
START_SPEED = 82
MAX_SPEED = 138
JUMP_VELOCITY = -250
GRAVITY = 640
MIN_OBSTACLE_GAP = 105
MAX_OBSTACLE_GAP = 160

COLOR_BLACK = 0x0000
COLOR_NAVY = 0x0841
COLOR_WHITE = 0xFFFF
COLOR_CREAM = 0xFFE0
COLOR_GREY = 0x8410
COLOR_DARK_GREY = 0x4208
COLOR_GREEN = 0x07E0
COLOR_GREEN_DARK = 0x03E0
COLOR_ORANGE = 0xFD20


class DinoRun:
    def __init__(self, ctx):
        self.ctx = ctx
        self.disp = ctx.ed.display
        self.sound = Speaker()
        self.high_score = self._load_high_score()
        self.mode = "ready"
        self.elapsed = 0
        self.distance = 0
        self.score = 0
        self.speed = START_SPEED
        self.jump_y = GROUND_Y
        self.jump_vy = 0
        self.ducking = False
        self.obstacles = []
        self.obstacle_count = 0
        self.next_gap = 140
        self.milestone = 0
        self.last_hit = 0
        self.should_exit = False
        self.new_record = False

    def _load_high_score(self):
        try:
            with open(HIGH_SCORE_FILE, "r") as score_file:
                return max(0, int(score_file.read().strip()))
        except Exception:
            return 0

    def _save_high_score(self):
        try:
            with open(HIGH_SCORE_FILE, "w") as score_file:
                score_file.write(str(int(self.high_score)))
        except Exception:
            pass

    def _beep(self, frequency, duration):
        try:
            self.sound.beep(frequency, duration)
        except Exception:
            pass

    def _reset(self):
        self.elapsed = 0
        self.distance = 0
        self.score = 0
        self.speed = START_SPEED
        self.jump_y = GROUND_Y
        self.jump_vy = 0
        self.ducking = False
        self.obstacles = []
        self.obstacle_count = 0
        self.next_gap = 140
        self.milestone = 0
        self.last_hit = 0
        self.new_record = False
        self.mode = "playing"
        self._beep(520, 45)

    def _jump(self):
        if self.jump_y >= GROUND_Y and not self.ducking:
            self.jump_vy = JUMP_VELOCITY
            self.jump_y -= 1
            self._beep(720, 30)

    def _game_over(self):
        self.mode = "over"
        self.ducking = False
        self.last_hit = time.ticks_ms()
        if self.score > self.high_score:
            self.high_score = int(self.score)
            self.new_record = True
            self._save_high_score()
        self._beep(120, 240)

    def _spawn_obstacle(self):
        # 低空翼龙需要下蹲或跳过，高空翼龙只需要保持奔跑。
        if self.obstacle_count > 0 and self.score > 70 and random.randint(0, 3) == 0:
            y = 74 if random.randint(0, 1) == 0 else 54
            self.obstacles.append({
                "kind": "bird",
                "x": SCREEN_WIDTH + 4,
                "y": y,
                "w": 20,
                "h": 11,
            })
        else:
            if self.obstacle_count == 0:
                height = 18
            else:
                height = random.choice((18, 24, 29))
            self.obstacles.append({
                "kind": "cactus",
                "x": SCREEN_WIDTH + 4,
                "y": GROUND_Y - height,
                "w": 11,
                "h": height,
            })

        # 障碍物间距按距离计算，速度提升后仍保留足够反应时间。
        self.next_gap = random.randint(MIN_OBSTACLE_GAP, MAX_OBSTACLE_GAP)
        self.obstacle_count += 1

    def _is_night(self):
        return (int(self.score) // 600) % 2 == 1

    def _palette(self):
        if self._is_night():
            return {
                "bg": COLOR_NAVY,
                "fg": COLOR_CREAM,
                "muted": 0x9CF3,
                "ground": 0x6B6D,
                "cactus": COLOR_GREEN,
            }
        return {
            "bg": COLOR_BLACK,
            "fg": COLOR_WHITE,
            "muted": COLOR_GREY,
            "ground": COLOR_DARK_GREY,
            "cactus": COLOR_GREEN_DARK,
        }

    def _update(self, delta):
        if self.mode != "playing":
            return

        self.elapsed += delta
        down_pressed = self.ctx.k_d.button.value() == 0
        self.ducking = down_pressed and self.jump_y >= GROUND_Y - 1

        if self.jump_y < GROUND_Y:
            self.ducking = False
            self.jump_y += self.jump_vy * delta
            self.jump_vy += GRAVITY * delta
            if self.jump_y >= GROUND_Y:
                self.jump_y = GROUND_Y
                self.jump_vy = 0
                self.ducking = down_pressed

        movement = self.speed * delta
        self.distance += movement
        self.score = self.distance / 5.0
        self.speed = min(MAX_SPEED, START_SPEED + self.score * 0.16)

        current_milestone = int(self.score) // 100
        if current_milestone > self.milestone:
            self.milestone = current_milestone
            self._beep(920, 35)

        self.next_gap -= movement
        if self.next_gap <= 0:
            self._spawn_obstacle()

        alive = []
        for obstacle in self.obstacles:
            obstacle["x"] -= movement
            if obstacle["x"] > -28:
                alive.append(obstacle)
        self.obstacles = alive

        if self._collides():
            self._game_over()

    def _collides(self):
        if self.ducking:
            player = (DINO_X - 1, int(self.jump_y) - 15, 34, 15)
        else:
            player = (DINO_X + 1, int(self.jump_y) - 30, 25, 30)

        px, py, pw, ph = player
        for obstacle in self.obstacles:
            if obstacle["kind"] == "bird":
                box = (
                    int(obstacle["x"]) + 2,
                    int(obstacle["y"]) + 2,
                    16,
                    9,
                )
            else:
                box = (
                    int(obstacle["x"]) + 2,
                    int(obstacle["y"]) + 1,
                    7,
                    int(obstacle["h"]) - 2,
                )

            ox, oy, ow, oh = box
            if px < ox + ow and px + pw > ox and py < oy + oh and py + ph > oy:
                return True
        return False

    def _draw_dino(self, palette, foot_y, ducking, frame, dead=False):
        color = palette["fg"]
        bg = palette["bg"]
        x = DINO_X
        foot = int(foot_y)

        if ducking:
            self.disp.fill_rect(x - 8, foot - 11, 10, 3, color)
            self.disp.fill_rect(x, foot - 14, 19, 10, color)
            self.disp.fill_rect(x + 17, foot - 18, 15, 10, color)
            self.disp.fill_rect(x + 29, foot - 16, 4, 4, color)
            self.disp.fill_rect(x + 2, foot - 4, 7, 4, color)
            self.disp.fill_rect(x + 19, foot - 4, 7, 4, color)
            self.disp.fill_rect(x + 27, foot - 16, 2, 2, bg)
        else:
            self.disp.fill_rect(x - 7, foot - 16, 9, 3, color)
            self.disp.fill_rect(x, foot - 20, 16, 12, color)
            self.disp.fill_rect(x + 11, foot - 27, 7, 10, color)
            self.disp.fill_rect(x + 14, foot - 31, 14, 10, color)
            self.disp.fill_rect(x + 27, foot - 27, 4, 4, color)
            self.disp.fill_rect(x + 21, foot - 24, 5, 2, bg)

            if dead:
                self.disp.fill_rect(x + 22, foot - 29, 4, 2, bg)
                self.disp.fill_rect(x + 23, foot - 28, 2, 1, color)
            else:
                self.disp.fill_rect(x + 23, foot - 28, 2, 2, bg)

            if frame:
                self.disp.fill_rect(x + 3, foot - 9, 4, 9, color)
                self.disp.fill_rect(x + 13, foot - 9, 4, 6, color)
                self.disp.fill_rect(x + 15, foot - 3, 7, 3, color)
            else:
                self.disp.fill_rect(x + 3, foot - 9, 4, 6, color)
                self.disp.fill_rect(x, foot - 3, 7, 3, color)
                self.disp.fill_rect(x + 13, foot - 9, 4, 9, color)

    def _draw_cactus(self, obstacle, palette):
        x = int(obstacle["x"])
        y = int(obstacle["y"])
        h = int(obstacle["h"])
        color = palette["cactus"]

        self.disp.fill_rect(x + 4, y, 4, h, color)
        self.disp.fill_rect(x + 2, y + 5, 3, 8, color)
        self.disp.fill_rect(x + 8, y + 10, 3, 7, color)
        if h > 20:
            self.disp.fill_rect(x, y + 3, 3, 8, color)
            self.disp.fill_rect(x + 3, y + 10, 3, 2, color)
            self.disp.fill_rect(x + 8, y + 6, 3, 9, color)
            self.disp.fill_rect(x + 7, y + 14, 3, 2, color)

    def _draw_bird(self, obstacle, palette):
        x = int(obstacle["x"])
        y = int(obstacle["y"])
        color = palette["fg"]
        wing_up = (time.ticks_ms() // 130) % 2 == 0

        self.disp.fill_rect(x + 4, y + 4, 12, 3, color)
        self.disp.fill_rect(x + 14, y + 2, 5, 3, color)
        self.disp.fill_rect(x + 19, y + 3, 3, 2, color)
        if wing_up:
            self.disp.line(x + 7, y + 4, x + 1, y, color)
            self.disp.line(x + 8, y + 4, x + 6, y, color)
            self.disp.line(x + 10, y + 7, x + 7, y + 10, color)
        else:
            self.disp.line(x + 7, y + 4, x + 2, y + 10, color)
            self.disp.line(x + 9, y + 4, x + 8, y + 9, color)
            self.disp.line(x + 11, y + 4, x + 15, y, color)

    def _draw_clouds(self, palette):
        cloud_color = palette["muted"]
        shift = int(self.distance * 0.09)
        for index in range(3):
            x = (44 + index * 62 - shift) % 210 - 25
            y = 20 + index * 13
            self.disp.hline(x, y, 12, cloud_color)
            self.disp.hline(x + 4, y - 2, 8, cloud_color)
            self.disp.hline(x + 8, y + 2, 7, cloud_color)

    def _draw_night_stars(self):
        positions = (
            (13, 25), (35, 18), (62, 31), (89, 20),
            (117, 29), (143, 19), (151, 38), (78, 45),
        )
        for index, position in enumerate(positions):
            if (time.ticks_ms() // 300 + index) % 3 != 0:
                self.disp.pixel(position[0], position[1], COLOR_WHITE)

    def _draw_ground(self, palette):
        self.disp.hline(0, GROUND_Y, SCREEN_WIDTH, palette["fg"])
        offset = int(self.distance) % 31
        for index in range(-1, 7):
            x = index * 31 - offset
            self.disp.hline(x, GROUND_Y + 8, 8, palette["ground"])
            self.disp.hline(x + 13, GROUND_Y + 17, 5, palette["ground"])

    def _draw_hud(self, palette):
        high = "HI {:04d}".format(min(9999, int(self.high_score)))
        score = "{:04d}".format(min(9999, int(self.score)))
        self.disp.text(high, 2, 2, palette["muted"])
        self.disp.text(score, SCREEN_WIDTH - len(score) * 8 - 2, 2, palette["fg"])
        self.disp.hline(0, 12, SCREEN_WIDTH, palette["ground"])

    def _draw_overlay(self, palette):
        if self.mode == "ready":
            self.disp.text("DINO RUN", 48, 33, palette["fg"])
            self.disp.text("UP/A  JUMP", 43, 51, palette["muted"])
            self.disp.text("DOWN   DUCK", 39, 63, palette["muted"])
            self.disp.text("A/UP START", 43, 80, COLOR_ORANGE)
            self.disp.text("B EXIT", 56, 92, palette["muted"])
        elif self.mode == "paused":
            self.disp.fill_rect(39, 43, 82, 38, palette["bg"])
            self.disp.rect(39, 43, 82, 38, palette["fg"])
            self.disp.text("PAUSED", 56, 52, palette["fg"])
            self.disp.text("B RESUME", 48, 67, palette["muted"])
        elif self.mode == "over":
            self.disp.text("GAME OVER", 44, 43, COLOR_ORANGE)
            if self.new_record:
                self.disp.text("NEW HIGH!", 48, 57, palette["fg"])
            self.disp.text("A/UP RETRY", 43, 72, palette["muted"])
            self.disp.text("B EXIT", 56, 85, palette["muted"])

    def _draw(self):
        palette = self._palette()
        self.disp.fill(palette["bg"])

        if self._is_night():
            self._draw_night_stars()
        else:
            self._draw_clouds(palette)

        self._draw_hud(palette)
        self._draw_ground(palette)

        for obstacle in self.obstacles:
            if obstacle["kind"] == "bird":
                self._draw_bird(obstacle, palette)
            else:
                self._draw_cactus(obstacle, palette)

        frame = int(self.elapsed * 10) % 2
        self._draw_dino(
            palette,
            self.jump_y,
            self.ducking,
            frame,
            dead=self.mode == "over",
        )
        self._draw_overlay(palette)
        self.disp.show()

    def play(self):
        saved = (
            self.ctx.k_u.down_func,
            self.ctx.k_d.down_func,
            self.ctx.k_a.down_func,
            self.ctx.k_b.down_func,
        )

        for button in (
            self.ctx.k_u,
            self.ctx.k_d,
            self.ctx.k_a,
            self.ctx.k_b,
        ):
            button.down_func = None

        pins = (
            self.ctx.k_u.button,
            self.ctx.k_d.button,
            self.ctx.k_a.button,
            self.ctx.k_b.button,
        )
        previous = [True, True, True, True]
        last_time = time.ticks_ms()

        try:
            while not self.should_exit:
                now = time.ticks_ms()
                delta = min(0.04, time.ticks_diff(now, last_time) / 1000.0)
                last_time = now

                current = [pin.value() == 0 for pin in pins]
                up_down = current[0] and not previous[0]
                a_down = current[2] and not previous[2]
                b_down = current[3] and not previous[3]

                if current[2] and current[3]:
                    self.should_exit = True
                    break

                if self.mode == "ready":
                    if a_down or up_down:
                        self._reset()
                    elif b_down:
                        self.should_exit = True
                        break
                elif self.mode == "over":
                    if a_down or up_down:
                        self._reset()
                    elif b_down:
                        self.should_exit = True
                        break
                elif self.mode == "paused":
                    if b_down or a_down or up_down:
                        self.mode = "playing"
                        last_time = time.ticks_ms()
                else:
                    if b_down:
                        self.mode = "paused"
                    elif a_down or up_down:
                        self._jump()

                previous = current
                self._update(delta)
                self._draw()
                time.sleep_ms(16)
        finally:
            self.ctx.k_u.down_func = saved[0]
            self.ctx.k_d.down_func = saved[1]
            self.ctx.k_a.down_func = saved[2]
            self.ctx.k_b.down_func = saved[3]
            try:
                self.sound.pin.deinit()
            except Exception:
                pass


def run(ctx):
    game = DinoRun(ctx)
    game.play()
