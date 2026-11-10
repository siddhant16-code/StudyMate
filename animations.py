"""
animations.py  -  StudyMate animation & dynamic-UI toolkit
==========================================================

Put this file in the SAME folder as main.py.

It contains:
  * AnimationsMixin  - methods that are added to the StudyMate class
  * ProgressRing     - animated circular progress ring
  * AnimatedBar      - animated progress bar (optional shimmer)
  * AvatarRing       - profile avatar with a rotating ring
  * RingTimerDisplay - the animated Pomodoro ring (drop-in for the old label)

Everything is pure Tkinter (after() + Canvas). No extra packages needed.
Every animation loop stops by itself when its widget is destroyed, so
nothing keeps running after you leave a page.
"""

import math
import random
import re
import tkinter as tk
from datetime import date, datetime, timedelta

from profile_photo import make_photo_image, overlay_disc


# =============================================================
# SMALL HELPERS
# =============================================================

def _rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def _mix(first, second, amount):
    a = _rgb(first)
    b = _rgb(second)
    amount = max(0.0, min(1.0, amount))

    return "#%02x%02x%02x" % tuple(
        int(round(a[i] + (b[i] - a[i]) * amount)) for i in range(3)
    )


def _ease_out(t):
    return 1 - (1 - t) ** 3


def _split_pad(value):
    """Turns a pack padding value (7, '0 18', (0, 18)) into (before, after)."""
    try:
        if isinstance(value, (tuple, list)):
            parts = [str(item) for item in value]
        else:
            parts = str(value).replace("{", " ").replace("}", " ").split()

        numbers = [int(float(part)) for part in parts]
    except (TypeError, ValueError):
        return 0, 0

    if not numbers:
        return 0, 0

    if len(numbers) == 1:
        return numbers[0], numbers[0]

    return numbers[0], numbers[1]


def _descendants(widget):
    result = []
    stack = list(widget.winfo_children())

    while stack:
        item = stack.pop()
        result.append(item)
        stack.extend(item.winfo_children())

    return result


QUOTES = [
    ("The secret of getting ahead is getting started.", "Mark Twain"),
    ("It always seems impossible until it's done.", "Nelson Mandela"),
    ("Small daily improvements lead to stunning results.", "Robin Sharma"),
    ("Don't watch the clock; do what it does. Keep going.", "Sam Levenson"),
    ("Education is the passport to the future.", "Malcolm X"),
    ("Success is the sum of small efforts, repeated daily.", "R. Collier"),
    ("The expert in anything was once a beginner.", "Helen Hayes"),
    ("Learning never exhausts the mind.", "Leonardo da Vinci"),
    ("Focus on progress, not perfection.", "StudyMate"),
    ("One more page, one more problem, one step closer.", "StudyMate"),
]

PAGES_WITHOUT_TRANSITION = ("Lecture Hub", "Dashboard")


# =============================================================
# ANIMATED WIDGETS
# =============================================================

class ProgressRing(tk.Canvas):
    """Circular progress ring that animates from its current value."""

    def __init__(
        self, master, app, size=150, thickness=14,
        color=None, caption="", text_fn=None
    ):
        super().__init__(
            master,
            width=size,
            height=size,
            bg=master.cget("bg"),
            highlightthickness=0
        )

        self.app = app
        self.size = size
        self.thickness = thickness
        self.color = color or app.accent
        self.text_fn = text_fn or (lambda value: f"{int(round(value * 100))}%")
        self._value = 0.0
        self._job = None

        pad = thickness / 2 + 4
        self.box = (pad, pad, size - pad, size - pad)
        self.cx = size / 2
        self.cy = size / 2
        self.radius = (size - 2 * pad) / 2

        self.create_oval(*self.box, outline=app.surface, width=thickness)

        self.arc = self.create_arc(
            *self.box,
            start=90,
            extent=-0.1,
            style="arc",
            outline=self.color,
            width=thickness
        )

        self.head = self.create_oval(
            0, 0, 0, 0, fill="#FFFFFF", outline="", state="hidden"
        )

        offset = size * 0.06 if caption else 0

        self.text_id = self.create_text(
            self.cx,
            self.cy - offset,
            text=self.text_fn(0),
            fill=app.text,
            font=("Segoe UI", max(10, int(size / 6)), "bold")
        )

        if caption:
            self.create_text(
                self.cx,
                self.cy + size * 0.16,
                text=caption,
                fill=app.muted,
                font=("Segoe UI", 9)
            )

    def _draw(self, value):
        self._value = value

        extent = -max(0.1, min(359.9, 360 * value))
        shade = _mix(self.app.accent2, self.color, min(1.0, value))

        self.itemconfigure(self.arc, extent=extent, outline=shade)
        self.itemconfigure(self.text_id, text=self.text_fn(value))

        if value > 0.004:
            angle = math.radians(90 + extent)
            hx = self.cx + self.radius * math.cos(angle)
            hy = self.cy - self.radius * math.sin(angle)
            hr = self.thickness * 0.38

            self.coords(self.head, hx - hr, hy - hr, hx + hr, hy + hr)
            self.itemconfigure(
                self.head,
                fill=_mix(shade, "#FFFFFF", 0.55),
                state="normal"
            )
        else:
            self.itemconfigure(self.head, state="hidden")

    def animate_to(self, target, steps=45, delay=18, start_delay=0):
        target = max(0.0, min(1.0, float(target)))

        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except Exception:
                pass

        start = self._value

        def step(index):
            try:
                if not self.winfo_exists():
                    return

                amount = _ease_out(index / steps)
                self._draw(start + (target - start) * amount)

            except tk.TclError:
                return

            if index < steps:
                self._job = self.after(delay, lambda: step(index + 1))
            else:
                self._job = None

        self._job = self.after(start_delay, lambda: step(1))


class AnimatedBar(tk.Canvas):
    """Horizontal bar that grows smoothly, with an optional shimmer."""

    def __init__(self, master, app, height=10, color=None, shimmer=False, width=None):
        kwargs = {}

        if width:
            kwargs["width"] = width

        super().__init__(
            master,
            height=height,
            bg=master.cget("bg"),
            highlightthickness=0,
            **kwargs
        )

        self.app = app
        self.bar_height = height
        self.color = color or app.accent
        self.shimmer = shimmer
        self._value = 0.0
        self._job = None
        self._phase = 0.0

        self.track = self.create_rectangle(
            0, 0, 0, height, fill=app.surface, outline=""
        )
        self.fill = self.create_rectangle(
            0, 0, 0, height, fill=self.color, outline=""
        )
        self.shine = self.create_rectangle(
            0, 0, 0, height,
            fill=_mix(self.color, "#FFFFFF", 0.38),
            outline="",
            state="hidden"
        )

        self.bind("<Configure>", lambda event: self._redraw())

        if shimmer:
            self._shimmer_tick()

    def _redraw(self):
        try:
            width = max(1, self.winfo_width())
            fill_width = width * self._value

            self.coords(self.track, 0, 0, width, self.bar_height)
            self.coords(self.fill, 0, 0, fill_width, self.bar_height)

        except tk.TclError:
            return

    def _shimmer_tick(self):
        try:
            if not self.winfo_exists():
                return

            width = max(1, self.winfo_width())
            fill_width = width * self._value

            if fill_width > 12:
                self._phase = (self._phase + 0.018) % 1.35
                position = self._phase * (fill_width + 60) - 40

                x0 = max(0, position)
                x1 = min(fill_width, position + 40)

                if x1 > x0:
                    self.coords(self.shine, x0, 0, x1, self.bar_height)
                    self.itemconfigure(self.shine, state="normal")
                else:
                    self.itemconfigure(self.shine, state="hidden")
            else:
                self.itemconfigure(self.shine, state="hidden")

        except tk.TclError:
            return

        self.after(40, self._shimmer_tick)

    def animate_to(self, target, steps=36, delay=18, start_delay=0):
        target = max(0.0, min(1.0, float(target)))

        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except Exception:
                pass

        start = self._value

        def step(index):
            try:
                if not self.winfo_exists():
                    return

                amount = _ease_out(index / steps)
                self._value = start + (target - start) * amount
                self._redraw()

            except tk.TclError:
                return

            if index < steps:
                self._job = self.after(delay, lambda: step(index + 1))
            else:
                self._job = None

        self._job = self.after(start_delay, lambda: step(1))


