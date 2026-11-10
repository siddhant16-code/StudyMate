"""
scene3d.py  -  StudyMate 3D engine
==================================

Put this file in the SAME folder as main.py.

Pure Tkinter canvas 3D (no extra packages). Everything is projected in
software and depth-sorted, so it works on any PC.

Widgets
-------
StudyGalaxy  - dashboard scene: a glowing core (you) with one orbiting orb
               per subject. Drag to rotate, hover for stats, click to open.
Bar3DChart   - rotatable isometric 3D bar chart (used on Analytics).

Both widgets stop their own animation when destroyed.
"""

import math
import random
import time
import tkinter as tk


# =============================================================
# COLOUR + MATH HELPERS
# =============================================================

def _rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def _hex(rgb):
    return "#%02X%02X%02X" % tuple(
        max(0, min(255, int(round(c)))) for c in rgb
    )


def mix(first, second, amount):
    a, b = _rgb(first), _rgb(second)
    amount = max(0.0, min(1.0, amount))
    return _hex(tuple(a[i] + (b[i] - a[i]) * amount for i in range(3)))


def rotate(point, yaw, pitch):
    """Rotate a 3D point around the Y axis (yaw) then the X axis (pitch)."""
    x, y, z = point

    c, s = math.cos(yaw), math.sin(yaw)
    x, z = x * c + z * s, -x * s + z * c

    c, s = math.cos(pitch), math.sin(pitch)
    y, z = y * c - z * s, y * s + z * c

    return x, y, z


def project(point, cx, cy, scale, camera=4.2):
    """Perspective projection. Returns (screen_x, screen_y, depth_scale)."""
    x, y, z = point
    depth = camera / max(0.6, camera + z)

    return cx + x * scale * depth, cy + y * scale * depth, depth


def ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def _short(text, limit):
    text = str(text)
    return text if len(text) <= limit else text[:limit - 1] + "…"


# =============================================================
# STUDY GALAXY
# =============================================================

