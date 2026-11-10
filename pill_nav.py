"""
pill_nav.py  -  StudyMate floating "stage": animated backdrop + pill menu
=========================================================================

Put this file in the SAME folder as main.py.

Performance notes (v2):
  * set ANIMATE = False below to freeze the banner completely
  * the animation pauses on pages that are already heavy
    (AI Assistant, Lecture Hub)
  * colours are worked out once, never inside the animation loop
  * resizing the window redraws once, after you stop dragging
"""

import math
import random
import time
import traceback
import tkinter as tk
from tkinter import messagebox
import tkinter.font as tkfont
from datetime import datetime

from profile_photo import make_photo_image, initials_of

# ---------------------------------------------------------------
# Easy switches
# ---------------------------------------------------------------

ANIMATE = True                              # False = still picture, zero CPU
ACTIVE_SECONDS = 3.0                        # banner moves this long after any action
FRAME_MS = 50                               # 50 ms = 20 frames per second
PARTICLES = 28
PAUSE_ON_PAGES = ("AI Assistant", "Lecture Hub")

STAGE_HEIGHT = 150
PILL_Y = 32
PILL_H = 42
MAX_PLANETS = 6


def _rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def _hex(rgb):
    return "#%02x%02x%02x" % tuple(
        max(0, min(255, int(round(c)))) for c in rgb
    )


def _mix(a, b, t):
    ra, rb = _rgb(a), _rgb(b)
    return _hex(ra[i] + (rb[i] - ra[i]) * t for i in range(3))


