"""
jarvis_hud.py  -  JARVIS / FRIDAY style heads-up display for StudyMate.

JarvisCore   : animated arc-reactor canvas (reacts to standby / listening /
               thinking / speaking).
JarvisPanel  : the full HUD card = core + boot log + live telemetry +
               persona / hands-free controls.

Nothing in here talks to the network or the microphone. It only reads state
from the StudyMate app object (see the jarvis_* methods in main.py).
"""

import math
import random
import time
import tkinter as tk


# =============================================================
# COLOUR HELPERS
# =============================================================

def _rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def _hex(rgb):
    return "#%02X%02X%02X" % tuple(
        max(0, min(255, int(round(channel)))) for channel in rgb
    )


def _mix(first, second, amount):
    amount = max(0.0, min(1.0, amount))
    a, b = _rgb(first), _rgb(second)
    return _hex(a[i] + (b[i] - a[i]) * amount for i in range(3))


STATE_TEXT = {
    "standby": "STANDBY",
    "listening": "LISTENING",
    "thinking": "PROCESSING",
    "speaking": "RESPONDING",
}


# =============================================================
# ANIMATED ARC-REACTOR CORE
# =============================================================

class JarvisCore(tk.Canvas):

    BARS = 48
    COIL = 12

    # how "excited" the core is in each state
    LEVEL = {
        "standby": 0.25,
        "listening": 0.75,
        "thinking": 0.95,
        "speaking": 0.85,
    }

    # core breathing speed in each state
    PULSE = {
        "standby": 1.4,
        "listening": 3.0,
        "thinking": 6.0,
        "speaking": 5.0,
    }

    def __init__(
        self,
        master,
        bg,
        palette,
        state_provider,
        on_click=None,
        size=270
    ):
        super().__init__(
            master,
            width=size,
            height=size,
            bg=bg,
            highlightthickness=0,
            bd=0
        )

        self.size = size
        self.cx = size / 2
        self.cy = size / 2
        self.R = size / 2 - 8
        self.bg = bg

        self.main = palette["main"]
        self.alt = palette["alt"]
        self.warm = palette["warm"]

        self.dim = _mix(bg, self.main, 0.28)
        self.mid = _mix(bg, self.main, 0.55)

        self.state_provider = state_provider
        self.on_click = on_click

        self.level = self.LEVEL["standby"]
        self.t0 = time.time()
        self._last = self.t0
        self._frame = 0
        self._job = None

        self.a_ticks = 0.0
        self.a_b = 0.0
        self.a_c = 0.0
        self.a_d = 0.0
        self.a_tri = 0.0

        self.wave = [0.0] * self.BARS

        self._build()

        if on_click is not None:
            self.configure(cursor="hand2")
            self.bind("<Button-1>", lambda event: on_click())

        self._tick()

    # ---------------------------------------------------------
    # Geometry helpers
    # ---------------------------------------------------------

    def _box(self, fraction):
        r = self.R * fraction
        return (self.cx - r, self.cy - r, self.cx + r, self.cy + r)

    # ---------------------------------------------------------
    # Build all canvas items once (they are only reconfigured later)
    # ---------------------------------------------------------

    def _build(self):
        s = self.size

        # Corner brackets
        bracket = 18
        pad = 3

        for sx, sy in ((0, 0), (1, 0), (0, 1), (1, 1)):
            x = pad if sx == 0 else s - pad
            y = pad if sy == 0 else s - pad
            dx = bracket if sx == 0 else -bracket
            dy = bracket if sy == 0 else -bracket

            self.create_line(
                x + dx, y, x, y, x, y + dy,
                fill=self.dim, width=2
            )

        # Faint crosshair
        self.create_line(
            self.cx, 6, self.cx, s - 6, fill=_mix(self.bg, self.main, 0.10)
        )
        self.create_line(
            6, self.cy, s - 6, self.cy, fill=_mix(self.bg, self.main, 0.10)
        )

        # Outer tick ring (a dashed thick arc looks like tick marks)
        self.ticks = self.create_arc(
            *self._box(1.0),
            start=0, extent=359, style="arc",
            width=7, dash=(1, 5), outline=self.dim
        )

        self.thin = self.create_oval(
            *self._box(0.935), outline=self.dim, width=1
        )

        # Segmented ring B (3 long arcs)
        self.ring_b = [
            self.create_arc(
                *self._box(0.87),
                start=i * 120, extent=72, style="arc",
                width=5, outline=self.mid
            )
            for i in range(3)
        ]

        # Segmented ring C (4 short bright arcs)
        self.ring_c = [
            self.create_arc(
                *self._box(0.79),
                start=i * 90, extent=36, style="arc",
                width=2, outline=self.main
            )
            for i in range(4)
        ]

        # Dashed ring D
        self.ring_d = self.create_arc(
            *self._box(0.755),
            start=0, extent=359, style="arc",
            width=1, dash=(2, 4), outline=self.dim
        )

        # Scanner sweep (only visible while thinking)
        self.scanner = self.create_arc(
            *self._box(0.66),
            start=0, extent=48, style="arc",
            width=5, outline=self.warm, state="hidden"
        )

        # Radial waveform bars
        self.bars = [
            self.create_line(
                self.cx, self.cy, self.cx, self.cy,
                fill=self.dim, width=2, capstyle="round"
            )
            for _ in range(self.BARS)
        ]

        # Coil ring (12 segments that light up)
        self.coil = [
            self.create_arc(
                *self._box(0.465),
                start=i * (360 / self.COIL) + 3,
                extent=360 / self.COIL - 8,
                style="arc", width=8, outline=self.dim
            )
            for i in range(self.COIL)
        ]

        # Core glow layers (outermost first)
        self.glow = [
            self.create_oval(0, 0, 0, 0, outline="", fill=self.bg)
            for _ in range(6)
        ]

        self.core_rim = self.create_oval(
            *self._box(0.19), outline=self.main, width=2
        )

        # Reactor triangle
        self.triangle = self.create_polygon(
            0, 0, 0, 0, 0, 0,
            outline=_mix(self.main, "#FFFFFF", 0.55),
            fill="", width=2
        )

        self.center_dot = self.create_oval(
            self.cx - 3, self.cy - 3, self.cx + 3, self.cy + 3,
            fill="#FFFFFF", outline=""
        )

    # ---------------------------------------------------------
    # Animation loop
    # ---------------------------------------------------------

    def _tick(self):
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return

        now = time.time()
        dt = min(0.1, now - self._last)
        self._last = now
        t = now - self.t0
        self._frame += 1

        try:
            state = self.state_provider() or "standby"
        except Exception:
            state = "standby"

        if state not in self.LEVEL:
            state = "standby"

        self.level += (self.LEVEL[state] - self.level) * min(1.0, dt * 4)
        level = self.level
        speed = 1 + 2.2 * level

        try:
            self._animate_rings(dt, t, state, speed)
            self._animate_waveform(dt, t, state)
            self._animate_coil(t, state, level)
            self._animate_core(t, state, level)
        except tk.TclError:
            return

        self._job = self.after(40, self._tick)

    def _animate_rings(self, dt, t, state, speed):
        self.a_ticks = (self.a_ticks - 8 * speed * dt) % 360
        self.a_b = (self.a_b + 22 * speed * dt) % 360
        self.a_c = (self.a_c - 38 * speed * dt) % 360
        self.a_d = (self.a_d + 14 * speed * dt) % 360

        self.itemconfigure(self.ticks, start=self.a_ticks)
        self.itemconfigure(self.ring_d, start=self.a_d)

        for i, item in enumerate(self.ring_b):
            self.itemconfigure(item, start=(self.a_b + i * 120) % 360)

        for i, item in enumerate(self.ring_c):
            self.itemconfigure(item, start=(self.a_c + i * 90) % 360)

        if state == "thinking":
            self.itemconfigure(
                self.scanner,
                state="normal",
                start=(-t * 320) % 360
            )
        else:
            self.itemconfigure(self.scanner, state="hidden")

    def _animate_waveform(self, dt, t, state):
        r0 = self.R * 0.52
        span = self.R * 0.21
        smooth = min(1.0, dt * 14)

        recolor = self._frame % 2 == 0

        for i in range(self.BARS):
            if state == "listening":
                target = 0.12 + 0.55 * random.random() * (
                    0.5 + 0.5 * abs(math.sin(t * 3 + i * 0.3))
                )
            elif state == "speaking":
                envelope = 0.45 + 0.35 * math.sin(t * 7) + 0.15 * math.sin(t * 13 + i)
                target = max(0.05, envelope) * (0.4 + 0.6 * random.random())
            elif state == "thinking":
                target = 0.14 + 0.12 * math.sin(t * 5 + i * 0.9)
            else:
                target = 0.07 + 0.05 * math.sin(t * 1.3 + i * 0.4)

            self.wave[i] += (target - self.wave[i]) * smooth
            w = max(0.03, min(1.0, self.wave[i]))

            angle = i / self.BARS * math.tau - math.pi / 2
            cos_a, sin_a = math.cos(angle), math.sin(angle)
            r1 = r0 + span * w

            self.coords(
                self.bars[i],
                self.cx + cos_a * r0, self.cy + sin_a * r0,
                self.cx + cos_a * r1, self.cy + sin_a * r1
            )

            if recolor:
                self.itemconfigure(
                    self.bars[i],
                    fill=_mix(self.dim, self.main, 0.25 + 0.75 * w)
                )

    def _animate_coil(self, t, state, level):
        energy = sum(self.wave) / self.BARS

        for i, item in enumerate(self.coil):
            if state == "thinking":
                head = (t * 2.2) % 1.0
                distance = (head - i / self.COIL) % 1.0
                brightness = max(0.15, 1 - distance * 2.2)
                color = _mix(
                    _mix(self.dim, self.main, brightness),
                    self.warm,
                    brightness * 0.45
                )
            elif state in ("listening", "speaking"):
                brightness = min(1.0, 0.35 + energy * 1.6)
                color = _mix(self.dim, self.main, brightness)
            else:
                brightness = 0.35 + 0.15 * math.sin(t * 1.5 + i * 0.5)
                color = _mix(self.dim, self.main, brightness)

            self.itemconfigure(item, outline=color)

    def _animate_core(self, t, state, level):
        pulse = (math.sin(t * self.PULSE[state]) + 1) / 2
        energy = sum(self.wave) / self.BARS

        count = len(self.glow)

        for i, item in enumerate(self.glow):
            radius = self.R * (0.40 - i * 0.04) * (1 + 0.035 * pulse)

            amount = 0.05 + i * 0.085 + 0.10 * pulse * level + 0.18 * energy

            self.coords(
                item,
                self.cx - radius, self.cy - radius,
                self.cx + radius, self.cy + radius
            )
            self.itemconfigure(
                item, fill=_mix(self.bg, self.main, min(0.92, amount))
            )

        self.itemconfigure(
            self.core_rim,
            outline=_mix(self.main, "#FFFFFF", 0.25 * pulse)
        )

        # Rotating reactor triangle
        self.a_tri = (self.a_tri + (0.6 + 2.5 * level) * 0.04) % math.tau
        tri_r = self.R * 0.13
        points = []

        for k in range(3):
            angle = self.a_tri + k * math.tau / 3 - math.pi / 2
            points.extend([
                self.cx + math.cos(angle) * tri_r,
                self.cy + math.sin(angle) * tri_r
            ])

        self.coords(self.triangle, *points)

    def stop(self):
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except Exception:
                pass

            self._job = None


