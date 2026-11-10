"""
auth_screen.py  -  StudyMate sign-in screen (Tkinter)
=====================================================

Put this file in the SAME folder as main.py (replace the old one).

Sign-in options
  * Email + password (sign in / create account / forgot password)
  * Google and Discord (opens your browser)
  * Mobile number with an SMS one-time code

Look and feel
  * slowly drifting aurora glow + faint floating dust
  * a calm glass card that rises into place
  * sliding tab underline, soft focus glow, hover fades
  * no pop-up boxes: messages appear quietly inside the card
"""

import math
import queue
import random
import threading
import tkinter as tk

from supabase_config import (
    register_user,
    login_user,
    send_password_reset,
    sign_in_with_provider,
    normalize_phone,
    send_phone_otp,
    verify_phone_otp,
)

try:
    import numpy as np
    from PIL import Image, ImageTk
    HAS_IMAGING = True
except Exception:                       # the screen still works, just flatter
    HAS_IMAGING = False


# =============================================================
# PALETTE
# =============================================================

BG_TOP = "#06141F"
BG_BOTTOM = "#0C3340"
CARD = "#0F2A33"
CARD_RIM = "#2C6471"
INPUT = "#143743"
INPUT_RIM = "#255563"
TEXT = "#EAFBFA"
MUTED = "#8FBBC2"
ACCENT = "#5EEAD4"
ACCENT_HOVER = "#8FF3E3"
ACCENT_TEXT = "#03211D"
SOFT = "#1B4655"
ERROR = "#FDA4AF"
WARM = "#FDE68A"

SERIF = "Georgia"
SANS = "Segoe UI"

CARD_OUTER_W = 452          # rounded shape
CARD_INNER_W = 436          # real frame, inset so its corners stay hidden


# =============================================================
# SMALL HELPERS
# =============================================================

def _rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def _hex(rgb):
    return "#%02X%02X%02X" % tuple(max(0, min(255, int(c))) for c in rgb)


def mix(first, second, amount):
    a, b = _rgb(first), _rgb(second)
    return _hex(tuple(a[i] + (b[i] - a[i]) * amount for i in range(3)))


def ease_out(t):
    return 1 - (1 - t) ** 3


def ease_in_out(t):
    return 3 * t * t - 2 * t * t * t


def rounded_points(x1, y1, x2, y2, r):
    return [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]


def friendly_error(error):
    """Turns raw library errors into calm, readable sentences."""

    text = str(error)
    low = text.lower()

    if low == "cancelled":
        return ""

    if isinstance(error, RuntimeError):
        return text

    if "invalid login credentials" in low:
        return "That email or password doesn't look right."
    if "email not confirmed" in low:
        return "Please verify your email first - check your inbox."
    if "already registered" in low or "already exists" in low:
        return "An account with this email already exists. Try signing in."
    if "password should be" in low or "weak password" in low:
        return "Please choose a stronger password (at least 6 characters)."
    if "rate limit" in low or "too many" in low or "after" in low and "seconds" in low:
        return "Too many attempts - please wait a moment and try again."
    if "unsupported provider" in low or "provider is not enabled" in low:
        return ("This sign-in method isn't switched on in Supabase yet. "
                "Enable the provider in the dashboard.")
    if "phone" in low and ("unsupported" in low or "provider" in low):
        return ("Mobile sign-in needs an SMS provider enabled in "
                "Supabase (Authentication > Providers > Phone).")
    if "token has expired" in low or "otp_expired" in low:
        return "That code has expired. Please request a new one."
    if "invalid" in low and ("token" in low or "otp" in low):
        return "That code isn't correct. Please check and try again."
    if "getaddrinfo" in low or "connecterror" in low or "timed out" in low \
            or "network" in low or "connection" in low:
        return "Can't reach the server. Please check your internet connection."
    return text if len(text) < 140 else text[:137] + "..."


# =============================================================
# FADING COLOURS (hover / focus)
# =============================================================

