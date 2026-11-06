"""原创 FC 风格公路竞速游戏，小喵掌机 MicroPython 版。

操作：
    左/右键：转向
    上键 / A：加速
    下键：刹车
    B：暂停；暂停后再次按 B 退出
"""

import math
import random
import time

from lib.hardware import Speaker


SCREEN_WIDTH = 160
SCREEN_HEIGHT = 128
HORIZON_Y = 38
PLAYER_BOTTOM = 122
PLAYER_WIDTH = 14
PLAYER_HEIGHT = 20
FINISH_DISTANCE = 5200
HIGH_SCORE_FILE = "/fc_racing_high_score.txt"

COLOR_BLACK = 0x0000
COLOR_WHITE = 0xFFFF
COLOR_SKY = 0x4A9C
COLOR_NIGHT = 0x0841
COLOR_HILL = 0x2A45
COLOR_GRASS = 0x2B42
COLOR_GRASS_DARK = 0x1A22
COLOR_ROAD = 0x4208
COLOR_ROAD_DARK = 0x2104
COLOR_RED = 0xE8A2
COLOR_RED_DARK = 0xA0E1
COLOR_YELLOW = 0xFFE0
COLOR_BLUE = 0x2B5D
COLOR_CYAN = 0x4DFF
COLOR_GREY = 0x8410
COLOR_TREE = 0x2DA5
COLOR_TREE_DARK = 0x1A63


def overlaps(a, b):
    return (
        a[0] < b[0] + b[2]
        and a[0] + a[2] > b[0]
        and a[1] < b[1] + b[3]
        and a[1] + a[3] > b[1]
    )


