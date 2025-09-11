# 🖥️ SITA - Cyber AI GUI Dashboard (Bubble Menu + Visual Indicators)

import sys
import os
import json
import threading
import pyttsx3
import openai
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QTextEdit, QFileDialog, QCheckBox, QLineEdit, QDialog, QFormLayout
)
import speech_recognition as sr
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QPoint, QEasingCurve
from PyQt5.QtGui import QFont
from pygame import mixer
import io
import requests

# === Config ===
ELEVENLABS_API_KEY = "sk_4f9992583aa191125309faf3f2f470205b19e2a25c3d012c"
ELEVENLABS_VOICE_ID = "cgSgspJ2msm6clMCkdW9"
MEMORY_PATH = "sita_memory.json"
CONFIG_PATH = "sita_config.json"

# === AI Connection Settings ===
openai.api_key = "lm-studio"
openai.api_base = "http://192.168.1.5:5412/v1"
MODEL_NAME = "nous-hermes-2-mistral-7b-dpo"


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setStyleSheet("background-color: #101820; color: #F2AA4C;")
        self.setFixedSize(420, 300)

        self.parent = parent

        # Preferences
        self.safe_mode_toggle = QCheckBox("Enable Safe Mode")
        self.float_toggle = QCheckBox("Show Floating Avatar")
        self.debug_toggle = QCheckBox("Verbose Logs")

        if parent is not None:
            try:
                self.safe_mode_toggle.setChecked(parent.safe_mode_toggle.isChecked())
                self.float_toggle.setChecked(parent.float_toggle.isChecked())
                self.debug_toggle.setChecked(parent.debug_toggle.isChecked())
            except:
                pass

        # Import prefs
        self.import_btn = QPushButton("Import Preferences")
        self.import_btn.setStyleSheet("background-color: #222; color: #F2AA4C;")
        self.import_btn.clicked.connect(self.import_preferences)

        # API key input
        self.api_key_input = QLineEdit()
        self.api_key_input.setText(openai.api_key)

        # Save button
        save_btn = QPushButton("Save")
        save_btn.setStyleSheet("background-color: #222; color: #F2AA4C;")
        save_btn.clicked.connect(self.save_settings)

        layout = QFormLayout()
        layout.addRow(QLabel("<b>Preferences</b>"))
        layout.addRow(self.safe_mode_toggle)
        layout.addRow(self.float_toggle)
        layout.addRow(self.debug_toggle)
        layout.addRow(self.import_btn)
        layout.addRow(QLabel("<b>API Key</b>"))
        layout.addRow(self.api_key_input)
        layout.addRow(save_btn)
        self.setLayout(layout)

    def import_preferences(self):
        if self.parent and hasattr(self.parent, "import_prefs"):
            self.parent.import_prefs()

    def save_settings(self):
        if self.parent:
            try:
                self.parent.safe_mode_toggle.setChecked(self.safe_mode_toggle.isChecked())
                self.parent.float_toggle.setChecked(self.float_toggle.isChecked())
                self.parent.debug_toggle.setChecked(self.debug_toggle.isChecked())
            except Exception as e:
                print(f"[Settings Error] {e}")

        new_key = self.api_key_input.text().strip()
        if new_key:
            openai.api_key = new_key
            with open(CONFIG_PATH, "w") as f:
                json.dump({"api_key": openai.api_key}, f)
            if self.parent and hasattr(self.parent, "load_last_api_key"):
                self.parent.load_last_api_key()

        self.accept()


class BubbleMenu(QWidget):
    def __init__(self, parent=None, width=250, height=300):
        super().__init__(parent)
        self.parent = parent
        self.setFixedSize(width, height)
        self.setStyleSheet("background-color: #222; color: #F2AA4C; border-radius: 20px;")
        self.move(-width, 50)
        self.hide()

        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        title = QLabel("Menu")
        title.setFont(QFont("Consolas", 16, QFont.Bold))
        layout.addWidget(title)

        btns = [
            ("Import Preferences", self.parent.import_prefs),
            ("Export Memory", self.parent.export_memory),
            ("Settings", self.parent.open_settings),
            ("Close", self.hide)
        ]
        for text, func in btns:
            b = QPushButton(text)
            b.setStyleSheet("background-color: #333; color: #F2AA4C; padding: 8px; border-radius: 8px;")
            b.clicked.connect(func)
            layout.addWidget(b)

        self.setLayout(layout)

        self.anim = QPropertyAnimation(self, b"pos")
        self.anim.setDuration(300)
        self.anim.setEasingCurve(QEasingCurve.OutBack)

    def show_with_animation(self):
        self.show()
        self.anim.stop()
        self.anim.setStartValue(self.pos())
        self.anim.setEndValue(QPoint(10, 50))
        self.anim.start()

    def hide_with_animation(self):
        self.anim.stop()
        self.anim.setStartValue(self.pos())
        self.anim.setEndValue(QPoint(-self.width(), 50))
        self.anim.finished.connect(self.hide)
        self.anim.start()


