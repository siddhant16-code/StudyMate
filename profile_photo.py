"""
profile_photo.py  -  StudyMate profile photo helpers
====================================================

Put this file in the SAME folder as main.py.

The chosen picture is centre-cropped to a square, shrunk to 256 x 256 and
stored as a small base64 JPEG inside the user's profile data
(profile["photo"]). Because it lives in the profile, it is saved in the
local JSON file AND synced to Supabase together with everything else - no
extra storage bucket is needed.

Needs Pillow (already installed as a matplotlib dependency).
"""

import base64
import io
import os
import tkinter as tk

from PIL import Image, ImageDraw, ImageOps, ImageTk

PHOTO_SIZE = 256
MAX_FILE_BYTES = 15 * 1024 * 1024

IMAGE_FILETYPES = [
    ("Pictures", "*.png *.jpg *.jpeg *.webp *.bmp *.gif"),
    ("All files", "*.*"),
]


def process_photo_file(path):
    """Reads a picture file and returns a small base64 JPEG string."""

    try:
        if os.path.getsize(path) > MAX_FILE_BYTES:
            raise ValueError("Please choose a picture smaller than 15 MB.")

        with Image.open(path) as image:
            image = ImageOps.exif_transpose(image)
            image = image.convert("RGB")

            # Slightly biased towards the top so faces stay in frame
            image = ImageOps.fit(
                image,
                (PHOTO_SIZE, PHOTO_SIZE),
                Image.LANCZOS,
                centering=(0.5, 0.4)
            )

    except ValueError:
        raise

    except Exception as error:
        raise ValueError("That file could not be read as a picture.") from error

    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=88, optimize=True)

    return base64.b64encode(buffer.getvalue()).decode("ascii")


def circular_image(photo_b64, diameter):
    """Circle-cropped PIL image (smooth edges) from a base64 photo."""

    raw = base64.b64decode(photo_b64)

    image = Image.open(io.BytesIO(raw)).convert("RGBA")
    image = image.resize((diameter, diameter), Image.LANCZOS)

    scale = 4
    mask = Image.new("L", (diameter * scale, diameter * scale), 0)

    ImageDraw.Draw(mask).ellipse(
        (0, 0, diameter * scale - 1, diameter * scale - 1),
        fill=255
    )

    mask = mask.resize((diameter, diameter), Image.LANCZOS)
    image.putalpha(mask)

    return image


def make_photo_image(photo_b64, diameter):
    """Tk image for a base64 photo, or None if it cannot be read."""

    if not photo_b64:
        return None

    try:
        return ImageTk.PhotoImage(circular_image(photo_b64, diameter))

    except Exception as error:
        print("Profile photo warning:", error)
        return None


def overlay_disc(diameter, alpha=150, color=(0, 0, 0)):
    """Soft dark circle used for the 'Change photo' hover overlay."""

    scale = 4
    big = Image.new("RGBA", (diameter * scale, diameter * scale), (0, 0, 0, 0))

    ImageDraw.Draw(big).ellipse(
        (0, 0, diameter * scale - 1, diameter * scale - 1),
        fill=color + (alpha,)
    )

    return ImageTk.PhotoImage(big.resize((diameter, diameter), Image.LANCZOS))


def initials_of(name):
    words = [word for word in (name or "S").split() if word]
    return "".join(word[0] for word in words[:2]).upper() or "S"


class MiniAvatar(tk.Canvas):
    """Small static avatar (photo or initials) for the sidebar."""

    def __init__(
        self,
        master,
        name,
        photo_b64,
        size,
        bg,
        disc,
        accent,
        ring=None
    ):
        super().__init__(
            master,
            width=size,
            height=size,
            bg=bg,
            highlightthickness=0,
            bd=0
        )

        pad = 2
        self._image = None

        self.create_oval(
            pad, pad, size - pad, size - pad,
            outline=ring or accent,
            width=2
        )

        inner = pad + 3
        self._image = make_photo_image(photo_b64, size - inner * 2)

        if self._image is not None:
            self.create_image(size / 2, size / 2, image=self._image)

        else:
            self.create_oval(
                inner, inner, size - inner, size - inner,
                fill=disc,
                outline=""
            )
            self.create_text(
                size / 2, size / 2,
                text=initials_of(name),
                fill=accent,
                font=("Georgia", max(8, int(size / 3.1)), "bold")
            )