class FcRacing:
    def __init__(self, ctx):
        self.ctx = ctx
        self.disp = ctx.ed.display
        self.sound = Speaker()
        self.high_score = self._load_high_score()
        self.should_exit = False
        self.mode = "ready"
        self._make_race()

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

    def _make_race(self):
        self.distance = 0.0
        self.speed = 32.0
        self.player_x = 80.0
        self.lives = 3
        self.traffic = []
        self.spawn_timer = 0.7
        self.invulnerable = 0.0
        self.shake = 0.0
        self.elapsed = 0.0
        self.milestone = 0
        self.new_record = False

    def _start(self):
        self._make_race()
        self.mode = "playing"
        self._beep(360, 50)

    def _meters(self):
        return int(self.distance / 8)

    def _is_night(self):
        return (self._meters() // 220) % 2 == 1

    def _road_metrics(self, y):
        p = min(1.0, max(0.0, (y - HORIZON_Y) / float(SCREEN_HEIGHT - HORIZON_Y)))
        half_width = 18.0 + 55.0 * p * p
        bend = (
            math.sin(self.distance * 0.006 + (1.0 - p) * 1.6) * 28.0
            + math.sin(self.distance * 0.017) * 7.0
        )
        bend *= (1.0 - p) * (1.0 - p)
        return 80.0 + bend, half_width

    def _traffic_x(self, car):
        center, half_width = self._road_metrics(car["y"])
        return center + car["lane"] * half_width * 0.48

    def _car_scale(self, y):
        progress = min(1.0, max(0.0, (y - HORIZON_Y) / float(SCREEN_HEIGHT - HORIZON_Y)))
        return 0.46 + progress * 0.72

    def _spawn_car(self):
        lane = random.choice((-1, 0, 1))
        self.traffic.append({
            "y": float(HORIZON_Y + 3),
            "lane": lane,
            "speed": random.uniform(24, 52),
            "color": random.choice((COLOR_BLUE, COLOR_YELLOW, COLOR_GREY, COLOR_CYAN)),
            "passed": False,
        })
        delay = max(0.52, 1.15 - self.speed / 240.0)
        self.spawn_timer = delay + random.uniform(0.1, 0.55)

    def _hit_car(self):
        if self.invulnerable > 0 or self.mode != "playing":
            return
        self.lives -= 1
        self.speed = min(self.speed, 24)
        self.invulnerable = 1.25
        self.shake = 0.35
        self._beep(110, 170)
        if self.lives <= 0:
            self._game_over()

    def _game_over(self):
        self.mode = "over"
        score = self._meters()
        if score > self.high_score:
            self.high_score = score
            self.new_record = True
            self._save_high_score()
        self._beep(85, 260)

    def _win(self):
        self.mode = "win"
        score = self._meters() + self.lives * 150
        if score > self.high_score:
            self.high_score = score
            self.new_record = True
            self._save_high_score()
        self._beep(560, 70)
        self._beep(760, 90)
        self._beep(980, 130)

    def _update(self, delta):
        if self.mode != "playing":
            return

        self.elapsed += delta
        self.invulnerable = max(0, self.invulnerable - delta)
        self.shake = max(0, self.shake - delta)

        accelerate = (
            self.ctx.k_u.button.value() == 0
            or self.ctx.k_a.button.value() == 0
        )
        brake = self.ctx.k_d.button.value() == 0

        if accelerate and not brake:
            self.speed += 43 * delta
        elif brake:
            self.speed -= 105 * delta
        else:
            self.speed -= 18 * delta
        self.speed = max(18.0, min(122.0, self.speed))

        steer = 0
        if self.ctx.k_l.button.value() == 0:
            steer -= 1
        if self.ctx.k_r.button.value() == 0:
            steer += 1
        self.player_x += steer * 72 * delta

        center, half_width = self._road_metrics(PLAYER_BOTTOM)
        road_left = center - half_width + 8
        road_right = center + half_width - 8
        if self.player_x < road_left:
            self.player_x = road_left
            self.speed = min(self.speed, 36)
            if steer < 0:
                self.shake = max(self.shake, 0.08)
        elif self.player_x > road_right:
            self.player_x = road_right
            self.speed = min(self.speed, 36)
            if steer > 0:
                self.shake = max(self.shake, 0.08)

        self.distance += self.speed * delta
        if self.distance >= FINISH_DISTANCE:
            self._win()
            return

        current_milestone = self._meters() // 100
        if current_milestone > self.milestone:
            self.milestone = current_milestone
            self._beep(820, 35)

        self.spawn_timer -= delta
        if self.spawn_timer <= 0 and len(self.traffic) < 9:
            self._spawn_car()

        alive = []
        player_box = (
            self.player_x - PLAYER_WIDTH / 2,
            PLAYER_BOTTOM - PLAYER_HEIGHT,
            PLAYER_WIDTH,
            PLAYER_HEIGHT,
        )

        for car in self.traffic:
            car["y"] += (self.speed - car["speed"]) * delta
            if car["y"] < HORIZON_Y - 12 or car["y"] > SCREEN_HEIGHT + 18:
                continue

            car_x = self._traffic_x(car)
            scale = self._car_scale(car["y"])
            car_width = 10 * scale
            car_height = 16 * scale
            car_box = (
                car_x - car_width / 2,
                car["y"] - car_height / 2,
                car_width,
                car_height,
            )

            if car["y"] > 82 and overlaps(player_box, car_box):
                self._hit_car()
                continue

            if not car["passed"] and car["y"] > PLAYER_BOTTOM - 10:
                car["passed"] = True
                self.distance += 45

            alive.append(car)
        self.traffic = alive

    def _draw_background(self):
        night = self._is_night()
        sky = COLOR_NIGHT if night else COLOR_SKY
        grass = COLOR_GRASS_DARK if night else COLOR_GRASS
        hill = 0x18A3 if night else COLOR_HILL

        self.disp.fill(grass)
        self.disp.fill_rect(0, 0, SCREEN_WIDTH, HORIZON_Y + 1, sky)

        if night:
            for index in range(18):
                x = (index * 37 + 11) % 154
                y = 5 + (index * 17) % 28
                if (time.ticks_ms() // 450 + index) % 4:
                    self.disp.pixel(x, y, COLOR_WHITE)

        hill_shift = int(self.distance * 0.025)
        for index in range(5):
            center = (24 + index * 47 - hill_shift) % 230 - 35
            for step in range(4):
                width = 38 - step * 8
                self.disp.hline(center - width // 2, HORIZON_Y - step * 3, width, hill)

    def _draw_road(self):
        night = self._is_night()
        road = COLOR_ROAD_DARK if night else COLOR_ROAD
        road_line = COLOR_GREY if night else COLOR_WHITE

        for y in range(HORIZON_Y, SCREEN_HEIGHT):
            center, half_width = self._road_metrics(y)
            left = max(0, int(center - half_width))
            right = min(SCREEN_WIDTH - 1, int(center + half_width))
            width = right - left + 1
            self.disp.hline(left, y, width, road)

            stripe = (int(self.distance * 0.075) + int((y - HORIZON_Y) * 0.42)) % 12 < 6
            edge_color = COLOR_YELLOW if stripe else COLOR_RED
            self.disp.hline(left, y, 2, edge_color)
            self.disp.hline(right - 1, y, 2, edge_color)

            if (int(self.distance * 0.08) + int((y - HORIZON_Y) * 0.55)) % 10 < 4:
                self.disp.pixel(int(left + width / 3), y, road_line)
                self.disp.pixel(int(left + width * 2 / 3), y, road_line)

    def _draw_trees(self):
        shift = int(self.distance * 0.32)
        for index in range(9):
            y = HORIZON_Y + ((index * 29 + shift) % 96)
            center, half_width = self._road_metrics(y)
            scale = 1.0 + (y - HORIZON_Y) / 90.0
            size = max(2, int(4 * scale))
            for side in (-1, 1):
                x = int(center + side * (half_width + 7 * scale))
                if 0 <= x < SCREEN_WIDTH:
                    self.disp.fill_rect(x - size, y - size * 2, size * 2, size * 3, COLOR_TREE)
                    self.disp.fill_rect(x - 1, y - size * 2 - 2, 2, size * 2, COLOR_TREE_DARK)

    def _draw_finish_line(self):
        remaining = FINISH_DISTANCE - self.distance
        if remaining <= 0 or remaining > 600:
            return
        progress = 1.0 - remaining / 600.0
        y = HORIZON_Y + int((PLAYER_BOTTOM - HORIZON_Y) * progress)
        center, half_width = self._road_metrics(y)
        left = int(center - half_width)
        right = int(center + half_width)
        tile = max(2, int(3 + progress * 4))
        for x in range(left, right, tile):
            color = COLOR_WHITE if ((x - left) // tile) % 2 == 0 else COLOR_BLACK
            self.disp.fill_rect(x, y, min(tile, right - x), tile, color)

    def _draw_traffic_car(self, car):
        if car["y"] < HORIZON_Y - 5 or car["y"] > SCREEN_HEIGHT + 8:
            return
        x = int(self._traffic_x(car))
        scale = self._car_scale(car["y"])
        width = max(4, int(10 * scale))
        height = max(7, int(16 * scale))
        y = int(car["y"] - height / 2)

        self.disp.fill_rect(x - width // 2, y + 2, width, height - 3, car["color"])
        self.disp.fill_rect(x - width // 2 + 1, y + 3, width - 2, 2, COLOR_BLACK)
        self.disp.fill_rect(x - width // 2 - 1, y + 5, 2, max(2, height // 3), COLOR_BLACK)
        self.disp.fill_rect(x + width // 2 - 1, y + 5, 2, max(2, height // 3), COLOR_BLACK)
        self.disp.fill_rect(x - max(1, width // 4), y + height - 3, max(1, width // 4), 2, COLOR_RED)
        self.disp.fill_rect(x + 1, y + height - 3, max(1, width // 4), 2, COLOR_RED)

    def _draw_player(self):
        if self.invulnerable > 0 and int(self.invulnerable * 15) % 2 == 0:
            return

        x = int(self.player_x)
        y = PLAYER_BOTTOM - PLAYER_HEIGHT
        jitter = 0
        if self.shake > 0:
            jitter = 1 if int(self.shake * 100) % 2 else -1
        x += jitter

        self.disp.fill_rect(x - 7, y + 4, 14, 14, COLOR_RED)
        self.disp.fill_rect(x - 5, y, 10, 8, COLOR_RED)
        self.disp.fill_rect(x - 4, y + 2, 8, 4, COLOR_CYAN)
        self.disp.fill_rect(x - 6, y + 7, 12, 5, COLOR_RED_DARK)
        self.disp.fill_rect(x - 8, y + 9, 3, 7, COLOR_BLACK)
        self.disp.fill_rect(x + 5, y + 9, 3, 7, COLOR_BLACK)
        self.disp.fill_rect(x - 6, y + 17, 3, 2, COLOR_BLACK)
        self.disp.fill_rect(x + 3, y + 17, 3, 2, COLOR_BLACK)
        self.disp.fill_rect(x - 6, y + 11, 2, 2, COLOR_YELLOW)
        self.disp.fill_rect(x + 4, y + 11, 2, 2, COLOR_YELLOW)

    def _draw_hud(self):
        meters = self._meters()
        self.disp.fill_rect(0, 0, SCREEN_WIDTH, 12, COLOR_BLACK)
        self.disp.text("{:04d}M".format(min(9999, meters)), 2, 2, COLOR_WHITE)
        self.disp.text("L{}".format(max(0, self.lives)), 76, 2, COLOR_YELLOW)
        speed_text = "V{:03d}".format(int(self.speed))
        self.disp.text(speed_text, SCREEN_WIDTH - len(speed_text) * 8 - 2, 2, COLOR_WHITE)

    def _draw_overlay(self):
        if self.mode == "ready":
            self.disp.fill_rect(13, 27, 134, 86, COLOR_BLACK)
            self.disp.rect(13, 27, 134, 86, COLOR_WHITE)
            self.disp.text("TURBO HIGHWAY", 32, 36, COLOR_YELLOW)
            self.disp.text("LEFT/RIGHT STEER", 24, 52, COLOR_WHITE)
            self.disp.text("A/UP GAS", 47, 64, COLOR_WHITE)
            self.disp.text("DOWN BRAKE", 43, 76, COLOR_WHITE)
            self.disp.text("A START B EXIT", 28, 94, COLOR_CYAN)
        elif self.mode == "paused":
            self.disp.fill_rect(38, 42, 84, 42, COLOR_BLACK)
            self.disp.rect(38, 42, 84, 42, COLOR_WHITE)
            self.disp.text("PAUSED", 56, 52, COLOR_WHITE)
            self.disp.text("A RESUME B EXIT", 24, 68, COLOR_YELLOW)
        elif self.mode == "over":
            self.disp.fill_rect(22, 40, 116, 52, COLOR_BLACK)
            self.disp.rect(22, 40, 116, 52, COLOR_RED)
            self.disp.text("GAME OVER", 44, 48, COLOR_RED)
            self.disp.text("A RETRY", 52, 64, COLOR_WHITE)
            self.disp.text("B EXIT", 56, 76, COLOR_YELLOW)
        elif self.mode == "win":
            self.disp.fill_rect(17, 33, 126, 66, COLOR_BLACK)
            self.disp.rect(17, 33, 126, 66, COLOR_YELLOW)
            self.disp.text("FINISH!", 52, 42, COLOR_YELLOW)
            if self.new_record:
                self.disp.text("NEW HIGH!", 48, 56, COLOR_WHITE)
            self.disp.text("{:04d} METERS".format(self._meters()), 32, 69, COLOR_WHITE)
            self.disp.text("A RETRY  B EXIT", 24, 84, COLOR_CYAN)

    def _draw(self):
        self._draw_background()
        self._draw_trees()
        self._draw_road()
        self._draw_finish_line()
        for car in self.traffic:
            self._draw_traffic_car(car)
        if self.mode in ("playing", "paused"):
            self._draw_player()
        self._draw_hud()
        self._draw_overlay()
        self.disp.show()

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
        pressed = [current[index] and not previous[index] for index in range(6)]
        return current, pressed

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
        last_time = time.ticks_ms()

        try:
            while not self.should_exit:
                now = time.ticks_ms()
                delta = min(0.04, time.ticks_diff(now, last_time) / 1000.0)
                last_time = now

                current, pressed = self._read_buttons(previous)
                up_pressed = pressed[0]
                a_pressed = pressed[4]
                b_pressed = pressed[5]

                if self.mode == "ready":
                    if a_pressed or up_pressed:
                        self._start()
                    elif b_pressed:
                        self.should_exit = True
                        break
                elif self.mode in ("over", "win"):
                    if a_pressed or up_pressed:
                        self._start()
                    elif b_pressed:
                        self.should_exit = True
                        break
                elif self.mode == "paused":
                    if a_pressed or up_pressed:
                        self.mode = "playing"
                        last_time = time.ticks_ms()
                    elif b_pressed:
                        self.should_exit = True
                        break
                else:
                    if b_pressed:
                        self.mode = "paused"

                previous = current
                self._update(delta)
                self._draw()
                time.sleep_ms(16)
        finally:
            for index, button in enumerate(buttons):
                button.down_func = saved[index]
            try:
                self.sound.pin.deinit()
            except Exception:
                pass


def run(ctx):
    game = FcRacing(ctx)
    game.play()
