"""
PowerDictate Desktop Floating Widget (Dragon Medical One Equivalent)
====================================================================
A lightweight, always-on-top floating pill widget that enables system-wide
voice dictation, dot-phrase macro expansion, and placeholder navigation
directly into any active window (Meditech, Citrix, EMR, Word, Browser).
"""

import sys
import time
import threading
import queue
import tkinter as tk
from tkinter import ttk
import numpy as np
import sounddevice as sd
import pyautogui
import pyperclip

from src.stt.transcriber import MedicalTranscriber
from src.stt.lexer import PowerPhraseLexer
from src.stt.stream_vad import StreamingAudioProcessor
from src.utils.template_loader import TemplateManager

try:
    from pynput import keyboard
    HAS_PYNPUT = True
except ImportError:
    HAS_PYNPUT = False


class DragonDesktopWidget:
    """
    Floating desktop widget for system-wide clinical dictation.
    """

    def __init__(self):
        self.is_recording = False
        self.audio_queue = queue.Queue()
        self.stt_engine = None
        self.lexer = PowerPhraseLexer()
        self.stream_processor = StreamingAudioProcessor(sample_rate=16000)
        self.template_mgr = TemplateManager()
        self.stream = None

        # Build UI
        self.root = tk.Tk()
        self.root.title("PowerDictate Mini")
        self.root.overrideredirect(True)  # Frameless floating pill
        self.root.attributes("-topmost", True)  # Always on top
        self.root.configure(bg="#1e293b")

        # Position at top-right corner of screen
        screen_w = self.root.winfo_screenwidth()
        self.root.geometry(f"260x52+{screen_w - 280}+40")

        self._build_ui()
        self._init_audio_thread()
        self._init_hotkeys()

    def _build_ui(self):
        # Drag bar / frame
        self.frame = tk.Frame(self.root, bg="#1e293b", bd=1, relief="solid")
        self.frame.pack(fill="both", expand=True, padx=2, pady=2)

        # Allow dragging window
        self.frame.bind("<Button-1>", self._start_drag)
        self.frame.bind("<B1-Motion>", self._on_drag)

        # Status Icon & Mic Button
        self.mic_btn = tk.Button(
            self.frame,
            text="🎙️ [F8]",
            font=("Segoe UI", 10, "bold"),
            bg="#0284c7",
            fg="white",
            activebackground="#0369a1",
            activeforeground="white",
            bd=0,
            padx=8,
            pady=4,
            command=self.toggle_recording
        )
        self.mic_btn.pack(side="left", padx=6, pady=6)

        # Status Label
        self.status_lbl = tk.Label(
            self.frame,
            text="Press F8 to Dictate",
            font=("Segoe UI", 9),
            bg="#1e293b",
            fg="#94a3b8"
        )
        self.status_lbl.pack(side="left", fill="x", expand=True, padx=4)

        # Close Button
        close_btn = tk.Button(
            self.frame,
            text="✕",
            font=("Segoe UI", 8),
            bg="#1e293b",
            fg="#64748b",
            activebackground="#ef4444",
            activeforeground="white",
            bd=0,
            command=self.root.destroy
        )
        close_btn.pack(side="right", padx=4)

    def _start_drag(self, event):
        self._x = event.x
        self._y = event.y

    def _on_drag(self, event):
        deltax = event.x - self._x
        deltay = event.y - self._y
        x = self.root.winfo_x() + deltax
        y = self.root.winfo_y() + deltay
        self.root.geometry(f"+{x}+{y}")

    def _init_hotkeys(self):
        """Registers global F8 hotkey for hands-free toggle."""
        if HAS_PYNPUT:
            def on_press(key):
                if key == keyboard.Key.f8:
                    self.root.after(0, self.toggle_recording)

            self.listener = keyboard.Listener(on_press=on_press)
            self.listener.daemon = True
            self.listener.start()

    def _init_audio_thread(self):
        """Worker thread to process STT without freezing GUI."""
        self.worker_thread = threading.Thread(target=self._stt_worker, daemon=True)
        self.worker_thread.start()

    def toggle_recording(self):
        if self.is_recording:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        self.is_recording = True
        self.mic_btn.configure(bg="#ef4444", text="🔴 REC")
        self.status_lbl.configure(text="Listening...", fg="#ef4444")

        def audio_callback(indata, frames, time_info, status):
            if self.is_recording:
                # Convert float32 [-1, 1] to pcm16 bytes
                pcm16 = (indata[:, 0] * 32767).astype(np.int16).tobytes()
                self.audio_queue.put(pcm16)

        try:
            self.stream = sd.InputStream(
                samplerate=16000,
                channels=1,
                dtype='float32',
                blocksize=2048,
                callback=audio_callback
            )
            self.stream.start()
        except Exception as e:
            self.status_lbl.configure(text=f"Mic Error: {e}")
            self.stop_recording()

    def stop_recording(self):
        self.is_recording = False
        self.mic_btn.configure(bg="#0284c7", text="🎙️ [F8]")
        self.status_lbl.configure(text="Ready (F8)", fg="#94a3b8")
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

    def _stt_worker(self):
        """Background thread executing Faster-Whisper and injecting keystrokes."""
        print("Loading Faster-Whisper GPU Engine for Desktop Widget...")
        self.stt_engine = MedicalTranscriber()
        print("Desktop STT Ready.")

        while True:
            try:
                chunk = self.audio_queue.get(timeout=0.2)
                utterance = self.stream_processor.process_chunk(chunk)
                if utterance is not None and len(utterance) > 0:
                    raw_text, _ = self.stt_engine.transcribe_audio(utterance, apply_lexer=False)
                    if raw_text.strip():
                        res = self.lexer.process(raw_text)
                        self._inject_result_into_active_window(res)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"STT Worker error: {e}")

    def _inject_result_into_active_window(self, lex_res):
        """Types recognized text or macro into whatever window currently has OS focus."""
        if lex_res.is_navigation_command:
            if lex_res.command_type == "next_field":
                pyautogui.press("tab")
            elif lex_res.command_type == "prev_field":
                pyautogui.hotkey("shift", "tab")
            elif lex_res.command_type == "new_paragraph":
                pyautogui.press("enter")
                pyautogui.press("enter")
            elif lex_res.command_type == "new_line":
                pyautogui.press("enter")
            elif lex_res.command_type == "scratch_that":
                pyautogui.hotkey("ctrl", "z")
        else:
            text = lex_res.text.strip()
            if not text:
                return

            # For long text or multi-line macros, paste via clipboard for instant insertion
            if len(text) > 40 or "\n" in text:
                old_clip = pyperclip.paste()
                pyperclip.copy(text + " ")
                pyautogui.hotkey("ctrl", "v")
                time.sleep(0.05)
                pyperclip.copy(old_clip)
            else:
                pyautogui.write(text + " ", interval=0.01)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = DragonDesktopWidget()
    app.run()
