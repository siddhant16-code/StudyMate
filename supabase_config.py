import os
import re
import time
import hashlib
import http.server
import urllib.parse
import webbrowser
from pathlib import Path

import keyring

from cryptography.fernet import Fernet, InvalidToken
from dotenv import load_dotenv
from supabase import create_client
from supabase.client import ClientOptions
from supabase_auth._sync.storage import SyncSupportedStorage

load_dotenv()


# Encrypted local session storage
class WindowsSecureStorage(SyncSupportedStorage):

    SERVICE_NAME = "StudyMateSessionEncryption"
    KEY_NAME = "fernet_key"

    def __init__(self):
        encryption_key = keyring.get_password(
            self.SERVICE_NAME,
            self.KEY_NAME
        )

        if encryption_key is None:
            encryption_key = Fernet.generate_key().decode()
            keyring.set_password(
                self.SERVICE_NAME,
                self.KEY_NAME,
                encryption_key
            )

        self.cipher = Fernet(encryption_key.encode())

        self.storage_folder = (
            Path(os.getenv("LOCALAPPDATA", str(Path.home())))
            / "StudyMate"
            / "SecureSession"
        )

        self.storage_folder.mkdir(parents=True, exist_ok=True)

    def _get_path(self, key):
        filename = hashlib.sha256(key.encode()).hexdigest()
        return self.storage_folder / f"{filename}.enc"

    def get_item(self, key: str) -> str | None:
        path = self._get_path(key)

        if not path.exists():
            return None

        try:
            encrypted_data = path.read_bytes()
            decrypted_data = self.cipher.decrypt(encrypted_data)
            return decrypted_data.decode()

        except InvalidToken:
            return None

    def set_item(self, key: str, value: str) -> None:
        path = self._get_path(key)

        encrypted_data = self.cipher.encrypt(value.encode())

        temporary_path = path.with_suffix(".tmp")
        temporary_path.write_bytes(encrypted_data)
        temporary_path.replace(path)

    def remove_item(self, key: str) -> None:
        path = self._get_path(key)

        if path.exists():
            path.unlink()


# Supabase credentials
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_PUBLISHABLE_KEY")

if not url or not key:
    raise RuntimeError("Supabase credentials missing in .env file")


# Create Supabase client
options = ClientOptions(
    auto_refresh_token=True,
    persist_session=True,
    storage=WindowsSecureStorage()
)

supabase = create_client(url, key, options=options)


def register_user(email, password, name):
    return supabase.auth.sign_up({
        "email": email,
        "password": password,
        "options": {
            "data": {
                "display_name": name
            }
        }
    })


def login_user(email, password):
    return supabase.auth.sign_in_with_password({
        "email": email,
        "password": password
    })


def logout_user():
    supabase.auth.sign_out()


def get_current_user():
    session = supabase.auth.get_session()

    if session:
        return supabase.auth.get_user().user

    return None


def save_user_profile(user_id, name):
    return supabase.table("profiles").upsert({
        "id": user_id,
        "display_name": name
    }).execute()


def load_cloud_data(user_id):
    response = (
        supabase.table("study_data")
        .select("data")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )

    if response.data:
        return response.data[0]["data"]

    return None


def save_cloud_data(user_id, data):
    return supabase.table("study_data").upsert({
        "user_id": user_id,
        "data": data
    }).execute()



# =============================================================
# PASSWORD RESET
# =============================================================

def send_password_reset(email):
    return supabase.auth.reset_password_for_email(email)


# =============================================================
# DISPLAY NAME (works for email, Google, Discord and phone users)
# =============================================================

def get_display_name(user):
    """Best-effort human name for a Supabase user, or '' if none."""

    metadata = getattr(user, "user_metadata", None) or {}

    for key in (
        "full_name",
        "name",
        "display_name",
        "user_name",
        "preferred_username"
    ):
        value = metadata.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()

    email = getattr(user, "email", None) or ""

    if "@" in email:
        return email.split("@")[0].replace(".", " ").replace("_", " ").title()

    return ""


# =============================================================
# GOOGLE / DISCORD LOGIN (browser + local callback)
# =============================================================
#
# In your Supabase dashboard:
#   Authentication > URL Configuration > Redirect URLs
#   add exactly:   http://127.0.0.1:53682/callback