class Fader:
    """Smoothly changes one colour option of a widget."""

    def __init__(self):
        self.jobs = {}

    def fade(self, widget, option, target, steps=8, delay=16):
        key = (str(widget), option)

        job = self.jobs.pop(key, None)
        if job is not None:
            try:
                widget.after_cancel(job)
            except Exception:
                pass

        try:
            start_rgb = _rgb(self._to_hex(widget, widget.cget(option)))
        except Exception:
            return

        target_rgb = _rgb(target)

        def step(index):
            try:
                if not widget.winfo_exists():
                    return

                t = ease_out(index / steps)
                color = _hex(tuple(
                    start_rgb[i] + (target_rgb[i] - start_rgb[i]) * t
                    for i in range(3)
                ))
                widget.configure(**{option: color})

            except tk.TclError:
                return

            if index < steps:
                self.jobs[key] = widget.after(delay, lambda: step(index + 1))
            else:
                self.jobs.pop(key, None)

        step(1)

    @staticmethod
    def _to_hex(widget, color):
        if color.startswith("#") and len(color) == 7:
            return color
        r, g, b = widget.winfo_rgb(color)
        return "#%02X%02X%02X" % (r // 256, g // 256, b // 256)


FADER = Fader()


# =============================================================
# CUSTOM WIDGETS
# =============================================================

class SoftButton(tk.Label):
    """Primary / secondary button with a gentle hover fade."""

    def __init__(self, master, text, command, primary=True, **kwargs):
        self.primary = primary
        self.command = command
        self.enabled = True

        self.normal = ACCENT if primary else SOFT
        self.hover = ACCENT_HOVER if primary else mix(SOFT, ACCENT, 0.25)

        super().__init__(
            master,
            text=text,
            bg=self.normal,
            fg=ACCENT_TEXT if primary else TEXT,
            font=(SANS, 10, "bold"),
            cursor="hand2",
            pady=11,
            **kwargs
        )

        self.label_text = text

        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<Button-1>", self._press)
        self.bind("<ButtonRelease-1>", self._release)

    def _enter(self, event=None):
        if self.enabled:
            FADER.fade(self, "bg", self.hover)

    def _leave(self, event=None):
        if self.enabled:
            FADER.fade(self, "bg", self.normal)

    def _press(self, event=None):
        if self.enabled:
            self.configure(bg=mix(self.normal, "#000000", 0.12))

    def _release(self, event=None):
        if not self.enabled:
            return

        self.configure(bg=self.hover)

        try:
            inside = (
                0 <= event.x <= self.winfo_width()
                and 0 <= event.y <= self.winfo_height()
            )
        except Exception:
            inside = False

        if inside and self.command:
            self.command()

    def set_busy(self, busy, busy_text=None):
        self.enabled = not busy

        if busy:
            self.configure(
                text=busy_text or "Please wait...",
                bg=mix(self.normal, BG_TOP, 0.45),
                cursor="watch"
            )
        else:
            self.configure(
                text=self.label_text,
                bg=self.normal,
                cursor="hand2"
            )


class SocialButton(tk.Frame):
    """Icon + name button used for Google / Discord / Phone."""

    NORMAL = INPUT
    HOVER = "#1D4C5C"

    def __init__(self, master, kind, text, command):
        super().__init__(
            master,
            bg=self.NORMAL,
            highlightthickness=1,
            highlightbackground=INPUT_RIM,
            highlightcolor=INPUT_RIM,
            cursor="hand2"
        )

        self.command = command
        self.enabled = True

        self.icon = tk.Canvas(
            self, width=24, height=24, bg=self.NORMAL,
            highlightthickness=0, bd=0, cursor="hand2"
        )
        self.icon.pack(side="left", padx=(12, 6), pady=10)

        self._draw_icon(kind)

        self.caption = tk.Label(
            self, text=text, bg=self.NORMAL, fg=TEXT,
            font=(SANS, 9, "bold"), cursor="hand2"
        )
        self.caption.pack(side="left", padx=(0, 12))

        for widget in (self, self.icon, self.caption):
            widget.bind("<Enter>", self._enter)
            widget.bind("<Leave>", self._leave)
            widget.bind("<Button-1>", self._click)

    def _draw_icon(self, kind):
        c = self.icon

        if kind == "google":
            box = (3, 3, 21, 21)
            for start, extent, color in (
                (42, 92, "#EA4335"),
                (134, 80, "#FBBC05"),
                (214, 100, "#34A853"),
                (314, 46, "#4285F4"),
            ):
                c.create_arc(
                    *box, start=start, extent=extent,
                    style="arc", outline=color, width=3
                )
            c.create_line(12, 12, 21, 12, fill="#4285F4", width=3)

        elif kind == "discord":
            blurple = "#5865F2"
            c.create_polygon(3, 8, 6, 4, 10, 6, 14, 6, 18, 4, 21, 8,
                             22, 16, 17, 20, 15, 18, 9, 18, 7, 20, 2, 16,
                             fill=blurple, outline=blurple, smooth=False)
            c.create_oval(7, 10, 11, 15, fill="white", outline="")
            c.create_oval(13, 10, 17, 15, fill="white", outline="")

        elif kind == "phone":
            c.create_rectangle(7, 2, 17, 22, outline=ACCENT, width=2)
            c.create_line(10, 5, 14, 5, fill=ACCENT, width=2)
            c.create_oval(11, 17, 13, 19, fill=ACCENT, outline="")

    def _paint(self, color):
        FADER.fade(self, "bg", color)
        for child in (self.icon, self.caption):
            FADER.fade(child, "bg", color)

    def _enter(self, event=None):
        if self.enabled:
            self._paint(self.HOVER)
            self.configure(highlightbackground=ACCENT)

    def _leave(self, event=None):
        if self.enabled:
            self._paint(self.NORMAL)
            self.configure(highlightbackground=INPUT_RIM)

    def _click(self, event=None):
        if self.enabled and self.command:
            self.command()

    def set_enabled(self, enabled):
        self.enabled = enabled

        fg = TEXT if enabled else MUTED
        self.caption.configure(fg=fg)

        for widget in (self, self.icon, self.caption):
            widget.configure(cursor="hand2" if enabled else "arrow")


class SoftEntry(tk.Frame):
    """Entry with a thin rim that glows mint when focused."""

    def __init__(self, master, secret=False, justify="left", font=None,
                 width=None):
        super().__init__(master, bg=INPUT_RIM, padx=1, pady=1)

        self.secret = secret
        self.showing = False

        inner = tk.Frame(self, bg=INPUT)
        inner.pack(fill="both", expand=True)

        self.entry = tk.Entry(
            inner,
            bg=INPUT,
            fg=TEXT,
            insertbackground=ACCENT,
            relief="flat",
            bd=0,
            highlightthickness=0,
            font=font or (SANS, 11),
            justify=justify,
            show="\u2022" if secret else "",
            width=width or 20
        )
        self.entry.pack(
            side="left", fill="x", expand=True, padx=12, ipady=9
        )

        if secret:
            self.toggle = tk.Label(
                inner, text="Show", bg=INPUT, fg=MUTED,
                font=(SANS, 8, "bold"), cursor="hand2"
            )
            self.toggle.pack(side="right", padx=(0, 12))
            self.toggle.bind("<Button-1>", self._toggle_secret)
            self.toggle.bind(
                "<Enter>", lambda e: self.toggle.configure(fg=ACCENT)
            )
            self.toggle.bind(
                "<Leave>", lambda e: self.toggle.configure(fg=MUTED)
            )

        self.entry.bind("<FocusIn>", lambda e: FADER.fade(self, "bg", ACCENT))
        self.entry.bind(
            "<FocusOut>", lambda e: FADER.fade(self, "bg", INPUT_RIM)
        )

    def _toggle_secret(self, event=None):
        self.showing = not self.showing
        self.entry.configure(show="" if self.showing else "\u2022")
        self.toggle.configure(text="Hide" if self.showing else "Show")

    def get(self):
        return self.entry.get()

    def set(self, text):
        self.entry.delete(0, "end")
        self.entry.insert(0, text)

    def focus(self):
        self.entry.focus_set()

    def bind_return(self, callback):
        self.entry.bind("<Return>", lambda e: callback())


class LogoMark(tk.Canvas):
    """Small rotating-ring emblem above the title."""

    def __init__(self, master, size=62):
        super().__init__(
            master, width=size, height=size, bg=CARD,
            highlightthickness=0, bd=0
        )

        self.size = size
        self.angle = 0
        self.phase = 0.0

        pad = 5
        box = (pad, pad, size - pad, size - pad)

        self.create_oval(*box, outline=SOFT, width=3)

        self.arc_a = self.create_arc(
            *box, start=0, extent=100, style="arc",
            outline=ACCENT, width=3
        )
        self.arc_b = self.create_arc(
            *box, start=180, extent=60, style="arc",
            outline="#93C5FD", width=3
        )

        self.create_text(
            size / 2, size / 2 - 1, text="S", fill=TEXT,
            font=(SERIF, int(size / 2.6), "bold")
        )

        self._tick()

    def _tick(self):
        try:
            if not self.winfo_exists():
                return

            self.angle = (self.angle + 2.2) % 360
            self.phase += 0.05
            wobble = 22 * math.sin(self.phase)

            self.itemconfigure(
                self.arc_a, start=self.angle, extent=100 + wobble
            )
            self.itemconfigure(
                self.arc_b, start=180 - self.angle * 0.7, extent=60 - wobble
            )

        except tk.TclError:
            return

        self.after(40, self._tick)


# =============================================================
# THE SCREEN
# =============================================================

class AuthScreen:

    def __init__(self, root, on_login):
        self.root = root
        self.on_login = on_login

        self._alive = True
        self._busy = False
        self._results = queue.Queue()
        self._cancel_event = None
        self._view = None
        self._phone = None
        self._resend_left = 0
        self._resend_job = None
        self._dots_job = None
        self._status_job = None
        self._anim_job = None
        self._resize_job = None
        self._intro_done = False
        self._tab_x = None

        self._bg_image = None
        self._bg_size = (0, 0)
        self._orb_images = []
        self._orbs = []
        self._dust = []
        self._tick_count = 0

        root.title("StudyMate - Sign in")
        root.configure(bg=BG_TOP)
        root.minsize(940, 700)

        width, height = 1040, 740
        x = max(0, (root.winfo_screenwidth() - width) // 2)
        y = max(0, (root.winfo_screenheight() - height) // 2 - 20)
        root.geometry(f"{width}x{height}+{x}+{y}")

        self.canvas = tk.Canvas(
            root, bg=BG_TOP, highlightthickness=0, bd=0
        )
        self.canvas.pack(fill="both", expand=True)

        self.canvas.bind("<Destroy>", self._on_destroy)
        self.canvas.bind("<Configure>", self._on_resize)

        self._build_background()
        self._build_card()

        self._footer = self.canvas.create_text(
            0, 0, text="Your learning, kept safe and in sync.",
            fill=mix(MUTED, BG_TOP, 0.35), font=(SANS, 9)
        )

        self._show_view("signin", animate=False)

        self.root.after(60, self._layout)
        self.root.after(120, self._play_intro)
        self.root.after(60, self._pump)
        self._animate_background()

    # ---------------------------------------------------------
    # lifecycle
    # ---------------------------------------------------------

    def _on_destroy(self, event):
        if event.widget is self.canvas:
            self._alive = False

            if self._cancel_event is not None:
                self._cancel_event.set()

    def _ok(self):
        if not self._alive:
            return False
        try:
            return bool(self.canvas.winfo_exists())
        except tk.TclError:
            return False

    # ---------------------------------------------------------
    # background: gradient, drifting glow, dust
    # ---------------------------------------------------------

    def _build_background(self):
        self._bg_item = self.canvas.create_image(0, 0, anchor="nw")

        if HAS_IMAGING:
            glow_specs = (
                # colour, size, strength, centre x, centre y, drift x, drift y, speed
                ("#1FB5A5", 560, 0.55, 0.16, 0.22, 0.07, 0.06, 0.55),
                ("#2D6BE0", 620, 0.42, 0.86, 0.30, 0.06, 0.08, 0.42),
                ("#5EEAD4", 480, 0.32, 0.70, 0.88, 0.08, 0.05, 0.62),
                ("#7C5CE0", 520, 0.28, 0.12, 0.86, 0.06, 0.07, 0.48),
                ("#0E8FA3", 420, 0.40, 0.50, 0.08, 0.09, 0.04, 0.70),
            )

            for color, size, strength, cx, cy, dx, dy, speed in glow_specs:
                image = self._make_orb(size, color, strength)
                photo = ImageTk.PhotoImage(image)
                self._orb_images.append(photo)

                item = self.canvas.create_image(0, 0, image=photo)

                self._orbs.append({
                    "item": item, "cx": cx, "cy": cy, "dx": dx, "dy": dy,
                    "speed": speed, "phase": random.uniform(0, 6.28),
                })

        rng = random.Random(7)

        for _ in range(34):
            size = rng.choice((1, 1, 2, 2, 3))
            item = self.canvas.create_oval(
                0, 0, size, size, fill=MUTED, outline=""
            )
            self._dust.append({
                "item": item,
                "x": rng.random(),
                "y": rng.random(),
                "size": size,
                "rise": rng.uniform(0.004, 0.012),
                "sway": rng.uniform(0.002, 0.008),
                "phase": rng.uniform(0, 6.28),
                "twinkle": rng.uniform(0.02, 0.06),
            })

    @staticmethod
    def _make_orb(size, color, strength):
        axis = np.linspace(-1, 1, size)
        xx, yy = np.meshgrid(axis, axis)
        distance = np.sqrt(xx ** 2 + yy ** 2)

        alpha = np.clip(1 - distance, 0, 1) ** 2.4 * strength

        r, g, b = _rgb(color)
        array = np.zeros((size, size, 4), dtype=np.uint8)
        array[..., 0] = r
        array[..., 1] = g
        array[..., 2] = b
        array[..., 3] = (alpha * 255).astype(np.uint8)

        return Image.fromarray(array, "RGBA")

    def _render_gradient(self, width, height):
        if not HAS_IMAGING or width < 2 or height < 2:
            return

        y, x = np.mgrid[0:height, 0:width]

        t = (x / max(width - 1, 1)) * 0.35 + (y / max(height - 1, 1)) * 0.65
        t = t[..., None]

        top = np.array(_rgb(BG_TOP), dtype=float)
        bottom = np.array(_rgb(BG_BOTTOM), dtype=float)

        array = top * (1 - t) + bottom * t

        # soft vignette keeps the eye on the card
        dx = (x - width / 2) / (width / 2)
        dy = (y - height / 2) / (height / 2)
        vignette = 1 - 0.28 * np.clip(np.sqrt(dx ** 2 + dy ** 2) - 0.55, 0, 1)

        array = array * vignette[..., None]

        image = Image.fromarray(array.astype(np.uint8), "RGB")

        self._bg_image = ImageTk.PhotoImage(image)
        self._bg_size = (width, height)

        self.canvas.itemconfigure(self._bg_item, image=self._bg_image)
        self.canvas.tag_lower(self._bg_item)

    def _animate_background(self):
        if not self._ok():
            return

        try:
            width = max(self.canvas.winfo_width(), 2)
            height = max(self.canvas.winfo_height(), 2)

            self._tick_count += 1
            clock = self._tick_count * 0.033

            for orb in self._orbs:
                angle = clock * orb["speed"] + orb["phase"]
                x = (orb["cx"] + orb["dx"] * math.sin(angle)) * width
                y = (orb["cy"] + orb["dy"] * math.cos(angle * 0.8)) * height
                self.canvas.coords(orb["item"], x, y)

            for mote in self._dust:
                mote["y"] -= mote["rise"] * 0.033 * 6
                mote["phase"] += mote["twinkle"]

                if mote["y"] < -0.02:
                    mote["y"] = 1.02
                    mote["x"] = random.random()

                x = (mote["x"] + mote["sway"] * math.sin(mote["phase"])) * width
                y = mote["y"] * height
                size = mote["size"]

                self.canvas.coords(
                    mote["item"], x, y, x + size, y + size
                )

                glow = 0.35 + 0.35 * (0.5 + 0.5 * math.sin(mote["phase"] * 2))
                self.canvas.itemconfigure(
                    mote["item"], fill=mix(BG_BOTTOM, "#CFFAF3", glow)
                )

        except tk.TclError:
            return

        self._anim_job = self.root.after(40, self._animate_background)

    def _on_resize(self, event):
        if self._resize_job is not None:
            try:
                self.root.after_cancel(self._resize_job)
            except Exception:
                pass

        self._layout()
        self._resize_job = self.root.after(140, self._refresh_gradient)

    def _refresh_gradient(self):
        self._resize_job = None

        if not self._ok():
            return

        size = (self.canvas.winfo_width(), self.canvas.winfo_height())

        if size != self._bg_size:
            self._render_gradient(*size)

    # ---------------------------------------------------------
    # the glass card
    # ---------------------------------------------------------

    def _build_card(self):
        self._shadow_items = []

        for _ in range(3):
            self._shadow_items.append(
                self.canvas.create_polygon(
                    [0, 0, 1, 1, 2, 2], smooth=True, outline="", fill=BG_TOP
                )
            )

        self._card_shape = self.canvas.create_polygon(
            [0, 0, 1, 1, 2, 2], smooth=True,
            fill=CARD, outline=CARD_RIM, width=1
        )

        self.card = tk.Frame(self.canvas, bg=CARD, width=CARD_INNER_W)
        self._card_window = self.canvas.create_window(
            0, 0, window=self.card, anchor="center", width=CARD_INNER_W
        )

        # Header that stays on every view
        self.header = tk.Frame(self.card, bg=CARD)
        self.header.pack(fill="x", pady=(30, 0))

        self.logo = LogoMark(self.header)
        self.logo.pack()

        self.title = tk.Label(
            self.header, text="StudyMate", bg=CARD, fg=CARD,
            font=(SERIF, 25, "bold")
        )
        self.title.pack(pady=(8, 0))

        self.tagline = tk.Label(
            self.header, text="Study calmly. Grow steadily.",
            bg=CARD, fg=CARD, font=(SERIF, 10, "italic")
        )
        self.tagline.pack(pady=(2, 0))

        self.body = tk.Frame(self.card, bg=CARD)
        self.body.pack(fill="x", padx=36, pady=(18, 30))

        self._dy = 0
        self._dx = 0
        self._inner_h = None

    def _card_height(self, remeasure=True):
        if remeasure or self._inner_h is None:
            self.card.update_idletasks()
            self._inner_h = self.card.winfo_reqheight()

        return self._inner_h

    def _layout(self):
        if not self._ok():
            return

        width = max(self.canvas.winfo_width(), 2)
        height = max(self.canvas.winfo_height(), 2)

        self._place_card(width, height, remeasure=False)

        self.canvas.coords(self._footer, width / 2, height - 22)

    def _place_card(self, width=None, height=None, remeasure=True):
        if not self._ok():
            return

        if width is None:
            width = max(self.canvas.winfo_width(), 2)
            height = max(self.canvas.winfo_height(), 2)

        inner_h = self._card_height(remeasure)
        outer_h = inner_h + 16

        cx = width / 2 + self._dx
        cy = height / 2 - 8 + self._dy

        x1 = cx - CARD_OUTER_W / 2
        x2 = cx + CARD_OUTER_W / 2
        y1 = cy - outer_h / 2
        y2 = cy + outer_h / 2

        for index, item in enumerate(self._shadow_items):
            grow = (3 - index) * 7
            drop = 10 + (3 - index) * 3
            tone = mix(BG_TOP, "#000000", 0.10 + index * 0.08)

            self.canvas.coords(
                item,
                *rounded_points(
                    x1 - grow, y1 - grow + drop,
                    x2 + grow, y2 + grow + drop, 34
                )
            )
            self.canvas.itemconfigure(item, fill=tone)

        self.canvas.coords(
            self._card_shape, *rounded_points(x1, y1, x2, y2, 26)
        )

        self.canvas.coords(self._card_window, cx, cy)
        self.canvas.itemconfigure(self._card_window, height=inner_h)

    # ---------------------------------------------------------
    # animations: intro, view change, shake
    # ---------------------------------------------------------

    def _animate_card(self, start_dy, steps, on_done=None, shake=False):
        if not self._ok():
            return

        if self._anim_card_job is not None:
            try:
                self.root.after_cancel(self._anim_card_job)
            except Exception:
                pass

        def step(index):
            if not self._ok():
                return

            t = index / steps

            if shake:
                self._dx = 9 * math.sin(t * math.pi * 5) * (1 - t)
                self._dy = 0
            else:
                self._dy = start_dy * (1 - ease_out(t))
                self._dx = 0

            self._place_card(remeasure=False)

            if index < steps:
                self._anim_card_job = self.root.after(
                    16, lambda: step(index + 1)
                )
            else:
                self._anim_card_job = None
                self._dx = 0
                self._dy = 0
                self._place_card(remeasure=False)

                if on_done:
                    on_done()

        step(1)

    _anim_card_job = None

    def _play_intro(self):
        if not self._ok():
            return

        self._animate_card(44, 30)
        self._fade_text(self.title, ACCENT, CARD, steps=22)
        self._fade_text(self.tagline, MUTED, CARD, steps=28)
        self._intro_done = True

    def _fade_text(self, label, final, start, steps=16):
        def step(index):
            try:
                if not label.winfo_exists():
                    return

                t = ease_out(index / steps)
                label.configure(fg=mix(start, final, t))

            except tk.TclError:
                return

            if index < steps:
                label.after(24, lambda: step(index + 1))

        step(0)

    def _shake(self):
        self._animate_card(0, 22, shake=True)

    # ---------------------------------------------------------
    # thread -> UI plumbing
    # ---------------------------------------------------------

    def _pump(self):
        if not self._ok():
            return

        try:
            while True:
                callback, args = self._results.get_nowait()
                try:
                    callback(*args)
                except tk.TclError:
                    pass
        except queue.Empty:
            pass

        self.root.after(60, self._pump)

    def _run_in_background(self, work, done):
        """work() runs in a thread; done(result, error) runs on the UI."""

        def runner():
            try:
                outcome = (work(), None)
            except Exception as error:
                outcome = (None, error)

            self._results.put((done, outcome))

        threading.Thread(target=runner, daemon=True).start()

    # ---------------------------------------------------------
    # small building blocks used by the views
    # ---------------------------------------------------------

    def _clear_body(self):
        for job_name in ("_resend_job", "_dots_job", "_status_job"):
            job = getattr(self, job_name)
            if job is not None:
                try:
                    self.root.after_cancel(job)
                except Exception:
                    pass
                setattr(self, job_name, None)

        for child in self.body.winfo_children():
            child.destroy()

        self.status = None

    def _field_label(self, text):
        tk.Label(
            self.body, text=text.upper(), bg=CARD, fg=MUTED,
            font=(SANS, 8, "bold")
        ).pack(anchor="w", pady=(12, 5))

    def _heading(self, text, sub):
        tk.Label(
            self.body, text=text, bg=CARD, fg=TEXT,
            font=(SERIF, 15, "bold")
        ).pack(anchor="w", pady=(2, 0))

        tk.Label(
            self.body, text=sub, bg=CARD, fg=MUTED,
            font=(SANS, 9), wraplength=360, justify="left"
        ).pack(anchor="w", pady=(2, 4))

    def _link(self, parent, text, command, size=9):
        label = tk.Label(
            parent, text=text, bg=CARD, fg=MUTED,
            font=(SANS, size), cursor="hand2"
        )
        label.bind("<Button-1>", lambda e: command())
        label.bind("<Enter>", lambda e: label.configure(fg=ACCENT))
        label.bind("<Leave>", lambda e: label.configure(fg=MUTED))
        return label

    def _make_status(self):
        self.status = tk.Label(
            self.body, text="", bg=CARD, fg=MUTED,
            font=(SANS, 9), wraplength=360, justify="left", anchor="w"
        )
        self.status.pack(fill="x", pady=(10, 0))

    def _set_status(self, text, kind="error"):
        if self.status is None:
            return

        try:
            if not self.status.winfo_exists():
                return
        except tk.TclError:
            return

        color = {"error": ERROR, "info": ACCENT, "warn": WARM}.get(kind, MUTED)

        self.status.configure(text=text, fg=CARD)
        self._fade_text(self.status, color, CARD, steps=14)

        self.root.after(30, self._place_card)

    def _divider(self, text):
        row = tk.Frame(self.body, bg=CARD)
        row.pack(fill="x", pady=(18, 12))

        tk.Frame(row, bg=SOFT, height=1).pack(
            side="left", fill="x", expand=True, pady=1
        )
        tk.Label(
            row, text=text, bg=CARD, fg=MUTED, font=(SANS, 8)
        ).pack(side="left", padx=10)
        tk.Frame(row, bg=SOFT, height=1).pack(
            side="left", fill="x", expand=True, pady=1
        )

    def _social_row(self):
        row = tk.Frame(self.body, bg=CARD)
        row.pack(fill="x")

        for column in range(3):
            row.grid_columnconfigure(column, weight=1, uniform="social")

        self.social_buttons = [
            SocialButton(
                row, "google", "Google",
                lambda: self._start_provider("google")
            ),
            SocialButton(
                row, "discord", "Discord",
                lambda: self._start_provider("discord")
            ),
            SocialButton(
                row, "phone", "Mobile",
                lambda: self._show_view("phone")
            ),
        ]

        for column, button in enumerate(self.social_buttons):
            button.grid(
                row=0, column=column, sticky="ew",
                padx=(0 if column == 0 else 5, 0 if column == 2 else 5)
            )

    def _tabs(self, active):
        wrap = tk.Frame(self.body, bg=CARD)
        wrap.pack(fill="x", pady=(0, 6))

        row = tk.Frame(wrap, bg=CARD)
        row.pack(fill="x")

        tabs = {}

        for column, (key, text) in enumerate(
            (("signin", "Sign in"), ("signup", "Create account"))
        ):
            row.grid_columnconfigure(column, weight=1, uniform="tabs")

            label = tk.Label(
                row, text=text, bg=CARD,
                fg=ACCENT if key == active else MUTED,
                font=(SANS, 10, "bold"), cursor="hand2", pady=8
            )
            label.grid(row=0, column=column, sticky="ew")

            if key != active:
                label.bind(
                    "<Button-1>", lambda e, k=key: self._show_view(k)
                )
                label.bind(
                    "<Enter>", lambda e, w=label: w.configure(fg=TEXT)
                )
                label.bind(
                    "<Leave>", lambda e, w=label: w.configure(fg=MUTED)
                )

            tabs[key] = label

        track = tk.Canvas(
            wrap, height=3, bg=CARD, highlightthickness=0, bd=0
        )
        track.pack(fill="x")

        track.create_rectangle(0, 1, 2000, 2, fill=SOFT, outline="")
        bar = track.create_rectangle(0, 0, 0, 3, fill=ACCENT, outline="")

        half = (CARD_INNER_W - 72) / 2

        def target_for(key):
            return (0, half) if key == "signin" else (half, half * 2)

        if self._tab_x is not None:
            track.coords(bar, self._tab_x[0], 0, self._tab_x[1], 3)

        def place(animate):
            if not self._ok():
                return

            try:
                x1, x2 = target_for(active)

                if not animate or self._tab_x is None:
                    track.coords(bar, x1, 0, x2, 3)
                    self._tab_x = (x1, x2)
                    return

                start1, start2 = self._tab_x
                steps = 14

                def step(index):
                    if not self._ok():
                        return

                    try:
                        t = ease_in_out(index / steps)
                        track.coords(
                            bar,
                            start1 + (x1 - start1) * t, 0,
                            start2 + (x2 - start2) * t, 3
                        )
                    except tk.TclError:
                        return

                    if index < steps:
                        track.after(14, lambda: step(index + 1))
                    else:
                        self._tab_x = (x1, x2)

                step(1)

            except tk.TclError:
                return

        self.root.after(10, lambda: place(True))

    def _password_strength(self, entry):
        bar = tk.Canvas(
            self.body, height=4, bg=CARD, highlightthickness=0, bd=0
        )
        bar.pack(fill="x", pady=(6, 0))

        track = bar.create_rectangle(0, 0, 2000, 4, fill=SOFT, outline="")
        fill = bar.create_rectangle(0, 0, 0, 4, fill=ERROR, outline="")

        state = {"now": 0.0, "goal": 0.0}

        def score(password):
            points = 0
            points += 1 if len(password) >= 6 else 0
            points += 1 if len(password) >= 10 else 0
            points += 1 if any(c.isdigit() for c in password) and any(
                c.isalpha() for c in password
            ) else 0
            points += 1 if any(
                not c.isalnum() for c in password
            ) or (any(c.isupper() for c in password)
                  and any(c.islower() for c in password)) else 0
            return points / 4

        def tick():
            try:
                if not bar.winfo_exists():
                    return

                state["now"] += (state["goal"] - state["now"]) * 0.25
                width = max(bar.winfo_width(), 2)

                color = (
                    ERROR if state["goal"] < 0.4
                    else WARM if state["goal"] < 0.75
                    else ACCENT
                )

                bar.coords(fill, 0, 0, width * state["now"], 4)
                bar.itemconfigure(fill, fill=color)
                bar.coords(track, 0, 0, width, 4)

                if abs(state["goal"] - state["now"]) > 0.005:
                    bar.after(20, tick)

            except tk.TclError:
                return

        def changed(event=None):
            state["goal"] = score(entry.get())
            tick()

        entry.entry.bind("<KeyRelease>", changed, add="+")

    # ---------------------------------------------------------
    # view switching
    # ---------------------------------------------------------

    def _show_view(self, name, animate=True):
        self._view = name
        self._clear_body()

        builder = {
            "signin": self._build_signin,
            "signup": self._build_signup,
            "phone": self._build_phone,
            "phone_code": self._build_phone_code,
            "waiting": self._build_waiting,
        }[name]

        builder()

        self._place_card()

        if animate:
            self._animate_card(16, 12)

    # ---------------------------------------------------------
    # view: sign in
    # ---------------------------------------------------------

    def _build_signin(self):
        self._tabs("signin")

        self._heading("Welcome back", "Pick up right where you left off.")

        self._field_label("Email")
        self.email = SoftEntry(self.body)
        self.email.pack(fill="x")

        self._field_label("Password")
        self.password = SoftEntry(self.body, secret=True)
        self.password.pack(fill="x")

        row = tk.Frame(self.body, bg=CARD)
        row.pack(fill="x", pady=(8, 12))

        self._link(row, "Forgot password?", self._forgot_password).pack(
            side="right"
        )

        self.primary = SoftButton(self.body, "Sign in", self._do_login)
        self.primary.pack(fill="x")

        self._make_status()

        self._divider("or continue with")
        self._social_row()

        self.email.bind_return(lambda: self.password.focus())
        self.password.bind_return(self._do_login)

        remembered = getattr(self, "_remember_email", "")
        if remembered:
            self.email.set(remembered)
            self.password.focus()
        else:
            self.email.focus()

    def _do_login(self):
        if self._busy:
            return

        email = self.email.get().strip()
        password = self.password.get()

        if not email or not password:
            self._set_status("Please enter your email and password.", "warn")
            self._shake()
            return

        self._remember_email = email
        self._set_busy(True, "Signing in...")

        self._run_in_background(
            lambda: login_user(email, password),
            self._after_credentials
        )

    def _forgot_password(self):
        if self._busy:
            return

        email = self.email.get().strip()

        if not email or "@" not in email:
            self._set_status(
                "Type your email above first, then tap Forgot password.",
                "warn"
            )
            return

        self._set_busy(True, "Sending link...")

        def done(result, error):
            self._set_busy(False)

            if error is not None:
                self._set_status(friendly_error(error))
            else:
                self._set_status(
                    "If an account exists for that email, a reset link is "
                    "on its way.", "info"
                )

        self._run_in_background(lambda: send_password_reset(email), done)

    # ---------------------------------------------------------
    # view: create account
    # ---------------------------------------------------------

    def _build_signup(self):
        self._tabs("signup")

        self._heading(
            "Begin your journey", "A calm place to organise your learning."
        )

        self._field_label("Full name")
        self.name = SoftEntry(self.body)
        self.name.pack(fill="x")

        self._field_label("Email")
        self.email = SoftEntry(self.body)
        self.email.pack(fill="x")

        self._field_label("Password")
        self.password = SoftEntry(self.body, secret=True)
        self.password.pack(fill="x")

        self._password_strength(self.password)

        self.primary = SoftButton(
            self.body, "Create account", self._do_register
        )
        self.primary.pack(fill="x", pady=(14, 0))

        self._make_status()

        self._divider("or sign up with")
        self._social_row()

        self.name.bind_return(lambda: self.email.focus())
        self.email.bind_return(lambda: self.password.focus())
        self.password.bind_return(self._do_register)

        remembered = getattr(self, "_remember_email", "")
        if remembered:
            self.email.set(remembered)

        self.name.focus()

    def _do_register(self):
        if self._busy:
            return

        name = self.name.get().strip()
        email = self.email.get().strip()
        password = self.password.get()

        if not name or not email or not password:
            self._set_status("Please fill in all three fields.", "warn")
            self._shake()
            return

        if "@" not in email or "." not in email.split("@")[-1]:
            self._set_status("That email address doesn't look right.", "warn")
            self._shake()
            return

        if len(password) < 6:
            self._set_status(
                "Your password needs at least 6 characters.", "warn"
            )
            self._shake()
            return

        self._remember_email = email
        self._set_busy(True, "Creating account...")

        def done(result, error):
            self._set_busy(False)

            if error is not None:
                self._set_status(friendly_error(error))
                self._shake()
                return

            user = getattr(result, "user", None)

            # Supabase hides "already registered" by returning no identities
            if user is not None and getattr(user, "identities", None) == []:
                self._set_status(
                    "An account with this email already exists. "
                    "Try signing in."
                )
                self._shake()
                return

            if getattr(result, "session", None) and user:
                self._finish(user)
                return

            self._show_view("signin")
            self._set_status(
                "Account created! Please verify your email, then sign in.",
                "info"
            )

        self._run_in_background(
            lambda: register_user(email, password, name), done
        )

    # ---------------------------------------------------------
    # Google / Discord
    # ---------------------------------------------------------

    def _start_provider(self, provider):
        if self._busy:
            return

        self._busy = True
        self._cancel_event = threading.Event()
        self._provider_name = provider.title()

        self._show_view("waiting")

        cancel_event = self._cancel_event

        def done(result, error):
            self._busy = False

            if cancel_event.is_set():
                return

            if error is not None:
                self._show_view("signin")
                message = friendly_error(error)

                if message:
                    self._set_status(message)
                    self._shake()
                return

            user = getattr(result, "user", None)

            if user:
                self._finish(user)
            else:
                self._show_view("signin")
                self._set_status("Sign-in did not complete. Please try again.")

        self._run_in_background(
            lambda: sign_in_with_provider(provider, cancel_event), done
        )

    def _build_waiting(self):
        provider = getattr(self, "_provider_name", "your account")

        tk.Label(
            self.body, text=f"Continue with {provider}", bg=CARD, fg=TEXT,
            font=(SERIF, 15, "bold")
        ).pack(pady=(14, 4))

        tk.Label(
            self.body,
            text="A browser tab has opened.\n"
                 "Finish signing in there, then come back here.",
            bg=CARD, fg=MUTED, font=(SANS, 10), justify="center"
        ).pack(pady=(0, 18))

        self.dots_canvas = tk.Canvas(
            self.body, width=120, height=26, bg=CARD,
            highlightthickness=0, bd=0
        )
        self.dots_canvas.pack()

        self._dots = [
            self.dots_canvas.create_oval(
                14 + i * 36, 8, 26 + i * 36, 20, fill=SOFT, outline=""
            )
            for i in range(3)
        ]

        self._dots_phase = 0.0
        self._animate_dots()

        cancel = SoftButton(
            self.body, "Cancel", self._cancel_provider, primary=False
        )
        cancel.pack(fill="x", pady=(22, 6))

        self._make_status()
        self._set_status(
            "If the browser shows an error, this sign-in method isn't "
            "switched on in Supabase yet.",
            "info"
        )

    def _animate_dots(self):
        if not self._ok() or self._view != "waiting":
            return

        try:
            self._dots_phase += 0.16

            for index, item in enumerate(self._dots):
                level = 0.5 + 0.5 * math.sin(self._dots_phase - index * 0.9)
                self.dots_canvas.itemconfigure(
                    item, fill=mix(SOFT, ACCENT, level)
                )

        except tk.TclError:
            return

        self._dots_job = self.root.after(40, self._animate_dots)

    def _cancel_provider(self):
        if self._cancel_event is not None:
            self._cancel_event.set()

        self._busy = False
        self._show_view("signin")

    # ---------------------------------------------------------
    # mobile number
    # ---------------------------------------------------------

    def _build_phone(self):
        self._heading(
            "Sign in with your mobile",
            "We'll text you a 6-digit code. New number? We'll create "
            "your account."
        )

        self._field_label("Mobile number")

        row = tk.Frame(self.body, bg=CARD)
        row.pack(fill="x")

        self.country = SoftEntry(row, width=4, justify="center")
        self.country.pack(side="left")
        self.country.set("+91")

        self.number = SoftEntry(row)
        self.number.pack(side="left", fill="x", expand=True, padx=(8, 0))

        self.primary = SoftButton(self.body, "Send code", self._send_code)
        self.primary.pack(fill="x", pady=(18, 0))

        self._make_status()

        back = self._link(
            self.body, "\u2190  Back to email sign in",
            lambda: self._show_view("signin")
        )
        back.pack(pady=(16, 0))

        self.country.bind_return(lambda: self.number.focus())
        self.number.bind_return(self._send_code)
        self.number.focus()

    def _send_code(self):
        if self._busy:
            return

        try:
            phone = normalize_phone(self.country.get(), self.number.get())
        except ValueError as error:
            self._set_status(str(error), "warn")
            self._shake()
            return

        self._set_busy(True, "Sending code...")

        def done(result, error):
            self._set_busy(False)

            if error is not None:
                self._set_status(friendly_error(error))
                self._shake()
                return

            self._phone = phone
            self._show_view("phone_code")

        self._run_in_background(lambda: send_phone_otp(phone), done)

    def _build_phone_code(self):
        self._heading(
            "Enter your code", f"We sent a 6-digit code to {self._phone}."
        )

        self._field_label("Verification code")

        self.code = SoftEntry(
            self.body, justify="center", font=("Consolas", 20, "bold")
        )
        self.code.pack(fill="x")

        self._code_guard = {"busy": False}

        def on_key(event=None):
            raw = self.code.get()
            digits = "".join(c for c in raw if c.isdigit())[:6]

            if digits != raw:
                self.code.set(digits)

            if len(digits) == 6:
                self._verify_code()

        self.code.entry.bind("<KeyRelease>", on_key)
        self.code.bind_return(self._verify_code)

        self.primary = SoftButton(self.body, "Verify", self._verify_code)
        self.primary.pack(fill="x", pady=(16, 0))

        self._make_status()

        links = tk.Frame(self.body, bg=CARD)
        links.pack(fill="x", pady=(14, 0))

        self._link(
            links, "Use a different number",
            lambda: self._show_view("phone")
        ).pack(side="left")

        self.resend = self._link(links, "", self._resend_code)
        self.resend.pack(side="right")

        self._resend_left = 30
        self._tick_resend()

        self.code.focus()

    def _tick_resend(self):
        if not self._ok() or self._view != "phone_code":
            return

        try:
            if self._resend_left > 0:
                self.resend.configure(
                    text=f"Resend code in {self._resend_left}s",
                    cursor="arrow"
                )
                self.resend.unbind("<Button-1>")
                self._resend_left -= 1
                self._resend_job = self.root.after(1000, self._tick_resend)
            else:
                self.resend.configure(text="Resend code", cursor="hand2")
                self.resend.bind("<Button-1>", lambda e: self._resend_code())

        except tk.TclError:
            return

    def _resend_code(self):
        if self._busy or self._resend_left > 0 or not self._phone:
            return

        phone = self._phone
        self._busy = True

        def done(result, error):
            self._busy = False

            if error is not None:
                self._set_status(friendly_error(error))
            else:
                self._set_status("A fresh code is on its way.", "info")
                self._resend_left = 30
                self._tick_resend()

        self._run_in_background(lambda: send_phone_otp(phone), done)

    def _verify_code(self):
        if self._busy:
            return

        code = "".join(c for c in self.code.get() if c.isdigit())

        if len(code) != 6:
            self._set_status("Please enter the 6-digit code.", "warn")
            self._shake()
            return

        phone = self._phone
        self._set_busy(True, "Verifying...")

        def done(result, error):
            self._set_busy(False)

            if error is not None:
                self._set_status(friendly_error(error))
                self._shake()

                try:
                    self.code.set("")
                    self.code.focus()
                except tk.TclError:
                    pass

                return

            user = getattr(result, "user", None)

            if user:
                self._finish(user)
            else:
                self._set_status("Could not verify that code.")

        self._run_in_background(lambda: verify_phone_otp(phone, code), done)

    # ---------------------------------------------------------
    # shared results
    # ---------------------------------------------------------

    def _set_busy(self, busy, text=None):
        self._busy = busy

        button = getattr(self, "primary", None)

        try:
            if button is not None and button.winfo_exists():
                button.set_busy(busy, text)
        except tk.TclError:
            pass

        for social in getattr(self, "social_buttons", []):
            try:
                if social.winfo_exists():
                    social.set_enabled(not busy)
            except tk.TclError:
                pass

    def _after_credentials(self, result, error):
        self._set_busy(False)

        if error is not None:
            self._set_status(friendly_error(error))
            self._shake()
            return

        user = getattr(result, "user", None)

        if user:
            self._finish(user)
        else:
            self._set_status("Could not sign you in. Please try again.")

    def _finish(self, user):
        if not self._ok():
            return

        self._set_status("Welcome! Opening your study space...", "info")

        # let the message be seen for a heartbeat, then hand over
        self.root.after(380, lambda: self.on_login(user))