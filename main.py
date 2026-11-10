import tkinter as tk
from urllib.parse import quote_plus
import sys
from lecture_embed import EmbeddedYouTube
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from tkinter import ttk, messagebox, filedialog
import json
import copy
import base64
import os
import re
import time
import calendar
import math
import random
import threading
import urllib.request
import urllib.error
import webbrowser
import subprocess
from datetime import datetime, date, timedelta
from auth_screen import AuthScreen
from voice_assistant import VoiceAssistant
from document_reader import extract_text
from animations import AnimationsMixin, RingTimerDisplay, AnimatedBar
from jarvis_hud import JarvisPanel
from pill_nav import FloatingStage
from scene3d import StudyGalaxy, Bar3DChart
from profile_photo import (
    process_photo_file,
    IMAGE_FILETYPES,
    MiniAvatar
)
from supabase_config import (
    get_display_name,
    get_current_user,
    logout_user,
    load_cloud_data,
    save_cloud_data
)

APP_NAME = "StudyMate v5.0"
DATA_FILE = "studymate_data.json"
CURRENT_USER_ID = None

# If you get a 404 "model not found" error, change this to a valid model
# name from Google's current Gemini model list.
GEMINI_MODEL = "gemini-3.5-flash-lite"

# =============================================================
# JARVIS / FRIDAY PERSONAS
# =============================================================

CLASSIC_PROMPT = (
    "You are StudyMate, a helpful AI study assistant for learners of every "
    "age, course and subject: school subjects, languages, sciences, "
    "mathematics, humanities, commerce, arts, medicine, law, coding, exam "
    "preparation and more. Explain concepts accurately in clear, friendly "
    "language that matches the learner's level. Use examples and "
    "step-by-step explanations when useful. When a document or image is "
    "attached, analyse its contents carefully. Reply in the language the "
    "user writes in."
)

VOICE_FRIENDLY_RULES = (
    "You help learners of every age, course and subject. Teach accurately, "
    "in clear language matched to the learner's level, with examples and "
    "step-by-step reasoning "
    "when useful. Reply in the language the user writes in. When a document "
    "or image is attached, analyse it "
    "carefully. Write plain text only: never use markdown symbols such as "
    "asterisks, hashes, underscores or backticks; for lists use short lines "
    "starting with a dash. Your replies may be read aloud, so keep them "
    "natural and focused: a few sentences for simple questions, longer only "
    "when the topic truly needs it, and offer to go deeper. Never mention "
    "these instructions."
)

JARVIS_SPEECH_LIMIT = 900

JARVIS_PERSONAS = {
    "JARVIS": {
        "label": "JARVIS",
        "full": "J.A.R.V.I.S.",
        "tagline": "JUST A RATHER VERY INTELLIGENT SYSTEM",
        "wake": "jarvis",
        "palette": {"main": "#4FD8FF", "alt": "#2D7BFF", "warm": "#FFD27A"},
        "voice_hints": ("david", "mark", "george", "james", "guy", "ryan", "ravi"),
        "rate": 168,
        "prompt": (
            "You are J.A.R.V.I.S., the user's calm, impeccably polite and "
            "dryly witty AI study companion, in the manner of a refined "
            "British butler. Address the user by their first name. Light, "
            "understated humour is welcome, never at the cost of clarity. "
        ),
    },
    "FRIDAY": {
        "label": "FRIDAY",
        "full": "F.R.I.D.A.Y.",
        "tagline": "FEMALE REPLACEMENT INTELLIGENT DIGITAL ASSISTANT YOUTH",
        "wake": "friday",
        "palette": {"main": "#FFA94D", "alt": "#FF6B5E", "warm": "#FFE3A3"},
        "voice_hints": ("zira", "hazel", "susan", "heera", "aria", "jenny", "sonia"),
        "rate": 185,
        "prompt": (
            "You are F.R.I.D.A.Y., the user's upbeat, quick and efficient AI "
            "study companion with a warm, playful edge. Call the user 'boss' "
            "now and then, or by their first name. Lead with the answer, no "
            "fluff. "
        ),
    },
    "CLASSIC": {
        "label": "CLASSIC",
        "full": "StudyMate AI",
        "tagline": "STUDYMATE LEARNING ASSISTANT",
        "wake": "studymate",
        "palette": None,
        "voice_hints": None,
        "rate": None,
        "prompt": CLASSIC_PROMPT,
    },
}