class AvatarRing(tk.Canvas):
    """
    Profile avatar: photo (or initials) inside a slowly rotating gradient
    ring. With on_click set, hovering shows a soft "Change photo" overlay.
    """

    def __init__(self, master, app, name, size=104, photo=None, on_click=None):
        super().__init__(
            master,
            width=size,
            height=size,
            bg=master.cget("bg"),
            highlightthickness=0
        )

        self.app = app
        self.size = size
        self.angle = 0
        self.pop = 0.0

        words = [word for word in (name or "S").split() if word]
        initials = "".join(word[0] for word in words[:2]).upper() or "S"

        pad = 6
        self.box = (pad, pad, size - pad, size - pad)

        self.create_oval(*self.box, outline=app.surface, width=5)

        self.arc_a = self.create_arc(
            *self.box, start=0, extent=110, style="arc",
            outline=app.accent, width=5
        )
        self.arc_b = self.create_arc(
            *self.box, start=180, extent=70, style="arc",
            outline=app.accent2, width=5
        )

        inner = pad + 9
        self.disc = self.create_oval(
            inner, inner, size - inner, size - inner,
            fill=app.surface, outline=""
        )

        diameter = size - inner * 2
        self._photo_image = make_photo_image(photo, diameter) if photo else None

        if self._photo_image is not None:
            self.create_image(size / 2, size / 2, image=self._photo_image)
        else:
            self.create_text(
                size / 2, size / 2,
                text=initials,
                fill=app.accent,
                font=("Georgia", int(size / 3.2), "bold")
            )

        if on_click is not None:
            self._overlay_image = overlay_disc(diameter, 150)

            self._overlay = self.create_image(
                size / 2, size / 2,
                image=self._overlay_image,
                state="hidden"
            )
            self._overlay_text = self.create_text(
                size / 2, size / 2,
                text="Change\nphoto" if self._photo_image is not None
                else "Add\nphoto",
                fill="#FFFFFF",
                justify="center",
                font=("Segoe UI", max(8, int(size / 11)), "bold"),
                state="hidden"
            )

            self.configure(cursor="hand2")

            self.bind("<Enter>", lambda event: self._show_overlay(True))
            self.bind("<Leave>", lambda event: self._show_overlay(False))
            self.bind("<Button-1>", lambda event: on_click())

        self._tick()

    def _show_overlay(self, visible):
        state = "normal" if visible else "hidden"

        try:
            self.itemconfigure(self._overlay, state=state)
            self.itemconfigure(self._overlay_text, state=state)
        except tk.TclError:
            pass

    def _tick(self):
        try:
            if not self.winfo_exists():
                return

            self.angle = (self.angle + 4) % 360
            self.pop += 0.06

            wobble = 25 * math.sin(self.pop)

            self.itemconfigure(
                self.arc_a, start=self.angle, extent=110 + wobble
            )
            self.itemconfigure(
                self.arc_b, start=(-self.angle * 0.7) + 180, extent=70 - wobble
            )

        except tk.TclError:
            return

        self.after(40, self._tick)


class RingTimerDisplay(tk.Canvas):
    """
    Animated Pomodoro ring. It is a drop-in replacement for the old timer
    Label: main.py keeps calling  self.timer_display.configure(text="25:00").

    * progress arc glides smoothly (not one jump per second)
    * glowing pulse while the timer is running
    * calm "breathing" circle during break time
    """

    def __init__(self, master, app, size=270):
        super().__init__(
            master,
            width=size,
            height=size,
            bg=app.card_bg,
            highlightthickness=0
        )

        self.app = app
        self.size = size
        self.thickness = 16
        self.cx = size / 2
        self.cy = size / 2
        self._phase = 0
        self._shown = 1.0
        self._text = "25:00"

        pad = self.thickness / 2 + 14
        self.box = (pad, pad, size - pad, size - pad)
        self.radius = (size - 2 * pad) / 2

        self.glow = self.create_oval(
            pad - 7, pad - 7, size - pad + 7, size - pad + 7,
            outline=app.card_bg, width=2
        )
        self.create_oval(*self.box, outline=app.surface, width=self.thickness)

        self.breath = self.create_oval(
            0, 0, 0, 0, fill=app.card_bg, outline="", state="hidden"
        )

        self.arc = self.create_arc(
            *self.box, start=90, extent=-359.9, style="arc",
            outline=app.accent, width=self.thickness
        )
        self.head = self.create_oval(
            0, 0, 0, 0, fill="#FFFFFF", outline="", state="hidden"
        )

        self.time_id = self.create_text(
            self.cx, self.cy - 10,
            text=self._text,
            fill=app.text,
            font=("Segoe UI", int(size / 5.2), "bold")
        )
        self.state_id = self.create_text(
            self.cx, self.cy + size * 0.17,
            text="READY",
            fill=app.muted,
            font=("Segoe UI", 10, "bold")
        )

        self._tick()

    # main.py calls .configure(text="MM:SS") on this object
    def configure(self, cnf=None, **kw):
        if isinstance(cnf, dict):
            kw = {**cnf, **kw}

        text = kw.pop("text", None)

        for ignored in ("fg", "foreground", "font"):
            kw.pop(ignored, None)

        if text is not None:
            self._text = str(text)

            try:
                self.itemconfigure(self.time_id, text=self._text)
            except tk.TclError:
                pass

        if kw:
            return super().configure(**kw)

        return None

    config = configure

    def celebrate(self):
        self.app.confetti_burst(self.master)

    def _tick(self):
        try:
            if not self.winfo_exists():
                return

            app = self.app

            total = max(1, getattr(app, "timer_total_seconds", 1) or 1)
            remaining = max(0, getattr(app, "timer_remaining", 0))
            mode = getattr(app, "timer_mode", "Focus")
            running = getattr(app, "timer_running", False)

            target = min(1.0, remaining / total)

            self._shown += (target - self._shown) * 0.12

            if abs(target - self._shown) < 0.0005:
                self._shown = target

            self._phase += 1

            base = app.accent if mode == "Focus" else app.green
            pulse = (math.sin(self._phase / 9) + 1) / 2 if running else 0.0

            extent = -max(0.1, 359.9 * self._shown)

            self.itemconfigure(
                self.arc,
                extent=extent,
                outline=_mix(base, "#FFFFFF", 0.18 * pulse)
            )

            if self._shown > 0.003:
                angle = math.radians(90 + extent)
                hx = self.cx + self.radius * math.cos(angle)
                hy = self.cy - self.radius * math.sin(angle)
                hr = self.thickness * 0.42 + 2 * pulse

                self.coords(self.head, hx - hr, hy - hr, hx + hr, hy + hr)
                self.itemconfigure(
                    self.head,
                    fill=_mix(base, "#FFFFFF", 0.6),
                    state="normal"
                )
            else:
                self.itemconfigure(self.head, state="hidden")

            if running:
                self.itemconfigure(
                    self.glow,
                    outline=_mix(app.card_bg, base, 0.18 + 0.40 * pulse),
                    width=2 + int(3 * pulse)
                )
            else:
                self.itemconfigure(self.glow, outline=app.card_bg, width=2)

            if mode == "Focus":
                self.itemconfigure(self.breath, state="hidden")

                if running:
                    label = "FOCUSING"
                elif remaining < total:
                    label = "PAUSED"
                else:
                    label = "READY"
            else:
                wave = (math.sin(self._phase / 22) + 1) / 2
                grow = math.cos(self._phase / 22) > 0
                rr = self.radius * (0.50 + 0.15 * wave)

                self.coords(
                    self.breath,
                    self.cx - rr, self.cy - rr, self.cx + rr, self.cy + rr
                )
                self.itemconfigure(
                    self.breath,
                    fill=_mix(app.card_bg, base, 0.06 + 0.12 * wave),
                    state="normal"
                )

                label = "BREATHE IN" if grow else "BREATHE OUT"

                if not running and remaining >= total:
                    label = "BREAK READY"

            self.itemconfigure(self.state_id, text=label)

        except tk.TclError:
            return

        self.after(40, self._tick)


