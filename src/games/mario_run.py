"""原创像素平台跳跃游戏，超级玛丽式玩法的小喵掌机版。

操作：
    左/右键：移动
    上键 / A：跳跃
    B：暂停或继续
    A+B：退出游戏

角色、关卡和音效均为原创，不使用原版游戏素材。
"""

import time

from lib.hardware import Speaker


SCREEN_WIDTH = 160
SCREEN_HEIGHT = 128
WORLD_WIDTH = 840
GROUND_Y = 104
PLAYER_WIDTH = 10
PLAYER_HEIGHT = 14
HIGH_SCORE_FILE = "/pixel_quest_high_score.txt"

COLOR_SKY = 0x18E3
COLOR_CLOUD = 0xD6BA
COLOR_HILL = 0x1A86
COLOR_HILL_DARK = 0x1164
COLOR_GROUND = 0x9A60
COLOR_GROUND_DARK = 0x6200
COLOR_GRASS = 0x2DA5
COLOR_BRICK = 0xE4A2
COLOR_BRICK_DARK = 0x9240
COLOR_BLOCK = 0xBDF7
COLOR_BLOCK_DARK = 0x6B6D
COLOR_COIN = 0xFFE0
COLOR_COIN_DARK = 0xD4A0
COLOR_RED = 0xE8A2
COLOR_RED_DARK = 0xA0E1
COLOR_BLUE = 0x2B5D
COLOR_SKIN = 0xFBD0
COLOR_WHITE = 0xFFFF
COLOR_BLACK = 0x0000
COLOR_ENEMY = 0x4DA6
COLOR_ENEMY_DARK = 0x2462
COLOR_GOAL = 0xEFE0


def overlaps(a, b):
    return (
        a[0] < b[0] + b[2]
        and a[0] + a[2] > b[0]
        and a[1] < b[1] + b[3]
        and a[1] + a[3] > b[1]
    )