OAUTH_PORT = 53682
OAUTH_REDIRECT = f"http://127.0.0.1:{OAUTH_PORT}/callback"
OAUTH_PROVIDERS = ("google", "discord")

_CALLBACK_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>StudyMate</title>
<style>
  body{margin:0;height:100vh;display:flex;align-items:center;justify-content:center;
       background:radial-gradient(circle at 30% 20%,#12404a,#06141f 70%);
       font-family:Segoe UI,Helvetica,Arial,sans-serif;color:#eafbfa}
  .card{max-width:420px;padding:44px 40px;text-align:center;border-radius:22px;
        background:rgba(15,42,51,.85);border:1px solid #2c6471;
        box-shadow:0 20px 60px rgba(0,0,0,.45)}
  h1{font-family:Georgia,serif;color:#5eead4;margin:0 0 10px;font-size:28px}
  p{color:#8fbbc2;line-height:1.6;margin:0}
</style></head>
<body><div class="card"><h1>__TITLE__</h1><p>__BODY__</p></div></body></html>"""


class _CallbackServer(http.server.HTTPServer):

    # On Windows, SO_REUSEADDR would allow two programs to share the port.
    allow_reuse_address = os.name != "nt"

    result = None


class _CallbackHandler(http.server.BaseHTTPRequestHandler):

    def log_message(self, *args):
        pass

    def do_GET(self):

        parsed = urllib.parse.urlparse(self.path)

        if parsed.path != "/callback":
            self.send_response(204)
            self.end_headers()
            return

        query = {
            key: values[0]
            for key, values in urllib.parse.parse_qs(parsed.query).items()
        }

        if query.get("code"):
            title = "You're signed in"
            body = "Return to StudyMate - you can close this tab now."
            self.server.result = {"code": query["code"]}

        else:
            problem = (
                query.get("error_description")
                or query.get("error")
                or "No sign-in code was received. Please try again."
            )
            title = "Sign-in did not finish"
            body = problem
            self.server.result = {"error": problem}

        page = (
            _CALLBACK_PAGE
            .replace("__TITLE__", title)
            .replace("__BODY__", body.replace("<", "&lt;"))
        ).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(page)))
        self.end_headers()
        self.wfile.write(page)


def sign_in_with_provider(provider, cancel_event=None, timeout=180):
    """
    Opens the browser for Google / Discord, waits for the redirect on a
    local port, then exchanges the code for a session.
    Blocking - call it from a background thread.
    """

    if provider not in OAUTH_PROVIDERS:
        raise ValueError(f"Unsupported provider: {provider}")

    try:
        server = _CallbackServer(("127.0.0.1", OAUTH_PORT), _CallbackHandler)

    except OSError as error:
        raise RuntimeError(
            f"Port {OAUTH_PORT} is busy. Close any other StudyMate window "
            "and try again."
        ) from error

    server.timeout = 0.5

    try:
        options = {"redirect_to": OAUTH_REDIRECT}

        if provider == "google":
            options["query_params"] = {"prompt": "select_account"}

        response = supabase.auth.sign_in_with_oauth({
            "provider": provider,
            "options": options
        })

        webbrowser.open(response.url)

        deadline = time.time() + timeout

        while server.result is None:

            if cancel_event is not None and cancel_event.is_set():
                raise RuntimeError("cancelled")

            if time.time() > deadline:
                raise RuntimeError(
                    "Sign-in timed out. Please try again."
                )

            server.handle_request()

    finally:
        server.server_close()

    result = server.result

    if result.get("error"):
        raise RuntimeError(result["error"])

    return supabase.auth.exchange_code_for_session({
        "auth_code": result["code"]
    })


# =============================================================
# MOBILE NUMBER LOGIN (SMS one-time code)
# =============================================================

def normalize_phone(country_code, number):
    """Returns a +<countrycode><number> string, or raises ValueError."""

    code = re.sub(r"\D", "", country_code or "")
    digits = re.sub(r"\D", "", number or "")

    if not code:
        raise ValueError("Enter a country code, for example +91.")

    digits = digits.lstrip("0")

    if not 6 <= len(digits) <= 13:
        raise ValueError("That mobile number does not look right.")

    return f"+{code}{digits}"


def send_phone_otp(phone):
    return supabase.auth.sign_in_with_otp({"phone": phone})


def verify_phone_otp(phone, code):
    return supabase.auth.verify_otp({
        "phone": phone,
        "token": code,
        "type": "sms"
    })