def clean_for_speech(text, limit=JARVIS_SPEECH_LIMIT):
    """Removes markdown / code so the voice never reads symbols aloud."""
    text = str(text)
    text = re.sub(r"```.*?```", " (code omitted) ", text, flags=re.S)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[*_#>~|]+", "", text)
    text = re.sub(r"^\s*[-\u2022]\s+", "", text, flags=re.M)
    text = re.sub(r"\n+", ". ", text)
    text = re.sub(r"([.!?:])\s*\.", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()

    if len(text) > limit:
        cut = text[:limit]
        end = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
        text = cut[:end + 1] if end > 200 else cut

    return text


# =============================================================
# FOR EVERY LEARNER, EVERY COURSE, EVERY SUBJECT
# =============================================================

EDUCATION_LEVELS = [
    "Primary School",
    "Middle / Secondary School",
    "High School / Pre-University",
    "Undergraduate / College",
    "Postgraduate / Masters / PhD",
    "Exam Preparation (competitive / entrance)",
    "Professional / Working Adult",
    "Self-learner / Hobbyist",
]

VOICE_LANGUAGES = [
    ("English (India)", "en-IN"),
    ("English (US)", "en-US"),
    ("English (UK)", "en-GB"),
    ("Hindi", "hi-IN"),
    ("Marathi", "mr-IN"),
    ("Spanish", "es-ES"),
    ("French", "fr-FR"),
    ("German", "de-DE"),
    ("Portuguese (Brazil)", "pt-BR"),
    ("Arabic", "ar-SA"),
    ("Japanese", "ja-JP"),
    ("Chinese (Mandarin)", "zh-CN"),
]

SUBJECT_SUGGESTIONS = [
    "Mathematics", "Physics", "Chemistry", "Biology",
    "English", "Literature", "History", "Geography",
    "Civics / Politics", "Economics", "Accountancy", "Business Studies",
    "Computer Science", "Statistics", "Psychology", "Sociology",
    "Environmental Science", "Art & Design", "Music", "Philosophy",
    "Medicine & Health", "Law", "Foreign Language", "Study Skills",
]

EXPLORE_TOPICS = [
    "Mathematics", "Physics", "Chemistry", "Biology",
    "History", "Geography", "English Grammar", "Economics",
    "Computer Science", "Psychology", "Study Skills", "Exam Preparation",
]


DEFAULT_DATA = {
    "profile": {
        "name": "Student",
        "college": "",
        "course": "",
        "level": "",
        "photo": "",
        "daily_goal": 120
    },
    "subjects": [],
    "tasks": [],
    "study_sessions": [],
    "settings": {"focus_minutes": 25, "break_minutes": 5, "theme": "Glass Aurora", "ai_persona": "JARVIS",
                 "voice_language": "en-IN", "onboarded": False},
    "ai_history": []
}


# =============================================================
# CALM THEMES
# =============================================================

THEMES = {
    "Midnight Gold": {
        "bg": "#0B0C10",
        "sidebar_bg": "#0F1117",
        "card_bg": "#161821",
        "card_border": "#2A2D3A",
        "input_bg": "#1E202B",
        "surface": "#262938",
        "accent": "#D4AF6A",
        "accent2": "#8FA3C7",
        "text": "#F2EEE6",
        "muted": "#9A9CAB",
        "green": "#8CC9A7",
        "red": "#E69A9A",
        "orange": "#E8C27A",
        "btn_text": "#1A1406",
        "hero": ["#1B1F33", "#2B2A3F", "#3A3042", "#202B3F"],
    },
    "Rose Noir": {
        "bg": "#120D14",
        "sidebar_bg": "#17101A",
        "card_bg": "#201720",
        "card_border": "#3A2A3A",
        "input_bg": "#2A1F2B",
        "surface": "#35283A",
        "accent": "#E8A0B4",
        "accent2": "#C9B6E4",
        "text": "#F6EDF1",
        "muted": "#AD9AA9",
        "green": "#9AD1B5",
        "red": "#F28B9B",
        "orange": "#EFC08A",
        "btn_text": "#2A0F1A",
        "hero": ["#3B1F3F", "#52284A", "#2F2A55", "#4A2A3F"],
    },
    "Emerald Ink": {
        "bg": "#07110F",
        "sidebar_bg": "#0A1815",
        "card_bg": "#10231F",
        "card_border": "#1E3F37",
        "input_bg": "#17302A",
        "surface": "#1F3D35",
        "accent": "#D8C58E",
        "accent2": "#7FC8B2",
        "text": "#EFF6F1",
        "muted": "#8FAEA3",
        "green": "#7BD8A8",
        "red": "#EE9A9A",
        "orange": "#E9C682",
        "btn_text": "#14110A",
        "hero": ["#0F3A33", "#145048", "#1B4A5A", "#0E4F44"],
    },
    "Ocean": {
        "bg": "#0A1628",
        "sidebar_bg": "#0C1D33",
        "card_bg": "#12263F",
        "card_border": "#1F3A5C",
        "input_bg": "#1A3150",
        "surface": "#21395A",
        "accent": "#5BC8F0",
        "accent2": "#9AA8FF",
        "text": "#EAF4FF",
        "muted": "#8FA9C4",
        "green": "#5FDDB5",
        "red": "#FF8FA3",
        "orange": "#FFCB85",
        "btn_text": "#06121F",
        "hero": ["#12306B", "#0E5A7A", "#2A4A9C", "#0F6E80"],
    },
    "Aurora": {
        "bg": "#08181A",
        "sidebar_bg": "#0A2023",
        "card_bg": "#102C30",
        "card_border": "#1B4B50",
        "input_bg": "#163A3F",
        "surface": "#1D474D",
        "accent": "#4FE3C1",
        "accent2": "#8EC5FF",
        "text": "#E9FBF7",
        "muted": "#86B3AE",
        "green": "#7CE8A3",
        "red": "#FF93A0",
        "orange": "#FFD08A",
        "btn_text": "#04201C",
        "hero": ["#0F4F55", "#126A62", "#1B5C8A", "#0E7F78"],
    },
    "Twilight": {
        "bg": "#0E1027",
        "sidebar_bg": "#12142F",
        "card_bg": "#1A1D3D",
        "card_border": "#2B3068",
        "input_bg": "#232754",
        "surface": "#2D3270",
        "accent": "#A5B4FC",
        "accent2": "#7DD3FC",
        "text": "#EEF0FF",
        "muted": "#9AA0D0",
        "green": "#7EE2C0",
        "red": "#FF9BB0",
        "orange": "#FFD29A",
        "btn_text": "#0B0D26",
        "hero": ["#2B2F7A", "#4B3A9A", "#2A5A9A", "#3F3F9F"],
    },
    "Glass Aurora": {
        "bg": "#0A1020",
        "sidebar_bg": "#0E1730",
        "card_bg": "#17234A",
        "card_border": "#46598F",
        "input_bg": "#1D2C58",
        "surface": "#2A3D78",
        "accent": "#7DD3FC",
        "accent2": "#C4B5FD",
        "text": "#F1F6FF",
        "muted": "#A3B3D9",
        "green": "#6EE7B7",
        "red": "#FDA4AF",
        "orange": "#FCD34D",
        "btn_text": "#06122B",
        "hero": ["#1E3A8A", "#5B21B6", "#0E7490", "#4338CA"],
    },
    "Glass Dusk": {
        "bg": "#150E22",
        "sidebar_bg": "#1B1230",
        "card_bg": "#2A1F48",
        "card_border": "#6A57A8",
        "input_bg": "#33265A",
        "surface": "#43337A",
        "accent": "#F0ABFC",
        "accent2": "#93C5FD",
        "text": "#F7F1FF",
        "muted": "#B5A8DA",
        "green": "#86EFAC",
        "red": "#FDA4AF",
        "orange": "#FCD34D",
        "btn_text": "#240A33",
        "hero": ["#5B21B6", "#9D174D", "#3730A3", "#7E22CE"],
    },
    "Glass Mint": {
        "bg": "#07161A",
        "sidebar_bg": "#0A1E24",
        "card_bg": "#12333D",
        "card_border": "#3A7F8F",
        "input_bg": "#183F4B",
        "surface": "#1F5260",
        "accent": "#5EEAD4",
        "accent2": "#93C5FD",
        "text": "#EAFBFA",
        "muted": "#8FBBC2",
        "green": "#86EFAC",
        "red": "#FDA4AF",
        "orange": "#FDE68A",
        "btn_text": "#03211D",
        "hero": ["#0F766E", "#155E75", "#1D4ED8", "#0E7490"],
    },
}


def hex_to_rgb(value):
    value = value.lstrip("#")

    if len(value) != 6:
        raise ValueError("Expected a #RRGGBB colour")

    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return "#%02x%02x%02x" % tuple(
        max(0, min(255, int(round(channel)))) for channel in rgb
    )


def mix_colors(first, second, amount):
    a = hex_to_rgb(first)
    b = hex_to_rgb(second)

    return rgb_to_hex(
        (a[i] + (b[i] - a[i]) * amount for i in range(3))
    )


# =============================================================
# TINY 3D ENGINE (pure Python, drawn on a Tk canvas)
# =============================================================

_PHI = (1 + math.sqrt(5)) / 2
_RAW_VERTS = [
    (-1, _PHI, 0), (1, _PHI, 0), (-1, -_PHI, 0), (1, -_PHI, 0),
    (0, -1, _PHI), (0, 1, _PHI), (0, -1, -_PHI), (0, 1, -_PHI),
    (_PHI, 0, -1), (_PHI, 0, 1), (-_PHI, 0, -1), (-_PHI, 0, 1),
]
_RAW_SCALE = math.sqrt(1 + _PHI * _PHI)

ICO_VERTS = [
    (x / _RAW_SCALE, y / _RAW_SCALE, z / _RAW_SCALE)
    for x, y, z in _RAW_VERTS
]

ICO_FACES = [
    (0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11),
    (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
    (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9),
    (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1),
]


def rotate_point(point, ax, ay, az):
    x, y, z = point

    c, s = math.cos(ax), math.sin(ax)
    y, z = y * c - z * s, y * s + z * c

    c, s = math.cos(ay), math.sin(ay)
    x, z = x * c + z * s, -x * s + z * c

    c, s = math.cos(az), math.sin(az)
    x, y = x * c - y * s, x * s + y * c

    return x, y, z


def face_normal(a, b, c):
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]

    nx = uy * vz - uz * vy
    ny = uz * vx - ux * vz
    nz = ux * vy - uy * vx

    length = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0

    return nx / length, ny / length, nz / length


def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as file:
                data = json.load(file)

            if not isinstance(data, dict):
                raise ValueError("Invalid data format")

            for key, value in DEFAULT_DATA.items():
                if key not in data:
                    data[key] = json.loads(json.dumps(value))

            for section in ("profile", "settings"):
                if not isinstance(data.get(section), dict):
                    data[section] = {}

                for key, value in DEFAULT_DATA[section].items():
                    data[section].setdefault(key, value)

            for key in ("subjects", "tasks", "study_sessions", "ai_history"):
                if not isinstance(data.get(key), list):
                    data[key] = []

            return data

        except (OSError, json.JSONDecodeError, ValueError):
            messagebox.showwarning(
                "Data Warning",
                "Saved data could not be read. Starting with fresh data."
            )

    return json.loads(json.dumps(DEFAULT_DATA))


def _cloud_sync_worker(user_id, snapshot):
    try:
        save_cloud_data(user_id, snapshot)
    except Exception as error:
        print("Cloud sync warning:", error)


def save_data(data):
    try:
        temp_file = DATA_FILE + ".tmp"

        with open(temp_file, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4, ensure_ascii=False)

        os.replace(temp_file, DATA_FILE)

        # Sync with Supabase in the background so the UI never freezes
        if CURRENT_USER_ID:
            snapshot = copy.deepcopy(data)
            threading.Thread(
                target=_cloud_sync_worker,
                args=(CURRENT_USER_ID, snapshot),
                daemon=True
            ).start()

    except OSError as error:
        messagebox.showerror("Save Error", str(error))


class StudyMate(AnimationsMixin):

    def __init__(self, root, user):
        global DATA_FILE, CURRENT_USER_ID

        DATA_FILE = f"studymate_{user.id}.json"
        CURRENT_USER_ID = user.id

        self.user = user
        self.root = root
        self.current_page = "Dashboard"

        self.root.title(APP_NAME)
        self.root.geometry("1200x780")
        self.root.resizable(True, True)
        self.root.minsize(850, 580)
        self.root.configure(bg="#0A1628")

        self.data = load_data()
        self.ai_history = self.data["ai_history"]
        self.ai_request_pending = False

        # JARVIS / FRIDAY interface state
        self.jarvis_listening = False
        self.jarvis_handsfree = False
        self._handsfree_job = None
        self._jarvis_awake_until = 0
        self._speak_pending_until = 0
        self._hf_was_busy = False
        self._jarvis_booted = False
        self.ai_name = "StudyMate AI"
        self.hud_color = "#8CC9A7"

        # Load study data from Supabase safely
        try:
            cloud_data = load_cloud_data(self.user.id)

            if isinstance(cloud_data, dict):

                # Only merge recognized data sections
                for key, default_value in DEFAULT_DATA.items():

                    if key not in cloud_data:
                        continue

                    cloud_value = cloud_data[key]

                    # Validate dictionary sections
                    if isinstance(default_value, dict):
                        if isinstance(cloud_value, dict):
                            self.data[key].update(cloud_value)

                    # Validate list sections
                    elif isinstance(default_value, list):
                        if isinstance(cloud_value, list):
                            self.data[key] = cloud_value

                # Recheck required sections
                for section in ("profile", "settings"):
                    if not isinstance(self.data.get(section), dict):
                        self.data[section] = {}

                    for key, value in DEFAULT_DATA[section].items():
                        self.data[section].setdefault(key, value)

                for section in (
                    "subjects",
                    "tasks",
                    "study_sessions",
                    "ai_history"
                ):
                    if not isinstance(self.data.get(section), list):
                        self.data[section] = []

                self.ai_history = self.data["ai_history"]
                save_data(self.data)

            else:
                save_cloud_data(self.user.id, self.data)

        except Exception as error:
            print("Cloud sync warning:", error)

        # First sign-in with Google / Discord / email: use the account name
        self._seed_profile_from_account()

        # =========================================================
        # TIMER AND CALENDAR STATE (after cloud sync so settings are final)
        # =========================================================

        focus_min = self.data["settings"].get("focus_minutes", 25)
        self.timer_running = False
        self.timer_after_id = None
        self.timer_mode = "Focus"
        self.timer_remaining = focus_min * 60
        self.timer_total_seconds = self.timer_remaining
        self.timer_subject = "General"
        self.timer_session_start = None

        today = date.today()
        self.calendar_year = today.year
        self.calendar_month = today.month

        # =========================================================
        # STUDYMATE VOICE ASSISTANT
        # =========================================================

        self.voice_assistant = None
        self.voice_enabled = True
        self.voice_language = self.data["settings"].get("voice_language", "en-IN")

        try:
            self.voice_assistant = VoiceAssistant()

            available_voices = self.voice_assistant.get_available_voices()

            if len(available_voices) > 1:
                self.voice_assistant.set_voice(1)

            print("StudyMate Voice Assistant initialized successfully!")

        except Exception as e:
            print("StudyMate Voice Assistant Error:", e)

        # =========================================================
        # THEME INITIALIZATION
        # =========================================================

        self._hero_job = None
        self._clock_job = None
        self.active_nav = None
        self.nav_commands = {}
        self.apply_theme(self.data["settings"].get("theme", "Midnight Gold"))

        # =========================================================
        # AI ATTACHMENTS
        # =========================================================

        self.attached_file_name = None
        self.attached_file_text = ""
        self.attached_image_data = None
        self.attached_image_mime = None

        # =========================================================
        # BUILD INTERFACE
        # =========================================================

        self.setup_styles()
        self.build_interface()
        self.show_dashboard()

        # Window bindings
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.root.bind_all(
            "<Return>",
            self.universal_enter_key,
            add="+"
        )

        # First-run setup for new learners (level, course, subjects)
        self.root.after(700, self.maybe_show_onboarding)

    # =========================================================
    # STYLES
    # =========================================================

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure(
            "Treeview",
            background=self.card_bg,
            foreground=self.text,
            fieldbackground=self.card_bg,
            rowheight=34,
            borderwidth=0,
            relief="flat",
            font=("Segoe UI", 10)
        )

        style.configure(
            "Treeview.Heading",
            background=self.surface,
            foreground=self.text,
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            borderwidth=0,
            padding=(8, 8)
        )

        style.map(
            "Treeview.Heading",
            background=[("active", self.card_border)]
        )

        style.map(
            "Treeview",
            background=[("selected", self.accent)],
            foreground=[("selected", self.btn_text)]
        )

        for scroll_style in ("Vertical.TScrollbar", "Horizontal.TScrollbar"):
            style.configure(
                scroll_style,
                background=self.surface,
                troughcolor=self.bg,
                bordercolor=self.bg,
                lightcolor=self.surface,
                darkcolor=self.surface,
                arrowcolor=self.text,
                relief="flat",
                gripcount=0
            )

            style.map(
                scroll_style,
                background=[("active", self.accent)]
            )

        style.configure(
            "TCombobox",
            fieldbackground=self.input_bg,
            background=self.surface,
            foreground=self.text,
            arrowcolor=self.text,
            bordercolor=self.card_border,
            lightcolor=self.input_bg,
            darkcolor=self.input_bg,
            selectbackground=self.input_bg,
            selectforeground=self.text,
            padding=6
        )

        style.map(
            "TCombobox",
            fieldbackground=[("readonly", self.input_bg)],
            foreground=[("readonly", self.text)],
            selectbackground=[("readonly", self.input_bg)],
            selectforeground=[("readonly", self.text)],
            background=[("active", self.card_border)]
        )

        self.root.option_add("*TCombobox*Listbox.background", self.input_bg)
        self.root.option_add("*TCombobox*Listbox.foreground", self.text)
        self.root.option_add("*TCombobox*Listbox.selectBackground", self.accent)
        self.root.option_add("*TCombobox*Listbox.selectForeground", self.btn_text)
        self.root.option_add("*TCombobox*Listbox.font", ("Segoe UI", 10))

        style.configure(
            "Horizontal.TProgressbar",
            troughcolor=self.input_bg,
            background=self.accent,
            bordercolor=self.input_bg,
            lightcolor=self.accent,
            darkcolor=self.accent,
            thickness=14
        )

    # =========================================================
    # MAIN INTERFACE WITH SCROLLBAR
    # =========================================================

    def build_interface(self):
        self.main_container = tk.Frame(self.root, bg=self.bg)
        self.main_container.pack(fill="both", expand=True)

        # Floating stage: animated backdrop + pill menu (see pill_nav.py)
        main_items = [
            ("Dashboard", self.show_dashboard),
            ("Subjects", self.show_subjects),
            ("Tasks", self.show_tasks),
            ("AI Assistant", self.show_ai_assistant),
            ("Focus Mode", self.show_focus_mode),
            ("Analytics", self.show_analytics),
        ]

        more_items = [
            ("Smart Scheduler", self.show_scheduler),
            ("Lecture Hub", self.show_lecture_hub),
            ("Daily Goals", self.show_daily_goals),
            ("Calendar", self.show_calendar),
            ("Profile", self.show_profile),
            ("Logout", self.logout),
        ]

        # Every page can still be reached by name (used by rebuild_interface)
        self.nav_commands = {
            label: command for label, command in main_items + more_items
        }

        self.stage = FloatingStage(
            self.main_container,
            self,
            main_items,
            more_items
        )
        self.stage.pack(side="top", fill="x")

        tk.Frame(
            self.main_container,
            bg=mix_colors(self.card_border, "#FFFFFF", 0.25),
            height=1
        ).pack(side="top", fill="x")

        # Main content area
        self.content = tk.Frame(self.main_container, bg=self.bg)
        self.content.pack(side="top", fill="both", expand=True)

        # Scrollbar
        self.page_scrollbar = ttk.Scrollbar(
            self.content,
            orient="vertical",
            style="Vertical.TScrollbar"
        )
        self.page_scrollbar.pack(side="right", fill="y")

        # Canvas
        self.page_canvas = tk.Canvas(
            self.content,
            bg=self.bg,
            highlightthickness=0,
            borderwidth=0,
            yscrollcommand=self.page_scrollbar.set
        )
        self.page_canvas.pack(side="left", fill="both", expand=True)

        self.page_scrollbar.config(command=self.page_canvas.yview)

        # Actual page frame inside canvas
        self.page_area = tk.Frame(
            self.page_canvas,
            bg=self.bg
        )

        self.page_window = self.page_canvas.create_window(
            (28, 25),
            window=self.page_area,
            anchor="nw"
        )

        self.page_area.bind(
            "<Configure>",
            self.update_scroll_region
        )

        self.page_canvas.bind(
            "<Configure>",
            self.resize_page_content
        )

        # Mouse wheel scrolling
        self.page_canvas.bind_all(
            "<MouseWheel>",
            self.on_page_mousewheel
        )

        self.page_canvas.bind_all(
            "<Button-4>",
            self.on_linux_scroll_up
        )

        self.page_canvas.bind_all(
            "<Button-5>",
            self.on_linux_scroll_down
        )

    # =========================================================
    # THEME + ANIMATION HELPERS
    # =========================================================

    def apply_theme(self, name):
        if name not in THEMES:
            name = "Midnight Gold"

        self.theme_name = name

        for key, value in THEMES[name].items():
            setattr(self, key, value)

        try:
            self.root.configure(bg=self.bg)
        except tk.TclError:
            pass

    def change_theme(self, name):
        if name not in THEMES or name == getattr(self, "theme_name", None):
            return

        self.data["settings"]["theme"] = name
        save_data(self.data)

        self.apply_theme(name)
        self.rebuild_interface()

    def rebuild_interface(self):
        page = self.current_page

        self.cancel_hero()

        try:
            self.main_container.destroy()
        except tk.TclError:
            pass

        self.setup_styles()
        self.build_interface()

        self.nav_commands.get(page, self.show_dashboard)()

    def time_greeting(self):
        hour = datetime.now().hour

        if hour < 5:
            return "Late night focus"
        if hour < 12:
            return "Good morning"
        if hour < 17:
            return "Good afternoon"
        if hour < 21:
            return "Good evening"

        return "Good night"

    def fade_color(self, widget, prop, target, steps=7, delay=14):
        previous = getattr(widget, "_fade_job", None)

        if previous:
            try:
                self.root.after_cancel(previous)
            except Exception:
                pass

            widget._fade_job = None

        try:
            start = hex_to_rgb(str(widget.cget(prop)))
            end = hex_to_rgb(target)
        except Exception:
            try:
                widget.configure(**{prop: target})
            except tk.TclError:
                pass
            return

        def step(index):
            try:
                if not widget.winfo_exists():
                    return

                amount = index / steps
                color = rgb_to_hex(
                    start[i] + (end[i] - start[i]) * amount
                    for i in range(3)
                )
                widget.configure(**{prop: color})

            except tk.TclError:
                return

            if index < steps:
                widget._fade_job = self.root.after(
                    delay,
                    lambda: step(index + 1)
                )
            else:
                widget._fade_job = None

        step(1)

    def cancel_fade(self, widget):
        job = getattr(widget, "_fade_job", None)

        if job:
            try:
                self.root.after_cancel(job)
            except Exception:
                pass

            widget._fade_job = None

    def add_hover(self, widget, normal, hover):
        def enter(event):
            self.fade_color(widget, "bg", hover)

        def leave(event):
            self.fade_color(widget, "bg", normal)

        def press(event):
            try:
                if str(widget.cget("state")) == "disabled":
                    return

                self.cancel_fade(widget)
                widget.configure(bg=mix_colors(normal, "#000000", 0.22))
            except tk.TclError:
                pass

        def release(event):
            self.fade_color(widget, "bg", hover, steps=6, delay=12)

        widget.bind("<Enter>", enter, add="+")
        widget.bind("<Leave>", leave, add="+")
        widget.bind("<ButtonPress-1>", press, add="+")
        widget.bind("<ButtonRelease-1>", release, add="+")

    def nav_hover(self, button, label, entering):
        if label == self.active_nav:
            return

        if entering:
            self.fade_color(
                button,
                "bg",
                mix_colors(self.sidebar_bg, self.surface, 0.65)
            )
            button.configure(fg=self.text)
        else:
            self.fade_color(button, "bg", self.sidebar_bg)
            button.configure(fg=self.muted)

    def animate_count(self, label, end, suffix="", steps=22, delay=24):
        try:
            end = int(end)
        except (TypeError, ValueError):
            label.configure(text=f"{end}{suffix}")
            return

        if end <= 0:
            label.configure(text=f"0{suffix}")
            return

        def step(index):
            try:
                if not label.winfo_exists():
                    return

                amount = index / steps
                eased = 1 - (1 - amount) ** 3
                label.configure(
                    text=f"{int(round(end * eased))}{suffix}"
                )

            except tk.TclError:
                return

            if index < steps:
                self.root.after(delay, lambda: step(index + 1))

        step(1)

    def cancel_hero(self):
        """Stops the banner and clock animations."""

        for name in ("_hero_job", "_clock_job"):
            job = getattr(self, name, None)

            if job is not None:
                try:
                    self.root.after_cancel(job)
                except Exception:
                    pass

                setattr(self, name, None)

    def create_clock_card(self, parent):
        """Analog + digital clock with a bevelled, shadowed 3D dial."""

        card = self.card(parent, padx=16, pady=14)

        size = 200
        center = size / 2
        radius = 90
        inner = radius - 8

        canvas = tk.Canvas(
            card,
            width=size,
            height=size,
            bg=self.card_bg,
            highlightthickness=0,
            bd=0
        )
        canvas.pack()

        bezel = mix_colors(self.card_border, self.accent, 0.5)
        bezel_dark = mix_colors(bezel, "#000000", 0.35)
        face = mix_colors(self.card_bg, self.surface, 0.55)
        drop_shadow = mix_colors(self.card_bg, "#000000", 0.55)
        hand_shadow = mix_colors(face, "#000000", 0.55)

        # drop shadow, bezel, inner bezel edge, dial face
        canvas.create_oval(
            center - radius + 4, center - radius + 7,
            center + radius + 4, center + radius + 7,
            fill=drop_shadow, width=0
        )
        canvas.create_oval(
            center - radius, center - radius,
            center + radius, center + radius,
            fill=bezel, outline=bezel_dark, width=1
        )
        canvas.create_arc(
            center - radius + 2, center - radius + 2,
            center + radius - 2, center + radius - 2,
            start=35, extent=110, style="arc",
            outline=mix_colors(bezel, "#FFFFFF", 0.45), width=2
        )
        canvas.create_oval(
            center - inner, center - inner,
            center + inner, center + inner,
            fill=face, outline=bezel_dark, width=2
        )
        canvas.create_arc(
            center - inner + 4, center - inner + 4,
            center + inner - 4, center + inner - 4,
            start=40, extent=100, style="arc",
            outline=mix_colors(face, "#FFFFFF", 0.12), width=2
        )

        # minute / hour ticks
        for index in range(60):
            angle = math.radians(index * 6 - 90)
            major = index % 5 == 0
            outer_r = inner - 5
            inner_r = outer_r - (11 if major else 5)

            canvas.create_line(
                center + math.cos(angle) * outer_r,
                center + math.sin(angle) * outer_r,
                center + math.cos(angle) * inner_r,
                center + math.sin(angle) * inner_r,
                fill=self.accent if major else self.muted,
                width=2 if major else 1
            )

        # numerals
        for hour in range(1, 13):
            angle = math.radians(hour * 30 - 90)

            canvas.create_text(
                center + math.cos(angle) * (inner - 28),
                center + math.sin(angle) * (inner - 28),
                text=str(hour),
                fill=self.text,
                font=("Georgia", 11, "bold")
            )

        canvas.create_text(
            center, center - 30,
            text="STUDYMATE",
            fill=self.muted,
            font=("Segoe UI", 7, "bold")
        )

        time_label = tk.Label(
            card,
            text="",
            bg=self.card_bg,
            fg=self.text,
            font=("Georgia", 20, "bold")
        )
        time_label.pack(pady=(10, 0))

        date_label = tk.Label(
            card,
            text="",
            bg=self.card_bg,
            fg=self.muted,
            font=("Segoe UI", 10)
        )
        date_label.pack(pady=(2, 0))

        last = {"second": -1}

        def draw_hand(degrees, length, width, color, tail=0):
            angle = math.radians(degrees - 90)
            dx, dy = math.cos(angle), math.sin(angle)

            start = (center - dx * tail, center - dy * tail)
            end = (center + dx * length, center + dy * length)

            canvas.create_line(
                start[0] + 2, start[1] + 3, end[0] + 2, end[1] + 3,
                fill=hand_shadow, width=width,
                capstyle="round", tags="hand"
            )
            canvas.create_line(
                start[0], start[1], end[0], end[1],
                fill=color, width=width,
                capstyle="round", tags="hand"
            )

        def tick():
            try:
                if not canvas.winfo_exists():
                    return

                now = datetime.now()
                seconds = now.second + now.microsecond / 1_000_000
                minutes = now.minute + seconds / 60
                hours = (now.hour % 12) + minutes / 60

                canvas.delete("hand")

                draw_hand(hours * 30, inner * 0.50, 5, self.text)
                draw_hand(minutes * 6, inner * 0.74, 3.5, self.text)
                draw_hand(seconds * 6, inner * 0.84, 1.5, self.accent, tail=16)

                canvas.create_oval(
                    center - 7, center - 7, center + 7, center + 7,
                    fill=self.accent, outline=bezel_dark, tags="hand"
                )
                canvas.create_oval(
                    center - 2.5, center - 2.5, center + 2.5, center + 2.5,
                    fill=self.card_bg, width=0, tags="hand"
                )

                if now.second != last["second"]:
                    last["second"] = now.second

                    time_label.configure(
                        text=now.strftime("%I:%M:%S %p").lstrip("0")
                    )
                    date_label.configure(
                        text=now.strftime("%A, %d %B %Y")
                    )

                self._clock_job = self.root.after(50, tick)

            except tk.TclError:
                self._clock_job = None

        tick()

        return card

    def create_hero_banner(self, title, subtitle):
        """Aurora gradient, parallax star-field and a rotating 3D crystal
        with an orbiting particle ring. Move the mouse over it to tilt it."""

        height = 170
        slice_count = 40
        star_count = 46
        palette = list(self.hero)

        canvas = tk.Canvas(
            self.page_area,
            height=height,
            bg=self.bg,
            highlightthickness=0,
            bd=0
        )
        canvas.pack(fill="x", pady=(0, 22))

        state = {
            "phase": 0.0,
            "width": 800,
            "frame": 0,
            "tx": 0.0,
            "ty": 0.0,
            "tilt_x": 0.0,
            "tilt_y": 0.0
        }
        slices = []

        def colour_at(position):
            count = len(palette)
            scaled = (position % 1.0) * count
            index = int(scaled)
            fraction = scaled - index
            fraction = fraction * fraction * (3 - 2 * fraction)

            return mix_colors(
                palette[index % count],
                palette[(index + 1) % count],
                fraction
            )

        # star-field (created once, moved every frame)
        rng = random.Random(11)
        stars = []

        for _ in range(star_count):
            item = canvas.create_oval(0, 0, 0, 0, width=0, fill="#FFFFFF")
            stars.append((
                item,
                rng.random(),
                rng.random(),
                0.2 + rng.random() * 0.8
            ))

        title_id = canvas.create_text(
            32, 70,
            text=title,
            anchor="w",
            fill="#F7F4EC",
            font=("Georgia", 22, "bold")
        )

        canvas.create_text(
            32, 110,
            text=subtitle,
            anchor="w",
            fill="#D9E2EE",
            font=("Segoe UI", 11)
        )

        date_id = canvas.create_text(
            0, 28,
            text=date.today().strftime("%A, %d %B"),
            anchor="e",
            fill="#E4EAF3",
            font=("Segoe UI", 10, "bold")
        )

        light = (-0.45, -0.55, -0.70)
        light_len = math.sqrt(sum(c * c for c in light))
        light = tuple(c / light_len for c in light)

        shadow_color = mix_colors(palette[0], "#000000", 0.45)
        glow_color = mix_colors(self.accent, "#FFFFFF", 0.22)
        camera = 3.6

        def layout(event=None):
            width = max(canvas.winfo_width(), 300)
            state["width"] = width

            canvas.delete("slice")
            slices.clear()

            step = width / slice_count

            for index in range(slice_count):
                item = canvas.create_rectangle(
                    index * step,
                    0,
                    (index + 1) * step + 1,
                    height,
                    width=0,
                    tags="slice",
                    fill=colour_at(index / slice_count * 0.5 + state["phase"])
                )
                slices.append(item)

            canvas.tag_lower("slice")
            canvas.coords(date_id, width - 28, 28)

        def on_motion(event):
            width = max(state["width"], 1)
            state["tx"] = (event.x / width - 0.5) * 2
            state["ty"] = (event.y / height - 0.5) * 2

        def on_leave(event):
            state["tx"] = 0.0
            state["ty"] = 0.0

        def move_stars(frame):
            width = state["width"]

            for index, (item, base_x, base_y, depth) in enumerate(stars):
                x = (base_x * width + frame * 0.35 * depth) % width
                y = base_y * height + math.sin(frame * 0.02 + base_x * 9) * 2 * depth
                radius = 0.7 + 1.6 * depth

                twinkle = 0.75 + 0.25 * math.sin(frame * 0.07 + index)
                brightness = 0.2 + 0.7 * depth * twinkle

                canvas.coords(
                    item, x - radius, y - radius, x + radius, y + radius
                )
                canvas.itemconfigure(
                    item,
                    fill=mix_colors(palette[0], "#FFFFFF", brightness)
                )

        def draw_scene(frame):
            canvas.delete("obj")

            width = state["width"]

            state["tilt_x"] += (state["tx"] - state["tilt_x"]) * 0.08
            state["tilt_y"] += (state["ty"] - state["tilt_y"]) * 0.08

            cx = width - 150
            cy = height / 2 + math.sin(frame * 0.03) * 4
            scale = 56

            ax = frame * 0.013 + state["tilt_y"] * 0.7
            ay = frame * 0.021 + state["tilt_x"] * 0.9
            az = frame * 0.007

            def project(point, size=scale):
                factor = camera / (camera + point[2])
                return (
                    cx + point[0] * size * factor,
                    cy + point[1] * size * factor,
                    factor
                )

            # faint orbit rings behind everything
            ring_color = mix_colors(palette[1], "#FFFFFF", 0.28)

            for number in range(2):
                radius = 82 + number * 22
                canvas.create_oval(
                    cx - radius, cy - radius * 0.38,
                    cx + radius, cy + radius * 0.38,
                    outline=ring_color, width=1, tags="obj"
                )

            vertices = [rotate_point(v, ax, ay, az) for v in ICO_VERTS]
            entries = []

            for a, b, c in ICO_FACES:
                va, vb, vc = vertices[a], vertices[b], vertices[c]
                normal = face_normal(va, vb, vc)

                centroid = (
                    (va[0] + vb[0] + vc[0]) / 3,
                    (va[1] + vb[1] + vc[1]) / 3,
                    (va[2] + vb[2] + vc[2]) / 3
                )

                if (
                    normal[0] * centroid[0]
                    + normal[1] * centroid[1]
                    + normal[2] * centroid[2]
                ) < 0:
                    normal = (-normal[0], -normal[1], -normal[2])

                if normal[2] > 0:
                    continue

                brightness = max(
                    0.0,
                    normal[0] * light[0]
                    + normal[1] * light[1]
                    + normal[2] * light[2]
                )

                entries.append((centroid[2], "face", (va, vb, vc), brightness))

            particles = 30

            for index in range(particles):
                theta = index / particles * math.tau + frame * 0.022
                point = (1.75 * math.cos(theta), 0.0, 1.75 * math.sin(theta))
                point = rotate_point(point, 0.55, 0.0, 0.35)
                entries.append((point[2], "dot", point, index))

            entries.sort(key=lambda entry: -entry[0])

            for z, kind, data, extra in entries:
                if kind == "face":
                    points = []

                    for vertex in data:
                        x, y, _ = project(vertex)
                        points.extend((x, y))

                    fill = mix_colors(
                        shadow_color, glow_color, 0.10 + 0.90 * extra
                    )

                    canvas.create_polygon(
                        points,
                        fill=fill,
                        outline=mix_colors(fill, "#FFFFFF", 0.28),
                        width=1,
                        tags="obj"
                    )
                else:
                    x, y, factor = project(data)
                    near = max(0.0, min(1.0, (1.75 - z) / 3.5))
                    radius = 0.8 + 2.4 * near * factor

                    canvas.create_oval(
                        x - radius, y - radius, x + radius, y + radius,
                        fill=mix_colors(
                            palette[0], self.accent2, 0.30 + 0.70 * near
                        ),
                        width=0,
                        tags="obj"
                    )

        def tick():
            try:
                if not canvas.winfo_exists():
                    return

                state["frame"] += 1
                frame = state["frame"]

                if frame % 4 == 0:
                    state["phase"] = (state["phase"] + 0.0035) % 1.0

                    for index, item in enumerate(slices):
                        canvas.itemconfigure(
                            item,
                            fill=colour_at(
                                index / slice_count * 0.5 + state["phase"]
                            )
                        )

                move_stars(frame)
                draw_scene(frame)

                self._hero_job = self.root.after(40, tick)

            except tk.TclError:
                self._hero_job = None

        canvas.bind("<Configure>", layout)
        canvas.bind("<Motion>", on_motion)
        canvas.bind("<Leave>", on_leave)

        layout()
        tick()

        return canvas

    def update_scroll_region(self, event=None):
        self.page_canvas.configure(
            scrollregion=self.page_canvas.bbox("all")
        )

    def resize_page_content(self, event):
        self.page_canvas.itemconfigure(
            self.page_window,
            width=max(100, event.width - 56)
        )

    def _pointer_over_self_scrolling_widget(self):
        """True when the mouse is over a Text box or Treeview, which scroll themselves."""
        try:
            widget = self.root.winfo_containing(
                self.root.winfo_pointerx(),
                self.root.winfo_pointery()
            )
        except Exception:
            return True

        if widget is None:
            return True

        return isinstance(widget, (tk.Text, ttk.Treeview))

    def on_page_mousewheel(self, event):
        if self._pointer_over_self_scrolling_widget():
            return

        if not event.delta:
            return

        if sys.platform == "darwin":
            steps = int(-event.delta)
        else:
            steps = int(-event.delta / 120)

        if steps:
            self.smooth_scroll(steps)

    def on_linux_scroll_up(self, event):
        if self._pointer_over_self_scrolling_widget():
            return
        self.smooth_scroll(-1)

    def on_linux_scroll_down(self, event):
        if self._pointer_over_self_scrolling_widget():
            return
        self.smooth_scroll(1)

    def clear_page(self):
        self.cancel_hero()

        for widget in self.page_area.winfo_children():
            widget.destroy()

        self.page_canvas.yview_moveto(0)

    def set_active_nav(self, name):
        self.active_nav = name

        # Animated page transition (see animations.py)
        self.begin_page_transition()

        # Slide the pill highlight to this page
        stage = getattr(self, "stage", None)

        if stage is not None:
            try:
                stage.set_active(name)
            except tk.TclError:
                pass

    # =========================================================
    # REUSABLE UI COMPONENTS
    # =========================================================

    def page_header(self, title, subtitle=""):
        header = tk.Frame(self.page_area, bg=self.bg)
        header.pack(fill="x", pady=(0, 25))

        tk.Label(
            header,
            text=title,
            bg=self.bg,
            fg=self.text,
            font=("Georgia", 25, "bold")
        ).pack(anchor="w")

        tk.Frame(
            header,
            bg=self.accent,
            width=46,
            height=3
        ).pack(anchor="w", pady=(6, 0))

        if subtitle:
            tk.Label(
                header,
                text=subtitle,
                bg=self.bg,
                fg=self.muted,
                font=("Segoe UI", 10)
            ).pack(anchor="w", pady=(8, 0))

    def card(self, parent=None, padx=20, pady=18):
        if parent is None:
            parent = self.page_area

        rim = mix_colors(self.card_border, "#FFFFFF", 0.14)

        frame = tk.Frame(
            parent,
            bg=self.card_bg,
            padx=padx,
            pady=pady,
            highlightthickness=1,
            highlightbackground=rim,
            highlightcolor=rim
        )

        # Light "specular" glass edges. place() is used so these never
        # clash with the pack()/grid() calls made inside the card.
        tk.Frame(
            frame,
            bg=mix_colors(self.card_bg, "#FFFFFF", 0.30),
            height=1
        ).place(x=0, y=0, relwidth=1)

        tk.Frame(
            frame,
            bg=mix_colors(self.card_bg, "#FFFFFF", 0.10),
            width=1
        ).place(x=0, y=0, relheight=1)

        return frame

    def section_title(self, parent, title):
        tk.Label(
            parent,
            text=title,
            bg=parent.cget("bg"),
            fg=self.text,
            font=("Segoe UI", 14, "bold")
        ).pack(anchor="w", pady=(0, 12))

    def styled_button(
        self,
        parent,
        text,
        command,
        color=None,
        width=None
    ):
        if color is None:
            color = self.accent

        # Glass button: tinted translucent-looking fill with a light rim
        base = mix_colors(self.surface, color, 0.30)
        hover = mix_colors(self.surface, color, 0.55)
        rim = mix_colors(color, "#FFFFFF", 0.20)

        button = tk.Button(
            parent,
            text=text,
            command=command,
            bg=base,
            fg=self.text,
            activebackground=hover,
            activeforeground=self.text,
            disabledforeground=self.muted,
            relief="flat",
            bd=0,
            padx=18,
            pady=9,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
            width=width,
            highlightthickness=1,
            highlightbackground=mix_colors(base, rim, 0.65),
            highlightcolor=rim
        )

        self.add_hover(button, base, hover)

        return button

    def make_entry(self, parent, width=30):
        return tk.Entry(
            parent,
            width=width,
            bg=self.input_bg,
            fg=self.text,
            insertbackground=self.accent,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=self.card_border,
            highlightcolor=self.accent,
            font=("Segoe UI", 10)
        )

    def make_text(self, parent, height=5):
        return tk.Text(
            parent,
            height=height,
            bg=self.input_bg,
            fg=self.text,
            insertbackground=self.accent,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=self.card_border,
            highlightcolor=self.accent,
            wrap="word",
            font=("Segoe UI", 10),
            padx=10,
            pady=8
        )

    # =========================================================
    # UNIVERSAL ENTER KEY SYSTEM
    # =========================================================

    def universal_enter_key(self, event):

        widget = event.widget

        # AI Assistant: Enter sends, Shift+Enter inserts a new line
        if widget == getattr(self, "ai_input", None):
            if event.state & 0x1:
                return None

            self.send_ai_message()
            return "break"

        # Preserve multiline text behaviour
        if isinstance(widget, tk.Text):
            return None

        # Preserve Combobox behaviour
        if isinstance(widget, ttk.Combobox):
            return None

        # Handle Entry widgets
        if isinstance(widget, tk.Entry):

            if widget == getattr(self, "subject_entry", None):
                self.add_subject()

            elif widget in (
                getattr(self, "task_title_entry", None),
                getattr(self, "task_date_entry", None)
            ):
                self.add_task()

            elif widget == getattr(self, "goal_entry", None):
                self.save_daily_goal()

            elif widget in getattr(self, "profile_entries", {}).values():
                self.save_profile()

            elif widget in (
                getattr(self, "focus_entry", None),
                getattr(self, "break_entry", None)
            ):
                self.save_timer_settings()

            else:
                return None

            return "break"

        return None

    # =========================================================
    # DASHBOARD
    # =========================================================

    # =========================================================
    # 3D FEATURES (see scene3d.py)
    # =========================================================

    def palette_3d(self):
        return {
            "bg": self.bg,
            "card_bg": self.card_bg,
            "surface": self.surface,
            "accent": self.accent,
            "accent2": self.accent2,
            "text": self.text,
            "muted": self.muted,
            "green": self.green,
            "red": self.red,
            "orange": self.orange,
        }

    def galaxy_planets(self):
        today = date.today().isoformat()
        names = list(self.data["subjects"])

        used = {
            task.get("subject") for task in self.data["tasks"]
        } | {
            session.get("subject") for session in self.data["study_sessions"]
        }

        if "General" in used:
            names.insert(0, "General")

        planets = []

        for name in names[:18]:
            subject_tasks = [
                task for task in self.data["tasks"]
                if task.get("subject") == name
            ]

            planets.append({
                "name": name,
                "tasks": len(subject_tasks),
                "done": sum(
                    1 for task in subject_tasks if task.get("completed")
                ),
                "overdue": sum(
                    1 for task in subject_tasks
                    if not task.get("completed")
                    and task.get("date") and task.get("date") < today
                ),
                "minutes": sum(
                    session.get("minutes", 0)
                    for session in self.data["study_sessions"]
                    if session.get("subject") == name
                ),
            })

        return planets

    def open_galaxy_subject(self, name):
        self.show_tasks()

        try:
            if name in ["General"] + self.data["subjects"]:
                self.task_subject_var.set(name)
        except Exception:
            pass

        self.toast(f"Opened {name}", "info")

    def create_galaxy_card(self):
        card = self.card(padx=0, pady=0)
        card.pack(fill="x", pady=(0, 22))

        galaxy = StudyGalaxy(
            card,
            self.galaxy_planets(),
            self.palette_3d(),
            on_open=self.open_galaxy_subject,
            height=320
        )
        galaxy.pack(fill="x", padx=1, pady=1)

        return card

    def study_level(self):
        """XP = study minutes + 10 per completed task. 150 XP per level."""
        minutes = sum(
            session.get("minutes", 0)
            for session in self.data["study_sessions"]
        )
        done = sum(
            1 for task in self.data["tasks"] if task.get("completed")
        )

        xp = minutes + done * 10
        per_level = 150
        level = 1 + xp // per_level

        titles = [
            "Rookie", "Explorer", "Learner", "Scholar", "Strategist",
            "Specialist", "Master", "Grandmaster", "Legend"
        ]

        return {
            "xp": xp,
            "level": level,
            "into": xp % per_level,
            "per_level": per_level,
            "title": titles[min(len(titles) - 1, level - 1)],
        }

    def create_level_card(self):
        info = self.study_level()

        card = self.card()
        card.pack(fill="x", pady=(0, 22))

        top = tk.Frame(card, bg=self.card_bg)
        top.pack(fill="x")

        badge = tk.Canvas(
            top, width=64, height=64, bg=self.card_bg,
            highlightthickness=0
        )
        badge.pack(side="left", padx=(0, 16))

        # Hexagon badge with the level number
        points = []

        for step in range(6):
            angle = math.pi / 3 * step - math.pi / 2
            points.extend((
                32 + math.cos(angle) * 28,
                32 + math.sin(angle) * 28
            ))

        badge.create_polygon(
            *points,
            fill=mix_colors(self.card_bg, self.accent, 0.25),
            outline=self.accent,
            width=2
        )
        badge.create_text(
            32, 32, text=str(info["level"]),
            fill=self.accent, font=("Georgia", 20, "bold")
        )

        text_box = tk.Frame(top, bg=self.card_bg)
        text_box.pack(side="left", fill="x", expand=True)

        tk.Label(
            text_box,
            text=f"Level {info['level']}  •  {info['title']}",
            bg=self.card_bg, fg=self.text,
            font=("Segoe UI", 14, "bold")
        ).pack(anchor="w")

        tk.Label(
            text_box,
            text=(
                f"{info['into']} / {info['per_level']} XP to the next "
                "level  •  study minutes + 10 XP per finished task"
            ),
            bg=self.card_bg, fg=self.muted,
            font=("Segoe UI", 9)
        ).pack(anchor="w", pady=(2, 8))

        bar = AnimatedBar(
            text_box, self, height=10, color=self.accent, shimmer=True
        )
        bar.pack(fill="x")
        bar.animate_to(info["into"] / info["per_level"], start_delay=200)

        return card

    def week_minutes(self):
        """Minutes studied for each of the last 7 days (oldest first)."""
        days = [date.today() - timedelta(days=offset)
                for offset in range(6, -1, -1)]

        totals = {day.isoformat(): 0 for day in days}

        for session in self.data["study_sessions"]:
            key = session.get("date")

            if key in totals:
                totals[key] += int(session.get("minutes", 0) or 0)

        return [(day.strftime("%a"), totals[day.isoformat()])
                for day in days]

    def create_week_3d_card(self):
        card = self.card()
        card.pack(fill="x", pady=(0, 18))

        self.section_title(card, "Last 7 Days  (3D)")

        chart = Bar3DChart(
            card,
            self.week_minutes(),
            self.palette_3d(),
            height=290,
            unit="minutes studied"
        )
        chart.pack(fill="x")

        return card

    def show_dashboard(self):
        self.current_page = "Dashboard"
        self.clear_page()
        self.set_active_nav("Dashboard")

        self.page_header(
            "Dashboard",
            "Your learning overview at a glance."
        )

        profile = self.data["profile"]
        today = date.today().isoformat()

        today_tasks = [
            task for task in self.data["tasks"]
            if task.get("date") == today
        ]

        pending_tasks = [
            task for task in self.data["tasks"]
            if not task.get("completed", False)
        ]

        completed_tasks = [
            task for task in self.data["tasks"]
            if task.get("completed", False)
        ]

        today_minutes = sum(
            session.get("minutes", 0)
            for session in self.data["study_sessions"]
            if session.get("date") == today
        )

        first_name = (profile.get("name") or "Student").split()[0]

        self.create_hero_banner(
            f"{self.time_greeting()}, {first_name}",
            "Small progress every day creates big results."
        )

        # Clock + statistics grid
        top_row = tk.Frame(self.page_area, bg=self.bg)
        top_row.pack(fill="x", pady=(0, 22))

        clock_card = self.create_clock_card(top_row)
        clock_card.pack(side="left", fill="y", padx=(0, 7), pady=7)

        stats_container = tk.Frame(top_row, bg=self.bg)
        stats_container.pack(side="left", fill="both", expand=True)

        stats = [
            ("Total Subjects", len(self.data["subjects"]), "", self.accent),
            ("Pending Tasks", len(pending_tasks), "", self.orange),
            ("Completed Tasks", len(completed_tasks), "", self.green),
            ("Today's Study", today_minutes, " min", self.accent2)
        ]

        for column in range(2):
            stats_container.grid_columnconfigure(
                column,
                weight=1,
                uniform="stats"
            )

        for index, (label, value, suffix, color) in enumerate(stats):
            row = index // 2
            column = index % 2

            stat_card = self.card(stats_container)
            stat_card.grid(
                row=row,
                column=column,
                sticky="nsew",
                padx=7,
                pady=7
            )

            tk.Frame(
                stat_card,
                bg=color,
                height=3
            ).pack(fill="x", pady=(0, 12))

            tk.Label(
                stat_card,
                text=label,
                bg=self.card_bg,
                fg=self.muted,
                font=("Segoe UI", 10)
            ).pack(anchor="w")

            value_label = tk.Label(
                stat_card,
                text=f"0{suffix}",
                bg=self.card_bg,
                fg=color,
                font=("Segoe UI", 25, "bold")
            )
            value_label.pack(anchor="w", pady=(7, 0))

            self.animate_count(value_label, value, suffix)

        # 3D study galaxy and level badge
        self.create_galaxy_card()
        self.create_level_card()

        # Daily goal ring, study streak and inspiration
        self.create_insight_row(
            today_minutes,
            max(1, int(profile.get("daily_goal", 120) or 120))
        )

        # Today's tasks
        task_card = self.card()
        task_card.pack(fill="x", pady=(0, 18))

        self.section_title(task_card, "Today's Tasks")

        if today_tasks:
            for task in today_tasks[:6]:
                status = "✓" if task.get("completed") else "○"
                self.info_row(
                    task_card,
                    f"{status}  {task.get('title', 'Untitled task')}",
                    fg=self.green if task.get("completed") else self.text
                )
        else:
            tk.Label(
                task_card,
                text="No tasks scheduled for today.",
                bg=self.card_bg,
                fg=self.muted,
                font=("Segoe UI", 10)
            ).pack(anchor="w")

        # Quick actions
        quick_card = self.card()
        quick_card.pack(fill="x", pady=(0, 18))

        self.section_title(quick_card, "Quick Actions")

        action_frame = tk.Frame(quick_card, bg=self.card_bg)
        action_frame.pack(fill="x")

        self.styled_button(
            action_frame, "Add Task", self.show_tasks
        ).pack(side="left", padx=(0, 8), pady=5)

        self.styled_button(
            action_frame, "Start Focus", self.show_focus_mode, self.green
        ).pack(side="left", padx=8, pady=5)

        self.styled_button(
            action_frame, "Ask AI", self.show_ai_assistant, self.accent2
        ).pack(side="left", padx=8, pady=5)

        # Upcoming tasks
        upcoming_card = self.card()
        upcoming_card.pack(fill="x", pady=(0, 18))

        self.section_title(upcoming_card, "Upcoming Tasks")

        upcoming = sorted(
            [
                task for task in pending_tasks
                if task.get("date")
            ],
            key=lambda task: task.get("date", "")
        )

        if upcoming:
            for task in upcoming[:5]:
                self.info_row(
                    upcoming_card,
                    f"{task.get('date')}  •  {task.get('title')}"
                )
        else:
            tk.Label(
                upcoming_card,
                text="No upcoming tasks. You're all caught up!",
                bg=self.card_bg,
                fg=self.muted,
                font=("Segoe UI", 10)
            ).pack(anchor="w")

    # =========================================================
    # SUBJECTS
    # =========================================================

    def show_subjects(self):
        self.current_page = "Subjects"
        self.clear_page()
        self.set_active_nav("Subjects")

        self.page_header(
            "My Subjects",
            "Organize the subjects you are currently studying."
        )

        form = self.card()
        form.pack(fill="x", pady=(0, 20))

        self.section_title(form, "Add a Subject")

        input_frame = tk.Frame(form, bg=self.card_bg)
        input_frame.pack(fill="x")

        self.subject_entry = self.make_entry(input_frame)
        self.subject_entry.pack(
            side="left",
            fill="x",
            expand=True,
            padx=(0, 10),
            ipady=9
        )

        self.styled_button(
            input_frame,
            "Add Subject",
            self.add_subject
        ).pack(side="left")

        suggestions = [
            name for name in SUBJECT_SUGGESTIONS
            if name not in self.data["subjects"]
        ]

        if suggestions:
            tk.Label(
                form,
                text="Quick add (tap a subject)",
                bg=self.card_bg,
                fg=self.muted,
                font=("Segoe UI", 9)
            ).pack(anchor="w", pady=(14, 6))

            chip_area = tk.Frame(form, bg=self.card_bg)
            chip_area.pack(fill="x")

            for column in range(4):
                chip_area.grid_columnconfigure(column, weight=1, uniform="subj")

            for index, name in enumerate(suggestions):
                chip = tk.Label(
                    chip_area,
                    text="+ " + name,
                    bg=self.surface,
                    fg=self.text,
                    font=("Segoe UI", 9),
                    padx=8,
                    pady=6,
                    cursor="hand2"
                )
                chip.grid(
                    row=index // 4, column=index % 4,
                    sticky="ew", padx=3, pady=3
                )
                chip.bind(
                    "<Button-1>",
                    lambda event, n=name: self.quick_add_subject(n)
                )

        list_card = self.card()
        list_card.pack(fill="x")

        self.section_title(list_card, "Your Subjects")

        if not self.data["subjects"]:
            tk.Label(
                list_card,
                text="You haven't added any subjects yet.",
                bg=self.card_bg,
                fg=self.muted
            ).pack(anchor="w")
            return

        for subject in self.data["subjects"]:
            row = tk.Frame(list_card, bg=self.card_bg)
            row.pack(fill="x", pady=7)

            tk.Label(
                row,
                text=subject,
                bg=self.card_bg,
                fg=self.text,
                font=("Segoe UI", 11)
            ).pack(side="left", anchor="w")

            self.styled_button(
                row,
                "Delete",
                lambda s=subject: self.delete_subject(s),
                self.red
            ).pack(side="right")

            self.make_row_interactive(
                row,
                flash=self.consume_flash("_flash_subject", subject)
            )

    def add_subject(self):
        subject = self.subject_entry.get().strip()

        if not subject:
            self.shake(self.subject_entry)
            self.toast("Please enter a subject name.", "error")
            return

        if subject in self.data["subjects"]:
            self.shake(self.subject_entry)
            self.toast("This subject is already in your list.", "warning")
            return

        self.data["subjects"].append(subject)
        save_data(self.data)
        self._flash_subject = subject
        self.show_subjects()
        self.toast(f"Added subject: {subject}")

    def delete_subject(self, subject):
        if messagebox.askyesno(
            "Delete Subject",
            f"Delete {subject}?"
        ):
            self.data["subjects"].remove(subject)
            save_data(self.data)
            self.show_subjects()
            self.toast(f"Deleted subject: {subject}", "info")

    # =========================================================
    # TASKS
    # =========================================================

    def show_tasks(self):
        self.current_page = "Tasks"
        self.clear_page()
        self.set_active_nav("Tasks")

        self.page_header(
            "Task Manager",
            "Create, organize and complete your academic tasks."
        )

        form = self.card()
        form.pack(fill="x", pady=(0, 20))

        self.section_title(form, "Create a New Task")

        title_row = tk.Frame(form, bg=self.card_bg)
        title_row.pack(fill="x", pady=5)

        tk.Label(
            title_row,
            text="Task title",
            bg=self.card_bg,
            fg=self.muted
        ).pack(anchor="w")

        self.task_title_entry = self.make_entry(title_row)
        self.task_title_entry.pack(fill="x", ipady=8, pady=(5, 8))

        details_row = tk.Frame(form, bg=self.card_bg)
        details_row.pack(fill="x", pady=5)

        # Date
        date_box = tk.Frame(details_row, bg=self.card_bg)
        date_box.pack(side="left", fill="x", expand=True, padx=(0, 10))

        tk.Label(
            date_box,
            text="Due date (YYYY-MM-DD)",
            bg=self.card_bg,
            fg=self.muted
        ).pack(anchor="w")

        self.task_date_entry = self.make_entry(date_box)
        self.task_date_entry.insert(0, date.today().isoformat())
        self.task_date_entry.pack(fill="x", ipady=8, pady=(5, 0))

        # Subject
        subject_box = tk.Frame(details_row, bg=self.card_bg)
        subject_box.pack(side="left", fill="x", expand=True, padx=10)

        tk.Label(
            subject_box,
            text="Subject",
            bg=self.card_bg,
            fg=self.muted
        ).pack(anchor="w")

        subjects = ["General"] + self.data["subjects"]

        self.task_subject_var = tk.StringVar(value=subjects[0])

        subject_combo = ttk.Combobox(
            subject_box,
            textvariable=self.task_subject_var,
            values=subjects,
            state="readonly"
        )
        subject_combo.pack(fill="x", ipady=5, pady=(5, 0))

        # Priority
        priority_box = tk.Frame(details_row, bg=self.card_bg)
        priority_box.pack(side="left", fill="x", expand=True, padx=(10, 0))

        tk.Label(
            priority_box,
            text="Priority",
            bg=self.card_bg,
            fg=self.muted
        ).pack(anchor="w")

        self.task_priority_var = tk.StringVar(value="Medium")

        priority_combo = ttk.Combobox(
            priority_box,
            textvariable=self.task_priority_var,
            values=["Low", "Medium", "High"],
            state="readonly"
        )
        priority_combo.pack(fill="x", ipady=5, pady=(5, 0))

        self.styled_button(
            form,
            "Add Task",
            self.add_task
        ).pack(anchor="w", pady=(15, 0))

        # Task list
        list_card = self.card()
        list_card.pack(fill="x", pady=(0, 20))

        self.section_title(list_card, "All Tasks")
        self.create_task_progress(list_card)

        table_frame = tk.Frame(list_card, bg=self.card_bg)
        table_frame.pack(fill="both", expand=True)

        columns = ("title", "date", "subject", "priority", "status")

        self.task_tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            height=9
        )

        self.task_tree.heading("title", text="Task")
        self.task_tree.heading("date", text="Due Date")
        self.task_tree.heading("subject", text="Subject")
        self.task_tree.heading("priority", text="Priority")
        self.task_tree.heading("status", text="Status")

        self.task_tree.column("title", width=220, minwidth=120)
        self.task_tree.column("date", width=110, minwidth=90)
        self.task_tree.column("subject", width=140, minwidth=90)
        self.task_tree.column("priority", width=90, minwidth=70)
        self.task_tree.column("status", width=100, minwidth=80)

        task_scrollbar = ttk.Scrollbar(
            table_frame,
            orient="vertical",
            command=self.task_tree.yview
        )

        self.task_tree.configure(
            yscrollcommand=task_scrollbar.set
        )

        self.task_tree.pack(side="left", fill="both", expand=True)
        task_scrollbar.pack(side="right", fill="y")

        for index, task in enumerate(self.data["tasks"]):
            status = (
                "Completed"
                if task.get("completed")
                else "Pending"
            )

            self.task_tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    task.get("title", ""),
                    task.get("date", ""),
                    task.get("subject", "General"),
                    task.get("priority", "Medium"),
                    status
                ),
                tags=self.task_row_tags(task)
            )

        self.style_task_tree(self.task_tree)

        buttons = tk.Frame(list_card, bg=self.card_bg)
        buttons.pack(fill="x", pady=(12, 0))

        self.styled_button(
            buttons,
            "Mark Complete",
            self.complete_task,
            self.green
        ).pack(side="left", padx=(0, 8))

        self.styled_button(
            buttons,
            "Delete Selected",
            self.delete_task,
            self.red
        ).pack(side="left", padx=8)

    def add_task(self):
        title = self.task_title_entry.get().strip()
        task_date = self.task_date_entry.get().strip()

        if not title:
            self.shake(self.task_title_entry)
            self.toast("Please enter a task title.", "error")
            return

        try:
            datetime.strptime(task_date, "%Y-%m-%d")
        except ValueError:
            self.shake(self.task_date_entry)
            self.toast("Enter the date as YYYY-MM-DD.", "error")
            return

        task = {
            "title": title,
            "date": task_date,
            "subject": self.task_subject_var.get(),
            "priority": self.task_priority_var.get(),
            "completed": False,
            "created_at": datetime.now().isoformat()
        }

        self.data["tasks"].append(task)
        save_data(self.data)
        self._flash_task_index = len(self.data["tasks"]) - 1
        self._flash_task_color = self.accent
        self.show_tasks()
        self.toast(f"Task added: {title}")

    def complete_task(self):
        selected = self.task_tree.selection()

        if not selected:
            self.toast("Please select a task first.", "warning")
            return

        index = int(selected[0])
        self.data["tasks"][index]["completed"] = True

        save_data(self.data)
        self._flash_task_index = index
        self._flash_task_color = self.green
        self.show_tasks()
        self.toast("Task completed - great job!")

    def delete_task(self):
        selected = self.task_tree.selection()

        if not selected:
            self.toast("Please select a task first.", "warning")
            return

        index = int(selected[0])

        if messagebox.askyesno(
            "Delete Task",
            "Are you sure you want to delete this task?"
        ):
            del self.data["tasks"][index]
            save_data(self.data)
            self.show_tasks()
            self.toast("Task deleted.", "info")

    # =========================================================
    # SMART SCHEDULER
    # =========================================================

    def show_scheduler(self):
        self.current_page = "Smart Scheduler"
        self.clear_page()
        self.set_active_nav("Smart Scheduler")

        self.page_header(
            "Smart Scheduler",
            "A simple suggested plan based on your pending tasks."
        )

        card = self.card()
        card.pack(fill="x")

        self.section_title(card, "Suggested Study Plan")

        pending = [
            task for task in self.data["tasks"]
            if not task.get("completed")
        ]

        pending.sort(
            key=lambda task: (
                {"High": 0, "Medium": 1, "Low": 2}.get(
                    task.get("priority", "Medium"), 1
                ),
                task.get("date", "9999-12-31")
            )
        )

        if not pending:
            tk.Label(
                card,
                text="No pending tasks. You're doing great!",
                bg=self.card_bg,
                fg=self.green,
                font=("Segoe UI", 11)
            ).pack(anchor="w")
            return

        total_minutes = sum(
            45 if task.get("priority") == "High" else 30
            for task in pending
        )

        summary = tk.Label(
            card,
            text="",
            bg=self.card_bg,
            fg=self.muted,
            font=("Segoe UI", 10)
        )
        summary.pack(anchor="w", pady=(0, 10))

        self.typewrite(
            summary,
            f"{len(pending)} task(s) planned  •  "
            f"about {total_minutes} minutes in total",
            delay=18
        )

        for index, task in enumerate(pending):
            duration = 45 if task.get("priority") == "High" else 30
            self.render_schedule_item(card, index, task, duration)

    # =========================================================
    # LECTURE HUB
    # =========================================================

    def show_lecture_hub(self):
        self.current_page = "Lecture Hub"
        self.clear_page()
        self.set_active_nav("Lecture Hub")

        self.page_header(
            "Lecture Hub",
            "Find educational lectures and tutorials on YouTube."
        )

        # Search Card
        search_card = self.card()
        search_card.pack(fill="x", pady=(0, 20))

        self.section_title(search_card, "Search Lectures")

        tk.Label(
            search_card,
            text="Enter a topic or subject",
            bg=self.card_bg,
            fg=self.muted
        ).pack(anchor="w", pady=(5, 5))

        self.lecture_search_entry = self.make_entry(search_card)
        self.lecture_search_entry.pack(
            fill="x",
            ipady=9,
            pady=(0, 12)
        )

        self.animate_placeholder(
            self.lecture_search_entry,
            [
                "Try: Photosynthesis explained",
                "Try: Algebra for beginners",
                "Try: Causes of World War II",
                "Try: English grammar basics",
                "Try: How the human heart works",
                "Try: Python for beginners",
            ]
        )

        tk.Label(
            search_card,
            text="Select Subject",
            bg=self.card_bg,
            fg=self.muted
        ).pack(anchor="w", pady=(5, 5))

        subjects = ["All Subjects"] + self.data["subjects"]

        self.lecture_subject_var = tk.StringVar(
            value="All Subjects"
        )

        ttk.Combobox(
            search_card,
            textvariable=self.lecture_subject_var,
            values=subjects,
            state="readonly"
        ).pack(fill="x", pady=(0, 12))

        search_buttons = tk.Frame(search_card, bg=self.card_bg)
        search_buttons.pack(anchor="w")

        self.styled_button(
            search_buttons,
            "Search on YouTube",
            self.search_youtube
        ).pack(side="left")

        self.styled_button(
            search_buttons,
            "Open in Browser",
            self.open_search_in_browser,
            self.accent2
        ).pack(side="left", padx=8)

        self.styled_button(
            search_buttons,
            "Pop-out Player",
            self.open_player_window,
            self.green
        ).pack(side="left")

        self.lecture_search_entry.bind(
            "<Return>",
            lambda event: self.search_youtube()
        )

        # Embedded Video Player
        player_card = self.card()
        player_card.pack(fill="x", pady=(0, 20))

        self.section_title(player_card, "Now Playing")

        self.lecture_player_frame = tk.Frame(
            player_card,
            bg="#000000",
            height=450
        )

        self.lecture_player_frame.pack(
            fill="both",
            expand=True
        )

        self.lecture_player_frame.pack_propagate(False)

        self.lecture_player = EmbeddedYouTube(
            self.root,
            self.lecture_player_frame
        )

        # Explore Topics
        quick_card = self.card()
        quick_card.pack(fill="x")

        self.section_title(
            quick_card,
            "Explore Learning Topics"
        )

        personal = self.data["subjects"][:9]

        if personal:
            tk.Label(
                quick_card,
                text="Your subjects",
                bg=self.card_bg,
                fg=self.muted,
                font=("Segoe UI", 9, "bold")
            ).pack(anchor="w", pady=(0, 6))

            self._topic_buttons(quick_card, personal, self.accent2)

        tk.Label(
            quick_card,
            text="Popular topics for every learner",
            bg=self.card_bg,
            fg=self.muted,
            font=("Segoe UI", 9, "bold")
        ).pack(anchor="w", pady=(0, 6))

        self._topic_buttons(quick_card, EXPLORE_TOPICS)

    # =========================================================
    # YOUTUBE SEARCH
    # =========================================================

    def search_youtube(self):

        query = self.lecture_search_entry.get().strip()

        if not query:
            messagebox.showwarning(
                "Empty Search",
                "Please enter a lecture topic."
            )
            return

        subject = self.lecture_subject_var.get()

        if subject != "All Subjects":
            query = subject + " " + query

        search_url = (
            "https://www.youtube.com/results?search_query="
            + quote_plus(query)
        )

        self.lecture_player.load(search_url)

    def open_search_in_browser(self):
        """Fallback: open the YouTube search in your normal web browser."""

        query = self.lecture_search_entry.get().strip()

        if not query:
            messagebox.showwarning(
                "Empty Search",
                "Please enter a lecture topic."
            )
            return

        subject = self.lecture_subject_var.get()

        if subject != "All Subjects":
            query = subject + " " + query

        webbrowser.open(
            "https://www.youtube.com/results?search_query="
            + quote_plus(query)
        )

    def open_player_window(self):
        """Open the YouTube search in a separate player window (lecture_player.py)."""

        query = self.lecture_search_entry.get().strip()

        if not query:
            messagebox.showwarning(
                "Empty Search",
                "Please enter a lecture topic."
            )
            return

        subject = self.lecture_subject_var.get()

        if subject != "All Subjects":
            query = subject + " " + query

        url = (
            "https://www.youtube.com/results?search_query="
            + quote_plus(query)
        )

        script = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "lecture_player.py"
        )

        try:
            subprocess.Popen([sys.executable, script, url])
        except Exception as error:
            messagebox.showerror("Player Error", str(error))

    # =========================================================
    # LEARNER PROFILE, TOPICS AND FIRST-RUN SETUP
    # =========================================================

    def learner_context(self):
        """Describes the learner to the AI so it adapts to any level/subject."""
        profile = self.data["profile"]

        level = (profile.get("level") or "").strip()
        course = (profile.get("course") or "").strip()
        subjects = self.data["subjects"][:12]

        parts = []

        if level:
            parts.append(f"Education level: {level}.")

        if course:
            parts.append(f"Course, class or field: {course}.")

        if subjects:
            parts.append("Subjects they study: " + ", ".join(subjects) + ".")

        if not parts:
            return (
                "The learner's level is unknown, so infer it from their "
                "questions and adapt your depth to it. "
            )

        return (
            " ".join(parts)
            + " Match your vocabulary and depth to this level. "
        )

    def _topic_buttons(self, parent, topics, color=None):
        grid = tk.Frame(parent, bg=self.card_bg)
        grid.pack(fill="x", pady=(0, 14))

        columns = 3

        for column in range(columns):
            grid.grid_columnconfigure(column, weight=1, uniform="topic")

        for index, topic in enumerate(topics):
            button = self.styled_button(
                grid,
                topic,
                lambda t=topic: self.open_youtube_topic(t),
                color
            )
            button.grid(
                row=index // columns,
                column=index % columns,
                sticky="ew",
                padx=4,
                pady=4
            )

    def quick_add_subject(self, name):
        self.subject_entry.delete(0, "end")
        self.subject_entry.insert(0, name)
        self.add_subject()

    def maybe_show_onboarding(self):
        settings = self.data["settings"]
        profile = self.data["profile"]

        if (
            settings.get("onboarded")
            or profile.get("course")
            or profile.get("level")
            or self.data["subjects"]
        ):
            return

        self.show_onboarding()

    def show_onboarding(self):
        settings = self.data["settings"]
        profile = self.data["profile"]

        win = tk.Toplevel(self.root)
        win.title("Welcome to StudyMate")
        win.configure(bg=self.bg)
        win.resizable(False, False)
        win.transient(self.root)

        width, height = 600, 720
        x = self.root.winfo_rootx() + max(0, (self.root.winfo_width() - width) // 2)
        y = self.root.winfo_rooty() + max(0, (self.root.winfo_height() - height) // 2)
        win.geometry(f"{width}x{height}+{x}+{y}")

        body = tk.Frame(win, bg=self.bg, padx=30, pady=24)
        body.pack(fill="both", expand=True)

        def label(text, pady=(0, 0), font=("Segoe UI", 10), fg=None, wrap=0):
            tk.Label(
                body,
                text=text,
                bg=self.bg,
                fg=fg or self.muted,
                font=font,
                wraplength=wrap,
                justify="left"
            ).pack(anchor="w", pady=pady)

        label(
            "Welcome to StudyMate",
            font=("Georgia", 22, "bold"),
            fg=self.text
        )
        label(
            "Tell us a little about you so StudyMate can adapt to your level "
            "and subjects. You can change everything later in Profile.",
            pady=(6, 16),
            wrap=540
        )

        label("Education level")
        level_box = ttk.Combobox(
            body, values=EDUCATION_LEVELS, state="readonly"
        )
        level_box.set(profile.get("level") or "")
        level_box.pack(fill="x", pady=(4, 12), ipady=4)

        label("Course, class or field of study (optional)")
        course_entry = self.make_entry(body)
        course_entry.insert(0, profile.get("course", ""))
        course_entry.pack(fill="x", ipady=8, pady=(4, 12))

        label("Language for voice input")
        current_code = settings.get("voice_language", "en-IN")
        language_box = ttk.Combobox(
            body,
            values=[name for name, code in VOICE_LANGUAGES],
            state="readonly"
        )
        language_box.set(
            next(
                (name for name, code in VOICE_LANGUAGES if code == current_code),
                "English (India)"
            )
        )
        language_box.pack(fill="x", pady=(4, 12), ipady=4)

        label("Pick the subjects you study (tap to select)")

        chip_area = tk.Frame(body, bg=self.bg)
        chip_area.pack(fill="x", pady=(4, 10))

        for column in range(4):
            chip_area.grid_columnconfigure(column, weight=1, uniform="onb")

        selected = {
            name for name in SUBJECT_SUGGESTIONS
            if name in self.data["subjects"]
        }
        chips = {}

        def paint(name):
            if name in selected:
                chips[name].configure(bg=self.accent, fg=self.btn_text)
            else:
                chips[name].configure(bg=self.surface, fg=self.text)

        def toggle(name):
            if name in selected:
                selected.discard(name)
            else:
                selected.add(name)

            paint(name)

        for index, name in enumerate(SUBJECT_SUGGESTIONS):
            chip = tk.Label(
                chip_area,
                text=name,
                font=("Segoe UI", 9),
                padx=6,
                pady=6,
                cursor="hand2",
                bg=self.surface,
                fg=self.text
            )
            chip.grid(
                row=index // 4, column=index % 4,
                sticky="ew", padx=3, pady=3
            )
            chip.bind("<Button-1>", lambda event, n=name: toggle(n))
            chips[name] = chip
            paint(name)

        buttons = tk.Frame(body, bg=self.bg)
        buttons.pack(fill="x", pady=(10, 0))

        def finish(skip=False):
            settings["onboarded"] = True

            if not skip:
                profile["level"] = level_box.get().strip()
                profile["course"] = course_entry.get().strip()

                for name in SUBJECT_SUGGESTIONS:
                    if name in selected and name not in self.data["subjects"]:
                        self.data["subjects"].append(name)

                chosen = language_box.get()

                for name, code in VOICE_LANGUAGES:
                    if name == chosen:
                        settings["voice_language"] = code
                        self.voice_language = code

            save_data(self.data)

            try:
                win.grab_release()
            except tk.TclError:
                pass

            win.destroy()

            self.nav_commands.get(self.current_page, self.show_dashboard)()

            if not skip:
                self.toast("You're all set. Welcome to StudyMate!")

        self.styled_button(
            buttons, "Get Started", lambda: finish(False)
        ).pack(side="left")

        self.styled_button(
            buttons, "Skip for now", lambda: finish(True), self.accent2
        ).pack(side="left", padx=10)

        win.protocol("WM_DELETE_WINDOW", lambda: finish(True))

        try:
            win.grab_set()
        except tk.TclError:
            pass

    def open_youtube_topic(self, topic):

        search_url = (
            "https://www.youtube.com/results?search_query="
            + quote_plus(topic + " lectures")
        )

        self.lecture_player.load(search_url)

    # =========================================================
    # AI ASSISTANT
    # =========================================================

    def show_ai_assistant(self):
        self.current_page = "AI Assistant"
        self.clear_page()
        self.set_active_nav("AI Assistant")

        persona = self.jarvis_persona()

        self.ai_name = (
            "StudyMate AI" if persona["key"] == "CLASSIC" else persona["label"]
        )
        self.hud_color = persona["palette"]["main"]

        if persona["key"] == "CLASSIC":
            self.page_header(
                "AI Learning Assistant",
                "Ask questions, understand concepts and get study help."
            )
        else:
            self.page_header(
                f"{persona['full']} Interface",
                "Voice-enabled AI study companion. Click the reactor core to talk."
            )

        boot = not self._jarvis_booted

        if boot:
            self._jarvis_booted = True
            self.apply_persona_voice(persona["key"])

        hud_card = self.card(padx=18, pady=14)
        hud_card.pack(fill="x", pady=(0, 18))

        JarvisPanel(
            hud_card,
            self,
            JARVIS_PERSONAS,
            persona["key"],
            persona["palette"],
            boot=boot
        ).pack(fill="x")

        chat_card = self.card()
        chat_card.pack(fill="both", expand=True, pady=(0, 18))

        self.section_title(chat_card, "Conversation")

        self.ai_output = tk.Text(
            chat_card,
            height=13,
            bg=self.bg,
            fg=self.text,
            insertbackground=self.text,
            relief="flat",
            bd=0,
            wrap="word",
            font=("Segoe UI", 10),
            padx=12,
            pady=12,
            state="disabled"
        )
        self.ai_output.pack(fill="both", expand=True)

        for item in self.ai_history[-30:]:
            self.append_ai_message(
                item.get("role", "assistant"),
                item.get("text", "")
            )

        # Returning to the page while a reply is still pending
        if self.ai_request_pending:
            self.root.after(
                80,
                lambda: (
                    self.ai_request_pending
                    and self.current_page == "AI Assistant"
                    and self.start_thinking()
                )
            )

        input_card = self.card()
        input_card.pack(fill="x")

        self.section_title(input_card, "Your Question")

        self.create_prompt_chips(input_card)

        self.ai_input = self.make_text(input_card, height=4)
        self.ai_input.pack(fill="x", pady=(0, 10))

        button_row = tk.Frame(input_card, bg=self.card_bg)
        button_row.pack(fill="x")

        self.styled_button(
            button_row,
            "🖼️ Attach Image",
            self.attach_image,
            self.accent2
        ).pack(side="left", padx=(0, 8))

        self.styled_button(
            button_row,
            "📄 Attach File",
            self.attach_document,
            self.accent2
        ).pack(side="left", padx=(0, 8))

        self.ai_send_button = self.styled_button(
            button_row,
            "Send Message",
            self.send_ai_message
        )
        self.ai_send_button.pack(side="left")

        if self.ai_request_pending:
            self.ai_send_button.configure(state="disabled")

        self.styled_button(
            button_row,
            "Microphone",
            self.start_voice_input
        ).pack(side="left", padx=8)

        self.styled_button(
            button_row,
            "Stop Speaking",
            self.stop_ai_speech,
            self.red
        ).pack(side="left", padx=8)

        self.voice_toggle_button = self.styled_button(
            button_row,
            "Voice: ON" if self.voice_enabled else "Voice: OFF",
            self.toggle_voice
        )
        self.voice_toggle_button.pack(side="left", padx=8)

        self.styled_button(
            button_row,
            "Remove Attachment",
            self.clear_attachment,
            self.orange
        ).pack(side="left", padx=8)

        self.styled_button(
            button_row,
            "Clear Chat",
            self.clear_ai_chat,
            self.red
        ).pack(side="left", padx=8)

        self.ai_file_label = tk.Label(
            input_card,
            text=(
                f"Attached: {self.attached_file_name}"
                if self.attached_file_name
                else "No file attached."
            ),
            bg=self.card_bg,
            fg=self.muted,
            font=("Segoe UI", 9)
        )
        self.ai_file_label.pack(anchor="w", pady=(10, 0))

        self.ai_status = tk.Label(
            input_card,
            text="Enter = send  |  Shift+Enter = new line",
            bg=self.card_bg,
            fg=self.muted,
            font=("Segoe UI", 9)
        )
        self.ai_status.pack(anchor="w", pady=(5, 0))

    # =========================================================
    # JARVIS / FRIDAY INTERFACE
    # =========================================================

    def jarvis_persona(self):
        key = self.data["settings"].get("ai_persona", "JARVIS")

        if key not in JARVIS_PERSONAS:
            key = "JARVIS"

        persona = dict(JARVIS_PERSONAS[key])
        persona["key"] = key

        if not persona.get("palette"):
            persona["palette"] = {
                "main": self.accent,
                "alt": self.accent2,
                "warm": self.orange
            }

        return persona

    def jarvis_first_name(self):
        return (self.data["profile"].get("name") or "Student").split()[0]

    def _set_status(self, text, color=None):
        try:
            self.ai_status.configure(text=text, fg=color or self.muted)
        except (tk.TclError, AttributeError):
            pass

    def _voice_busy(self):
        if time.time() < self._speak_pending_until:
            return True

        assistant = self.voice_assistant

        if assistant is None:
            return False

        check = getattr(assistant, "is_speaking", None)

        try:
            return bool(check()) if callable(check) else False
        except Exception:
            return False

    def jarvis_state(self):
        """Read by the HUD every frame: standby/listening/thinking/speaking."""
        if self.jarvis_listening:
            return "listening"

        if self.ai_request_pending:
            return "thinking"

        if self._voice_busy() or getattr(self, "_ai_typing", False):
            return "speaking"

        return "standby"

    def jarvis_telemetry(self):
        now = datetime.now()
        today = date.today().isoformat()

        pending = sum(
            1 for task in self.data["tasks"]
            if not task.get("completed", False)
        )

        studied = sum(
            session.get("minutes", 0)
            for session in self.data["study_sessions"]
            if session.get("date") == today
        )

        goal = self.data["profile"].get("daily_goal", 120)
        streak = self.study_streak()

        return [
            ("SYS TIME", now.strftime("%H:%M:%S")),
            ("DATE", now.strftime("%a %d %b").upper()),
            ("TASKS PENDING", str(pending)),
            ("STUDIED TODAY", f"{studied}/{goal} MIN"),
            ("STREAK", f"{streak} DAY{'S' if streak != 1 else ''}"),
            ("VOICE", "ONLINE" if self.voice_assistant else "OFFLINE"),
            ("NEURAL LINK", "GEMINI"),
            ("HANDS-FREE", "ARMED" if self.jarvis_handsfree else "OFF"),
        ]

    def jarvis_boot_lines(self):
        persona = self.jarvis_persona()
        first = self.jarvis_first_name().upper()
        voice = "ONLINE" if self.voice_assistant else "OFFLINE"

        return [
            f"> BOOTING {persona['full'].upper()} CORE ........ OK",
            f"> VOICE INTERFACE ............ {voice}",
            "> NEURAL LINK (GEMINI) ....... ESTABLISHED",
            "> CLOUD SYNC ................. ACTIVE",
            f"> USER {first} ........ AUTHENTICATED",
        ]

    def jarvis_greet(self):
        persona = self.jarvis_persona()
        hour = datetime.now().hour
        part = (
            "Good morning" if hour < 12
            else "Good afternoon" if hour < 17
            else "Good evening"
        )
        first = self.jarvis_first_name()

        if persona["key"] == "JARVIS":
            greeting = f"{part}, {first}. All systems are online. How may I assist you?"
        elif persona["key"] == "FRIDAY":
            greeting = f"{part}, boss. Friday online and ready. What do we tackle first?"
        else:
            return

        if self.current_page != "AI Assistant":
            return

        self._set_status(greeting, self.green)

        if self.voice_enabled:
            self._speak_text(greeting)

    def apply_persona_voice(self, key):
        assistant = self.voice_assistant
        persona = JARVIS_PERSONAS.get(key)

        if assistant is None or not persona or not persona.get("voice_hints"):
            return

        try:
            voices = assistant.get_available_voices()
            chosen = None

            for hint in persona["voice_hints"]:
                for voice in voices:
                    if hint in voice["name"].lower():
                        chosen = voice["index"]
                        break

                if chosen is not None:
                    break

            if chosen is not None:
                assistant.set_voice(chosen)

            assistant.set_speed(persona["rate"])

        except Exception as error:
            print("Voice selection warning:", error)

    def jarvis_set_persona(self, key):
        if key not in JARVIS_PERSONAS:
            return

        if key == self.data["settings"].get("ai_persona", "JARVIS"):
            return

        self.data["settings"]["ai_persona"] = key
        save_data(self.data)

        self.apply_persona_voice(key)

        # Wake word changes with the persona; restart the awake window
        self._jarvis_awake_until = 0

        self.show_ai_assistant()

    def jarvis_system_prompt(self):
        persona = self.jarvis_persona()

        if persona["key"] == "CLASSIC":
            return CLASSIC_PROMPT + " " + self.learner_context()

        profile = self.data["profile"]
        today = date.today().isoformat()

        pending = sum(
            1 for task in self.data["tasks"]
            if not task.get("completed", False)
        )

        studied = sum(
            session.get("minutes", 0)
            for session in self.data["study_sessions"]
            if session.get("date") == today
        )

        context = (
            f"Context: the user's first name is {self.jarvis_first_name()}. "
            f"{self.learner_context()}"
            f"Right now it is {datetime.now().strftime('%A %d %B %Y, %H:%M')}. "
            f"They have {pending} pending tasks and have studied {studied} of "
            f"{profile.get('daily_goal', 120)} minutes today. "
        )

        return persona["prompt"] + context + VOICE_FRIENDLY_RULES

    # ---------------------------------------------------------
    # Core click + hands-free
    # ---------------------------------------------------------

    def jarvis_core_click(self):
        if self.voice_assistant is None:
            messagebox.showwarning(
                "Voice Unavailable",
                "Voice assistant is not initialized."
            )
            return

        if self._voice_busy():
            self.stop_ai_speech()
            return

        if self.ai_request_pending or self.jarvis_listening:
            return

        self._listen_once("send")

    def toggle_handsfree(self):
        if self.voice_assistant is None:
            messagebox.showwarning(
                "Voice Unavailable",
                "Voice assistant is not initialized."
            )
            return

        self.jarvis_handsfree = not self.jarvis_handsfree

        if self._handsfree_job is not None:
            try:
                self.root.after_cancel(self._handsfree_job)
            except Exception:
                pass

            self._handsfree_job = None

        if self.jarvis_handsfree:
            wake = self.jarvis_persona()["wake"].title()
            self._jarvis_awake_until = 0
            self._hf_was_busy = False

            self._set_status(
                f'Hands-free armed. Say "{wake}" to wake me.',
                self.green
            )

            self._handsfree_tick()

        else:
            self._set_status("Hands-free disabled.", self.muted)

    def _handsfree_tick(self):
        self._handsfree_job = None

        if not self.jarvis_handsfree:
            return

        # Never keep the microphone open on other pages
        if self.current_page != "AI Assistant":
            self.jarvis_handsfree = False
            return

        working = (
            self.ai_request_pending
            or getattr(self, "_ai_typing", False)
            or self._voice_busy()
        )

        # After a reply finishes, follow-up commands need no wake word
        if self._hf_was_busy and not working:
            self._jarvis_awake_until = time.time() + 12

        self._hf_was_busy = working

        if not working and not self.jarvis_listening:
            self._listen_once("wake")

        self._handsfree_job = self.root.after(600, self._handsfree_tick)

    def _strip_wake_word(self, text):
        """Returns the command, '' if only the wake word was said, or None."""
        wake = self.jarvis_persona()["wake"]

        pattern = r"\b(?:hey|hi|ok|okay)?\s*,?\s*" + re.escape(wake) + r"\b[\s,.!:;-]*"
        match = re.search(pattern, text, flags=re.IGNORECASE)

        if match:
            return (text[:match.start()] + " " + text[match.end():]).strip()

        if time.time() < self._jarvis_awake_until:
            return text.strip()

        return None

    def _listen_once(self, mode):
        """mode: 'insert' = fill the box, 'send' = auto-send, 'wake' = hands-free."""
        if self.voice_assistant is None or self.jarvis_listening:
            return

        self.jarvis_listening = True

        if mode != "wake":
            self._set_status("Listening... speak now.", self.orange)

        def worker():
            spoken = None
            problem = None

            try:
                spoken = self.voice_assistant.listen(
                    timeout=4 if mode == "wake" else 5,
                    phrase_time_limit=12,
                    language=self.voice_language
                )
            except Exception as error:
                problem = str(error)

            try:
                self.root.after(
                    0,
                    lambda: self._listen_done(mode, spoken, problem)
                )
            except Exception:
                self.jarvis_listening = False

        threading.Thread(target=worker, daemon=True).start()

    def _listen_done(self, mode, spoken, problem):
        self.jarvis_listening = False

        if self.current_page != "AI Assistant":
            return

        if problem:
            if mode == "wake":
                self.jarvis_handsfree = False

            self._set_status(f"Voice error: {problem}", self.red)
            return

        if not spoken:
            if mode != "wake":
                self._set_status("No speech detected.", self.muted)
            return

        if mode == "insert":
            try:
                self.ai_input.insert("end", spoken)
            except tk.TclError:
                return

            self._set_status("Voice input received.", self.green)
            return

        if mode == "wake":
            command = self._strip_wake_word(spoken)

            if command is None:
                return

            if not command:
                self._jarvis_awake_until = time.time() + 12
                self._set_status("Yes? I'm listening.", self.green)
                self._speak_text("Yes?")
                return

            spoken = command

        try:
            self.ai_input.delete("1.0", "end")
            self.ai_input.insert("1.0", spoken)
        except tk.TclError:
            return

        self.send_ai_message()

    def append_ai_message(self, role, text):
        self.ai_insert_message(role, text, animated=False)

    # =========================================================
    # AI ASSISTANT - SENDING MESSAGES
    # =========================================================

    def send_ai_message(self):

        if self.ai_request_pending or getattr(self, "_ai_typing", False):
            return

        question = self.ai_input.get("1.0", "end").strip()

        if (
            not question
            and not self.attached_file_text
            and not self.attached_image_data
        ):
            messagebox.showwarning(
                "Empty Message",
                "Please enter a question or attach a file/image."
            )
            return

        api_key = os.environ.get("GEMINI_API_KEY", "").strip()

        if not api_key:
            messagebox.showerror(
                "API Key Missing",
                "Gemini API key was not found.\n\n"
                "Set GEMINI_API_KEY in your terminal before starting StudyMate."
            )
            return

        if not question:
            question = "Please analyse the attached material and explain it."

        self.ai_history.append({
            "role": "user",
            "text": question
        })

        self.data["ai_history"] = self.ai_history[-100:]
        save_data(self.data)

        self.append_ai_message("user", question)

        self.ai_input.delete("1.0", "end")

        self.ai_request_pending = True
        self.ai_send_button.configure(state="disabled")

        self.ai_status.configure(
            text="StudyMate AI is thinking...",
            fg=self.orange
        )

        self.start_thinking()

        conversation_history = self.ai_history[:-1][-12:]

        # Take attachment snapshots before starting the thread
        attachment_text = self.attached_file_text
        image_data = self.attached_image_data
        image_mime = self.attached_image_mime

        # Attachments are used for this message only
        self.clear_attachment(silent=True)

        threading.Thread(
            target=self.ask_gemini,
            args=(
                question,
                api_key,
                conversation_history,
                attachment_text,
                image_data,
                image_mime
            ),
            daemon=True
        ).start()

    # =========================================================
    # AI ASSISTANT - ATTACHMENTS
    # =========================================================

    def clear_attachment(self, silent=False):
        self.attached_file_name = None
        self.attached_file_text = ""
        self.attached_image_data = None
        self.attached_image_mime = None

        label = getattr(self, "ai_file_label", None)

        if label is not None:
            try:
                label.configure(
                    text="No file attached.",
                    fg=self.muted
                )
            except tk.TclError:
                pass

        if not silent:
            status = getattr(self, "ai_status", None)

            if status is not None:
                try:
                    status.configure(
                        text="Attachment removed.",
                        fg=self.muted
                    )
                except tk.TclError:
                    pass

    def attach_document(self):

        file_path = filedialog.askopenfilename(
            title="Select a document",
            filetypes=[
                ("Supported Documents", "*.pdf *.docx *.txt"),
                ("PDF Files", "*.pdf"),
                ("Word Documents", "*.docx"),
                ("Text Files", "*.txt"),
                ("All Files", "*.*")
            ]
        )

        if file_path:
            self._process_attachment(file_path)

    def attach_image(self):

        file_path = filedialog.askopenfilename(
            title="Select an image",
            filetypes=[
                ("Supported Images", "*.png *.jpg *.jpeg *.webp"),
                ("PNG Images", "*.png"),
                ("JPG Images", "*.jpg *.jpeg"),
                ("WEBP Images", "*.webp"),
                ("All Files", "*.*")
            ]
        )

        if file_path:
            self._process_attachment(file_path)

    def _process_attachment(self, file_path):

        try:
            extension = os.path.splitext(file_path)[1].lower()

            image_types = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".webp": "image/webp"
            }

            file_name = os.path.basename(file_path)

            # Temporary values: don't change current attachment yet
            new_text = ""
            new_image_data = None
            new_image_mime = None

            if extension in image_types:

                with open(file_path, "rb") as image_file:
                    image_bytes = image_file.read()

                if len(image_bytes) > 15 * 1024 * 1024:
                    raise ValueError(
                        "Please select an image smaller than 15 MB."
                    )

                new_image_data = base64.b64encode(
                    image_bytes
                ).decode("utf-8")

                new_image_mime = image_types[extension]

            elif extension in (".pdf", ".docx", ".txt"):

                new_text = extract_text(file_path)

                if not new_text or not new_text.strip():
                    raise ValueError(
                        "No readable text was found in this document."
                    )

            else:
                raise ValueError("Unsupported file format.")

            # Commit only after successful processing
            self.attached_file_name = file_name
            self.attached_file_text = new_text
            self.attached_image_data = new_image_data
            self.attached_image_mime = new_image_mime

            self.ai_file_label.configure(
                text=f"Attached: {file_name}",
                fg=self.green
            )

            self.ai_status.configure(
                text="Attachment added successfully.",
                fg=self.green
            )

        except Exception as error:

            messagebox.showerror(
                "Attachment Error",
                str(error)
            )

    # =========================================================
    # GEMINI API REQUEST
    # =========================================================

    def ask_gemini(
        self,
        question,
        api_key,
        conversation_history,
        attachment_text="",
        image_data=None,
        image_mime=None
    ):
        try:
            url = (
                "https://generativelanguage.googleapis.com/v1beta/"
                f"models/{GEMINI_MODEL}:generateContent"
            )

            contents = []

            # Previous conversation
            for item in conversation_history:
                role = item.get("role")
                message = item.get("text", "")

                if role not in ("user", "assistant") or not message:
                    continue

                contents.append({
                    "role": "user" if role == "user" else "model",
                    "parts": [{"text": message}]
                })

            # Current question
            current_parts = [{"text": question}]

            # Add document text
            if attachment_text:
                current_parts.append({
                    "text": (
                        "\n\nAttached document content:\n"
                        + attachment_text[:30000]
                    )
                })

            # Add image data
            if image_data and image_mime:
                current_parts.append({
                    "inline_data": {
                        "mime_type": image_mime,
                        "data": image_data
                    }
                })

            contents.append({
                "role": "user",
                "parts": current_parts
            })

            payload = {
                "system_instruction": {
                    "parts": [{"text": self.jarvis_system_prompt()}]
                },
                "contents": contents
            }

            request = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": api_key
                },
                method="POST"
            )

            with urllib.request.urlopen(request, timeout=120) as response:
                result = json.loads(response.read().decode("utf-8"))

            # Safe parsing: handles blocked or empty replies
            candidates = result.get("candidates") or []

            if not candidates:
                feedback = result.get("promptFeedback", {})
                reason = feedback.get("blockReason", "no response returned")
                raise ValueError(f"The AI returned no answer ({reason}).")

            first = candidates[0]
            parts = (first.get("content") or {}).get("parts") or []

            answer = "".join(
                part.get("text", "") for part in parts
            ).strip()

            if not answer:
                reason = first.get("finishReason", "unknown reason")
                raise ValueError(f"The AI returned an empty answer ({reason}).")

            self.root.after(
                0,
                lambda a=answer: self.finish_ai_response(a, None)
            )

        except urllib.error.HTTPError as error:
            try:
                details = error.read().decode("utf-8")
            except Exception:
                details = str(error)

            self.root.after(
                0,
                lambda d=details: self.finish_ai_response(
                    None, f"API error: {d}"
                )
            )

        except Exception as error:
            self.root.after(
                0,
                lambda e=str(error): self.finish_ai_response(
                    None, f"Could not get a reply: {e}"
                )
            )

    def finish_ai_response(self, answer, error):
        self.ai_request_pending = False
        self.stop_thinking()

        # User navigated away from the AI page while waiting
        if (
            self.current_page != "AI Assistant"
            or not hasattr(self, "ai_send_button")
            or not self.ai_send_button.winfo_exists()
        ):
            if answer:
                self.ai_history.append({
                    "role": "assistant",
                    "text": answer
                })
                self.data["ai_history"] = self.ai_history[-100:]
                save_data(self.data)
            return

        self.ai_send_button.configure(state="normal")

        if error:
            self.ai_status.configure(text=error[:200], fg=self.red)
            return

        self.ai_history.append({
            "role": "assistant",
            "text": answer
        })
        self.data["ai_history"] = self.ai_history[-100:]
        save_data(self.data)

        self.append_ai_message_animated("assistant", answer)
        self.ai_status.configure(
            text="Response received.",
            fg=self.green
        )

        if self.voice_enabled:
            self._speak_text(answer)

    def _speak_text(self, text):
        """Speak text (markdown stripped, long replies shortened)."""
        assistant = self.voice_assistant

        if assistant is None:
            return

        spoken = clean_for_speech(text)

        if not spoken:
            return

        # Covers the short gap before the voice thread starts talking
        self._speak_pending_until = time.time() + 1.5

        for method_name in ("speak", "speak_text", "say"):
            method = getattr(assistant, method_name, None)

            if callable(method):
                threading.Thread(
                    target=method,
                    args=(spoken,),
                    daemon=True
                ).start()
                return

        print(
            "Speech error: VoiceAssistant has no speak/speak_text/say method."
        )

    # =========================================================
    # VOICE INPUT
    # =========================================================

    def start_voice_input(self):

        if self.voice_assistant is None:

            messagebox.showwarning(
                "Voice Unavailable",
                "Voice assistant is not initialized."
            )
            return

        if self.ai_request_pending:
            return

        # Mic button: fills the message box (you press Send yourself)
        self._listen_once("insert")

    # =========================================================
    # VOICE SETTINGS
    # =========================================================

    def toggle_voice(self):

        self.voice_enabled = not self.voice_enabled

        self.voice_toggle_button.configure(
            text="Voice: ON" if self.voice_enabled else "Voice: OFF"
        )

        self.ai_status.configure(
            text=(
                "Automatic voice responses enabled."
                if self.voice_enabled
                else "Automatic voice responses disabled."
            )
        )

    def stop_ai_speech(self):

        if self.voice_assistant is not None:
            try:
                self.voice_assistant.stop_speaking()
            except Exception as error:
                print("Stop speech error:", error)

        self.ai_status.configure(
            text="Speech stopped."
        )

    # =========================================================
    # CLEAR AI CHAT
    # =========================================================

    def clear_ai_chat(self):

        if not messagebox.askyesno(
            "Clear Chat",
            "Clear the saved AI conversation?"
        ):
            return

        self.ai_history = []
        self.data["ai_history"] = []

        save_data(self.data)

        self.show_ai_assistant()

    # =========================================================
    # DAILY GOALS
    # =========================================================

    def show_daily_goals(self):
        self.current_page = "Daily Goals"
        self.clear_page()
        self.set_active_nav("Daily Goals")

        self.page_header(
            "Daily Goals",
            "Build a consistent study routine."
        )

        today = date.today().isoformat()

        studied = sum(
            session.get("minutes", 0)
            for session in self.data["study_sessions"]
            if session.get("date") == today
        )

        goal = int(self.data["profile"].get("daily_goal", 120))
        percentage = min(100, int((studied / goal) * 100)) if goal else 0

        goal_card = self.card()
        goal_card.pack(fill="x", pady=(0, 18))

        self.section_title(goal_card, "Today's Progress")

        studied_label = tk.Label(
            goal_card,
            text=f"0 / {goal} minutes",
            bg=self.card_bg,
            fg=self.text,
            font=("Segoe UI", 24, "bold")
        )
        studied_label.pack(anchor="w", pady=8)

        self.animate_count(
            studied_label, studied, f" / {goal} minutes", steps=30, delay=26
        )

        self.create_goal_visual(goal_card, percentage, studied, goal)

        percent_label = tk.Label(
            goal_card,
            text="0% completed",
            bg=self.card_bg,
            fg=self.green,
            font=("Segoe UI", 11, "bold")
        )
        percent_label.pack(anchor="w")

        self.animate_count(
            percent_label, percentage, "% completed", steps=30, delay=26
        )

        settings_card = self.card()
        settings_card.pack(fill="x")

        self.section_title(settings_card, "Set Your Daily Goal")

        self.goal_entry = self.make_entry(settings_card)
        self.goal_entry.insert(0, str(goal))
        self.goal_entry.pack(fill="x", ipady=8, pady=(0, 12))

        self.styled_button(
            settings_card,
            "Save Daily Goal",
            self.save_daily_goal
        ).pack(anchor="w")

    def save_daily_goal(self):
        try:
            goal = int(self.goal_entry.get())

            if goal <= 0:
                raise ValueError

        except ValueError:
            self.shake(self.goal_entry)
            self.toast("Enter a positive number of minutes.", "error")
            return

        self.data["profile"]["daily_goal"] = goal
        save_data(self.data)
        self.show_daily_goals()
        self.toast(f"Daily goal set to {goal} minutes.")

    # =========================================================
    # FOCUS MODE / POMODORO
    # =========================================================

    def show_focus_mode(self):
        self.current_page = "Focus Mode"
        self.clear_page()
        self.set_active_nav("Focus Mode")

        self.page_header(
            "Focus Mode",
            "Use focused sessions to improve your concentration."
        )

        timer_card = self.card()
        timer_card.pack(fill="x", pady=(0, 18))

        self.section_title(timer_card, "Pomodoro Timer")

        # Animated ring (drop-in replacement for the old timer label)
        self.timer_display = RingTimerDisplay(timer_card, self, size=270)
        self.timer_display.pack(pady=15)

        self.timer_mode_label = tk.Label(
            timer_card,
            text=(
                "Focus Session"
                if self.timer_mode == "Focus"
                else "Break Time"
            ),
            bg=self.card_bg,
            fg=self.muted,
            font=("Segoe UI", 12)
        )
        self.timer_mode_label.pack(pady=(0, 15))

        controls = tk.Frame(timer_card, bg=self.card_bg)
        controls.pack(pady=10)

        self.styled_button(
            controls,
            "Start",
            self.start_timer,
            self.green
        ).pack(side="left", padx=5)

        self.styled_button(
            controls,
            "Pause",
            self.pause_timer,
            self.orange
        ).pack(side="left", padx=5)

        self.styled_button(
            controls,
            "Reset",
            self.reset_timer,
            self.red
        ).pack(side="left", padx=5)

        settings_card = self.card()
        settings_card.pack(fill="x")

        self.section_title(settings_card, "Timer Settings")

        focus_row = tk.Frame(settings_card, bg=self.card_bg)
        focus_row.pack(fill="x", pady=5)

        tk.Label(
            focus_row,
            text="Focus duration (minutes)",
            bg=self.card_bg,
            fg=self.text
        ).pack(side="left")

        self.focus_entry = self.make_entry(focus_row, 10)
        self.focus_entry.insert(
            0,
            str(self.data["settings"].get("focus_minutes", 25))
        )
        self.focus_entry.pack(side="right", ipady=6)

        break_row = tk.Frame(settings_card, bg=self.card_bg)
        break_row.pack(fill="x", pady=5)

        tk.Label(
            break_row,
            text="Break duration (minutes)",
            bg=self.card_bg,
            fg=self.text
        ).pack(side="left")

        self.break_entry = self.make_entry(break_row, 10)
        self.break_entry.insert(
            0,
            str(self.data["settings"].get("break_minutes", 5))
        )
        self.break_entry.pack(side="right", ipady=6)

        self.styled_button(
            settings_card,
            "Save Timer Settings",
            self.save_timer_settings
        ).pack(anchor="w", pady=(12, 0))

        self.timer_subject_var = tk.StringVar(
            value=self.timer_subject
        )

        tk.Label(
            settings_card,
            text="Study subject",
            bg=self.card_bg,
            fg=self.muted
        ).pack(anchor="w", pady=(18, 5))

        ttk.Combobox(
            settings_card,
            textvariable=self.timer_subject_var,
            values=["General"] + self.data["subjects"],
            state="readonly"
        ).pack(fill="x")

        self.update_timer_display()

    def save_timer_settings(self):
        try:
            focus = int(self.focus_entry.get())
            break_time = int(self.break_entry.get())

            if focus <= 0 or break_time <= 0:
                raise ValueError

        except ValueError:
            self.shake(self.focus_entry)
            self.shake(self.break_entry)
            self.toast(
                "Enter positive numbers for focus and break duration.",
                "error"
            )
            return

        self.data["settings"]["focus_minutes"] = focus
        self.data["settings"]["break_minutes"] = break_time

        save_data(self.data)
        self.reset_timer()

        self.toast("Timer settings updated.")

    def update_timer_display(self):
        if (
            hasattr(self, "timer_display")
            and self.timer_display.winfo_exists()
        ):
            minutes = self.timer_remaining // 60
            seconds = self.timer_remaining % 60

            self.timer_display.configure(
                text=f"{minutes:02d}:{seconds:02d}"
            )

    def start_timer(self):
        if self.timer_running:
            return

        if self.timer_remaining <= 0:
            minutes = (
                self.data["settings"]["focus_minutes"]
                if self.timer_mode == "Focus"
                else self.data["settings"]["break_minutes"]
            )

            self.timer_remaining = minutes * 60
            self.timer_total_seconds = self.timer_remaining

        if self.timer_mode == "Focus":
            if self.timer_session_start is None:
                self.timer_session_start = time.time()

            subject_var = getattr(self, "timer_subject_var", None)

            if subject_var is not None:
                self.timer_subject = subject_var.get()

        self.timer_running = True
        self.timer_tick()

    def timer_tick(self):
        if not self.timer_running:
            return

        self.update_timer_display()

        if self.timer_remaining <= 0:
            self.timer_running = False
            self.timer_completed()
            return

        self.timer_remaining -= 1
        self.timer_after_id = self.root.after(
            1000,
            self.timer_tick
        )

    def pause_timer(self):
        self.timer_running = False

        if self.timer_after_id:
            self.root.after_cancel(self.timer_after_id)
            self.timer_after_id = None

    def reset_timer(self):
        self.pause_timer()

        self.timer_remaining = (
            self.data["settings"]["focus_minutes"] * 60
            if self.timer_mode == "Focus"
            else self.data["settings"]["break_minutes"] * 60
        )

        self.timer_total_seconds = self.timer_remaining
        self.timer_session_start = None

        self.update_timer_display()

    def timer_completed(self):
        self.celebrate_timer()

        if self.timer_mode == "Focus":
            minutes = max(1, self.timer_total_seconds // 60)

            self.data["study_sessions"].append({
                "date": date.today().isoformat(),
                "minutes": minutes,
                "subject": self.timer_subject,
                "created_at": datetime.now().isoformat()
            })

            save_data(self.data)

            messagebox.showinfo(
                "Focus Complete",
                "Great work! Your study session has been saved."
            )

            self.timer_mode = "Break"

            if (
                hasattr(self, "timer_mode_label")
                and self.timer_mode_label.winfo_exists()
            ):
                self.timer_mode_label.configure(
                    text="Break Time"
                )

        else:
            messagebox.showinfo(
                "Break Complete",
                "Break finished. Ready for another focus session?"
            )

            self.timer_mode = "Focus"

            if (
                hasattr(self, "timer_mode_label")
                and self.timer_mode_label.winfo_exists()
            ):
                self.timer_mode_label.configure(
                    text="Focus Session"
                )

        self.timer_session_start = None
        self.timer_remaining = 0
        self.update_timer_display()

    # =========================================================
    # CALENDAR
    # =========================================================

    def show_calendar(self):
        self.current_page = "Calendar"
        self._cal_cells = []
        self.clear_page()
        self.set_active_nav("Calendar")

        self.page_header(
            "Study Calendar",
            "View your deadlines and planned tasks."
        )

        calendar_card = self.card()
        calendar_card.pack(fill="x", pady=(0, 18))

        navigation = tk.Frame(calendar_card, bg=self.card_bg)
        navigation.pack(fill="x", pady=(0, 15))

        self.styled_button(
            navigation,
            "Previous",
            self.previous_month
        ).pack(side="left")

        month_title = (
            f"{calendar.month_name[self.calendar_month]} "
            f"{self.calendar_year}"
        )

        tk.Label(
            navigation,
            text=month_title,
            bg=self.card_bg,
            fg=self.text,
            font=("Segoe UI", 16, "bold")
        ).pack(side="left", expand=True)

        self.styled_button(
            navigation,
            "Next",
            self.next_month
        ).pack(side="right")

        grid = tk.Frame(calendar_card, bg=self.card_bg)
        grid.pack(fill="x")

        for column, day_name in enumerate(
            ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        ):
            grid.grid_columnconfigure(column, weight=1)

            tk.Label(
                grid,
                text=day_name,
                bg=self.card_bg,
                fg=self.accent,
                font=("Segoe UI", 9, "bold")
            ).grid(
                row=0,
                column=column,
                sticky="nsew",
                padx=2,
                pady=5
            )

        month_calendar = calendar.monthcalendar(
            self.calendar_year,
            self.calendar_month
        )

        for row_index, week in enumerate(month_calendar, start=1):
            for column, day_number in enumerate(week):
                if day_number == 0:
                    continue

                current_date = date(
                    self.calendar_year,
                    self.calendar_month,
                    day_number
                ).isoformat()

                has_task = any(
                    task.get("date") == current_date
                    and not task.get("completed")
                    for task in self.data["tasks"]
                )

                is_today = current_date == date.today().isoformat()

                bg = (
                    self.accent if is_today
                    else self.card_border if has_task
                    else self.input_bg
                )

                day_label = tk.Label(
                    grid,
                    text=str(day_number) + (" •" if has_task else ""),
                    bg=bg,
                    fg=self.btn_text if is_today else self.text,
                    font=("Segoe UI", 10, "bold" if is_today else "normal"),
                    padx=8,
                    pady=10
                )
                day_label.grid(
                    row=row_index,
                    column=column,
                    sticky="nsew",
                    padx=3,
                    pady=3
                )

                self.register_calendar_cell(
                    day_label, current_date, has_task, is_today,
                    row_index, column
                )

        self.build_calendar_detail(calendar_card)

        tasks_card = self.card()
        tasks_card.pack(fill="x")

        self.section_title(tasks_card, "Tasks This Month")

        month_prefix = (
            f"{self.calendar_year}-{self.calendar_month:02d}"
        )

        month_tasks = [
            task for task in self.data["tasks"]
            if task.get("date", "").startswith(month_prefix)
        ]

        if not month_tasks:
            tk.Label(
                tasks_card,
                text="No tasks scheduled for this month.",
                bg=self.card_bg,
                fg=self.muted
            ).pack(anchor="w")
        else:
            for task in sorted(
                month_tasks,
                key=lambda item: item.get("date", "")
            ):
                status = "Completed" if task.get("completed") else "Pending"

                self.info_row(
                    tasks_card,
                    f"{task.get('date')}  •  {task.get('title')}  •  {status}",
                    fg=self.green if status == "Completed" else self.text
                )

    def previous_month(self):
        self.calendar_month -= 1

        if self.calendar_month < 1:
            self.calendar_month = 12
            self.calendar_year -= 1

        self.show_calendar()

    def next_month(self):
        self.calendar_month += 1

        if self.calendar_month > 12:
            self.calendar_month = 1
            self.calendar_year += 1

        self.show_calendar()

    # =========================================================
    # ANALYTICS
    # =========================================================

    def show_analytics(self):
        self.current_page = "Analytics"
        self.clear_page()
        self.set_active_nav("Analytics")

        self.page_header(
            "Study Analytics",
            "Visualize your learning activity and consistency."
        )

        # =====================================================
        # CALCULATE STATISTICS
        # =====================================================

        sessions = self.data["study_sessions"]
        tasks = self.data["tasks"]

        total_minutes = sum(
            session.get("minutes", 0)
            for session in sessions
        )

        total_sessions = len(sessions)

        completed = sum(
            1 for task in tasks
            if task.get("completed")
        )

        total_tasks = len(tasks)
        pending = total_tasks - completed

        completion_rate = (
            int(completed / total_tasks * 100)
            if total_tasks else 0
        )

        # =====================================================
        # OVERALL STATISTICS
        # =====================================================

        analytics_card = self.card()
        analytics_card.pack(fill="x", pady=(0, 18))

        self.section_title(analytics_card, "Overall Statistics")

        stats = [
            ("Total Study Time", f"{total_minutes} minutes"),
            ("Total Focus Sessions", str(total_sessions)),
            ("Completed Tasks", str(completed)),
            ("Task Completion Rate", f"{completion_rate}%")
        ]

        for label, value in stats:
            row = tk.Frame(analytics_card, bg=self.card_bg)
            row.pack(fill="x", pady=10)

            tk.Label(
                row,
                text=label,
                bg=self.card_bg,
                fg=self.muted,
                font=("Segoe UI", 10)
            ).pack(side="left")

            value_label = tk.Label(
                row,
                text=value,
                bg=self.card_bg,
                fg=self.text,
                font=("Segoe UI", 12, "bold")
            )
            value_label.pack(side="right")

            self.animate_text_number(value_label, value)

        self.create_week_3d_card()

        # =====================================================
        # TASK COMPLETION PIE CHART
        # =====================================================

        task_card = self.card()
        task_card.pack(fill="x", pady=(0, 18))

        self.section_title(
            task_card,
            "Task Completion Overview"
        )

        if total_tasks == 0:
            tk.Label(
                task_card,
                text="Add tasks to see your completion chart.",
                bg=self.card_bg,
                fg=self.muted
            ).pack(anchor="w")

        else:
            fig = Figure(figsize=(8, 3.5), dpi=100)
            fig.patch.set_facecolor(self.card_bg)

            ax = fig.add_subplot(111)
            ax.set_facecolor(self.card_bg)

            pie_result = ax.pie(
                [completed, pending],
                labels=["Completed", "Pending"],
                colors=[self.green, self.orange],
                autopct="%1.1f%%",
                startangle=90,
                textprops={
                    "color": self.text,
                    "fontsize": 11
                },
                wedgeprops={
                    "edgecolor": self.card_bg,
                    "linewidth": 3
                }
            )

            ax.set_title(
                "Your Task Progress",
                color=self.text,
                fontsize=13,
                pad=15
            )

            fig.tight_layout()

            chart = FigureCanvasTkAgg(
                fig,
                master=task_card
            )

            chart.draw()
            chart.get_tk_widget().pack(fill="x", expand=True)

            self.animate_pie(chart, pie_result)

        # =====================================================
        # STUDY TIME BY SUBJECT
        # =====================================================

        subject_card = self.card()
        subject_card.pack(fill="x", pady=(0, 18))

        self.section_title(
            subject_card,
            "Study Time by Subject"
        )

        subject_minutes = {}

        for session in sessions:
            subject = session.get("subject", "General")
            minutes = session.get("minutes", 0)

            subject_minutes[subject] = (
                subject_minutes.get(subject, 0) + minutes
            )

        if not subject_minutes:
            tk.Label(
                subject_card,
                text="Complete focus sessions to see subject analytics.",
                bg=self.card_bg,
                fg=self.muted
            ).pack(anchor="w")

        else:
            sorted_subjects = sorted(
                subject_minutes.items(),
                key=lambda item: item[1]
            )

            names = [item[0] for item in sorted_subjects]
            values = [item[1] for item in sorted_subjects]

            fig = Figure(figsize=(8, 4), dpi=100)
            fig.patch.set_facecolor(self.card_bg)

            ax = fig.add_subplot(111)
            ax.set_facecolor(self.card_bg)

            bars = ax.barh(
                names,
                values,
                color=self.accent,
                height=0.55
            )

            ax.set_xlabel(
                "Study Time (Minutes)",
                color=self.muted
            )

            ax.set_title(
                "Subject-wise Study Distribution",
                color=self.text,
                fontsize=13,
                pad=15
            )

            ax.tick_params(colors=self.muted)

            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)

            ax.spines["bottom"].set_color(self.surface)
            ax.spines["left"].set_color(self.surface)

            ax.grid(
                axis="x",
                color=self.surface,
                alpha=0.4
            )

            ax.set_axisbelow(True)

            for bar, value in zip(bars, values):
                ax.text(
                    value,
                    bar.get_y() + bar.get_height() / 2,
                    f" {value} min",
                    va="center",
                    color=self.text,
                    fontsize=9
                )

            fig.tight_layout()

            chart = FigureCanvasTkAgg(
                fig,
                master=subject_card
            )

            chart.draw()
            chart.get_tk_widget().pack(fill="x", expand=True)

            self.animate_bars(chart, bars, values, horizontal=True)

        # =====================================================
        # WEEKLY STUDY TREND
        # =====================================================

        weekly_card = self.card()
        weekly_card.pack(fill="x", pady=(0, 18))

        self.section_title(
            weekly_card,
            "Last 7 Days — Study Trend"
        )

        today = date.today()

        last_seven_days = [
            today - timedelta(days=i)
            for i in range(6, -1, -1)
        ]

        daily_minutes = {
            day.isoformat(): 0
            for day in last_seven_days
        }

        for session in sessions:
            session_date = session.get("date", "")

            if session_date in daily_minutes:
                daily_minutes[session_date] += (
                    session.get("minutes", 0)
                )

        dates = [
            day.strftime("%a")
            for day in last_seven_days
        ]

        study_values = [
            daily_minutes[day.isoformat()]
            for day in last_seven_days
        ]

        fig = Figure(figsize=(8, 3.8), dpi=100)
        fig.patch.set_facecolor(self.card_bg)

        ax = fig.add_subplot(111)
        ax.set_facecolor(self.card_bg)

        bars = ax.bar(
            dates,
            study_values,
            color=self.green,
            width=0.5
        )

        ax.set_ylabel(
            "Study Time (Minutes)",
            color=self.muted
        )

        ax.set_title(
            "Your Weekly Learning Activity",
            color=self.text,
            fontsize=13,
            pad=15
        )

        ax.tick_params(colors=self.muted)

        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        ax.spines["bottom"].set_color(self.surface)
        ax.spines["left"].set_color(self.surface)

        ax.grid(
            axis="y",
            color=self.surface,
            alpha=0.4
        )

        ax.set_axisbelow(True)

        for bar, value in zip(bars, study_values):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height(),
                str(value),
                ha="center",
                va="bottom",
                color=self.text,
                fontsize=9
            )

        fig.tight_layout()

        chart = FigureCanvasTkAgg(
            fig,
            master=weekly_card
        )

        chart.draw()
        chart.get_tk_widget().pack(fill="x", expand=True)

        self.animate_bars(chart, bars, study_values)

    # =========================================================
    # PROFILE
    # =========================================================

    def show_profile(self):
        self.current_page = "Profile"
        self.clear_page()
        self.set_active_nav("Profile")

        self.page_header(
            "My Profile",
            "Manage your StudyMate profile and preferences."
        )

        self.create_profile_banner()

        profile_card = self.card()
        profile_card.pack(fill="x", pady=(0, 18))

        self.section_title(profile_card, "Personal Information")

        profile = self.data["profile"]

        photo_row = tk.Frame(profile_card, bg=self.card_bg)
        photo_row.pack(fill="x", pady=(0, 6))

        self.styled_button(
            photo_row,
            "Change Photo" if profile.get("photo") else "Upload Photo",
            self.choose_profile_photo
        ).pack(side="left")

        if profile.get("photo"):
            self.styled_button(
                photo_row,
                "Remove Photo",
                self.remove_profile_photo,
                self.red
            ).pack(side="left", padx=(10, 0))

        tk.Label(
            photo_row,
            text="JPG, PNG or WebP. It is centred and cropped to a circle.",
            bg=self.card_bg,
            fg=self.muted,
            font=("Segoe UI", 9)
        ).pack(side="left", padx=(14, 0))

        fields = [
            ("Name", "name"),
            ("School / College / Institution", "college"),
            ("Course, Class or Field of Study", "course"),
        ]

        self.profile_entries = {}

        for label, key in fields:
            tk.Label(
                profile_card,
                text=label,
                bg=self.card_bg,
                fg=self.muted
            ).pack(anchor="w", pady=(10, 5))

            entry = self.make_entry(profile_card)
            entry.insert(0, profile.get(key, ""))
            entry.pack(fill="x", ipady=8)

            self.profile_entries[key] = entry

        self.profile_combos = {}

        tk.Label(
            profile_card,
            text="Education Level",
            bg=self.card_bg,
            fg=self.muted
        ).pack(anchor="w", pady=(10, 5))

        level_box = ttk.Combobox(
            profile_card, values=EDUCATION_LEVELS, state="readonly"
        )
        level_box.set(profile.get("level") or "")
        level_box.pack(fill="x", ipady=4)
        self.profile_combos["level"] = level_box

        tk.Label(
            profile_card,
            text="Voice Input Language",
            bg=self.card_bg,
            fg=self.muted
        ).pack(anchor="w", pady=(10, 5))

        current_code = self.data["settings"].get("voice_language", "en-IN")

        language_box = ttk.Combobox(
            profile_card,
            values=[name for name, code in VOICE_LANGUAGES],
            state="readonly"
        )
        language_box.set(
            next(
                (name for name, code in VOICE_LANGUAGES if code == current_code),
                "English (India)"
            )
        )
        language_box.pack(fill="x", ipady=4)
        self.profile_combos["language"] = language_box

        self.styled_button(
            profile_card,
            "Save Profile",
            self.save_profile
        ).pack(anchor="w", pady=(18, 0))

        self.styled_button(
            profile_card,
            "Run Setup Guide",
            self.show_onboarding,
            self.accent2
        ).pack(anchor="w", pady=(10, 0))

        theme_card = self.card()
        theme_card.pack(fill="x", pady=(0, 18))

        self.section_title(theme_card, "Appearance")

        tk.Label(
            theme_card,
            text="Pick a calm theme. It applies instantly and is saved to your account.",
            bg=self.card_bg,
            fg=self.muted,
            font=("Segoe UI", 10)
        ).pack(anchor="w", pady=(0, 12))

        theme_row = tk.Frame(theme_card, bg=self.card_bg)
        theme_row.pack(anchor="w")

        current_theme = self.data["settings"].get("theme", "Midnight Gold")

        for theme_index, (theme_name, palette) in enumerate(THEMES.items()):
            is_active = theme_name == current_theme

            swatch = tk.Frame(
                theme_row,
                bg=palette["card_bg"],
                highlightthickness=2,
                highlightbackground=(
                    palette["accent"] if is_active else palette["card_border"]
                ),
                padx=14,
                pady=12,
                cursor="hand2"
            )
            swatch.grid(
                row=theme_index // 3,
                column=theme_index % 3,
                padx=(0, 14),
                pady=(0, 14)
            )

            dots = tk.Frame(swatch, bg=palette["card_bg"], cursor="hand2")
            dots.pack()

            clickable = [swatch, dots]

            for key in ("accent", "accent2", "green"):
                dot = tk.Frame(
                    dots,
                    bg=palette[key],
                    width=16,
                    height=16,
                    cursor="hand2"
                )
                dot.pack(side="left", padx=3)
                clickable.append(dot)

            name_label = tk.Label(
                swatch,
                text=theme_name + ("  ✓" if is_active else ""),
                bg=palette["card_bg"],
                fg=palette["text"],
                font=("Segoe UI", 9, "bold"),
                cursor="hand2"
            )
            name_label.pack(pady=(8, 0))
            clickable.append(name_label)

            for widget in clickable:
                widget.bind(
                    "<Button-1>",
                    lambda event, n=theme_name: self.change_theme(n)
                )

            if not is_active:
                self.hover_highlight(
                    swatch,
                    clickable,
                    palette["card_border"],
                    palette["accent"]
                )

        data_card = self.card()
        data_card.pack(fill="x")

        self.section_title(data_card, "Data Management")

        self.styled_button(
            data_card,
            "Export Backup",
            self.export_backup
        ).pack(anchor="w", pady=5)

        self.styled_button(
            data_card,
            "Restore Backup",
            self.restore_backup,
            self.orange
        ).pack(anchor="w", pady=5)

    def save_profile(self, silent=False):
        for key, entry in self.profile_entries.items():
            self.data["profile"][key] = entry.get().strip()

        combos = getattr(self, "profile_combos", {})

        if "level" in combos:
            self.data["profile"]["level"] = combos["level"].get().strip()

        if "language" in combos:
            chosen = combos["language"].get()

            for name, code in VOICE_LANGUAGES:
                if name == chosen:
                    self.data["settings"]["voice_language"] = code
                    self.voice_language = code

        save_data(self.data)

        self.refresh_sidebar_user_chip()

        if not silent:
            self.flash_entries(self.profile_entries.values())
            self.toast("Profile saved successfully.")

    # ---------------------------------------------------------
    # Profile photo, sidebar user chip, account name
    # ---------------------------------------------------------

    def choose_profile_photo(self):
        path = filedialog.askopenfilename(
            title="Choose a profile picture",
            filetypes=IMAGE_FILETYPES
        )

        if not path:
            return

        try:
            photo = process_photo_file(path)
        except ValueError as error:
            messagebox.showwarning("Profile Photo", str(error))
            return

        # Keep anything already typed in the form before the page redraws
        if self.current_page == "Profile":
            try:
                self.save_profile(silent=True)
            except (AttributeError, tk.TclError):
                pass

        self.data["profile"]["photo"] = photo
        save_data(self.data)

        self.refresh_sidebar_user_chip()

        if self.current_page == "Profile":
            self.show_profile()

        self.toast("Profile photo updated.")

    def remove_profile_photo(self):
        if not self.data["profile"].get("photo"):
            return

        if not messagebox.askyesno(
            "Remove Photo",
            "Remove your profile photo?"
        ):
            return

        if self.current_page == "Profile":
            try:
                self.save_profile(silent=True)
            except (AttributeError, tk.TclError):
                pass

        self.data["profile"]["photo"] = ""
        save_data(self.data)

        self.refresh_sidebar_user_chip()

        if self.current_page == "Profile":
            self.show_profile()

        self.toast("Profile photo removed.")

    def refresh_sidebar_user_chip(self):
        """Name or photo changed: redraw the avatar and greeting."""

        stage = getattr(self, "stage", None)

        if stage is None:
            return

        try:
            stage._draw_static()
            stage.set_active(self.active_nav)
        except tk.TclError:
            pass

    def _seed_profile_from_account(self):
        try:
            current = (self.data["profile"].get("name") or "").strip()

            if current.lower() in ("", "student"):
                account_name = get_display_name(self.user)

                if account_name:
                    self.data["profile"]["name"] = account_name
                    save_data(self.data)

        except Exception as error:
            print("Profile name warning:", error)

    # =========================================================
    # BACKUP AND RESTORE
    # =========================================================

    def export_backup(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            initialfile="studymate_backup.json"
        )

        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8") as file:
                json.dump(
                    self.data,
                    file,
                    indent=4,
                    ensure_ascii=False
                )

            messagebox.showinfo(
                "Backup Created",
                "Your backup has been exported successfully."
            )

        except OSError as error:
            messagebox.showerror("Export Error", str(error))

    def restore_backup(self):
        path = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json")]
        )

        if not path:
            return

        if not messagebox.askyesno(
            "Restore Backup",
            "Restoring will replace your current StudyMate data. Continue?"
        ):
            return

        try:
            with open(path, "r", encoding="utf-8") as file:
                restored = json.load(file)

            if not isinstance(restored, dict):
                raise ValueError("Invalid backup format.")

            defaults = json.loads(json.dumps(DEFAULT_DATA))

            for section in ("profile", "settings"):
                if section in restored and not isinstance(
                    restored[section], dict
                ):
                    raise ValueError(
                        f"Invalid '{section}' data in backup."
                    )

                restored[section] = {
                    **defaults[section],
                    **restored.get(section, {})
                }

            for key in (
                "subjects",
                "tasks",
                "study_sessions",
                "ai_history"
            ):
                if key not in restored:
                    restored[key] = defaults[key]

                elif not isinstance(restored[key], list):
                    raise ValueError(
                        f"Invalid '{key}' data in backup."
                    )

            self.data = restored
            self.ai_history = self.data["ai_history"]

            save_data(self.data)

            messagebox.showinfo(
                "Restore Complete",
                "Your backup has been restored."
            )

            self.show_dashboard()

        except (OSError, json.JSONDecodeError, ValueError) as error:
            messagebox.showerror(
                "Restore Error",
                f"Could not restore backup:\n{error}"
            )

    # =========================================================
    # LOGOUT AND CLOSE APPLICATION
    # =========================================================

    def logout(self):
        try:
            self.pause_timer()
            self.data["ai_history"] = self.ai_history[-100:]
            save_data(self.data)

            try:
                self.page_canvas.unbind_all("<MouseWheel>")
                self.page_canvas.unbind_all("<Button-4>")
                self.page_canvas.unbind_all("<Button-5>")
                self.root.unbind_all("<Return>")
            except Exception:
                pass

            self.cancel_hero()

            logout_user()

            self.root.show_login_callback()

        except Exception as error:
            messagebox.showerror(
                "Logout Failed",
                str(error)
            )

    def on_close(self):
        self.pause_timer()

        self.data["ai_history"] = self.ai_history[-100:]
        save_data(self.data)

        try:
            self.page_canvas.unbind_all("<MouseWheel>")
            self.page_canvas.unbind_all("<Button-4>")
            self.page_canvas.unbind_all("<Button-5>")
        except Exception:
            pass

        self.root.destroy()


if __name__ == "__main__":

    root = tk.Tk()

    app = None
    auth_app = None

    def open_studymate(user):
        global app

        for widget in root.winfo_children():
            widget.destroy()

        app = StudyMate(root, user)

    def open_login():
        global auth_app

        for widget in root.winfo_children():
            widget.destroy()

        root.minsize(1, 1)
        auth_app = AuthScreen(root, open_studymate)

    # Register the callback once, before either screen can be opened.
    # StudyMate.logout() uses this to return to the login screen.
    root.show_login_callback = open_login

    # Restore an existing session, or show the login screen.
    try:
        user = get_current_user()

        if user:
            open_studymate(user)
        else:
            open_login()

    except Exception as error:
        print("Authentication startup warning:", error)
        open_login()

    root.mainloop()