class PixelQuest:
    def __init__(self, ctx):
        self.ctx = ctx
        self.disp = ctx.ed.display
        self.sound = Speaker()
        self.high_score = self._load_high_score()
        self.should_exit = False
        self.mode = "ready"
        self._make_level()

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

    def _make_level(self):
        self.platforms = [
            {"x": 0, "y": 104, "w": 144, "h": 24, "kind": "ground"},
            {"x": 160, "y": 104, "w": 160, "h": 24, "kind": "ground"},
            {"x": 368, "y": 104, "w": 152, "h": 24, "kind": "ground"},
            {"x": 548, "y": 104, "w": 152, "h": 24, "kind": "ground"},
            {"x": 716, "y": 104, "w": 124, "h": 24, "kind": "ground"},
            {"x": 72, "y": 84, "w": 32, "h": 8, "kind": "brick"},
            {"x": 112, "y": 66, "w": 24, "h": 8, "kind": "brick"},
            {"x": 204, "y": 84, "w": 40, "h": 8, "kind": "brick"},
            {"x": 258, "y": 68, "w": 32, "h": 8, "kind": "brick"},
            {"x": 330, "y": 92, "w": 18, "h": 8, "kind": "block"},
            {"x": 452, "y": 82, "w": 40, "h": 8, "kind": "brick"},
            {"x": 576, "y": 78, "w": 32, "h": 8, "kind": "brick"},
            {"x": 622, "y": 91, "w": 30, "h": 8, "kind": "brick"},
            {"x": 676, "y": 74, "w": 24, "h": 8, "kind": "block"},
        ]

        self.coins = [
            {"x": 88, "y": 72},
            {"x": 118, "y": 54},
            {"x": 132, "y": 54},
            {"x": 216, "y": 70},
            {"x": 228, "y": 70},
            {"x": 266, "y": 54},
            {"x": 278, "y": 54},
            {"x": 333, "y": 78},
            {"x": 464, "y": 68},
            {"x": 476, "y": 68},
            {"x": 590, "y": 62},
            {"x": 638, "y": 76},
            {"x": 688, "y": 58},
            {"x": 742, "y": 90},
        ]
        for coin in self.coins:
            coin["collected"] = False

        self.enemies = [
            {"x": 196, "y": 96, "min_x": 176, "max_x": 258, "vx": 28},
            {"x": 394, "y": 96, "min_x": 376, "max_x": 454, "vx": 32},
            {"x": 568, "y": 96, "min_x": 556, "max_x": 628, "vx": 35},
            {"x": 738, "y": 96, "min_x": 728, "max_x": 788, "vx": 38},
        ]
        for enemy in self.enemies:
            enemy["alive"] = True

        self.goal_x = 812
        self.player_x = 20.0
        self.player_y = float(GROUND_Y - PLAYER_HEIGHT)
        self.player_vx = 0.0
        self.player_vy = 0.0
        self.facing = 1
        self.on_ground = True
        self.coyote_timer = 0.0
        self.camera_x = 0.0
        self.elapsed = 0.0
        self.score = 0
        self.coins_collected = 0
        self.lives = 3
        self.invulnerable = 0.0
        self.checkpoint_x = 20.0
        self.checkpoint_y = float(GROUND_Y - PLAYER_HEIGHT)
        self.win_timer = 0.0
        self.new_record = False

    def _start(self):
        self._make_level()
        self.mode = "playing"
        self._beep(520, 40)

    def _jump(self):
        if self.mode == "playing" and self.coyote_timer > 0:
            self.player_vy = -194
            self.on_ground = False
            self.coyote_timer = 0
            self._beep(740, 28)

    def _player_box(self):
        return (
            self.player_x + 1,
            self.player_y + 1,
            PLAYER_WIDTH - 2,
            PLAYER_HEIGHT - 1,
        )

    def _platform_box(self, platform):
        return (
            platform["x"],
            platform["y"],
            platform["w"],
            platform["h"],
        )

    def _move_horizontal(self, delta):
        self.player_x += self.player_vx * delta
        if self.player_x < 0:
            self.player_x = 0
            self.player_vx = 0
        if self.player_x + PLAYER_WIDTH > WORLD_WIDTH:
            self.player_x = WORLD_WIDTH - PLAYER_WIDTH
            self.player_vx = 0

        player = self._player_box()
        for platform in self.platforms:
            if overlaps(player, self._platform_box(platform)):
                if self.player_vx > 0:
                    self.player_x = platform["x"] - PLAYER_WIDTH
                elif self.player_vx < 0:
                    self.player_x = platform["x"] + platform["w"]
                self.player_vx = 0
                player = self._player_box()

    def _move_vertical(self, delta):
        self.player_vy += 610 * delta
        self.player_y += self.player_vy * delta
        self.on_ground = False

        player = self._player_box()
        for platform in self.platforms:
            if overlaps(player, self._platform_box(platform)):
                if self.player_vy > 0:
                    self.player_y = platform["y"] - PLAYER_HEIGHT
                    self.player_vy = 0
                    self.on_ground = True
                elif self.player_vy < 0:
                    self.player_y = platform["y"] + platform["h"]
                    self.player_vy = 0
                player = self._player_box()

        if self.player_y > SCREEN_HEIGHT + 20:
            self._lose_life(True)

    def _lose_life(self, pit=False):
        if self.mode != "playing":
            return
        self.lives -= 1
        self._beep(130, 180)
        if self.lives <= 0:
            self._game_over()
            return

        self.invulnerable = 1.2
        if pit:
            self.player_x = self.checkpoint_x
            self.player_y = self.checkpoint_y
            self.player_vx = 0
            self.player_vy = 0
        else:
            self.player_vy = -105
            self.player_vx = -self.facing * 55

    def _game_over(self):
        self.mode = "over"
        if self.score > self.high_score:
            self.high_score = int(self.score)
            self.new_record = True
            self._save_high_score()
        self._beep(95, 260)

    def _win(self):
        self.mode = "win"
        self.score += self.lives * 500
        if self.score > self.high_score:
            self.high_score = int(self.score)
            self.new_record = True
            self._save_high_score()
        self._beep(620, 80)
        self._beep(820, 100)
        self._beep(1040, 140)

    def _update_enemies(self, delta):
        for enemy in self.enemies:
            if not enemy["alive"]:
                continue
            enemy["x"] += enemy["vx"] * delta
            if enemy["x"] < enemy["min_x"]:
                enemy["x"] = enemy["min_x"]
                enemy["vx"] = abs(enemy["vx"])
            elif enemy["x"] > enemy["max_x"]:
                enemy["x"] = enemy["max_x"]
                enemy["vx"] = -abs(enemy["vx"])

            if self.mode != "playing":
                continue
            enemy_box = (enemy["x"] + 1, enemy["y"] + 1, 10, 7)
            if not overlaps(self._player_box(), enemy_box):
                continue

            stomp = self.player_vy > 0 and self.player_y + PLAYER_HEIGHT < enemy["y"] + 8
            if stomp:
                enemy["alive"] = False
                self.player_vy = -128
                self.score += 100
                self._beep(420, 45)
            elif self.invulnerable <= 0:
                self._lose_life(False)

    def _update(self, delta):
        if self.mode != "playing":
            return

        self.elapsed += delta
        self.invulnerable = max(0, self.invulnerable - delta)

        move_left = self.ctx.k_l.button.value() == 0
        move_right = self.ctx.k_r.button.value() == 0
        if move_left and not move_right:
            self.player_vx = max(-91, self.player_vx - 520 * delta)
            self.facing = -1
        elif move_right and not move_left:
            self.player_vx = min(91, self.player_vx + 520 * delta)
            self.facing = 1
        else:
            if self.player_vx > 0:
                self.player_vx = max(0, self.player_vx - 650 * delta)
            else:
                self.player_vx = min(0, self.player_vx + 650 * delta)

        self._move_horizontal(delta)
        self._move_vertical(delta)

        if self.on_ground:
            self.coyote_timer = 0.1
        else:
            self.coyote_timer = max(0, self.coyote_timer - delta)

        if self.player_x > 390:
            self.checkpoint_x = 392.0
            self.checkpoint_y = float(GROUND_Y - PLAYER_HEIGHT)

        for coin in self.coins:
            if coin["collected"]:
                continue
            coin_box = (coin["x"], coin["y"], 7, 7)
            if overlaps(self._player_box(), coin_box):
                coin["collected"] = True
                self.coins_collected += 1
                self.score += 50
                self._beep(980, 30)

        self._update_enemies(delta)

        goal_box = (self.goal_x - 3, 42, 12, GROUND_Y - 42)
        if overlaps(self._player_box(), goal_box):
            self._win()
            return

        target_camera = self.player_x - 54
        target_camera = max(0, min(WORLD_WIDTH - SCREEN_WIDTH, target_camera))
        self.camera_x += (target_camera - self.camera_x) * min(1, delta * 7)
        if self.camera_x < 0:
            self.camera_x = 0

    def _screen_x(self, world_x):
        return int(world_x - self.camera_x)

    def _fill_world_rect(self, x, y, w, h, color):
        sx = self._screen_x(x)
        if sx < 0:
            w += sx
            sx = 0
        if sx + w > SCREEN_WIDTH:
            w = SCREEN_WIDTH - sx
        if w > 0 and y < SCREEN_HEIGHT and y + h > 0:
            self.disp.fill_rect(sx, y, w, h, color)

    def _draw_background(self):
        self.disp.fill(COLOR_SKY)

        cloud_shift = int(self.camera_x * 0.12)
        for index in range(5):
            x = (24 + index * 61 - cloud_shift) % 250 - 35
            y = 18 + (index % 3) * 12
            self.disp.hline(x, y, 15, COLOR_CLOUD)
            self.disp.hline(x + 4, y - 2, 10, COLOR_CLOUD)
            self.disp.hline(x + 9, y + 2, 9, COLOR_CLOUD)

        hill_shift = int(self.camera_x * 0.24)
        for index in range(5):
            center = (30 + index * 72 - hill_shift) % 300 - 50
            for step in range(6):
                width = 54 - step * 8
                x = center - width // 2
                y = 92 - step * 4
                self.disp.hline(x, y, width, COLOR_HILL if index % 2 else COLOR_HILL_DARK)

    def _draw_platform(self, platform):
        sx = self._screen_x(platform["x"])
        if sx + platform["w"] < 0 or sx >= SCREEN_WIDTH:
            return

        x = platform["x"]
        y = platform["y"]
        w = platform["w"]
        h = platform["h"]
        kind = platform["kind"]

        if kind == "ground":
            self._fill_world_rect(x, y, w, h, COLOR_GROUND)
            self._fill_world_rect(x, y, w, 3, COLOR_GRASS)
            self._fill_world_rect(x, y + 4, w, 1, COLOR_GROUND_DARK)
            for row in range(1, 3):
                for column in range(0, w // 12 + 1):
                    self._fill_world_rect(
                        x + column * 12 + 2,
                        y + 7 + row * 6,
                        5,
                        2,
                        COLOR_GROUND_DARK,
                    )
        else:
            color = COLOR_BRICK if kind == "brick" else COLOR_BLOCK
            dark = COLOR_BRICK_DARK if kind == "brick" else COLOR_BLOCK_DARK
            self._fill_world_rect(x, y, w, h, color)
            self._fill_world_rect(x, y + h - 2, w, 2, dark)
            for column in range(0, w, 8):
                self._fill_world_rect(x + column, y, 1, h, dark)
            self._fill_world_rect(x + 2, y + 2, min(5, w - 3), 1, COLOR_WHITE)

    def _draw_coin(self, coin):
        if coin["collected"]:
            return
        sx = self._screen_x(coin["x"])
        if sx < -8 or sx > SCREEN_WIDTH:
            return
        y = coin["y"]
        sparkle = (time.ticks_ms() // 220 + coin["x"]) % 4 != 0
        self.disp.fill_rect(sx + 2, y, 3, 7, COLOR_COIN)
        self.disp.fill_rect(sx + 1, y + 1, 5, 5, COLOR_COIN)
        self.disp.fill_rect(sx + 2, y + 1, 1, 5, COLOR_COIN_DARK)
        if sparkle:
            self.disp.pixel(sx + 3, y + 3, COLOR_WHITE)

    def _draw_enemy(self, enemy):
        if not enemy["alive"]:
            return
        sx = self._screen_x(enemy["x"])
        if sx < -14 or sx > SCREEN_WIDTH:
            return
        y = int(enemy["y"])
        self.disp.fill_rect(sx, y + 2, 12, 6, COLOR_ENEMY)
        self.disp.fill_rect(sx + 2, y, 8, 3, COLOR_ENEMY)
        self.disp.fill_rect(sx + 1, y + 7, 4, 2, COLOR_ENEMY_DARK)
        self.disp.fill_rect(sx + 8, y + 7, 3, 2, COLOR_ENEMY_DARK)
        self.disp.fill_rect(sx + 3, y + 2, 2, 2, COLOR_WHITE)
        self.disp.fill_rect(sx + 8, y + 2, 2, 2, COLOR_WHITE)

    def _draw_player(self):
        if self.invulnerable > 0 and int(self.invulnerable * 14) % 2 == 0:
            return

        x = self._screen_x(self.player_x)
        y = int(self.player_y)
        walk_frame = int(self.elapsed * 10) % 2 if self.on_ground else 0

        self.disp.fill_rect(x + 1, y, 8, 3, COLOR_RED)
        self.disp.fill_rect(x, y + 2, 3, 2, COLOR_RED_DARK)
        self.disp.fill_rect(x + 2, y + 3, 6, 3, COLOR_SKIN)
        self.disp.fill_rect(x + 2, y + 6, 6, 5, COLOR_RED)
        self.disp.fill_rect(x + 2, y + 8, 6, 4, COLOR_BLUE)
        self.disp.fill_rect(x + 1, y + 9, 2, 2, COLOR_SKIN)
        self.disp.fill_rect(x + 7, y + 9, 2, 2, COLOR_SKIN)

        if self.facing > 0:
            self.disp.fill_rect(x + 6, y + 4, 1, 2, COLOR_BLACK)
        else:
            self.disp.fill_rect(x + 3, y + 4, 1, 2, COLOR_BLACK)

        if self.on_ground:
            if walk_frame:
                self.disp.fill_rect(x + 2, y + 12, 3, 2, COLOR_BLUE)
                self.disp.fill_rect(x + 7, y + 12, 2, 2, COLOR_BRICK_DARK)
            else:
                self.disp.fill_rect(x + 1, y + 12, 2, 2, COLOR_BRICK_DARK)
                self.disp.fill_rect(x + 6, y + 12, 3, 2, COLOR_BLUE)
        else:
            self.disp.fill_rect(x + 1, y + 12, 3, 2, COLOR_BRICK_DARK)
            self.disp.fill_rect(x + 7, y + 11, 3, 2, COLOR_BLUE)

    def _draw_goal(self):
        sx = self._screen_x(self.goal_x)
        if sx < -16 or sx > SCREEN_WIDTH + 16:
            return
        self.disp.fill_rect(sx, 42, 2, GROUND_Y - 42, COLOR_WHITE)
        self.disp.fill_rect(sx - 13, 45, 15, 9, COLOR_GOAL)
        self.disp.fill_rect(sx - 10, 48, 7, 3, COLOR_RED)
        self.disp.fill_rect(sx - 4, 86, 10, 3, COLOR_BLOCK_DARK)

    def _draw_hud(self):
        self.disp.fill_rect(0, 0, SCREEN_WIDTH, 12, COLOR_BLACK)
        self.disp.text("S{:05d}".format(min(99999, int(self.score))), 2, 2, COLOR_WHITE)
        self.disp.text("C{:02d}".format(min(99, self.coins_collected)), 73, 2, COLOR_COIN)
        self.disp.text("L{}".format(max(0, self.lives)), 145, 2, COLOR_WHITE)

    def _draw_overlay(self):
        if self.mode == "ready":
            self.disp.fill_rect(14, 30, 132, 76, COLOR_BLACK)
            self.disp.rect(14, 30, 132, 76, COLOR_WHITE)
            self.disp.text("PIXEL QUEST", 40, 39, COLOR_GOAL)
            self.disp.text("LEFT/RIGHT RUN", 28, 55, COLOR_WHITE)
            self.disp.text("A/UP JUMP", 44, 67, COLOR_WHITE)
            self.disp.text("A START B EXIT", 28, 84, COLOR_COIN)
        elif self.mode == "paused":
            self.disp.fill_rect(38, 42, 84, 42, COLOR_BLACK)
            self.disp.rect(38, 42, 84, 42, COLOR_WHITE)
            self.disp.text("PAUSED", 56, 52, COLOR_WHITE)
            self.disp.text("B RESUME", 48, 68, COLOR_COIN)
        elif self.mode == "over":
            self.disp.fill_rect(22, 40, 116, 52, COLOR_BLACK)
            self.disp.rect(22, 40, 116, 52, COLOR_RED)
            self.disp.text("GAME OVER", 44, 48, COLOR_RED)
            self.disp.text("A RETRY", 52, 64, COLOR_WHITE)
            self.disp.text("B EXIT", 56, 76, COLOR_COIN)
        elif self.mode == "win":
            self.disp.fill_rect(18, 34, 124, 64, COLOR_BLACK)
            self.disp.rect(18, 34, 124, 64, COLOR_GOAL)
            self.disp.text("LEVEL CLEAR!", 36, 43, COLOR_GOAL)
            if self.new_record:
                self.disp.text("NEW HIGH!", 48, 57, COLOR_WHITE)
            self.disp.text("SCORE {:05d}".format(int(self.score)), 36, 69, COLOR_COIN)
            self.disp.text("A RETRY  B EXIT", 24, 84, COLOR_WHITE)

    def _draw(self):
        self._draw_background()
        for platform in self.platforms:
            self._draw_platform(platform)
        self._draw_goal()
        for coin in self.coins:
            self._draw_coin(coin)
        for enemy in self.enemies:
            self._draw_enemy(enemy)
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

                if current[4] and current[5]:
                    self.should_exit = True
                    break

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
                    if b_pressed or a_pressed or up_pressed:
                        self.mode = "playing"
                        last_time = time.ticks_ms()
                else:
                    if b_pressed:
                        self.mode = "paused"
                    elif a_pressed or up_pressed:
                        self._jump()

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
    game = PixelQuest(ctx)
    game.play()
