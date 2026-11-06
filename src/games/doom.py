"""原创第一人称光线投射射击游戏，类似 DOOM 的基础玩法。

操作：
    左/右键：转向
    上/下键：前进/后退
    A：射击
    B：暂停；暂停后再次按 B 退出

游戏使用原创地图、角色和音效，不使用 DOOM 的素材。
"""

import math
import random
import time

from lib.hardware import Speaker


SCREEN_WIDTH = 160
SCREEN_HEIGHT = 128
RENDER_WIDTH = 80
HUD_HEIGHT = 12
MAX_WAVES = 3
HIGH_SCORE_FILE = "/ray_station_high_score.txt"

COLOR_BLACK = 0x0000
COLOR_WHITE = 0xFFFF
COLOR_RED = 0xE8A2
COLOR_RED_DARK = 0x8800
COLOR_YELLOW = 0xFFE0
COLOR_ORANGE = 0xFC60
COLOR_CYAN = 0x4DFF
COLOR_GREY = 0x8410
COLOR_DARK_GREY = 0x3186
COLOR_FLOOR = 0x39C7
COLOR_CEILING = 0x0861

# 1 = 普通金属墙，2 = 装甲墙，3 = 最终出口墙。
MAP = (
    "1111111111111111",
    "1000000000000001",
    "1022220222222201",
    "1000000000000001",
    "1110211111110221",
    "1000200000000201",
    "1010201222220201",
    "1010001000000001",
    "1011101011111101",
    "1000001000000001",
    "1111111111110201",
    "1000000000000201",
    "1022222222222201",
    "1000000000000001",
    "1111111111111111",
    "1111111111111111",
)

SPAWN_POINTS = (
    (12.5, 1.5),
    (4.5, 3.5),
    (8.5, 5.5),
    (4.5, 7.5),
    (12.5, 9.5),
    (8.5, 13.5),
)


def shuffle_items(items):
    """MicroPython v1.28 的 random 模块没有 shuffle。"""
    for index in range(len(items) - 1, 0, -1):
        swap_index = random.randint(0, index)
        items[index], items[swap_index] = items[swap_index], items[index]