class FloatingStage(tk.Canvas):
    """Top banner shared by every page."""

    def __init__(self, master, app, main_items, more_items):
        super().__init__(
            master,
            height=STAGE_HEIGHT,
            bg=app.bg,
            highlightthickness=0,
            bd=0
        )

        self.app = app
        self.main_items = list(main_items)
        self.more_items = list(more_items)
        self.labels = [label for label, _ in self.main_items] + ["More"]

        self.active = None
        self.hover = None
        self.width = 900
        self.mouse = (0.5, 0.5)

        self.font = tkfont.Font(family="Segoe UI", size=10)
        self.font_bold = tkfont.Font(family="Segoe UI", size=10, weight="bold")

        self._boxes = []
        self._pill = (0, 0)
        self._hl = [0.0, 0.0]
        self._hl_to = [0.0, 0.0]
        self._avatar_img = None
        self._avatar_box = (0, 0, 0, 0)

        self._tick_job = None
        self._slide_job = None
        self._shown_active = None
        self._run_until = 0.0
        self._resize_job = None
        self._paused = False
        self._drawn = False
        self._frame = 0
        self._phase = 0.0
        self._cursor = ""
        self._cx = 560
        self._cy = 96

        self.highlight = None
        self.label_ids = []
        self._core = []
        self._parts = []
        self._planets = []
        self._pos = {}
        self._planet_hover = None

        self._build_menu()
        self._sync_planets()

        self.bind("<Configure>", self._on_resize)
        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)

    # ---------------------------------------------------------
    # Setup
    # ---------------------------------------------------------

    def _build_menu(self):
        app = self.app

        self.menu = tk.Menu(
            self,
            tearoff=0,
            bg=app.card_bg,
            fg=app.text,
            activebackground=app.accent,
            activeforeground=app.btn_text,
            bd=0,
            relief="flat",
            font=("Segoe UI", 10)
        )

        for label, command in self.more_items:
            if label == "Logout":
                self.menu.add_separator()

            self.menu.add_command(
                label="   " + label + "   ",
                command=lambda n=label, c=command: self._run(n, c)
            )

    def _subject_names(self):
        names = []

        for item in self.app.data.get("subjects", []):
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, dict):
                names.append(str(item.get("name", "Subject")))

        return names[:MAX_PLANETS] or ["", "", ""]

    def _sync_planets(self):
        app = self.app
        palette = [
            app.accent, app.accent2, app.green,
            app.orange, app.red, _mix(app.accent, app.accent2, 0.5)
        ]

        old = {p["name"]: p for p in self._planets if p["name"]}
        planets = []

        for index, name in enumerate(self._subject_names()):
            planet = old.get(name) if name else None

            if planet is None:
                planet = {"angle": random.uniform(0, math.tau), "name": name}

            planet["index"] = index
            planet["color"] = palette[index % len(palette)]
            planet["speed"] = 0.03 + 0.012 * ((index * 7) % 5)
            planet["ids"] = None
            planets.append(planet)

        self._planets = planets
        self._pos = {}

    # ---------------------------------------------------------
    # Hooks used by main.py
    # ---------------------------------------------------------

    def set_active(self, label):
        """Highlights the pill item for this page (or 'More')."""

        if not label:
            return

        main_labels = [name for name, _ in self.main_items]
        self.active = label if label in main_labels else "More"

        names_before = [p["name"] for p in self._planets]
        self._sync_planets()

        if self._drawn and names_before != [p["name"] for p in self._planets]:
            self._draw_static()

        self._paint_labels()

        if self._boxes and self.active in self.labels:
            target = list(self._boxes[self.labels.index(self.active)])

            if target != self._hl_to:
                self._shown_active = None

            self._hl_to = target

            if self._hl[1] <= 0:          # very first time: no sliding
                self._hl = list(target)
                self._place_highlight()

            self._start_slide()

        # Heavy pages get the CPU to themselves
        self._paused = (not ANIMATE) or (label in PAUSE_ON_PAGES)

        if not self._paused:
            self._wake()

    def refresh_avatar(self):
        self._draw_avatar()

    # ---------------------------------------------------------
    # Layout (debounced)
    # ---------------------------------------------------------

    def _on_resize(self, event):
        new_width = max(600, event.width)

        if self._drawn and new_width == self.width:
            return

        self.width = new_width

        if self._resize_job is not None:
            try:
                self.after_cancel(self._resize_job)
            except Exception:
                pass

        delay = 1 if not self._drawn else 120
        self._resize_job = self.after(delay, self._redraw)

    def _redraw(self):
        self._resize_job = None

        try:
            self._draw_static()
        except tk.TclError:
            return

        if self.active in self.labels and self._boxes:
            box = self._boxes[self.labels.index(self.active)]
            self._hl = list(box)
            self._hl_to = list(box)
            self._shown_active = self.active
            self._place_highlight()
            self._paint_labels()

        self._wake(1.0)

    def _layout(self):
        pad = 15
        gap = 2

        widths = [
            self.font_bold.measure(
                label + (" \u25BE" if label == "More" else "")
            ) + pad * 2
            for label in self.labels
        ]

        total = sum(widths) + gap * (len(widths) - 1) + 10
        left = (self.width - total) / 2 + 5

        boxes = []
        x = left

        for w in widths:
            boxes.append((x, x + w))
            x += w + gap

        self._boxes = boxes
        self._pill = (left - 5, left - 5 + total)

    # ---------------------------------------------------------
    # Static drawing
    # ---------------------------------------------------------

    def _draw_static(self):
        app = self.app

        for tag in ("static", "sky", "hl", "part", "planet", "core", "avatar"):
            self.delete(tag)

        self._layout()
        self._drawn = True

        top = _mix(app.bg, app.hero[0], 0.55)
        mid = _mix(app.bg, app.hero[2], 0.35)
        self._top = top

        # Sky
        steps = 18

        for i in range(steps):
            t = i / (steps - 1)
            color = (
                _mix(top, mid, t * 2) if t < 0.5
                else _mix(mid, app.bg, (t - 0.5) * 2)
            )

            self.create_rectangle(
                0, i * STAGE_HEIGHT / steps,
                self.width + 4, (i + 1) * STAGE_HEIGHT / steps + 1,
                fill=color, outline="", tags="sky"
            )

        # Greeting
        profile = app.data.get("profile", {})
        first = (profile.get("name") or "").split(" ")[0] or "there"

        self.create_text(
            38, 98,
            text=f"{app.time_greeting()}, {first}",
            anchor="w", fill=app.text,
            font=("Georgia", 21, "bold"), tags="static"
        )
        self.create_text(
            40, 127,
            text=datetime.now().strftime("%A, %d %B"),
            anchor="w", fill=app.muted,
            font=("Segoe UI", 9), tags="static"
        )

        # Orbits
        self._cx = max(540, self.width - 230)
        self._cy = 98

        ring_color = _mix(top, app.accent, 0.20)

        for planet in self._planets:
            rx = 44 + planet["index"] * 18
            self.create_oval(
                self._cx - rx, self._cy - rx * 0.30,
                self._cx + rx, self._cy + rx * 0.30,
                outline=ring_color, tags="sky"
            )

        # Pill
        x0, x1 = self._pill
        r = PILL_H / 2

        self.create_line(
            x0 + r, PILL_Y, x1 - r, PILL_Y,
            width=PILL_H, capstyle="round",
            fill=_mix(app.accent2, "#FFFFFF", 0.1), tags="static"
        )
        self.create_line(
            x0 + r, PILL_Y, x1 - r, PILL_Y,
            width=PILL_H - 2, capstyle="round",
            fill=_mix(app.bg, app.card_bg, 0.85), tags="static"
        )

        self.highlight = self.create_line(
            0, PILL_Y, 0, PILL_Y,
            width=PILL_H - 10, capstyle="round",
            fill=app.accent, tags="hl"
        )

        self.label_ids = []

        for index, label in enumerate(self.labels):
            a, b = self._boxes[index]

            item = self.create_text(
                (a + b) / 2, PILL_Y,
                text=label + (" \u25BE" if label == "More" else ""),
                fill=app.muted, font=self.font,
                tags=("static", "labels")
            )
            self.label_ids.append(item)

        self._draw_avatar()
        self._paint_labels()

        # Moving things (colours are fixed here, never inside the loop)
        self._parts = []
        dim = _mix(top, app.accent2, 0.25)
        mid_c = _mix(top, app.accent2, 0.55)
        bright = _mix(top, app.accent2, 0.85)

        for _ in range(PARTICLES):
            z = random.uniform(0.3, 1.0)
            size = 0.8 + 1.4 * z

            self._parts.append({
                "x": random.random(),
                "y": random.random(),
                "z": z,
                "size": size,
                "tw": random.uniform(0, math.tau),
                "ci": 0,
                "colors": (dim, mid_c, bright),
                "id": self.create_oval(
                    0, 0, 0, 0, outline="", fill=dim, tags="part"
                ),
            })

        self._core = [
            self.create_oval(0, 0, 0, 0, outline="",
                             fill=_mix(top, app.accent, 0.80), tags="core"),
            self.create_oval(0, 0, 0, 0, fill="",
                             outline=_mix(top, app.accent, 0.35), tags="core"),
            self.create_oval(0, 0, 0, 0, fill="",
                             outline=_mix(top, app.accent, 0.20), tags="core"),
        ]

        for planet in self._planets:
            color = planet["color"]
            planet["glow_fill"] = _mix(top, color, 0.25)
            planet["glow_hover"] = _mix(top, color, 0.50)
            planet["ids"] = (
                self.create_oval(0, 0, 0, 0, outline="",
                                 fill=planet["glow_fill"], tags="planet"),
                self.create_oval(0, 0, 0, 0, outline="",
                                 fill=_mix(color, "#FFFFFF", 0.15),
                                 tags="planet"),
                self.create_text(0, 0, text="", fill=app.text,
                                 font=("Segoe UI", 8, "bold"), tags="planet"),
            )

        # Layer order, set once
        self.tag_lower("sky")
        self.tag_raise("static")
        self.tag_raise("hl")
        self.tag_raise("labels")
        self.tag_raise("avatar")

        self._place_highlight()
        self._animate()          # paint one frame so it is never empty

    def _draw_avatar(self):
        app = self.app
        self.delete("avatar")

        size = 44
        cx = self.width - 42
        cy = PILL_Y

        self._avatar_box = (
            cx - size / 2, cy - size / 2, cx + size / 2, cy + size / 2
        )

        profile = app.data.get("profile", {})
        name = profile.get("name") or "Student"

        self.create_oval(
            cx - size / 2, cy - size / 2, cx + size / 2, cy + size / 2,
            outline=app.accent, width=2,
            fill=_mix(app.bg, app.card_bg, 0.85), tags="avatar"
        )

        self._avatar_img = make_photo_image(profile.get("photo"), size - 8)

        if self._avatar_img is not None:
            self.create_image(cx, cy, image=self._avatar_img, tags="avatar")
        else:
            self.create_text(
                cx, cy, text=initials_of(name),
                fill=app.accent, font=("Georgia", 13, "bold"),
                tags="avatar"
            )

    def _paint_labels(self):
        app = self.app

        for index, label in enumerate(self.labels):
            if index >= len(self.label_ids):
                break

            if label == self._shown_active:
                color, font = app.btn_text, self.font_bold
            elif label == self.hover:
                color, font = app.text, self.font
            else:
                color, font = app.muted, self.font

            self.itemconfigure(self.label_ids[index], fill=color, font=font)

    def _place_highlight(self):
        if self.highlight is None or self._hl[1] <= 0:
            return

        r = (PILL_H - 10) / 2
        a = self._hl[0] + 3 + r
        b = max(a, self._hl[1] - 3 - r)

        self.coords(self.highlight, a, PILL_Y, b, PILL_Y)

    # ---------------------------------------------------------
    # Mouse
    # ---------------------------------------------------------

    def _item_at(self, x, y):
        if abs(y - PILL_Y) > PILL_H / 2:
            return None

        for index, (a, b) in enumerate(self._boxes):
            if a <= x <= b:
                return self.labels[index]

        return None

    def _over_avatar(self, x, y):
        a, b, c, d = self._avatar_box
        return a <= x <= c and b <= y <= d

    def _planet_at(self, x, y):
        for planet in self._planets:
            pos = self._pos.get(planet["index"])

            if pos and (x - pos[0]) ** 2 + (y - pos[1]) ** 2 <= (pos[2] + 5) ** 2:
                return planet["index"]

        return None

    def _on_motion(self, event):
        self.mouse = (event.x / max(1, self.width), event.y / STAGE_HEIGHT)
        self._wake(2.0)

        hover = self._item_at(event.x, event.y)

        if hover != self.hover:
            self.hover = hover
            self._paint_labels()

        planet = self._planet_at(event.x, event.y)

        if planet != self._planet_hover:
            self._set_planet_hover(planet)

        clickable = bool(hover) or planet is not None \
            or self._over_avatar(event.x, event.y)
        cursor = "hand2" if clickable else ""

        if cursor != self._cursor:
            self._cursor = cursor
            self.configure(cursor=cursor)

    def _set_planet_hover(self, index):
        self._planet_hover = index

        for planet in self._planets:
            if not planet.get("ids"):
                continue

            glow_id, _, text_id = planet["ids"]
            hovered = planet["index"] == index

            self.itemconfigure(
                glow_id,
                fill=planet["glow_hover"] if hovered else planet["glow_fill"]
            )
            self.itemconfigure(
                text_id,
                text=planet["name"][:18] if hovered else ""
            )

    def _on_leave(self, event):
        self.hover = None
        self._paint_labels()

        if self._planet_hover is not None:
            self._set_planet_hover(None)

    def _run(self, name, command):
        """Runs a page command; shows any error instead of failing silently."""

        try:
            command()

        except Exception as error:
            traceback.print_exc()
            messagebox.showerror(
                "StudyMate",
                f"The '{name}' page could not open.\n\n"
                f"{type(error).__name__}: {error}"
            )

    def _on_click(self, event):
        label = self._item_at(event.x, event.y)

        if label == "More":
            x0, _ = self._boxes[self.labels.index("More")]

            try:
                self.menu.tk_popup(
                    int(self.winfo_rootx() + x0),
                    int(self.winfo_rooty() + PILL_Y + PILL_H / 2 + 6)
                )
            finally:
                self.menu.grab_release()

            return

        if label:
            for name, command in self.main_items:
                if name == label:
                    self._run(name, command)
                    return

        if self._over_avatar(event.x, event.y):
            self.app.show_profile()
            return

        if self._planet_at(event.x, event.y) is not None:
            self.app.show_subjects()

    # ---------------------------------------------------------
    # Animation loop (kept very small)
    # ---------------------------------------------------------

    def _start_slide(self):
        if self._slide_job is None:
            self._slide_job = self.after(16, self._slide)

    def _slide(self):
        """Moves the pill highlight. Runs even on paused pages (tiny cost)."""

        self._slide_job = None

        try:
            if not self.winfo_exists() or self.highlight is None:
                return

            moved = False

            for i in range(2):
                diff = self._hl_to[i] - self._hl[i]

                if abs(diff) > 0.5:
                    self._hl[i] += diff * 0.32
                    moved = True
                else:
                    self._hl[i] = self._hl_to[i]

            self._place_highlight()

            if moved:
                self._slide_job = self.after(16, self._slide)
            else:
                self._shown_active = self.active
                self._paint_labels()

        except tk.TclError:
            return

    def _wake(self, seconds=None):
        """Animate for a few seconds, then rest until the next action."""

        self._run_until = max(
            self._run_until,
            time.time() + (seconds or ACTIVE_SECONDS)
        )
        self._start_loop()

    def _start_loop(self):
        if self._tick_job is None and ANIMATE and not self._paused:
            self._tick_job = self.after(FRAME_MS, self._tick)

    def _tick(self):
        self._tick_job = None

        try:
            if not self.winfo_exists():
                return

            self._animate()

        except tk.TclError:
            return

        if not self._paused and time.time() < self._run_until:
            self._start_loop()

    def _animate(self):
        if self.highlight is None or not self._drawn:
            return

        self._frame += 1
        self._phase += 0.10

        mx = (self.mouse[0] - 0.5) * 16
        my = (self.mouse[1] - 0.5) * 6
        width = self.width

        # Particles: move only; colour changes only when a step is crossed
        for part in self._parts:
            part["x"] -= 0.0012 * part["z"]
            part["tw"] += 0.15

            if part["x"] < -0.02:
                part["x"] = 1.02
                part["y"] = random.random()

            px = part["x"] * width - mx * part["z"]
            py = part["y"] * STAGE_HEIGHT - my * part["z"]
            s = part["size"]

            self.coords(part["id"], px - s, py - s, px + s, py + s)

            ci = int((math.sin(part["tw"]) + 1) * 1.49)

            if ci != part["ci"]:
                part["ci"] = ci
                self.itemconfigure(part["id"], fill=part["colors"][ci])

        cx = self._cx + mx * 0.5
        cy = self._cy + my * 0.5

        # Core
        pulse = (math.sin(self._phase * 0.8) + 1) / 2

        for i, item in enumerate(self._core):
            radius = 7 + i * 7 + pulse * 2
            self.coords(item, cx - radius, cy - radius, cx + radius, cy + radius)

        # Planets
        for planet in self._planets:
            ids = planet.get("ids")

            if not ids:
                continue

            planet["angle"] += planet["speed"]
            angle = planet["angle"]
            rx = 44 + planet["index"] * 18

            x = cx + math.cos(angle) * rx
            y = cy + math.sin(angle) * rx * 0.30
            depth = (math.sin(angle) + 1) / 2
            radius = 4 + planet["index"] * 0.3 + depth * 3
            glow = radius + (7 if planet["index"] == self._planet_hover else 4)

            self._pos[planet["index"]] = (x, y, radius)

            self.coords(ids[0], x - glow, y - glow, x + glow, y + glow)
            self.coords(ids[1], x - radius, y - radius, x + radius, y + radius)

            if planet["index"] == self._planet_hover:
                self.coords(ids[2], x, y - radius - 11)