# =============================================================
# FULL HUD PANEL
# =============================================================

class JarvisPanel(tk.Frame):
    """
    Core + info column. `app` must provide:

        card_bg, surface, text, muted, green, orange, red, fade_color()
        jarvis_state()            -> "standby"|"listening"|"thinking"|"speaking"
        jarvis_core_click()
        jarvis_telemetry()        -> [(key, value), ...]  (fixed length)
        jarvis_boot_lines()       -> [str, ...]
        jarvis_greet()
        jarvis_set_persona(key)
        toggle_handsfree()
        jarvis_handsfree          -> bool
    """

    def __init__(self, parent, app, personas, persona_key, palette, boot=False):
        bg = app.card_bg

        super().__init__(parent, bg=bg)

        self.app = app
        self.bg = bg
        self.palette = palette
        self.main = palette["main"]
        self.warm = palette["warm"]

        persona = personas[persona_key]

        self._job = None
        self._boot_job = None
        self._count = 0
        self._t0 = time.time()
        self.tele_values = []

        mono = "Consolas"

        # ---------------- Core ----------------
        self.core = JarvisCore(
            self,
            bg=bg,
            palette=palette,
            state_provider=app.jarvis_state,
            on_click=app.jarvis_core_click,
            size=270
        )
        self.core.pack(side="left", padx=(4, 24), pady=4)

        # ---------------- Info column ----------------
        info = tk.Frame(self, bg=bg)
        info.pack(side="left", fill="both", expand=True)

        tk.Label(
            info,
            text=persona["full"],
            bg=bg,
            fg=self.main,
            font=(mono, 22, "bold")
        ).pack(anchor="w")

        tk.Label(
            info,
            text=persona["tagline"],
            bg=bg,
            fg=app.muted,
            font=(mono, 8)
        ).pack(anchor="w", pady=(0, 8))

        status_row = tk.Frame(info, bg=bg)
        status_row.pack(anchor="w")

        self.state_dot = tk.Label(
            status_row, text="●", bg=bg, fg=self.main, font=(mono, 11)
        )
        self.state_dot.pack(side="left")

        self.state_label = tk.Label(
            status_row,
            text="STANDBY",
            bg=bg,
            fg=self.main,
            font=(mono, 11, "bold")
        )
        self.state_label.pack(side="left", padx=(6, 0))

        self._rule(info, pady=(8, 8))

        self.boot_label = tk.Label(
            info,
            text="",
            bg=bg,
            fg=_mix(bg, self.main, 0.75),
            font=(mono, 9),
            justify="left",
            anchor="w"
        )
        self.boot_label.pack(anchor="w")

        self._rule(info, pady=(8, 8))

        # Telemetry grid
        grid = tk.Frame(info, bg=bg)
        grid.pack(anchor="w", fill="x")

        for index, (key, value) in enumerate(app.jarvis_telemetry()):
            row = index // 2
            column = (index % 2) * 2

            tk.Label(
                grid, text=key, bg=bg, fg=app.muted, font=(mono, 8)
            ).grid(row=row, column=column, sticky="w", padx=(0, 8), pady=1)

            value_label = tk.Label(
                grid, text=value, bg=bg, fg=app.text, font=(mono, 9, "bold")
            )
            value_label.grid(
                row=row, column=column + 1, sticky="w", padx=(0, 26), pady=1
            )

            self.tele_values.append(value_label)

        self._rule(info, pady=(10, 8))

        # Controls
        controls = tk.Frame(info, bg=bg)
        controls.pack(anchor="w")

        for key, item in personas.items():
            self._chip(
                controls,
                item["label"],
                lambda k=key: app.jarvis_set_persona(k),
                active=(key == persona_key)
            ).pack(side="left", padx=(0, 6))

        tk.Frame(controls, bg=bg, width=10).pack(side="left")

        self.hf_chip = self._chip(
            controls,
            "HANDS-FREE",
            app.toggle_handsfree,
            active=False
        )
        self.hf_chip.pack(side="left", padx=(0, 6))

        self._chip(
            controls,
            "TALK",
            app.jarvis_core_click,
            active=False
        ).pack(side="left")

        # ---------------- Start ----------------
        lines = app.jarvis_boot_lines()

        if boot:
            self._type_boot(lines)
        else:
            self.boot_label.configure(text="\n".join(lines))

        self.bind("<Destroy>", self._on_destroy)
        self._refresh()

    # ---------------------------------------------------------
    # Small builders
    # ---------------------------------------------------------

    def _rule(self, parent, pady=(6, 6)):
        tk.Frame(
            parent,
            bg=_mix(self.bg, self.main, 0.28),
            height=1
        ).pack(fill="x", pady=pady)

    def _chip(self, parent, text, command, active=False):
        app = self.app

        base = _mix(app.surface, self.main, 0.40 if active else 0.0)
        hover = _mix(app.surface, self.main, 0.55)

        chip = tk.Label(
            parent,
            text=text,
            bg=base,
            fg=app.text,
            font=("Consolas", 8, "bold"),
            padx=10,
            pady=5,
            cursor="hand2",
            highlightthickness=1,
            highlightbackground=_mix(base, self.main, 0.55 if active else 0.25)
        )

        chip._base = base
        chip._hover = hover

        chip.bind(
            "<Enter>",
            lambda event, c=chip: c.configure(bg=c._hover)
        )
        chip.bind(
            "<Leave>",
            lambda event, c=chip: c.configure(bg=c._base)
        )
        chip.bind("<Button-1>", lambda event: command())

        return chip

    # ---------------------------------------------------------
    # Boot sequence
    # ---------------------------------------------------------

    def _type_boot(self, lines):
        full = "\n".join(lines)
        position = [0]

        def step():
            try:
                if not self.winfo_exists():
                    return
            except tk.TclError:
                return

            position[0] = min(len(full), position[0] + 2)
            self.boot_label.configure(text=full[:position[0]] + "▌")

            if position[0] < len(full):
                self._boot_job = self.after(14, step)
            else:
                self.boot_label.configure(text=full)
                self._boot_job = None

                try:
                    self.app.jarvis_greet()
                except Exception as error:
                    print("Greeting error:", error)

        step()

    # ---------------------------------------------------------
    # Live refresh
    # ---------------------------------------------------------

    def _refresh(self):
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return

        app = self.app

        try:
            state = app.jarvis_state()

            color = {
                "standby": self.main,
                "listening": app.green,
                "thinking": self.warm,
                "speaking": self.main,
            }.get(state, self.main)

            blink = 0.55 + 0.45 * math.sin((time.time() - self._t0) * 4)

            self.state_label.configure(
                text=STATE_TEXT.get(state, "STANDBY"), fg=color
            )
            self.state_dot.configure(fg=_mix(self.bg, color, blink))

            if self._count % 4 == 0:
                for label, (key, value) in zip(
                    self.tele_values, app.jarvis_telemetry()
                ):
                    label.configure(text=value)

            armed = bool(getattr(app, "jarvis_handsfree", False))
            target = _mix(app.surface, self.main, 0.55 if armed else 0.0)

            self.hf_chip._base = target
            self.hf_chip.configure(
                bg=target,
                highlightbackground=_mix(target, self.main, 0.6 if armed else 0.25)
            )

        except tk.TclError:
            return

        self._count += 1
        self._job = self.after(250, self._refresh)

    def _on_destroy(self, event):
        if event.widget is not self:
            return

        for job in (self._job, self._boot_job):
            if job is not None:
                try:
                    self.after_cancel(job)
                except Exception:
                    pass

        try:
            self.core.stop()
        except Exception:
            pass