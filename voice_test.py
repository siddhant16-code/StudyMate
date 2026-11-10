"""
Run this on its own:   python voice_test.py
It tells you whether your PC can speak at all, outside StudyMate.
"""
import time

from voice_assistant import VoiceAssistant

assistant = VoiceAssistant()

print("Installed voices:")

for voice in assistant.get_available_voices():
    print(" ", voice["index"], "-", voice["name"])

print("\nSpeaking with the default voice...")
assistant.speak("Testing. Can you hear me?")

time.sleep(0.5)

while assistant.is_speaking():
    time.sleep(0.2)

print("Finished. If you heard nothing, check the messages printed above,")
print("your Windows volume mixer, and the selected output device.")