class SITADashboard(QWidget):
    append_text_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("SITA Dashboard")
        self.setGeometry(300, 100, 1000, 700)
        self.setStyleSheet("background-color: #101820; color: #F2AA4C;")

        self.stop_flag = False
        self.load_last_api_key()

        self.tts_engine = pyttsx3.init()
        self.tts_engine.setProperty('rate', 165)
        self.tts_engine.setProperty('voice', self._get_female_voice())

        self.safe_mode_toggle = QCheckBox()
        self.float_toggle = QCheckBox()
        self.debug_toggle = QCheckBox()

        self.init_ui()
        self.update_logs()
        self.append_text_signal.connect(self.chat_display.append)

        self.menu_panel = BubbleMenu(self)

    def load_last_api_key(self):
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r") as f:
                config = json.load(f)
                if "api_key" in config:
                    openai.api_key = config["api_key"]

    def _get_female_voice(self):
        voices = self.tts_engine.getProperty('voices')
        for voice in voices:
            if "female" in voice.name.lower() or "zira" in voice.name.lower():
                return voice.id
        return voices[0].id

    def init_ui(self):
        self.menu_btn = QPushButton("☰")
        self.menu_btn.setFixedSize(36, 36)
        self.menu_btn.setStyleSheet("background-color: #222; font-size:18px;")
        self.menu_btn.clicked.connect(self.toggle_menu)

        title = QLabel("SITA: Secure Intelligent Tech Assistant")
        title.setFont(QFont("Consolas", 20, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)

        # Mic button
        self.mic_btn = QPushButton("🎙️")
        self.mic_btn.setFixedSize(36, 36)
        self.mic_btn.setStyleSheet("background-color: #222; border-radius: 18px;")
        self.mic_btn.clicked.connect(self.voice_command)

        # Stop button
        self.stop_btn = QPushButton("⏹")
        self.stop_btn.setFixedSize(36, 36)
        self.stop_btn.setStyleSheet("background-color: #222; border-radius: 18px;")
        self.stop_btn.clicked.connect(self.stop_ai)

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("background-color: #181A1B; color: #00FF88;")

        self.chat_input = QLineEdit()
        self.chat_input.setFixedHeight(50)  # increased height
        self.chat_input.setPlaceholderText("Type your message...")
        self.chat_input.returnPressed.connect(self.send_message)

        chat_input_layout = QHBoxLayout()
        chat_input_layout.addWidget(self.chat_input)
        chat_input_layout.addWidget(self.mic_btn)
        chat_input_layout.addWidget(self.stop_btn)

        top_bar = QHBoxLayout()
        top_bar.addWidget(self.menu_btn)
        top_bar.addWidget(title)
        top_bar.addStretch()

        layout = QVBoxLayout()
        layout.addLayout(top_bar)
        layout.addWidget(QLabel("Chat:"))
        layout.addWidget(self.chat_display)
        layout.addLayout(chat_input_layout)
        self.setLayout(layout)

    def toggle_menu(self):
        if self.menu_panel.isVisible():
            self.menu_panel.hide_with_animation()
        else:
            self.menu_panel.show_with_animation()

    def open_settings(self):
        dlg = SettingsDialog(self)
        dlg.exec_()

    def stop_ai(self):
        self.stop_flag = True
        self.stop_btn.setStyleSheet("background-color: #222; border: 3px solid green; border-radius: 18px;")
        try:
            if mixer.get_init():
                mixer.music.stop()
            self.append_text_signal.emit("[System] Stopped AI response.")
        except:
            pass

    def import_prefs(self):
        file, _ = QFileDialog.getOpenFileName(self, "Import Preferences", "", "JSON Files (*.json)")
        if file:
            os.system(f"copy \"{file}\" \"{MEMORY_PATH}\" /Y")

    def export_memory(self):
        file, _ = QFileDialog.getSaveFileName(self, "Export Memory", "sita_memory.json", "JSON Files (*.json)")
        if file:
            os.system(f"copy \"{MEMORY_PATH}\" \"{file}\" /Y")

    def send_message(self):
        user_text = self.chat_input.text().strip()
        if not user_text:
            return
        self.append_text_signal.emit(f"You: {user_text}")
        self.chat_input.clear()
        self.stop_flag = False
        threading.Thread(target=self.process_ai_reply, args=(user_text,), daemon=True).start()

    def process_ai_reply(self, user_text):
        try:
            self.stop_btn.setStyleSheet("background-color: #222; border: 3px solid green; border-radius: 18px;")
            response = openai.ChatCompletion.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": "You are SITA, a professional, warm, and intelligent AI partner."},
                    {"role": "user", "content": user_text}
                ],
                temperature=0.7,
                stream=True
            )

            full_reply = ""
            for chunk in response:
                if self.stop_flag:
                    break
                if "choices" in chunk and len(chunk["choices"]) > 0:
                    delta = chunk["choices"][0]["delta"].get("content", "")
                    if delta:
                        full_reply += delta

            if not self.stop_flag and full_reply.strip():
                self.append_text_signal.emit(f"SITA: {full_reply}")

                url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
                headers = {"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"}
                data = {"text": full_reply, "model_id": "eleven_multilingual_v2", "voice_settings": {"stability": 0.4, "similarity_boost": 0.85}}
                tts_response = requests.post(url, headers=headers, json=data)

                if tts_response.status_code == 200:
                    mixer.init()
                    mixer.music.load(io.BytesIO(tts_response.content))
                    mixer.music.play()
                else:
                    self.append_text_signal.emit(f"[TTS Error] {tts_response.status_code}")

        except Exception as e:
            self.append_text_signal.emit(f"[Error] {e}")
        finally:
            self.stop_btn.setStyleSheet("background-color: #222; border-radius: 18px;")

    def voice_command(self):
        """Toggle continuous listening mode."""
        if not hasattr(self, "listening"):
            self.listening = False

        if not self.listening:
            # Start continuous listening
            self.listening = True
            self.append_text_signal.emit("[Voice] Recording... Click mic again to stop.")
            self.mic_btn.setStyleSheet("background-color: #222; border: 3px solid green; border-radius: 18px;")
            threading.Thread(target=self._continuous_listen, daemon=True).start()
        else:
            # Stop continuous listening
            self.listening = False
            self.mic_btn.setStyleSheet("background-color: #222; border-radius: 18px;")
            self.append_text_signal.emit("[Voice] Stopped recording, processing audio...")

    def _continuous_listen(self):
        """Continuously record until stopped, then process as one audio."""
        try:
            mic_list = sr.Microphone.list_microphone_names()
            if not mic_list:
                self.append_text_signal.emit("[Voice] No microphone detected.")
                return

            recognizer = sr.Recognizer()
            chunks = []

            with sr.Microphone(device_index=0) as source:
                recognizer.energy_threshold = 300
                recognizer.adjust_for_ambient_noise(source, duration=1)

                while self.listening:
                    try:
                        audio_chunk = recognizer.listen(source, timeout=1, phrase_time_limit=5)
                        chunks.append(audio_chunk)
                    except sr.WaitTimeoutError:
                        pass  # No speech in this small window, just keep looping

            # Combine chunks into one audio stream
            if chunks:
                audio_data = sr.AudioData(
                    b''.join(c.get_raw_data() for c in chunks),
                    chunks[0].sample_rate,
                    chunks[0].sample_width
                )

                try:
                    user_text = recognizer.recognize_google(audio_data)
                    self.append_text_signal.emit(f"You (voice): {user_text}")
                    self.stop_flag = False
                    threading.Thread(target=self.process_ai_reply, args=(user_text,), daemon=True).start()
                except sr.UnknownValueError:
                    self.append_text_signal.emit("[Voice] Could not understand audio.")
                except sr.RequestError as e:
                    self.append_text_signal.emit(f"[Voice] API unavailable: {e}")

        except Exception as e:
            self.append_text_signal.emit(f"[Voice] Error: {e}")


    def update_logs(self):
        if os.path.exists(MEMORY_PATH):
            try:
                with open(MEMORY_PATH, "r") as f:
                    json.load(f)
            except:
                pass
        QTimer.singleShot(10000, self.update_logs)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    dashboard = SITADashboard()
    dashboard.show()
    sys.exit(app.exec_())