class RayStation:
    def __init__(self, ctx):
        self.ctx = ctx
        self.disp = ctx.ed.display
        self.sound = Speaker()
        self.high_score = self._load_high_score()
        self.should_exit = False
        self.mode = "ready"
        self.z_buffer = [20.0] * RENDER_WIDTH
        self._reset()

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
        self.player_x = 2.5
        self.player_y = 1.5
        self.angle = 0.0
        self.health = 100
        self.wave = 1
        self.score = 0
        self.enemies = []
        self.shoot_flash = 0.0
        self.hurt_flash = 0.0
        self.new_record = False
        self._spawn_wave()

    def _start(self):
        self._reset()
        self.mode = "playing"
        self._beep(330, 45)
        self._beep(520, 65)

    def _is_wall(self, x, y):
        map_x = int(x)
        map_y = int(y)
        if map_x < 0 or map_y < 0 or map_y >= len(MAP) or map_x >= len(MAP[0]):
            return True
        return MAP[map_y][map_x] != "0"

    def _spawn_wave(self):
        self.enemies = []
        count = self.wave + 1
        points = list(SPAWN_POINTS)
        shuffle_items(points)
        for index in range(min(count, len(points))):
            x, y = points[index]
            self.enemies.append({
                "x": float(x),
                "y": float(y),
                "hp": 1 + (1 if self.wave == 3 and index % 2 == 0 else 0),
                "cooldown": 0.8 + index * 0.2,
                "hurt": 0.0,
            })

    def _try_move(self, direction, delta):
        move_x = math.cos(self.angle) * direction * 1.65 * delta
        move_y = math.sin(self.angle) * direction * 1.65 * delta
        radius = 0.19

        next_x = self.player_x + move_x
        side = radius if move_x > 0 else -radius
        if not self._is_wall(next_x + side, self.player_y):
            self.player_x = next_x

        next_y = self.player_y + move_y
        side = radius if move_y > 0 else -radius
        if not self._is_wall(self.player_x, next_y + side):
            self.player_y = next_y

    def _visibility_depth(self, depth, screen_column):
        column = max(0, min(RENDER_WIDTH - 1, screen_column))
        return depth < self.z_buffer[column] + 0.22

    def _shoot(self):
        if self.mode != "playing":
            return
        self.shoot_flash = 0.13
        direction_x = math.cos(self.angle)
        direction_y = math.sin(self.angle)
        target = None
        target_depth = 20.0

        for enemy in self.enemies:
            if enemy["hp"] <= 0:
                continue
            dx = enemy["x"] - self.player_x
            dy = enemy["y"] - self.player_y
            depth = dx * direction_x + dy * direction_y
            side = -dx * direction_y + dy * direction_x
            if depth <= 0.15 or depth >= target_depth:
                continue

            projected_x = 80.0 + side / depth * 108.0
            screen_column = int(projected_x / 2)
            if abs(projected_x - 80.0) <= 11.0 and depth < 7.0:
                if self._visibility_depth(depth, screen_column):
                    target = enemy
                    target_depth = depth

        self._beep(190, 55)
        if target is not None:
            target["hp"] -= 1
            target["hurt"] = 0.16
            self.score += 25
            if target["hp"] <= 0:
                self.score += 100 + self.wave * 25
                self._beep(95, 95)

    def _game_over(self):
        self.mode = "over"
        if self.score > self.high_score:
            self.high_score = self.score
            self.new_record = True
            self._save_high_score()
        self._beep(80, 280)

    def _win(self):
        self.mode = "win"
        self.score += self.health * 5
        if self.score > self.high_score:
            self.high_score = self.score
            self.new_record = True
            self._save_high_score()
        self._beep(600, 70)
        self._beep(820, 90)
        self._beep(1080, 140)

    def _update_enemies(self, delta):
        player_hit = False
        for enemy in self.enemies:
            if enemy["hp"] <= 0:
                continue

            enemy["hurt"] = max(0, enemy["hurt"] - delta)
            enemy["cooldown"] = max(0, enemy["cooldown"] - delta)
            dx = self.player_x - enemy["x"]
            dy = self.player_y - enemy["y"]
            distance = math.sqrt(dx * dx + dy * dy)

            if distance < 5.5 and distance > 0.52:
                speed = (0.37 + self.wave * 0.04) * delta
                move_x = dx / distance * speed
                move_y = dy / distance * speed
                if not self._is_wall(enemy["x"] + move_x, enemy["y"]):
                    enemy["x"] += move_x
                if not self._is_wall(enemy["x"], enemy["y"] + move_y):
                    enemy["y"] += move_y
            elif distance <= 0.62 and enemy["cooldown"] <= 0:
                enemy["cooldown"] = 1.15
                self.health -= 8 + self.wave * 3
                self.hurt_flash = 0.22
                player_hit = True

        if player_hit:
            self._beep(75, 120)
            if self.health <= 0:
                self.health = 0
                self._game_over()

    def _update(self, delta):
        if self.mode != "playing":
            return

        self.shoot_flash = max(0, self.shoot_flash - delta)
        self.hurt_flash = max(0, self.hurt_flash - delta)

        turn = 0
        if self.ctx.k_l.button.value() == 0:
            turn -= 1
        if self.ctx.k_r.button.value() == 0:
            turn += 1
        self.angle += turn * 1.9 * delta

        move = 0
        if self.ctx.k_u.button.value() == 0:
            move += 1
        if self.ctx.k_d.button.value() == 0:
            move -= 1
        if move:
            self._try_move(move, delta)

        self._update_enemies(delta)
        if self.mode != "playing":
            return

        if all(enemy["hp"] <= 0 for enemy in self.enemies):
            if self.wave >= MAX_WAVES:
                self._win()
            else:
                self.wave += 1
                self.score += 200
                self._beep(700, 90)
                self._spawn_wave()

    def _cast_walls(self, direction_x, direction_y):
        plane_x = -direction_y * 0.66
        plane_y = direction_x * 0.66

        for column in range(RENDER_WIDTH):
            camera_x = 2.0 * column / float(RENDER_WIDTH - 1) - 1.0
            ray_x = direction_x + plane_x * camera_x
            ray_y = direction_y + plane_y * camera_x
            map_x = int(self.player_x)
            map_y = int(self.player_y)

            delta_x = abs(1.0 / ray_x) if ray_x != 0 else 1000000.0
            delta_y = abs(1.0 / ray_y) if ray_y != 0 else 1000000.0
            if ray_x < 0:
                step_x = -1
                side_x = (self.player_x - map_x) * delta_x
            else:
                step_x = 1
                side_x = (map_x + 1.0 - self.player_x) * delta_x
            if ray_y < 0:
                step_y = -1
                side_y = (self.player_y - map_y) * delta_y
            else:
                step_y = 1
                side_y = (map_y + 1.0 - self.player_y) * delta_y

            hit = "0"
            side = 0
            for _ in range(32):
                if side_x < side_y:
                    side_x += delta_x
                    map_x += step_x
                    side = 0
                else:
                    side_y += delta_y
                    map_y += step_y
                    side = 1
                if map_x < 0 or map_y < 0 or map_y >= len(MAP) or map_x >= len(MAP[0]):
                    hit = "1"
                    break
                hit = MAP[map_y][map_x]
                if hit != "0":
                    break

            if side == 0:
                distance = side_x - delta_x
            else:
                distance = side_y - delta_y
            distance = max(0.05, distance)
            self.z_buffer[column] = distance

            wall_height = min(420, int(SCREEN_HEIGHT / distance))
            draw_start = max(HUD_HEIGHT, int(SCREEN_HEIGHT / 2 - wall_height / 2))
            draw_end = min(SCREEN_HEIGHT - 1, int(SCREEN_HEIGHT / 2 + wall_height / 2))

            if hit == "2":
                color = COLOR_DARK_GREY if side else 0x5AEB
            elif hit == "3":
                color = COLOR_RED_DARK if side else COLOR_RED
            elif side:
                color = 0x39E7
            else:
                color = 0x6B6D

            if distance > 7.0:
                color = COLOR_DARK_GREY
            elif distance > 4.0:
                color = 0x39E7 if side else 0x4A69

            self.disp.fill_rect(
                column * 2,
                draw_start,
                2,
                max(1, draw_end - draw_start + 1),
                color,
            )

    def _draw_environment(self):
        self.disp.fill_rect(0, HUD_HEIGHT, SCREEN_WIDTH, 52 - HUD_HEIGHT, COLOR_CEILING)
        self.disp.fill_rect(0, 52, SCREEN_WIDTH, SCREEN_HEIGHT - 52, COLOR_FLOOR)
        for index in range(4):
            color = 0x0861 + index * 0x0821
            self.disp.hline(0, HUD_HEIGHT + index * 10, SCREEN_WIDTH, color)
        for index in range(4):
            color = 0x39C7 + index * 0x0421
            self.disp.hline(0, 76 + index * 12, SCREEN_WIDTH, color)

    def _draw_enemy(self, enemy, direction_x, direction_y):
        if enemy["hp"] <= 0:
            return

        dx = enemy["x"] - self.player_x
        dy = enemy["y"] - self.player_y
        depth = dx * direction_x + dy * direction_y
        if depth <= 0.18 or depth > 9.0:
            return

        side = -dx * direction_y + dy * direction_x
        screen_x = int(80.0 + side / depth * 108.0)
        if screen_x < -30 or screen_x > SCREEN_WIDTH + 30:
            return

        column = int(screen_x / 2)
        if not self._visibility_depth(depth, column):
            return

        size = max(6, min(78, int(44.0 / depth)))
        width = max(4, int(size * 0.58))
        bob = int(math.sin(time.ticks_ms() / 170.0) * min(2, size / 20.0))
        top = 64 - size // 2 + bob
        left = screen_x - width // 2
        body_color = COLOR_WHITE if enemy["hurt"] > 0 else COLOR_RED_DARK

        self.disp.fill_rect(left + 1, top + size // 4, width - 2, size // 2, body_color)
        self.disp.fill_rect(left + width // 4, top, width // 2, size // 3, COLOR_RED)

        horn_width = max(1, width // 4)
        self.disp.fill_rect(left, top + 1, horn_width, max(2, size // 6), COLOR_ORANGE)
        self.disp.fill_rect(left + width - horn_width, top + 1, horn_width, max(2, size // 6), COLOR_ORANGE)

        eye_y = top + max(3, size // 4)
        eye_size = max(1, size // 10)
        self.disp.fill_rect(left + width // 5, eye_y, eye_size, eye_size, COLOR_YELLOW)
        self.disp.fill_rect(left + width - width // 5 - eye_size, eye_y, eye_size, eye_size, COLOR_YELLOW)

        mouth_y = top + size // 2
        self.disp.fill_rect(left + width // 3, mouth_y, width // 3, max(1, size // 14), COLOR_BLACK)

    def _draw_crosshair(self):
        self.disp.hline(75, 64, 10, COLOR_WHITE)
        self.disp.vline(79, 60, 9, COLOR_WHITE)
        self.disp.pixel(79, 64, COLOR_RED)

    def _draw_weapon(self):
        self.disp.fill_rect(72, 104, 16, 24, COLOR_DARK_GREY)
        self.disp.fill_rect(75, 108, 10, 16, COLOR_GREY)
        self.disp.fill_rect(78, 96, 4, 14, COLOR_DARK_GREY)
        self.disp.fill_rect(76, 112, 8, 7, COLOR_BLACK)
        if self.shoot_flash > 0:
            self.disp.fill_rect(75, 91, 10, 7, COLOR_YELLOW)
            self.disp.fill_rect(78, 87, 4, 11, COLOR_ORANGE)

    def _draw_hud(self):
        self.disp.fill_rect(0, 0, SCREEN_WIDTH, HUD_HEIGHT, COLOR_BLACK)
        health_color = COLOR_RED if self.health <= 30 else COLOR_WHITE
        self.disp.text("H{:03d}".format(max(0, self.health)), 2, 2, health_color)
        self.disp.text("W{}/{}".format(self.wave, MAX_WAVES), 47, 2, COLOR_CYAN)
        score_text = "S{:04d}".format(min(9999, self.score))
        self.disp.text(score_text, SCREEN_WIDTH - len(score_text) * 8 - 2, 2, COLOR_YELLOW)

    def _draw_overlay(self):
        if self.mode == "ready":
            self.disp.fill_rect(10, 24, 140, 88, COLOR_BLACK)
            self.disp.rect(10, 24, 140, 88, COLOR_RED)
            self.disp.text("RAY STATION", 40, 34, COLOR_RED)
            self.disp.text("LEFT/RIGHT TURN", 28, 50, COLOR_WHITE)
            self.disp.text("UP/DOWN MOVE", 36, 62, COLOR_WHITE)
            self.disp.text("A FIRE  B PAUSE", 28, 74, COLOR_YELLOW)
            self.disp.text("A START B EXIT", 28, 94, COLOR_CYAN)
        elif self.mode == "paused":
            self.disp.fill_rect(31, 41, 98, 46, COLOR_BLACK)
            self.disp.rect(31, 41, 98, 46, COLOR_WHITE)
            self.disp.text("PAUSED", 56, 50, COLOR_WHITE)
            self.disp.text("A RESUME", 52, 64, COLOR_CYAN)
            self.disp.text("B EXIT", 56, 76, COLOR_YELLOW)
        elif self.mode == "over":
            self.disp.fill_rect(21, 38, 118, 56, COLOR_BLACK)
            self.disp.rect(21, 38, 118, 56, COLOR_RED)
            self.disp.text("YOU DIED", 52, 46, COLOR_RED)
            if self.new_record:
                self.disp.text("NEW HIGH!", 48, 60, COLOR_YELLOW)
            self.disp.text("A RETRY", 52, 74, COLOR_WHITE)
            self.disp.text("B EXIT", 56, 84, COLOR_YELLOW)
        elif self.mode == "win":
            self.disp.fill_rect(18, 34, 124, 62, COLOR_BLACK)
            self.disp.rect(18, 34, 124, 62, COLOR_CYAN)
            self.disp.text("STATION CLEAR", 36, 44, COLOR_CYAN)
            if self.new_record:
                self.disp.text("NEW HIGH!", 48, 58, COLOR_YELLOW)
            self.disp.text("A RETRY  B EXIT", 24, 82, COLOR_WHITE)

    def _draw(self):
        self._draw_environment()
        direction_x = math.cos(self.angle)
        direction_y = math.sin(self.angle)
        self._cast_walls(direction_x, direction_y)

        # 远的敌人先画，近的敌人后画。
        ordered = sorted(
            self.enemies,
            key=lambda enemy: (
                enemy["x"] - self.player_x
            ) * (enemy["x"] - self.player_x)
            + (
                enemy["y"] - self.player_y
            ) * (enemy["y"] - self.player_y),
            reverse=True,
        )
        for enemy in ordered:
            self._draw_enemy(enemy, direction_x, direction_y)

        self._draw_weapon()
        self._draw_crosshair()
        if self.hurt_flash > 0:
            self.disp.rect(0, HUD_HEIGHT, SCREEN_WIDTH, SCREEN_HEIGHT - HUD_HEIGHT, COLOR_RED)
            self.disp.rect(1, HUD_HEIGHT + 1, SCREEN_WIDTH - 2, SCREEN_HEIGHT - HUD_HEIGHT - 2, COLOR_RED)
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
                    elif a_pressed:
                        self._shoot()

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
    game = RayStation(ctx)
    game.play()
