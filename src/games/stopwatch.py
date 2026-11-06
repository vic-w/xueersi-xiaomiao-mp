import machine
import time

from lib.hardware import Speaker


COLOR_WHITE = 0xFFFF
COLOR_GRAY = 0x7BEF
COLOR_GREEN = 0x07E0
COLOR_YELLOW = 0xFFE0

TONE_A = 720
TONE_B = 460
TONE_UP = 620
TONE_DOWN = 380
TONE_DURATION_MS = 45


def format_time(total_ms):
    """Format milliseconds as MM:SS.hh, or H:MM:SS.hh after one hour."""
    total_ms = max(0, total_ms)
    hours = total_ms // 3600000
    minutes = (total_ms // 60000) % 60
    seconds = (total_ms // 1000) % 60
    hundredths = (total_ms % 1000) // 10
    if hours:
        return "{}:{:02d}:{:02d}.{:02d}".format(
            hours, minutes, seconds, hundredths
        )
    return "{:02d}:{:02d}.{:02d}".format(minutes, seconds, hundredths)


class Stopwatch:
    def __init__(self, ctx):
        self.ctx = ctx
        self.disp = ctx.ed.display
        try:
            self.sound = Speaker()
        except Exception:
            self.sound = None
        self.accumulated_ms = 0
        self.started_at = 0
        self.running = False
        self.laps = []
        self.last_lap_ms = 0
        self.selected_lap = 0

    def beep(self, frequency):
        if self.sound is None:
            return
        try:
            self.sound.beep(frequency, TONE_DURATION_MS)
        except Exception:
            pass

    def elapsed_ms(self):
        if self.running:
            now = time.ticks_ms()
            return self.accumulated_ms + time.ticks_diff(now, self.started_at)
        return self.accumulated_ms

    def toggle(self):
        now = time.ticks_ms()
        if self.running:
            self.accumulated_ms += time.ticks_diff(now, self.started_at)
            self.running = False
            self.selected_lap = max(0, len(self.laps) - 1)
        else:
            self.started_at = now
            self.running = True
            self.selected_lap = max(0, len(self.laps) - 1)

    def lap_or_reset(self):
        if self.running:
            total = self.elapsed_ms()
            self.laps.append(total - self.last_lap_ms)
            self.last_lap_ms = total
            self.selected_lap = len(self.laps) - 1
        elif self.accumulated_ms or self.laps:
            self.accumulated_ms = 0
            self.last_lap_ms = 0
            self.laps = []
            self.selected_lap = 0

    def browse_lap(self, direction):
        if self.running or not self.laps:
            return
        self.selected_lap = max(
            0,
            min(len(self.laps) - 1, self.selected_lap + direction),
        )

    def draw(self):
        disp = self.disp
        disp.fill(0)

        disp.text("STOPWATCH", 0, 0, COLOR_WHITE)
        if self.running:
            status = "RUN"
            status_color = COLOR_GREEN
        elif self.accumulated_ms or self.laps:
            status = "STOP"
            status_color = COLOR_YELLOW
        else:
            status = "IDLE"
            status_color = COLOR_GRAY
        disp.text(status, 128, 0, status_color)

        elapsed = format_time(self.elapsed_ms())
        time_x = (160 - len(elapsed) * 8) // 2
        disp.text(elapsed, time_x, 20, COLOR_YELLOW)

        disp.text("LAPS {}".format(len(self.laps)), 0, 10, COLOR_GRAY)

        if self.laps:
            selected = max(0, min(len(self.laps) - 1, self.selected_lap))
            page_start = (selected // 4) * 4
            visible = self.laps[page_start:page_start + 4]
            for index, lap in enumerate(visible):
                lap_number = page_start + index
                is_selected = lap_number == selected
                color = COLOR_YELLOW if is_selected else COLOR_WHITE
                line = "#{:02d} {}".format(
                    lap_number + 1,
                    format_time(lap),
                )
                disp.text(line, 16, 38 + index * 10, color)
                if is_selected and not self.running:
                    disp.text(">", 0, 38 + index * 10, color)

        disp.text("A: START/STOP", 0, 82, COLOR_GRAY)
        disp.text("B: LAP/RESET", 0, 94, COLOR_GRAY)
        disp.text("UP/DN: BROWSE", 0, 106, COLOR_GRAY)
        disp.text("A+B: MENU", 0, 118, COLOR_GRAY)
        disp.show()

    def run(self):
        saved = (
            self.ctx.k_u.down_func,
            self.ctx.k_d.down_func,
            self.ctx.k_l.down_func,
            self.ctx.k_r.down_func,
            self.ctx.k_a.down_func,
            self.ctx.k_b.down_func,
        )

        for btn in (
            self.ctx.k_u,
            self.ctx.k_d,
            self.ctx.k_l,
            self.ctx.k_r,
            self.ctx.k_a,
            self.ctx.k_b,
        ):
            btn.down_func = None
            btn.button.irq(handler=None)

        pin_a = self.ctx.k_a.button
        pin_b = self.ctx.k_b.button
        pin_u = self.ctx.k_u.button
        pin_d = self.ctx.k_d.button
        prev_a = pin_a.value()
        prev_b = pin_b.value()
        prev_u = pin_u.value()
        prev_d = pin_d.value()
        active = True

        try:
            while active:
                state_a = pin_a.value()
                state_b = pin_b.value()
                state_u = pin_u.value()
                state_d = pin_d.value()
                a_pressed = prev_a and not state_a
                b_pressed = prev_b and not state_b
                u_pressed = prev_u and not state_u
                d_pressed = prev_d and not state_d

                if a_pressed or b_pressed:
                    if not state_a and not state_b:
                        active = False
                        self.beep(TONE_A)
                        self.beep(TONE_B)
                    elif a_pressed:
                        self.toggle()
                        self.beep(TONE_A)
                    else:
                        self.lap_or_reset()
                        self.beep(TONE_B)
                    time.sleep_ms(80)
                elif u_pressed or d_pressed:
                    if u_pressed:
                        self.browse_lap(-1)
                        self.beep(TONE_UP)
                    else:
                        self.browse_lap(1)
                        self.beep(TONE_DOWN)
                    time.sleep_ms(80)

                prev_a = pin_a.value()
                prev_b = pin_b.value()
                prev_u = pin_u.value()
                prev_d = pin_d.value()
                self.draw()
                time.sleep_ms(20)
        finally:
            self.ctx.k_u.down_func = saved[0]
            self.ctx.k_d.down_func = saved[1]
            self.ctx.k_l.down_func = saved[2]
            self.ctx.k_r.down_func = saved[3]
            self.ctx.k_a.down_func = saved[4]
            self.ctx.k_b.down_func = saved[5]
            for btn in (
                self.ctx.k_u,
                self.ctx.k_d,
                self.ctx.k_l,
                self.ctx.k_r,
                self.ctx.k_a,
                self.ctx.k_b,
            ):
                btn.irq = btn.button.irq(
                    handler=btn._detection,
                    trigger=machine.Pin.IRQ_FALLING,
                )


def run(ctx):
    Stopwatch(ctx).run()