class StudyGalaxy(tk.Canvas):
    """
    planets: list of dicts
        {"name": str, "tasks": int, "done": int, "overdue": int,
         "minutes": int}
    palette: dict with bg, card_bg, text, muted, accent, accent2, green,
             red, orange
    on_open: callable(subject_name) when an orb is clicked
    """

    def __init__(self, master, planets, palette, on_open=None,
                 height=300, title="Your Study Galaxy"):

        super().__init__(
            master,
            height=height,
            bg=palette["card_bg"],
            highlightthickness=0,
            bd=0,
            cursor="fleur"
        )

        self.planets = planets
        self.p = palette
        self.on_open = on_open
        self.title_text = title

        self.yaw = 0.6
        self.pitch = 0.38
        self.yaw_speed = 0.006
        self.dragging = False
        self.last_mouse = (0, 0)
        self.drag_moved = 0
        self.hover = None
        self.mouse = None

        self.alive = True
        self.after_id = None
        self.t0 = time.time()
        self.last = self.t0
        self.intro = 0.0

        rng = random.Random(7)

        self.stars = [
            (
                rng.uniform(-1, 1),
                rng.uniform(-1, 1),
                rng.uniform(-1, 1),
                rng.uniform(0.3, 1.0)
            )
            for _ in range(70)
        ]

        self.hit_areas = []

        palette_cycle = [
            palette["accent"], palette["accent2"], palette["green"],
            palette["orange"], palette["red"]
        ]

        count = max(1, len(planets))

        for index, planet in enumerate(planets):
            ring = 1 + index // 6
            slot = index % 6
            in_ring = min(6, count - (ring - 1) * 6)

            planet["_radius"] = 0.95 + 0.62 * (ring - 1)
            planet["_phase"] = (
                slot / max(1, in_ring) * math.tau + ring * 0.7
            )
            planet["_speed"] = 0.55 / ring
            planet["_tilt"] = (index % 3 - 1) * 0.16
            planet["_color"] = palette_cycle[index % len(palette_cycle)]

            tasks = planet.get("tasks", 0)
            planet["_size"] = 0.15 + min(0.16, tasks * 0.022)

        self.bind("<ButtonPress-1>", self._press)
        self.bind("<B1-Motion>", self._drag)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<Motion>", self._motion)
        self.bind("<Leave>", self._leave)
        self.bind("<Destroy>", self._on_destroy)

        self._tick()

    # ---------------------------------------------------------
    # Input
    # ---------------------------------------------------------

    def _press(self, event):
        self.dragging = True
        self.drag_moved = 0
        self.last_mouse = (event.x, event.y)

    def _drag(self, event):
        dx = event.x - self.last_mouse[0]
        dy = event.y - self.last_mouse[1]
        self.last_mouse = (event.x, event.y)
        self.drag_moved += abs(dx) + abs(dy)

        self.yaw += dx * 0.011
        self.pitch = max(-0.5, min(1.2, self.pitch + dy * 0.008))

    def _release(self, event):
        self.dragging = False

        if self.drag_moved < 6 and self.hover is not None:
            name = self.hover.get("name")

            if self.on_open and name:
                try:
                    self.on_open(name)
                except Exception as error:
                    print("Galaxy click warning:", error)

    def _motion(self, event):
        self.mouse = (event.x, event.y)

    def _leave(self, event):
        self.mouse = None
        self.hover = None

    def _on_destroy(self, event):
        if event.widget is self:
            self.alive = False

            if self.after_id is not None:
                try:
                    self.after_cancel(self.after_id)
                except Exception:
                    pass

    # ---------------------------------------------------------
    # Frame loop
    # ---------------------------------------------------------

    def _tick(self):
        if not self.alive:
            return

        try:
            if not self.winfo_exists():
                return

            now = time.time()
            dt = min(0.1, now - self.last)
            self.last = now

            self.intro = min(1.0, self.intro + dt / 1.3)

            if not self.dragging:
                self.yaw += self.yaw_speed

            self._draw(now - self.t0)

        except tk.TclError:
            return

        self.after_id = self.after(33, self._tick)

    # ---------------------------------------------------------
    # Drawing
    # ---------------------------------------------------------

    def _draw(self, t):
        self.delete("all")

        width = max(200, self.winfo_width())
        height = max(150, self.winfo_height())
        cx, cy = width / 2, height / 2 + 6
        scale = min(width / 3.1, height / 2.15) * ease(self.intro)

        p = self.p

        # Soft background glow
        for radius, amount in ((0.95, 0.04), (0.65, 0.06), (0.38, 0.09)):
            r = radius * min(width, height) * 0.62
            self.create_oval(
                cx - r, cy - r, cx + r, cy + r,
                fill=mix(p["card_bg"], p["accent"], amount),
                outline=""
            )

        # Stars (slow parallax with rotation)
        for sx, sy, sz, bright in self.stars:
            px, py, pz = rotate((sx * 2.6, sy * 1.3, sz * 2.0),
                                self.yaw * 0.35, self.pitch * 0.35)
            x, y, d = project((px, py, pz), cx, cy, scale)
            tw = 0.55 + 0.45 * math.sin(t * 2 + sx * 9)
            color = mix(p["card_bg"], p["text"], bright * tw * 0.55)
            self.create_oval(x - 1, y - 1, x + 1, y + 1,
                             fill=color, outline="")

        items = []  # (depth, kind, data)

        # Orbit rings
        radii = sorted({round(pl["_radius"], 2) for pl in self.planets}
                       or {1.0})

        for radius in radii:
            points = []

            for step in range(48):
                a = step / 48 * math.tau
                points.append(rotate(
                    (math.cos(a) * radius, 0, math.sin(a) * radius),
                    self.yaw, self.pitch
                ))

            items.append((0.0, "ring", points))

        # Core
        core = rotate((0, 0, 0), self.yaw, self.pitch)
        items.append((core[2], "core", core))

        # Planets
        self.hit_areas = []

        for planet in self.planets:
            angle = planet["_phase"] + t * planet["_speed"]
            r = planet["_radius"]
            raw = (
                math.cos(angle) * r,
                math.sin(angle * 2) * planet["_tilt"],
                math.sin(angle) * r
            )
            pos = rotate(raw, self.yaw, self.pitch)
            items.append((pos[2], "planet", (planet, pos)))

        items.sort(key=lambda item: item[0], reverse=True)

        hover_candidate = None

        for depth, kind, data in items:

            if kind == "ring":
                coords = []

                for point in data:
                    x, y, d = project(point, cx, cy, scale)
                    coords.extend((x, y))

                self.create_line(
                    *coords, coords[0], coords[1],
                    fill=mix(p["card_bg"], p["muted"], 0.30),
                    width=1, dash=(2, 5)
                )

            elif kind == "core":
                self._draw_core(data, cx, cy, scale, t)

            else:
                planet, pos = data
                hit = self._draw_planet(planet, pos, cx, cy, scale, t)

                if self.mouse and hit:
                    hx, hy, hr = hit
                    dist = math.hypot(self.mouse[0] - hx,
                                      self.mouse[1] - hy)

                    if dist <= hr + 4:
                        hover_candidate = (planet, hx, hy, hr)

        self.hover = hover_candidate[0] if hover_candidate else None

        self.configure(cursor="hand2" if self.hover else "fleur")

        if hover_candidate:
            self._draw_tooltip(*hover_candidate)

        # Title + hint
        self.create_text(
            18, 16, anchor="w",
            text=self.title_text,
            fill=p["text"], font=("Georgia", 14, "bold")
        )
        self.create_text(
            18, 38, anchor="w",
            text="Drag to rotate  •  click an orb to open the subject",
            fill=p["muted"], font=("Segoe UI", 9)
        )

        if not self.planets:
            self.create_text(
                cx, cy + 70,
                text="Add subjects to launch your galaxy",
                fill=p["muted"], font=("Segoe UI", 10)
            )

    def _draw_core(self, pos, cx, cy, scale, t):
        p = self.p
        x, y, d = project(pos, cx, cy, scale)
        pulse = 1 + 0.06 * math.sin(t * 2.4)
        base = 0.34 * scale * d * pulse

        for mult, amount in ((2.2, 0.10), (1.7, 0.18), (1.3, 0.30)):
            r = base * mult
            self.create_oval(
                x - r, y - r, x + r, y + r,
                fill=mix(p["card_bg"], p["accent"], amount), outline=""
            )

        # Layered sphere for a lit look
        shades = (
            (1.00, mix(p["accent"], "#000000", 0.45)),
            (0.85, mix(p["accent"], "#000000", 0.20)),
            (0.66, p["accent"]),
            (0.44, mix(p["accent"], "#FFFFFF", 0.35)),
            (0.22, mix(p["accent"], "#FFFFFF", 0.70)),
        )

        for i, (mult, color) in enumerate(shades):
            r = base * mult
            off = base * 0.18 * (1 - mult)
            self.create_oval(
                x - r - off, y - r - off, x + r - off, y + r - off,
                fill=color, outline=""
            )

    def _draw_planet(self, planet, pos, cx, cy, scale, t):
        p = self.p
        x, y, d = project(pos, cx, cy, scale)

        radius = planet["_size"] * scale * d
        color = planet["_color"]

        hovered = self.hover is planet

        # Shadow on the "floor"
        self.create_oval(
            x - radius * 0.9, y + radius * 1.5,
            x + radius * 0.9, y + radius * 1.8,
            fill=mix(p["card_bg"], "#000000", 0.35), outline=""
        )

        if hovered:
            glow = radius * 1.7
            self.create_oval(
                x - glow, y - glow, x + glow, y + glow,
                fill=mix(p["card_bg"], color, 0.30), outline=""
            )

        # Progress ring
        tasks = planet.get("tasks", 0)
        done = planet.get("done", 0)
        fraction = done / tasks if tasks else 0
        ring_r = radius * 1.38

        self.create_oval(
            x - ring_r, y - ring_r, x + ring_r, y + ring_r,
            outline=mix(p["card_bg"], p["muted"], 0.35), width=2
        )

        if fraction > 0:
            self.create_arc(
                x - ring_r, y - ring_r, x + ring_r, y + ring_r,
                start=90, extent=-359.9 * fraction,
                style="arc", outline=p["green"], width=3
            )

        # Overdue pulse
        if planet.get("overdue", 0) > 0:
            pulse = 1.15 + 0.12 * math.sin(t * 5)
            r = radius * pulse * 1.75
            self.create_oval(
                x - r, y - r, x + r, y + r,
                outline=p["red"], width=1
            )

        # Lit sphere
        shades = (
            (1.00, mix(color, "#000000", 0.50)),
            (0.88, mix(color, "#000000", 0.25)),
            (0.70, color),
            (0.46, mix(color, "#FFFFFF", 0.38)),
            (0.22, mix(color, "#FFFFFF", 0.75)),
        )

        for mult, shade in shades:
            r = radius * mult
            off = radius * 0.22 * (1 - mult)
            self.create_oval(
                x - r - off, y - r - off, x + r - off, y + r - off,
                fill=shade, outline=""
            )

        # Label
        if d > 0.8:
            self.create_text(
                x, y + radius * 2.15 + 8,
                text=_short(planet.get("name", ""), 14),
                fill=p["text"] if hovered else p["muted"],
                font=("Segoe UI", 9, "bold" if hovered else "normal")
            )

        return x, y, ring_r

    def _draw_tooltip(self, planet, x, y, r):
        p = self.p

        lines = [
            _short(planet.get("name", ""), 26),
            f"Tasks: {planet.get('done', 0)}/{planet.get('tasks', 0)} done",
            f"Study time: {planet.get('minutes', 0)} min",
        ]

        if planet.get("overdue", 0):
            lines.append(f"Overdue: {planet['overdue']}")

        w = 168
        h = 14 + 17 * len(lines)
        width = max(200, self.winfo_width())

        tx = min(max(8, x + r + 10), width - w - 8)
        ty = max(52, y - h / 2)

        self.create_rectangle(
            tx + 3, ty + 3, tx + w + 3, ty + h + 3,
            fill=mix(p["card_bg"], "#000000", 0.45), outline=""
        )
        self.create_rectangle(
            tx, ty, tx + w, ty + h,
            fill=p["bg"], outline=planet["_color"], width=1
        )

        for i, line in enumerate(lines):
            self.create_text(
                tx + 10, ty + 14 + i * 17, anchor="w", text=line,
                fill=p["text"] if i == 0 else p["muted"],
                font=("Segoe UI", 9, "bold" if i == 0 else "normal")
            )


