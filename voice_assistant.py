import base64
import os
import queue
import subprocess
import threading

import pyttsx3
import speech_recognition as sr


class VoiceAssistant:
    """
    Text-to-speech runs on ONE dedicated worker thread, so speech is never
    started from several threads at once. speak() returns immediately.

    Reliability notes (Windows):
      * COM is initialised on the worker thread (SAPI needs this).
      * A FRESH pyttsx3 engine is created for every sentence. A long-lived
        engine can go permanently silent after engine.stop().
      * If pyttsx3 fails or produces an error, the same text is spoken
        through Windows PowerShell (System.Speech) as a fallback.
    """

    def __init__(self, voice_id=None, rate=175, volume=1.0):

        self.recognizer = sr.Recognizer()

        self.rate = rate
        self.volume = max(0.0, min(1.0, volume))

        self.engine = None
        self.voices = []
        self.selected_voice = None
        self.voice_id = None

        self.lock = threading.RLock()
        self.speech_queue = queue.Queue()

        self._speaking = False
        self._process = None
        self._ready_ok = False

        self._ready = threading.Event()
        self._init_error = None

        self._worker = threading.Thread(
            target=self._speech_worker,
            daemon=True
        )
        self._worker.start()

        self._ready.wait(timeout=15)

        if self._init_error is not None:
            raise RuntimeError(
                f"Text-to-speech could not start: {self._init_error}"
            )

        if not self._ready_ok:
            raise RuntimeError("Text-to-speech engine did not start in time.")

        if voice_id:
            self.set_voice_by_id(voice_id)

    # ---------------------------------------------------------
    # Speech worker
    # ---------------------------------------------------------

    @staticmethod
    def _init_com():
        """SAPI (Windows speech) needs COM initialised on this thread."""
        try:
            import pythoncom
            pythoncom.CoInitialize()
            return
        except Exception:
            pass

        try:
            import comtypes
            comtypes.CoInitialize()
        except Exception:
            pass

    def _speech_worker(self):

        self._init_com()

        try:
            probe = pyttsx3.init()
            self.voices = list(probe.getProperty("voices"))
            del probe
        except Exception as error:
            self._init_error = error
            self._ready.set()
            return

        self._ready_ok = True
        self._ready.set()

        while True:
            text = self.speech_queue.get()

            if text is None:
                break

            self._speaking = True

            try:
                if not self._speak_pyttsx3(text):
                    self._speak_powershell(text)

            except Exception as error:
                print("Speech error:", error)

            finally:
                self._speaking = False

    def _speak_pyttsx3(self, text):
        """Returns True if the sentence was spoken without an error."""

        engine = None

        try:
            engine = pyttsx3.init()

            with self.lock:
                voice_id = self.voice_id
                rate = self.rate
                volume = self.volume

            if voice_id:
                engine.setProperty("voice", voice_id)

            engine.setProperty("rate", rate)
            engine.setProperty("volume", volume)

            self.engine = engine

            engine.say(text)
            engine.runAndWait()

            return True

        except Exception as error:
            print("Speech error (pyttsx3):", error)
            return False

        finally:
            self.engine = None

            if engine is not None:
                try:
                    engine.stop()
                except Exception:
                    pass

            del engine

    def _speak_powershell(self, text):
        """Fallback: Windows built-in System.Speech through PowerShell."""

        if os.name != "nt":
            return

        with self.lock:
            rate = self.rate
            volume = self.volume
            voice = self.get_selected_voice()

        # pyttsx3 rate (~175 wpm) -> System.Speech rate (-10..10)
        ps_rate = max(-10, min(10, round((rate - 175) / 12)))
        ps_volume = int(volume * 100)

        voice_name = ""

        if voice:
            voice_name = voice["name"].split(" - ")[0].strip()

        escaped_text = text.replace("'", "''")
        escaped_voice = voice_name.replace("'", "''")

        script = (
            "Add-Type -AssemblyName System.Speech; "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$s.Rate = {ps_rate}; $s.Volume = {ps_volume}; "
            f"try {{ $s.SelectVoice('{escaped_voice}') }} catch {{}}; "
            f"$s.Speak('{escaped_text}')"
        )

        encoded = base64.b64encode(script.encode("utf-16-le")).decode()

        print("Speaking through the PowerShell fallback...")

        try:
            self._process = subprocess.Popen(
                [
                    "powershell",
                    "-NoProfile",
                    "-NonInteractive",
                    "-EncodedCommand",
                    encoded
                ],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            )
            self._process.wait()

        except Exception as error:
            print("Speech error (PowerShell fallback):", error)

        finally:
            self._process = None

    # ---------------------------------------------------------
    # Voice settings
    # ---------------------------------------------------------

    def get_available_voices(self):

        return [
            {
                "index": index,
                "id": voice.id,
                "name": voice.name
            }
            for index, voice in enumerate(self.voices)
        ]

    def set_voice(self, voice_index):

        if not isinstance(voice_index, int):
            raise ValueError("Voice index must be an integer.")

        if not 0 <= voice_index < len(self.voices):
            raise ValueError("Invalid voice selection.")

        with self.lock:
            self.voice_id = self.voices[voice_index].id
            self.selected_voice = voice_index

        return True

    def set_voice_by_id(self, voice_id):

        for index, voice in enumerate(self.voices):
            if voice.id == voice_id:
                return self.set_voice(index)

        raise ValueError("Selected voice is not available.")

    def get_selected_voice(self):

        if self.selected_voice is None:
            return None

        voice = self.voices[self.selected_voice]

        return {
            "index": self.selected_voice,
            "id": voice.id,
            "name": voice.name
        }

    def set_speed(self, speed):

        speed = int(speed)

        if not 80 <= speed <= 300:
            raise ValueError("Speech speed must be between 80 and 300.")

        with self.lock:
            self.rate = speed

    def set_volume(self, volume):

        volume = max(0.0, min(1.0, float(volume)))

        with self.lock:
            self.volume = volume

    # ---------------------------------------------------------
    # Speaking
    # ---------------------------------------------------------

    def speak(self, text):

        if not text or not str(text).strip():
            return

        # Replace anything still waiting, so replies never pile up
        self._clear_queue()
        self.speech_queue.put(str(text))

    def _clear_queue(self):

        try:
            while True:
                self.speech_queue.get_nowait()
        except queue.Empty:
            pass

    def stop_speaking(self):

        self._clear_queue()

        # Do not take the lock here, otherwise stopping could wait
        # until the current sentence finishes.
        try:
            if self.engine is not None:
                self.engine.stop()
        except Exception:
            pass

        try:
            if self._process is not None:
                self._process.terminate()
        except Exception:
            pass

    def is_speaking(self):
        """True while speech is playing or still queued."""
        return self._speaking or not self.speech_queue.empty()

    # ---------------------------------------------------------
    # Listening
    # ---------------------------------------------------------

    def listen(self, timeout=5, phrase_time_limit=10, language="en-IN"):

        try:
            with sr.Microphone() as source:

                self.recognizer.adjust_for_ambient_noise(
                    source,
                    duration=0.5
                )

                audio = self.recognizer.listen(
                    source,
                    timeout=timeout,
                    phrase_time_limit=phrase_time_limit
                )

            return self.recognizer.recognize_google(
                audio,
                language=language
            ).strip()

        except sr.WaitTimeoutError:
            return None

        except sr.UnknownValueError:
            return None

        except sr.RequestError as error:
            raise RuntimeError(
                f"Speech recognition service error: {error}"
            ) from error

        except OSError as error:
            raise RuntimeError(
                f"Microphone error: {error}"
            ) from error

    def preview_voice(self):

        self.speak(
            "Hello! I am your StudyMate AI assistant. "
            "How can I help you with your studies today?"
        )

    def close(self):

        self.stop_speaking()
        self.speech_queue.put(None)