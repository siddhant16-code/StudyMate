# StudyMate

A desktop learning companion built with Python and Tkinter. StudyMate helps you organise subjects and tasks, stay focused, track progress, and get help from an AI study assistant, with accounts and cloud sync powered by Supabase.

## Features

- **Dashboard and Analytics**: progress overview, charts, and a 3D study galaxy
- **Subjects and Tasks**: organise coursework and deadlines
- **AI Assistant**: ask doubts, analyse uploaded PDF/DOCX/TXT notes (Google Gemini), with optional voice input and spoken replies
- **Focus Mode**: Pomodoro timer
- **Smart Scheduler, Daily Goals and Calendar**
- **Lecture Hub**: embedded YouTube browser for lectures
- **Profile**: custom profile photo, themes, and animated floating pill navigation
- **Accounts**: email, Google, Discord and phone (SMS) sign-in, with encrypted local sessions and cloud sync

## Requirements

- Windows 10/11 (uses Windows-specific APIs for the embedded browser, speech and secure session storage)
- Python 3.10 or newer
- A free [Supabase](https://supabase.com) project
- A [Google Gemini API key](https://aistudio.google.com/apikey)

## Setup

```bash
git clone https://github.com/YOUR-USERNAME/studymate.git
cd studymate
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Open `.env` and fill in your own keys, then run:

```bash
python main.py
```

### Supabase setup

1. Create a project and copy the project URL and publishable key into `.env`.
2. Create two tables: `profiles` (`id`, `display_name`) and `study_data` (`user_id` unique, `data` jsonb), with row-level security so each user can only access their own rows.
3. For Google/Discord login, add `http://127.0.0.1:53682/callback` under Authentication > URL Configuration > Redirect URLs.

## Project structure

| File | Purpose |
|---|---|
| `main.py` | Main application |
| `auth_screen.py`, `supabase_config.py` | Sign-in screens and Supabase client |
| `animations.py`, `pill_nav.py`, `scene3d.py`, `jarvis_hud.py` | Animations, navigation, 3D and HUD visuals |
| `voice_assistant.py` | Text-to-speech and speech recognition |
| `lecture_embed.py` | Embedded YouTube browser (PySide6 WebEngine) |
| `document_reader.py` | Text extraction from PDF, DOCX and TXT |
| `profile_photo.py` | Profile photo processing |

## Privacy

Your study data is stored locally in `studymate_*.json` (git-ignored) and synced to your own Supabase project. API keys live only in `.env`.

## Contributing

Issues and pull requests are welcome.

## License

MIT. See [LICENSE](LICENSE).