# =============================================================
# 3D BAR CHART
# =============================================================

class Bar3DChart(tk.Canvas):
    """
    bars: list of (label, value)
    Drag horizontally to turn the chart. Bars grow in on first draw.
    """

    def __init__(self, master, bars, palette, height=280,
                 unit="min", bar_color=None):

        super().__init__(
            master,
            height=height,
            bg=palette["card_bg"],
            highlightthickness=0,
            bd=0,
            cursor="fleur"
        )

        self.bars = list(bars)
        self.p = palette
        self.unit = unit
        self.color = bar_color or palette["accent"]

        self.yaw = -0.55
        self.pitch = 0.52
        self.dragging = False
        self.last_mouse = (0, 0)
        self.grow = 0.0
        self.sway = 0.0
        self.alive = True
        self.after_id = None
        self.last = time.time()

        self.bind("<ButtonPress-1>", self._press)
        self.bind("<B1-Motion>", self._drag)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<Destroy>", self._on_destroy)

        self._tick()

    def _press(self, event):
        self.dragging = True
        self.last_mouse = (event.x, event.y)

    def _drag(self, event):
        dx = event.x - self.last_mouse[0]
        dy = event.y - self.last_mouse[1]
        self.last_mouse = (event.x, event.y)

        self.yaw = max(-1.35, min(1.35, self.yaw + dx * 0.010))
        self.pitch = max(0.15, min(1.05, self.pitch + dy * 0.006))

    def _release(self, event):
        self.dragging = False

    def _on_destroy(self, event):
        if event.widget is self:
            self.alive = False

            if self.after_id is not None:
                try:
                    self.after_cancel(self.after_id)
                except Exception:
                    pass

    def _tick(self):
        if not self.alive:
            return

        try:
            if not self.winfo_exists():
                return

            now = time.time()
            dt = min(0.1, now - self.last)
            self.last = now

            self.grow = min(1.0, self.grow + dt / 1.1)
            self.sway += dt

            if not self.dragging:
                # gentle idle sway so the 3D is always visible
                self.yaw += math.sin(self.sway * 0.7) * 0.0016

            self._draw()

        except tk.TclError:
            return

        self.after_id = self.after(33, self._tick)

    def _draw(self):
        self.delete("all")

        p = self.p
        width = max(260, self.winfo_width())
        height = max(180, self.winfo_height())

        count = max(1, len(self.bars))
        top = max([value for _, value in self.bars] + [1])

        cx, cy = width / 2, height / 2 + 24
        scale = min(width / (count * 0.62 + 1.4), height / 2.4)

        spacing = 0.62
        half_w = 0.20
        max_h = 1.5

        # Floor grid
        floor_y = 0.0
        x0 = -(count * spacing) / 2 - 0.2
        x1 = (count * spacing) / 2 + 0.2

        corners = [
            (x0, floor_y, -0.45), (x1, floor_y, -0.45),
            (x1, floor_y, 0.45), (x0, floor_y, 0.45)
        ]
        pts = []

        for corner in corners:
            r = rotate(corner, self.yaw, self.pitch)
            x, y, d = project(r, cx, cy, scale, camera=5.2)
            pts.extend((x, y))

        self.create_polygon(
            *pts,
            fill=mix(p["card_bg"], p["surface"], 0.55),
            outline=mix(p["card_bg"], p["muted"], 0.35)
        )

        # Grid lines
        for i in range(1, 4):
            z = -0.45 + 0.9 * i / 4
            a = rotate((x0, floor_y, z), self.yaw, self.pitch)
            b = rotate((x1, floor_y, z), self.yaw, self.pitch)
            ax, ay, _ = project(a, cx, cy, scale, camera=5.2)
            bx, by, _ = project(b, cx, cy, scale, camera=5.2)
            self.create_line(ax, ay, bx, by,
                             fill=mix(p["card_bg"], p["muted"], 0.18))

        # Build each bar as 3 visible faces, drawn back to front
        order = []

        for index, (label, value) in enumerate(self.bars):
            bx = (index - (count - 1) / 2) * spacing
            centre = rotate((bx, 0, 0), self.yaw, self.pitch)
            order.append((centre[2], index, label, value, bx))

        order.sort(key=lambda item: item[0], reverse=True)

        for depth, index, label, value, bx in order:

            ratio = value / top if top else 0
            bar_h = max(0.03, ratio * max_h) * ease(
                self.grow * 1.25 - index * 0.06
            )

            color = self.color

            if value == top and value > 0:
                color = self.p["green"]

            verts = [
                (bx - half_w, 0, -half_w), (bx + half_w, 0, -half_w),
                (bx + half_w, 0, half_w), (bx - half_w, 0, half_w),
                (bx - half_w, -bar_h, -half_w), (bx + half_w, -bar_h, -half_w),
                (bx + half_w, -bar_h, half_w), (bx - half_w, -bar_h, half_w),
            ]

            rv = [rotate(v, self.yaw, self.pitch) for v in verts]
            sv = [project(v, cx, cy, scale, camera=5.2) for v in rv]

            faces = [
                ((0, 1, 5, 4), 0.62),   # back-ish side
                ((1, 2, 6, 5), 0.78),   # right
                ((2, 3, 7, 6), 0.90),   # front
                ((3, 0, 4, 7), 0.70),   # left
                ((4, 5, 6, 7), 1.18),   # top
            ]

            drawn = []

            mid = rotate((bx, -bar_h / 2, 0), self.yaw, self.pitch)
            cam = (0.0, 0.0, -5.2)

            for ids, light in faces:
                cxf = sum(rv[i][0] for i in ids) / 4
                cyf = sum(rv[i][1] for i in ids) / 4
                czf = sum(rv[i][2] for i in ids) / 4

                # outward direction of this face, from the bar centre
                ox, oy, oz = cxf - mid[0], cyf - mid[1], czf - mid[2]

                # visible when it points toward the camera
                tx_, ty_, tz_ = cam[0] - cxf, cam[1] - cyf, cam[2] - czf

                if ox * tx_ + oy * ty_ + oz * tz_ <= 0:
                    continue

                drawn.append((czf, ids, light))

            drawn.sort(key=lambda item: item[0], reverse=True)

            for avg_z, ids, light in drawn:
                shade = (
                    mix(color, "#FFFFFF", min(0.5, (light - 1) * 2.2))
                    if light > 1 else mix(color, "#000000", 1 - light)
                )
                coords = []

                for i in ids:
                    coords.extend((sv[i][0], sv[i][1]))

                self.create_polygon(
                    *coords, fill=shade,
                    outline=mix(color, "#000000", 0.5)
                )

            # Value + label
            tx, ty, _ = project(rv[4], cx, cy, scale, camera=5.2)

            if value > 0 and self.grow > 0.85:
                self.create_text(
                    tx + (sv[6][0] - sv[4][0]) / 2, ty - 12,
                    text=f"{value}",
                    fill=p["text"], font=("Segoe UI", 9, "bold")
                )

            lx, ly, _ = project(
                rotate((bx, 0.0, 0.0), self.yaw, self.pitch),
                cx, cy, scale, camera=5.2
            )
            self.create_text(
                lx, ly + 24, text=_short(label, 6),
                fill=p["muted"], font=("Segoe UI", 8)
            )

        self.create_text(
            width - 14, 14, anchor="e",
            text=f"Drag to rotate  •  {self.unit}",
            fill=p["muted"], font=("Segoe UI", 9)
        )