# =============================================================
# MIXIN: methods added to the StudyMate class
# =============================================================

class AnimationsMixin:

    # ---------------------------------------------------------
    # Generic colour animation
    # ---------------------------------------------------------

    def _fade_props(self, widget, props, steps=8, delay=16, start_delay=0):
        """Fades several colour options at once, e.g. {'bg': x, 'fg': y}."""

        previous = getattr(widget, "_multi_fade_job", None)

        if previous:
            try:
                self.root.after_cancel(previous)
            except Exception:
                pass

        def begin():
            try:
                starts = {
                    prop: _rgb(str(widget.cget(prop))) for prop in props
                }
                ends = {prop: _rgb(target) for prop, target in props.items()}
            except Exception:
                try:
                    widget.configure(**props)
                except tk.TclError:
                    pass
                return

            def step(index):
                try:
                    if not widget.winfo_exists():
                        return

                    amount = index / steps
                    widget.configure(**{
                        prop: "#%02x%02x%02x" % tuple(
                            int(round(
                                starts[prop][i]
                                + (ends[prop][i] - starts[prop][i]) * amount
                            ))
                            for i in range(3)
                        )
                        for prop in props
                    })

                except tk.TclError:
                    return

                if index < steps:
                    widget._multi_fade_job = self.root.after(
                        delay, lambda: step(index + 1)
                    )
                else:
                    widget._multi_fade_job = None

            step(1)

        widget._multi_fade_job = self.root.after(start_delay, begin)

    def typewrite(self, label, text, delay=22, on_done=None):
        """Types text into a Label one character at a time."""

        previous = getattr(label, "_type_job", None)

        if previous:
            try:
                label.after_cancel(previous)
            except Exception:
                pass

        state = {"i": 0}

        def step():
            try:
                if not label.winfo_exists():
                    return

                state["i"] = min(len(text), state["i"] + 1)
                cursor = "▌" if state["i"] < len(text) else ""
                label.configure(text=text[:state["i"]] + cursor)

            except tk.TclError:
                return

            if state["i"] < len(text):
                label._type_job = label.after(delay, step)
            else:
                label._type_job = None

                if on_done:
                    on_done()

        step()

    def animate_text_number(self, label, text, steps=24, delay=24):
        """Counts up the number inside text such as '120 minutes' or '40%'."""

        match = re.match(r"^\s*(\d+)(.*)$", str(text), re.S)

        if not match:
            label.configure(text=str(text))
            return

        self.animate_count(
            label, int(match.group(1)), match.group(2),
            steps=steps, delay=delay
        )

    def consume_flash(self, attribute, value):
        """True once if `attribute` equals `value`, then clears the flag."""

        if getattr(self, attribute, None) == value:
            setattr(self, attribute, None)
            return True

        return False

    # ---------------------------------------------------------
    # Page transition (staggered slide-in of every card)
    # ---------------------------------------------------------

    def begin_page_transition(self):
        """Called right after clear_page(). Hides the half-built page and
        schedules the staggered reveal once the page is fully built."""

        self._row_counter = 0
        self._transition_token = getattr(self, "_transition_token", 0) + 1
        token = self._transition_token

        if getattr(self, "current_page", "") in PAGES_WITHOUT_TRANSITION:
            try:
                self.page_canvas.itemconfigure(
                    self.page_window, state="normal"
                )
            except tk.TclError:
                pass

            return

        try:
            self.page_canvas.itemconfigure(self.page_window, state="hidden")
        except tk.TclError:
            return

        self.root.after_idle(lambda: self.reveal_page(token))

    def reveal_page(self, token):
        if token != self._transition_token:
            return

        try:
            children = list(self.page_area.winfo_children())
            infos = []

            for child in children:
                info = child.pack_info()
                info.pop("in", None)
                infos.append(info)

            for child in children:
                child.pack_forget()

        except tk.TclError:
            # A child is not managed by pack: show the page without effects
            infos = None

        finally:
            try:
                self.page_canvas.itemconfigure(
                    self.page_window, state="normal"
                )
            except tk.TclError:
                return

        if infos is None:
            # Re-pack nothing: children that failed were never forgotten
            return

        for index, (child, info) in enumerate(zip(children, infos)):
            delay = min(index, 8) * 70 + max(0, index - 8) * 2

            self.root.after(
                delay,
                lambda c=child, i=info: self._slide_in(c, i, token)
            )

    def _slide_in(self, widget, info, token):
        if token != self._transition_token:
            return

        top, bottom = _split_pad(info.get("pady", 0))
        offset = 28
        steps = 9

        try:
            if not widget.winfo_exists():
                return

            first = dict(info)
            first["pady"] = (top + offset, bottom)
            widget.pack(**first)

        except tk.TclError:
            return

        def step(index):
            if token != self._transition_token:
                return

            try:
                if not widget.winfo_exists():
                    return

                amount = _ease_out(index / steps)
                current = dict(info)
                current["pady"] = (top + int(offset * (1 - amount)), bottom)
                widget.pack_configure(**current)

            except tk.TclError:
                return

            if index < steps:
                self.root.after(14, lambda: step(index + 1))

        step(1)

    # ---------------------------------------------------------
    # Smooth mouse-wheel scrolling
    # ---------------------------------------------------------

    def smooth_scroll(self, units):
        canvas = self.page_canvas

        try:
            top, bottom = canvas.yview()
        except tk.TclError:
            return

        span = bottom - top

        if span >= 0.999:
            return

        running = getattr(self, "_scroll_job", None) is not None
        base = self._scroll_target if running else top

        self._scroll_target = max(
            0.0, min(1.0 - span, base + units * span * 0.14)
        )

        if running:
            return

        def step():
            try:
                current, _ = canvas.yview()
                difference = self._scroll_target - current

                if abs(difference) < 0.0006:
                    canvas.yview_moveto(self._scroll_target)
                    self._scroll_job = None
                    return

                canvas.yview_moveto(current + difference * 0.28)
                self._scroll_job = self.root.after(12, step)

            except tk.TclError:
                self._scroll_job = None

        self._scroll_job = self.root.after(0, step)

    # ---------------------------------------------------------
    # Toast notifications
    # ---------------------------------------------------------

    def toast(self, message, kind="success", duration=2600):
        colors = {
            "success": self.green,
            "error": self.red,
            "warning": self.orange,
            "info": self.accent2,
        }
        icons = {"success": "✓", "error": "✕", "warning": "!", "info": "i"}

        color = colors.get(kind, self.accent)

        previous = getattr(self, "_toast", None)

        if previous is not None:
            try:
                previous.destroy()
            except tk.TclError:
                pass

        frame = tk.Frame(
            self.root,
            bg=self.surface,
            highlightthickness=1,
            highlightbackground=color
        )

        tk.Frame(frame, bg=color, width=5).pack(side="left", fill="y")

        tk.Label(
            frame,
            text=icons.get(kind, "i"),
            bg=self.surface,
            fg=color,
            font=("Segoe UI", 13, "bold"),
            padx=12
        ).pack(side="left")

        tk.Label(
            frame,
            text=message,
            bg=self.surface,
            fg=self.text,
            font=("Segoe UI", 10, "bold"),
            pady=12
        ).pack(side="left", padx=(0, 18))

        self._toast = frame

        frame.update_idletasks()
        width = frame.winfo_reqwidth() + 40
        steps = 10

        def place_at(offset):
            try:
                frame.place(relx=1.0, rely=1.0, x=-24 + offset, y=-24, anchor="se")
                frame.lift()
            except tk.TclError:
                pass

        def slide_in(index):
            if self._toast is not frame:
                return

            place_at(int(width * (1 - _ease_out(index / steps))))

            if index < steps:
                self.root.after(14, lambda: slide_in(index + 1))
            else:
                self.root.after(duration, lambda: slide_out(0))

        def slide_out(index):
            if self._toast is not frame:
                return

            place_at(int(width * _ease_out(index / steps)))

            if index < steps:
                self.root.after(14, lambda: slide_out(index + 1))
            else:
                try:
                    frame.destroy()
                except tk.TclError:
                    pass

                self._toast = None

        slide_in(0)

    # ---------------------------------------------------------
    # Shake an invalid input
    # ---------------------------------------------------------

    def shake(self, widget, distance=8, steps=12):
        try:
            info = widget.pack_info()
        except tk.TclError:
            return

        info.pop("in", None)
        left, right = _split_pad(info.get("padx", 0))

        offsets = [
            int(distance * math.sin(i / steps * math.pi * 4) * (1 - i / steps))
            for i in range(steps + 1)
        ]

        def step(index):
            try:
                if not widget.winfo_exists():
                    return

                shift = offsets[index]
                current = dict(info)
                current["padx"] = (
                    max(0, left + shift), max(0, right - shift)
                )
                widget.pack_configure(**current)

            except tk.TclError:
                return

            if index < steps:
                widget.after(22, lambda: step(index + 1))

        step(0)

    # ---------------------------------------------------------
    # Confetti
    # ---------------------------------------------------------

    def confetti_burst(self, parent, height=130, count=70, duration=2800):
        try:
            canvas = tk.Canvas(
                parent,
                height=height,
                bg=parent.cget("bg"),
                highlightthickness=0
            )
            canvas.pack(fill="x", pady=(8, 0))
            canvas.update_idletasks()
        except tk.TclError:
            return

        width = canvas.winfo_width()

        if width < 80:
            width = 560

        palette = [
            self.accent, self.accent2, self.green, self.orange, self.red
        ]

        pieces = []

        for _ in range(count):
            size = random.uniform(5, 9)
            pieces.append({
                "x": random.uniform(0, width),
                "y": random.uniform(-height, 0),
                "vx": random.uniform(-1.2, 1.2),
                "vy": random.uniform(1.5, 4.0),
                "spin": random.uniform(0, math.tau),
                "spin_speed": random.uniform(0.12, 0.35),
                "size": size,
                "id": canvas.create_rectangle(
                    0, 0, 0, 0,
                    fill=random.choice(palette),
                    outline=""
                ),
            })

        started = {"frame": 0}
        limit = int(duration / 22)

        def tick():
            try:
                if not canvas.winfo_exists():
                    return

                started["frame"] += 1
                alive = 0

                for piece in pieces:
                    piece["vy"] += 0.07
                    piece["x"] += piece["vx"] + math.sin(piece["spin"]) * 0.6
                    piece["y"] += piece["vy"]
                    piece["spin"] += piece["spin_speed"]

                    flip = abs(math.cos(piece["spin"])) * piece["size"]
                    half_h = piece["size"] * 0.55

                    canvas.coords(
                        piece["id"],
                        piece["x"] - flip / 2, piece["y"] - half_h,
                        piece["x"] + flip / 2, piece["y"] + half_h
                    )

                    if piece["y"] < height + 12:
                        alive += 1

                if alive == 0 or started["frame"] > limit:
                    canvas.destroy()
                    return

            except tk.TclError:
                return

            canvas.after(22, tick)

        tick()

    # ---------------------------------------------------------
    # Rows: hover, fade-in text, flash
    # ---------------------------------------------------------

    def make_row_interactive(self, row, flash=False):
        """Gives a row a smooth hover highlight, staggered text fade-in and
        an optional 'new item' flash."""

        normal = self.card_bg
        hover = _mix(self.card_bg, self.accent, 0.09)
        state = {"items": []}

        def hover_targets():
            items = []

            for widget in [row] + _descendants(row):
                if isinstance(widget, (tk.Label, tk.Frame)):
                    try:
                        if str(widget.cget("bg")) == normal:
                            items.append(widget)
                    except tk.TclError:
                        pass

            return items

        def enter(event=None):
            state["items"] = hover_targets() or state["items"]

            for widget in state["items"]:
                self.fade_color(widget, "bg", hover, steps=6, delay=12)

        def leave(event=None):
            try:
                x, y = row.winfo_pointerxy()
                under = row.winfo_containing(x, y)

                if under is not None and str(under).startswith(str(row)):
                    return

            except (tk.TclError, KeyError):
                pass

            for widget in state["items"]:
                self.fade_color(widget, "bg", normal, steps=8, delay=14)

        for widget in [row] + _descendants(row):
            widget.bind("<Enter>", enter, add="+")
            widget.bind("<Leave>", leave, add="+")

        # staggered text fade-in
        self._row_counter = getattr(self, "_row_counter", 0)
        order = self._row_counter
        self._row_counter += 1

        for widget in [row] + _descendants(row):
            if isinstance(widget, tk.Label):
                try:
                    final = str(widget.cget("fg"))
                    background = str(widget.cget("bg"))
                    widget.configure(fg=background)
                    self._fade_props(
                        widget,
                        {"fg": final},
                        steps=9,
                        delay=18,
                        start_delay=380 + order * 60
                    )
                except (tk.TclError, ValueError):
                    pass

        if flash:
            def do_flash():
                for widget in hover_targets():
                    try:
                        widget.configure(bg=_mix(normal, self.accent, 0.30))
                        self.fade_color(widget, "bg", normal, steps=26, delay=34)
                    except tk.TclError:
                        pass

            self.root.after(520, do_flash)

    def info_row(self, parent, text, fg=None, font=None, pady=4):
        """A full-width text row with hover highlight and fade-in."""

        label = tk.Label(
            parent,
            text=text,
            bg=self.card_bg,
            fg=fg or self.text,
            font=font or ("Segoe UI", 10),
            anchor="w",
            padx=8,
            pady=pady
        )
        label.pack(fill="x", pady=1)

        self.make_row_interactive(label)

        return label

    def hover_highlight(self, frame, widgets, normal, hover):
        """Fades a frame's border colour on hover (used by theme swatches)."""

        def enter(event):
            self.fade_color(
                frame, "highlightbackground", hover, steps=6, delay=12
            )

        def leave(event):
            try:
                x, y = frame.winfo_pointerxy()
                under = frame.winfo_containing(x, y)

                if under is not None and str(under).startswith(str(frame)):
                    return

            except (tk.TclError, KeyError):
                pass

            self.fade_color(
                frame, "highlightbackground", normal, steps=8, delay=14
            )

        for widget in widgets:
            widget.bind("<Enter>", enter, add="+")
            widget.bind("<Leave>", leave, add="+")

    def flash_tree_row(self, tree, iid, color=None, steps=24, delay=38):
        try:
            if iid not in tree.get_children():
                return
        except tk.TclError:
            return

        color = color or self.accent
        original = tree.item(iid, "tags")

        tree.see(iid)
        tree.item(iid, tags=("flash",))

        def step(index):
            try:
                if not tree.winfo_exists():
                    return

                amount = index / steps
                tree.tag_configure(
                    "flash",
                    background=_mix(
                        _mix(self.card_bg, color, 0.45), self.card_bg, amount
                    )
                )

                if index >= steps:
                    tree.item(iid, tags=original)
                    return

            except tk.TclError:
                return

            tree.after(delay, lambda: step(index + 1))

        step(0)

    # ---------------------------------------------------------
    # Sidebar extras
    # ---------------------------------------------------------

    def pulse_logo(self, logo):
        state = {"t": 0.0}
        bright = _mix(self.accent, self.text, 0.42)

        def tick():
            try:
                if not logo.winfo_exists():
                    return

                state["t"] += 0.05
                level = (math.sin(state["t"]) + 1) / 2
                logo.configure(fg=_mix(self.accent, bright, level))

            except tk.TclError:
                return

            logo.after(90, tick)

        tick()

    def create_sidebar_ambient(self):
        canvas = tk.Canvas(
            self.sidebar,
            height=56,
            bg=self.sidebar_bg,
            highlightthickness=0
        )
        canvas.pack(side="bottom", fill="x", pady=(0, 2))

        dots = []

        for _ in range(16):
            dots.append({
                "x": random.uniform(0, 225),
                "y": random.uniform(0, 56),
                "speed": random.uniform(0.15, 0.5),
                "drift": random.uniform(-0.15, 0.15),
                "radius": random.uniform(1.0, 2.4),
                "twinkle": random.uniform(0, math.tau),
                "id": canvas.create_oval(0, 0, 0, 0, outline="")
            })

        def tick():
            try:
                if not canvas.winfo_exists():
                    return

                width = max(60, canvas.winfo_width())

                for dot in dots:
                    dot["y"] -= dot["speed"]
                    dot["x"] += dot["drift"]
                    dot["twinkle"] += 0.08

                    if dot["y"] < -4:
                        dot["y"] = 60
                        dot["x"] = random.uniform(0, width)

                    glow = (math.sin(dot["twinkle"]) + 1) / 2
                    r = dot["radius"]

                    canvas.coords(
                        dot["id"],
                        dot["x"] - r, dot["y"] - r, dot["x"] + r, dot["y"] + r
                    )
                    canvas.itemconfigure(
                        dot["id"],
                        fill=_mix(self.sidebar_bg, self.accent, 0.15 + 0.5 * glow)
                    )

            except tk.TclError:
                return

            canvas.after(60, tick)

        tick()

    # ---------------------------------------------------------
    # Dashboard
    # ---------------------------------------------------------

    def study_streak(self):
        days = {
            session.get("date")
            for session in self.data["study_sessions"]
            if session.get("minutes", 0) > 0
        }

        streak = 0
        day = date.today()

        if day.isoformat() not in days:
            day -= timedelta(days=1)

        while day.isoformat() in days:
            streak += 1
            day -= timedelta(days=1)

        return streak

    def create_insight_row(self, studied, goal):
        row = tk.Frame(self.page_area, bg=self.bg)
        row.pack(fill="x", pady=(0, 18))

        for column in range(3):
            row.grid_columnconfigure(column, weight=1, uniform="insight")

        # ----- card 1: daily goal ring -----
        goal_card = self.card(row)
        goal_card.grid(row=0, column=0, sticky="nsew", padx=7, pady=7)

        self.section_title(goal_card, "Daily Goal")

        fraction = min(1.0, studied / goal) if goal else 0.0

        ring = ProgressRing(
            goal_card, self, size=132, thickness=13,
            color=self.green if fraction >= 1 else self.accent,
            caption=f"{studied}/{goal} min"
        )
        ring.pack(pady=(0, 4))
        ring.animate_to(fraction, start_delay=450)

        # ----- card 2: streak -----
        streak_card = self.card(row)
        streak_card.grid(row=0, column=1, sticky="nsew", padx=7, pady=7)

        self.section_title(streak_card, "Study Streak")

        streak = self.study_streak()

        flame = tk.Canvas(
            streak_card, width=70, height=58,
            bg=self.card_bg, highlightthickness=0
        )
        flame.pack()

        flame_id = flame.create_text(
            35, 30,
            text="🔥" if streak else "🌱",
            font=("Segoe UI Emoji", 26)
        )

        flame_state = {"t": 0.0}

        def flicker():
            try:
                if not flame.winfo_exists():
                    return

                flame_state["t"] += 0.18
                size = 26 + int(3 * math.sin(flame_state["t"]))
                flame.itemconfigure(
                    flame_id, font=("Segoe UI Emoji", size)
                )
                flame.coords(
                    flame_id,
                    35 + math.sin(flame_state["t"] * 1.7),
                    30 - math.sin(flame_state["t"]) * 1.5
                )

            except tk.TclError:
                return

            flame.after(70, flicker)

        flicker()

        streak_label = tk.Label(
            streak_card,
            text="0 days",
            bg=self.card_bg,
            fg=self.orange if streak else self.muted,
            font=("Segoe UI", 18, "bold")
        )
        streak_label.pack()

        self.animate_count(
            streak_label, streak, " day" if streak == 1 else " days"
        )

        week = tk.Canvas(
            streak_card, width=7 * 27, height=44,
            bg=self.card_bg, highlightthickness=0
        )
        week.pack(pady=(8, 0))

        studied_days = {
            session.get("date")
            for session in self.data["study_sessions"]
            if session.get("minutes", 0) > 0
        }

        today = date.today()

        for index in range(7):
            day = today - timedelta(days=6 - index)
            active = day.isoformat() in studied_days
            x = 14 + index * 27

            week.create_text(
                x, 36, text=day.strftime("%a")[0],
                fill=self.muted, font=("Segoe UI", 8)
            )

            circle = week.create_oval(
                x, 14, x, 14,
                fill=self.green if active else self.card_bg,
                outline=self.green if active else self.card_border,
                width=2
            )

            week.after(
                500 + index * 90,
                lambda c=circle, cx=x: self._grow_circle(week, c, cx, 14, 9)
            )

        # ----- card 3: quote -----
        quote_card = self.card(row)
        quote_card.grid(row=0, column=2, sticky="nsew", padx=7, pady=7)

        self.section_title(quote_card, "Daily Inspiration")

        quote_label = tk.Label(
            quote_card,
            text="",
            bg=self.card_bg,
            fg=self.text,
            font=("Georgia", 11, "italic"),
            wraplength=240,
            justify="left",
            anchor="nw",
            height=5
        )
        quote_label.pack(fill="x")

        author_label = tk.Label(
            quote_card,
            text="",
            bg=self.card_bg,
            fg=self.accent,
            font=("Segoe UI", 9, "bold"),
            anchor="w"
        )
        author_label.pack(fill="x", pady=(4, 0))

        self.rotating_quotes(quote_label, author_label)

        return row

    def _grow_circle(self, canvas, circle, x, y, max_radius, step=1, steps=8):
        try:
            if not canvas.winfo_exists():
                return

            radius = max_radius * _ease_out(step / steps)
            canvas.coords(circle, x - radius, y - radius, x + radius, y + radius)

        except tk.TclError:
            return

        if step < steps:
            canvas.after(
                25,
                lambda: self._grow_circle(
                    canvas, circle, x, y, max_radius, step + 1, steps
                )
            )

    def rotating_quotes(self, label, author_label):
        state = {"i": random.randrange(len(QUOTES))}

        def show():
            try:
                if not label.winfo_exists():
                    return

                quote, author = QUOTES[state["i"] % len(QUOTES)]
                state["i"] += 1

                author_label.configure(text="")

                self.typewrite(
                    label,
                    "“" + quote + "”",
                    delay=24,
                    on_done=lambda: author_label.configure(text="— " + author)
                )

                label.after(len(quote) * 24 + 7500, show)

            except tk.TclError:
                return

        label.after(600, show)

    # ---------------------------------------------------------
    # Tasks
    # ---------------------------------------------------------

    def create_task_progress(self, parent):
        tasks = self.data["tasks"]
        total = len(tasks)

        if not total:
            return

        done = sum(1 for task in tasks if task.get("completed"))

        top = tk.Frame(parent, bg=self.card_bg)
        top.pack(fill="x", pady=(0, 6))

        summary = tk.Label(
            top,
            text=f"0 of {total} tasks completed",
            bg=self.card_bg,
            fg=self.muted,
            font=("Segoe UI", 10)
        )
        summary.pack(side="left")

        percent = tk.Label(
            top,
            text="0%",
            bg=self.card_bg,
            fg=self.green,
            font=("Segoe UI", 10, "bold")
        )
        percent.pack(side="right")

        self.animate_count(summary, done, f" of {total} tasks completed")
        self.animate_count(percent, int(done / total * 100), "%")

        bar = AnimatedBar(parent, self, height=10, color=self.green, shimmer=True)
        bar.pack(fill="x", pady=(0, 14))
        bar.animate_to(done / total, start_delay=450)

    def task_row_tags(self, task):
        if task.get("completed"):
            return ("done",)

        return ({"High": "high", "Low": "low"}.get(
            task.get("priority", "Medium"), "medium"
        ),)

    def style_task_tree(self, tree):
        tree.tag_configure("done", foreground=self.muted)
        tree.tag_configure("high", foreground=self.red)
        tree.tag_configure("medium", foreground=self.text)
        tree.tag_configure("low", foreground=self.green)

        index = getattr(self, "_flash_task_index", None)

        if index is not None:
            self._flash_task_index = None
            color = getattr(self, "_flash_task_color", None) or self.accent
            tree.after(
                520,
                lambda: self.flash_tree_row(tree, str(index), color)
            )

    # ---------------------------------------------------------
    # Smart Scheduler
    # ---------------------------------------------------------

    def render_schedule_item(self, parent, index, task, duration):
        priority = task.get("priority", "Medium")
        accent = {
            "High": self.red, "Medium": self.orange, "Low": self.green
        }.get(priority, self.accent)

        row = tk.Frame(parent, bg=self.card_bg)
        row.pack(fill="x", pady=6)

        tk.Frame(row, bg=accent, width=4).pack(
            side="left", fill="y", padx=(0, 12)
        )

        tk.Label(
            row,
            text=str(index + 1),
            bg=self.surface,
            fg=accent,
            font=("Segoe UI", 12, "bold"),
            width=3,
            pady=6
        ).pack(side="left", padx=(0, 14))

        body = tk.Frame(row, bg=self.card_bg)
        body.pack(side="left", fill="x", expand=True)

        tk.Label(
            body,
            text=task.get("title", "Untitled task"),
            bg=self.card_bg,
            fg=self.text,
            font=("Segoe UI", 10, "bold"),
            anchor="w"
        ).pack(fill="x")

        due = task.get("date", "")
        today = date.today().isoformat()

        meta = (
            f"Subject: {task.get('subject', 'General')}   |   "
            f"Due: {due or 'No date'}   |   {priority} priority"
        )

        if due and due < today:
            meta += "   |   OVERDUE"
        elif due == today:
            meta += "   |   DUE TODAY"

        tk.Label(
            body,
            text=meta,
            bg=self.card_bg,
            fg=(
                self.red if due and due < today
                else self.orange if due == today
                else self.muted
            ),
            font=("Segoe UI", 9),
            anchor="w"
        ).pack(fill="x", pady=(2, 0))

        side = tk.Frame(row, bg=self.card_bg)
        side.pack(side="right", padx=(12, 6))

        tk.Label(
            side,
            text=f"{duration} min",
            bg=self.card_bg,
            fg=accent,
            font=("Segoe UI", 10, "bold")
        ).pack(anchor="e")

        bar = AnimatedBar(side, self, height=7, color=accent, width=130)
        bar.pack(pady=(4, 0))
        bar.animate_to(duration / 60, start_delay=520 + index * 110)

        self.make_row_interactive(row)

    # ---------------------------------------------------------
    # Lecture Hub: typing placeholder
    # ---------------------------------------------------------

    def animate_placeholder(self, entry, phrases):
        hint = tk.Label(
            entry.master,
            text="",
            bg=self.input_bg,
            fg=self.muted,
            font=("Segoe UI", 10),
            anchor="w",
            cursor="xterm"
        )

        hint.bind("<Button-1>", lambda event: entry.focus_set())

        state = {
            "phrase": 0, "chars": 0, "wait": 0,
            "erasing": False, "shown": False
        }

        def set_visible(visible):
            if visible and not state["shown"]:
                hint.place(in_=entry, x=10, rely=0.5, anchor="w")
                hint.lift()
                state["shown"] = True
            elif not visible and state["shown"]:
                hint.place_forget()
                state["shown"] = False

        def tick():
            try:
                if not entry.winfo_exists() or not hint.winfo_exists():
                    return

                try:
                    focused = entry.focus_get() is entry
                except KeyError:
                    focused = False

                if entry.get() or focused:
                    set_visible(False)
                    entry.after(200, tick)
                    return

                set_visible(True)

                text = phrases[state["phrase"] % len(phrases)]

                if state["wait"] > 0:
                    state["wait"] -= 1

                elif not state["erasing"]:
                    state["chars"] += 1
                    hint.configure(text=text[:state["chars"]] + "▌")

                    if state["chars"] >= len(text):
                        state["wait"] = 28
                        state["erasing"] = True
                        hint.configure(text=text)

                else:
                    state["chars"] = max(0, state["chars"] - 2)
                    hint.configure(text=text[:state["chars"]] + "▌")

                    if state["chars"] == 0:
                        state["erasing"] = False
                        state["phrase"] += 1
                        state["wait"] = 6

            except tk.TclError:
                return

            entry.after(65, tick)

        tick()

    # ---------------------------------------------------------
    # AI Assistant
    # ---------------------------------------------------------

    def ai_insert_message(self, role, text, animated=False):
        out = getattr(self, "ai_output", None)

        try:
            if out is None or not out.winfo_exists():
                return
        except tk.TclError:
            return

        is_user = role == "user"
        label = "You" if is_user else getattr(self, "ai_name", "StudyMate AI")
        color = self.accent2 if is_user else getattr(self, "hud_color", self.green)
        tag = "speaker_user" if is_user else "speaker_ai"

        try:
            out.tag_configure(
                tag, foreground=color, font=("Segoe UI", 10, "bold")
            )
            out.configure(state="normal")
            out.insert("end", f"{label}\n", (tag,))

            if not animated or not text:
                out.insert("end", text + "\n\n")
                out.see("end")
                out.configure(state="disabled")
                return

            out.see("end")
            out.configure(state="disabled")

        except tk.TclError:
            return

        self._ai_typing = True
        chunk = max(2, len(text) // 150)
        position = [0]

        def step():
            try:
                if not out.winfo_exists():
                    self._ai_typing = False
                    return

                out.configure(state="normal")

                piece = text[position[0]:position[0] + chunk]
                position[0] += chunk
                finished = position[0] >= len(text)

                out.insert("end", piece)

                if finished:
                    out.insert("end", "\n\n")

                out.see("end")
                out.configure(state="disabled")

            except tk.TclError:
                self._ai_typing = False
                return

            if finished:
                self._ai_typing = False
            else:
                out.after(12, step)

        step()

    def append_ai_message_animated(self, role, text):
        self.ai_insert_message(role, text, animated=True)

    def start_thinking(self):
        """Bouncing three-dot 'thinking' indicator inside the chat."""

        job = getattr(self, "_think_job", None)

        if job:
            try:
                self.root.after_cancel(job)
            except Exception:
                pass

        self._thinking = True
        self._think_frame = 0

        out = getattr(self, "ai_output", None)

        try:
            out.tag_configure(
                "speaker_ai", foreground=getattr(self, "hud_color", self.green),
                font=("Segoe UI", 10, "bold")
            )
            out.configure(state="normal")
            out.mark_set("think_start", "end-1c")
            out.mark_gravity("think_start", "left")
            out.insert(
                "end",
                getattr(self, "ai_name", "StudyMate AI") + "\n",
                ("speaker_ai",)
            )
            out.insert("end", "●", ("think0",))
            out.insert("end", " ●", ("think1",))
            out.insert("end", " ●", ("think2",))
            out.insert("end", "\n\n")
            out.see("end")
            out.configure(state="disabled")

        except (tk.TclError, AttributeError):
            self._thinking = False
            return

        self._think_tick()

    def _think_tick(self):
        if not getattr(self, "_thinking", False):
            return

        frame = self._think_frame
        self._think_frame += 1

        try:
            out = self.ai_output

            for index in range(3):
                level = (math.sin(frame / 3.2 - index * 0.9) + 1) / 2

                out.tag_configure(
                    f"think{index}",
                    foreground=_mix(self.muted, self.accent, level),
                    offset=int(5 * level)
                )

            dots = "." * (1 + (frame // 4) % 3)

            self.ai_status.configure(
                text=getattr(self, "ai_name", "StudyMate AI") + " is thinking" + dots,
                fg=self.orange
            )

        except (tk.TclError, AttributeError):
            self._thinking = False
            return

        self._think_job = self.root.after(70, self._think_tick)

    def stop_thinking(self):
        if not getattr(self, "_thinking", False):
            return

        self._thinking = False

        try:
            out = self.ai_output
            out.configure(state="normal")
            out.delete("think_start", "end-1c")
            out.configure(state="disabled")
        except (tk.TclError, AttributeError):
            pass

    def create_prompt_chips(self, parent):
        chips = [
            ("💡 Explain simply", "Explain this in simple words with an example: "),
            ("📝 Quiz me", "Quiz me with 5 questions on: "),
            ("📚 Summarise", "Summarise the key points of: "),
            ("🧠 Memory trick", "Give me a memory trick to remember: "),
            ("🔍 Step by step", "Solve this step by step: "),
        ]

        row = tk.Frame(parent, bg=self.card_bg)
        row.pack(fill="x", pady=(0, 10))

        def use(prefix):
            box = getattr(self, "ai_input", None)

            try:
                existing = box.get("1.0", "end").strip()
                box.delete("1.0", "end")
                box.insert("1.0", prefix + existing)
                box.focus_set()
                box.mark_set("insert", "end-1c")
            except (tk.TclError, AttributeError):
                pass

        for index, (text, prefix) in enumerate(chips):
            chip = tk.Label(
                row,
                text=text,
                bg=self.surface,
                fg=self.card_bg,
                font=("Segoe UI", 9),
                padx=12,
                pady=6,
                cursor="hand2"
            )
            chip.pack(side="left", padx=(0, 8))

            hover = _mix(self.surface, self.accent, 0.35)

            chip.bind(
                "<Enter>",
                lambda event, c=chip, h=hover:
                    self.fade_color(c, "bg", h, steps=6, delay=12)
            )
            chip.bind(
                "<Leave>",
                lambda event, c=chip:
                    self.fade_color(c, "bg", self.surface, steps=8, delay=14)
            )
            chip.bind("<Button-1>", lambda event, p=prefix: use(p))

            self._fade_props(
                chip, {"fg": self.text},
                steps=9, delay=18, start_delay=450 + index * 80
            )

    # ---------------------------------------------------------
    # Daily Goals
    # ---------------------------------------------------------

    def create_goal_visual(self, parent, percentage, studied, goal):
        wrap = tk.Frame(parent, bg=self.card_bg)
        wrap.pack(fill="x", pady=8)

        reached = percentage >= 100
        color = self.green if reached else self.accent

        ring = ProgressRing(
            wrap, self, size=170, thickness=15,
            color=color, caption="of daily goal"
        )
        ring.pack(side="left", padx=(0, 30))
        ring.animate_to(percentage / 100, steps=55, start_delay=500)

        side = tk.Frame(wrap, bg=self.card_bg)
        side.pack(side="left", fill="x", expand=True)

        tk.Label(
            side,
            text="Progress",
            bg=self.card_bg,
            fg=self.muted,
            font=("Segoe UI", 10)
        ).pack(anchor="w")

        bar = AnimatedBar(side, self, height=12, color=color, shimmer=True)
        bar.pack(fill="x", pady=(8, 14))
        bar.animate_to(percentage / 100, steps=55, start_delay=500)

        chips = tk.Frame(side, bg=self.card_bg)
        chips.pack(anchor="w")

        for mark in (25, 50, 75, 100):
            chip = tk.Label(
                chips,
                text=f"{mark}%",
                bg=self.surface,
                fg=self.muted,
                font=("Segoe UI", 9, "bold"),
                padx=12,
                pady=5
            )
            chip.pack(side="left", padx=(0, 8))

            if percentage >= mark:
                self._fade_props(
                    chip,
                    {"bg": _mix(self.card_bg, color, 0.85), "fg": self.btn_text},
                    steps=10,
                    delay=20,
                    start_delay=500 + int(mark / 100 * 1100)
                )

        remaining = max(0, goal - studied)

        message = tk.Label(
            side,
            text="",
            bg=self.card_bg,
            fg=self.green if reached else self.muted,
            font=("Segoe UI", 10, "bold" if reached else "normal")
        )
        message.pack(anchor="w", pady=(14, 0))

        self.typewrite(
            message,
            "🎉 Goal reached - fantastic work!"
            if reached else f"{remaining} more minutes to hit today's goal.",
            delay=28
        )

        if reached:
            self.root.after(1300, lambda: self.confetti_burst(parent))

        return wrap

    # ---------------------------------------------------------
    # Focus Mode
    # ---------------------------------------------------------

    def celebrate_timer(self):
        display = getattr(self, "timer_display", None)

        try:
            if display is not None and display.winfo_exists():
                self.confetti_burst(display.master)
        except (tk.TclError, AttributeError):
            pass

    # ---------------------------------------------------------
    # Calendar
    # ---------------------------------------------------------

    def register_calendar_cell(self, label, current_date, has_task, is_today,
                               row_index, column):
        normal_bg = str(label.cget("bg"))
        normal_fg = str(label.cget("fg"))

        cell = {
            "label": label,
            "date": current_date,
            "bg": normal_bg,
            "fg": normal_fg,
            "order": (row_index - 1) * 7 + column,
            "today": is_today,
        }

        self._cal_cells.append(cell)

        label.configure(
            cursor="hand2",
            highlightthickness=2,
            highlightbackground=self.card_bg,
            bg=self.card_bg,
            fg=self.card_bg
        )

        hover = _mix(normal_bg, self.accent2, 0.30)

        def enter(event):
            if not is_today:
                self.fade_color(label, "bg", hover, steps=5, delay=10)

        def leave(event):
            if not is_today:
                self.fade_color(label, "bg", normal_bg, steps=7, delay=12)

        label.bind("<Enter>", enter)
        label.bind("<Leave>", leave)
        label.bind("<Button-1>", lambda event, c=cell: self.select_calendar_day(c))

    def build_calendar_detail(self, parent):
        self._cal_selected = None

        self._cal_detail = tk.Label(
            parent,
            text="Click any day to see its tasks.",
            bg=self.card_bg,
            fg=self.muted,
            font=("Segoe UI", 10),
            anchor="w",
            justify="left"
        )
        self._cal_detail.pack(fill="x", pady=(14, 0))

        # wave-in animation of the day cells
        for cell in self._cal_cells:
            self._fade_props(
                cell["label"],
                {"bg": cell["bg"], "fg": cell["fg"]},
                steps=8,
                delay=16,
                start_delay=260 + cell["order"] * 18
            )

        # gentle pulse on today's date
        today_cells = [cell for cell in self._cal_cells if cell["today"]]

        if today_cells:
            label = today_cells[0]["label"]
            base = today_cells[0]["bg"]
            bright = _mix(base, "#FFFFFF", 0.32)
            state = {"t": 0.0}

            def pulse():
                try:
                    if not label.winfo_exists():
                        return

                    state["t"] += 0.12
                    level = (math.sin(state["t"]) + 1) / 2
                    label.configure(bg=_mix(base, bright, level))

                except tk.TclError:
                    return

                label.after(70, pulse)

            label.after(1300, pulse)

    def select_calendar_day(self, cell):
        previous = getattr(self, "_cal_selected", None)

        try:
            if previous is not None and previous["label"].winfo_exists():
                previous["label"].configure(highlightbackground=self.card_bg)

            cell["label"].configure(highlightbackground=self.accent2)
        except tk.TclError:
            return

        self._cal_selected = cell

        tasks = [
            task for task in self.data["tasks"]
            if task.get("date") == cell["date"]
        ]

        try:
            when = datetime.strptime(cell["date"], "%Y-%m-%d").strftime(
                "%A, %d %B %Y"
            )
        except ValueError:
            when = cell["date"]

        if not tasks:
            text = f"{when}\nNothing planned - a free day!"
        else:
            lines = [f"{when}  -  {len(tasks)} task(s)"]

            for task in tasks:
                mark = "✓" if task.get("completed") else "○"
                lines.append(
                    f"   {mark}  {task.get('title', 'Untitled')}"
                    f"  ({task.get('subject', 'General')})"
                )

            text = "\n".join(lines)

        self._cal_detail.configure(fg=self.text)
        self.typewrite(self._cal_detail, text, delay=7)

    # ---------------------------------------------------------
    # Analytics: animated charts
    # ---------------------------------------------------------

    def animate_bars(self, chart, bars, values, horizontal=False,
                     steps=30, delay=22, start_delay=700):
        """Bars grow from zero (and their value labels appear at the end)."""

        axis = chart.figure.axes[0]
        texts = list(axis.texts)
        widget = chart.get_tk_widget()

        def apply(amount):
            for bar, value in zip(bars, values):
                if horizontal:
                    bar.set_width(value * amount)
                else:
                    bar.set_height(value * amount)

        for text in texts:
            text.set_visible(False)

        apply(0)
        chart.draw()

        def step(index):
            try:
                if not widget.winfo_exists():
                    return

                apply(_ease_out(index / steps))

                if index >= steps:
                    for text in texts:
                        text.set_visible(True)

                chart.draw_idle()

            except tk.TclError:
                return

            if index < steps:
                widget.after(delay, lambda: step(index + 1))

        widget.after(start_delay, lambda: step(1))

    def animate_pie(self, chart, pie_result, steps=30, delay=22,
                    start_delay=700):
        """Pie chart grows outward from the centre."""

        wedges = list(pie_result[0])
        extras = list(pie_result[1]) + (
            list(pie_result[2]) if len(pie_result) > 2 else []
        )
        widget = chart.get_tk_widget()

        for text in extras:
            text.set_visible(False)

        for wedge in wedges:
            wedge.set_radius(0.001)

        chart.draw()

        def step(index):
            try:
                if not widget.winfo_exists():
                    return

                radius = max(0.001, _ease_out(index / steps))

                for wedge in wedges:
                    wedge.set_radius(radius)

                if index >= steps:
                    for text in extras:
                        text.set_visible(True)

                chart.draw_idle()

            except tk.TclError:
                return

            if index < steps:
                widget.after(delay, lambda: step(index + 1))

        widget.after(start_delay, lambda: step(1))

    # ---------------------------------------------------------
    # Profile
    # ---------------------------------------------------------

    def create_profile_banner(self):
        profile = self.data["profile"]

        card = self.card()
        card.pack(fill="x", pady=(0, 18))

        row = tk.Frame(card, bg=self.card_bg)
        row.pack(fill="x")

        name = profile.get("name") or "Student"

        AvatarRing(
            row, self, name, size=104,
            photo=profile.get("photo"),
            on_click=self.choose_profile_photo
        ).pack(side="left", padx=(0, 24))

        info = tk.Frame(row, bg=self.card_bg)
        info.pack(side="left", fill="x", expand=True)

        name_label = tk.Label(
            info,
            text="",
            bg=self.card_bg,
            fg=self.text,
            font=("Georgia", 18, "bold"),
            anchor="w"
        )
        name_label.pack(fill="x")

        self.typewrite(name_label, name, delay=38)

        details = " • ".join(
            part for part in (
                profile.get("level"),
                profile.get("course"),
                profile.get("college")
            )
            if part
        )

        tk.Label(
            info,
            text=details or "Add your education level and course below.",
            bg=self.card_bg,
            fg=self.muted,
            font=("Segoe UI", 10),
            anchor="w"
        ).pack(fill="x", pady=(4, 0))

        stats = tk.Frame(row, bg=self.card_bg)
        stats.pack(side="right")

        sessions = self.data["study_sessions"]
        total_minutes = sum(item.get("minutes", 0) for item in sessions)
        done = sum(1 for task in self.data["tasks"] if task.get("completed"))

        for value, caption, color in (
            (total_minutes, "minutes studied", self.accent),
            (len(sessions), "focus sessions", self.accent2),
            (done, "tasks done", self.green),
        ):
            box = tk.Frame(stats, bg=self.card_bg)
            box.pack(side="left", padx=14)

            number = tk.Label(
                box, text="0", bg=self.card_bg, fg=color,
                font=("Segoe UI", 20, "bold")
            )
            number.pack()

            tk.Label(
                box, text=caption, bg=self.card_bg, fg=self.muted,
                font=("Segoe UI", 8)
            ).pack()

            self.animate_count(number, value, steps=30)

    def flash_entries(self, entries, color=None):
        color = color or self.green

        for entry in entries:
            try:
                entry.configure(
                    highlightbackground=color, highlightcolor=color
                )
                entry.after(
                    900,
                    lambda e=entry: e.configure(
                        highlightbackground=self.card_border,
                        highlightcolor=self.accent
                    )
                )
            except tk.TclError:
                pass