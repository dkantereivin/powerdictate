"""
VoIP.ms SIP Client for Hospital Dictation Submission
===================================================
Manages SIP trunking connections with voip.ms to dial hospital dictation lines
(or clinician mobile phone), waits for the line to be answered before proceeding,
transmits DTMF tones, streams synthesized oral clinical notes, and provides
real-time bi-directional audio monitoring and live transcript feedback.
"""

import time
import queue
import logging
import threading
from typing import Optional, Callable
import audioop
import numpy as np
import scipy.signal

logger = logging.getLogger("tts.telephony.voip_client")


class VoIPMsClient:
    """
    SIP telephony client interface for dialing, waiting for connection,
    and streaming bi-directional dictation via voip.ms.
    """

    def __init__(
        self,
        server: str = "toronto.voip.ms",
        username: str = "",
        password: str = "",
        port: int = 5060,
        caller_id: str = "",
        listen_in_real_time: bool = True,
        status_callback: Optional[Callable[[str], None]] = None,
        transcript_callback: Optional[Callable[[str, str], None]] = None,
        audio_activity_callback: Optional[Callable[[str, float], None]] = None,
    ):
        self.server = (server or "toronto.voip.ms").strip()
        self.username = (username or "").strip()
        self.password = (password or "").strip()
        self.port = port
        self.caller_id = (caller_id or "").strip()
        self.listen_in_real_time = listen_in_real_time

        self.status_callback = status_callback
        self.transcript_callback = transcript_callback
        self.audio_activity_callback = audio_activity_callback

        self._phone = None
        self._active_call = None
        self._is_connected = False
        self._stop_bridge = False
        self._bridge_thread = None

        # Local audio output stream for hearing both sides
        self._monitor_stream = None
        self._outbound_audio_queue = queue.Queue()

        # Speech recognition for incoming remote audio
        self._whisper_model = None
        self._whisper_load_attempted = False

    @property
    def is_configured(self) -> bool:
        """Returns True if minimum SIP credentials (username and password) are set."""
        return bool(self.username and self.password and self.server)

    def _emit_status(self, text: str):
        logger.info(f"[Call Status] {text}")
        if self.status_callback:
            try:
                self.status_callback(text)
            except Exception:
                pass

    def _emit_transcript(self, speaker: str, text: str):
        logger.info(f"[Transcript] [{speaker}] {text}")
        if self.transcript_callback:
            try:
                self.transcript_callback(speaker, text)
            except Exception:
                pass

    def _emit_activity(self, source: str, level: float):
        if self.audio_activity_callback:
            try:
                self.audio_activity_callback(source, level)
            except Exception:
                pass

    def connect(self) -> bool:
        """
        Initializes SIP client, registers with voip.ms server, and waits
        for PhoneStatus.REGISTERED.
        """
        if not self.is_configured:
            logger.info("VoIP.ms credentials not fully configured; operating in simulation mode.")
            return False

        try:
            from pyVoIP.VoIP import VoIPPhone, PhoneStatus, CallState
            from pyVoIP.SIP import SIPMessageType, SIPStatus

            self._emit_status(f"Connecting to SIP server {self.server}:{self.port}...")
            self._phone = VoIPPhone(
                server=self.server,
                port=self.port,
                username=self.username,
                password=self.password,
                myIP="0.0.0.0",
                callCallback=self._on_incoming_call
            )

            # Hook SIP message parsing to track Ringing and SIP rejection codes
            orig_parse_message = self._phone.sip.parse_message

            def custom_parse_message(message):
                try:
                    if message.type != SIPMessageType.MESSAGE:
                        call_id = message.headers.get("Call-ID")
                        if call_id and hasattr(self._phone, "calls") and call_id in self._phone.calls:
                            c = self._phone.calls[call_id]
                            # Detect Ringing
                            if message.status == SIPStatus.RINGING or (
                                hasattr(SIPStatus, "SESSION_PROGRESS") and message.status == SIPStatus.SESSION_PROGRESS
                            ):
                                c.state = CallState.RINGING
                            # Detect errors (e.g. 4xx, 5xx, 6xx)
                            elif hasattr(message.status, "value"):
                                code_str = message.status.value.split()[0]
                                if code_str.isdigit() and int(code_str) >= 400:
                                    logger.warning(f"SIP Call failed with remote status: {message.status}")
                                    c.state = CallState.ENDED
                except Exception as ex:
                    logger.debug(f"Error in custom parse message: {ex}")
                return orig_parse_message(message)

            self._phone.sip.parse_message = custom_parse_message
            self._phone.start()

            # Wait for registration to complete (up to 4 seconds)
            start_wait = time.time()
            while time.time() - start_wait < 4.0:
                status = self._phone.get_status()
                if status == PhoneStatus.REGISTERED:
                    self._is_connected = True
                    self._emit_status("✓ Registered with VoIP.ms SIP server.")
                    return True
                time.sleep(0.2)

            self._is_connected = (self._phone.get_status() == PhoneStatus.REGISTERED)
            if self._is_connected:
                self._emit_status("✓ Registered with VoIP.ms SIP server.")
                return True
            else:
                logger.warning(f"Registration pending (status: {self._phone.get_status()})")
                return True  # Proceed to dial anyway
        except Exception as e:
            logger.error(f"Failed to connect to voip.ms SIP trunk: {e}", exc_info=True)
            self._is_connected = False
            return False

    def _on_incoming_call(self, call):
        """Rejects inbound calls on this outgoing dictation trunk."""
        try:
            call.hangup()
        except Exception:
            pass

    def dial(self, phone_number: str, timeout_sec: float = 60.0) -> bool:
        """
        Initiates outbound SIP call to the hospital dictation number (or clinician mobile phone).
        CRITICAL: Blocks and WAITS until the call is explicitly answered (CallState.ANSWERED).
        Does NOT return True until the connection is fully established.
        """
        cleaned_num = "".join(c for c in phone_number if c.isdigit())
        if not self._is_connected or not self._phone:
            self._emit_status(f"[SIMULATED] Dialing {cleaned_num}...")
            self._emit_transcript("Outbound", f"Simulated call placed to {cleaned_num}")
            time.sleep(1.5)
            self._emit_status("🔔 Simulated Ringing...")
            time.sleep(2.0)
            self._emit_status("🟢 Call Answered (Simulation)")
            self._emit_transcript("System", "Call Answered. Audio stream active.")
            self._start_audio_bridge()
            return True

        try:
            from pyVoIP.VoIP import CallState

            self._emit_status(f"📞 Dialing {cleaned_num} via VoIP.ms...")
            self._emit_transcript("Outbound", f"Dialing {cleaned_num}...")
            self._active_call = self._phone.call(cleaned_num)

            last_reported_state = None
            start_t = time.time()

            # Wait loop: strictly wait until answered or terminated
            while time.time() - start_t < timeout_sec:
                if self._active_call is None:
                    self._emit_status("❌ Call aborted.")
                    return False

                state = getattr(self._active_call, "state", None)

                if state != last_reported_state:
                    last_reported_state = state
                    if state == CallState.DIALING:
                        self._emit_status(f"📞 Dialing {cleaned_num}...")
                    elif state == CallState.RINGING:
                        self._emit_status(f"🔔 Ringing {cleaned_num}... (waiting for answer)")
                        self._emit_transcript("System", "Phone is ringing, waiting for clinician to answer...")
                    elif state == CallState.ANSWERED:
                        elapsed = time.time() - start_t
                        self._emit_status(f"🟢 Call Answered! (in {elapsed:.1f}s)")
                        self._emit_transcript("System", f"Call Answered! Audio channel connected in {elapsed:.1f}s.")
                        # Start bi-directional audio bridge immediately upon answer
                        self._start_audio_bridge()
                        return True
                    elif state == CallState.ENDED:
                        self._emit_status("❌ Call rejected or ended by remote party.")
                        self._emit_transcript("System", "Call was disconnected or rejected.")
                        return False

                time.sleep(0.15)

            self._emit_status(f"⏱️ Call timed out waiting for answer ({timeout_sec}s).")
            self._emit_transcript("System", "Call timed out waiting for answer.")
            self.hangup()
            return False

        except Exception as e:
            logger.error(f"Error dialing {cleaned_num}: {e}", exc_info=True)
            self._emit_status(f"⚠️ Dial error: {e}")
            return False

    def _start_audio_bridge(self):
        """
        Starts the real-time bi-directional audio bridge:
        - Receives incoming audio from the remote phone / hospital IVR.
        - Mixes and plays both incoming and outbound audio to local PC speakers.
        - Analyzes speech energy and transcribes incoming IVR prompts in real time.
        """
        self._stop_bridge = False
        self._bridge_thread = threading.Thread(target=self._audio_bridge_loop, daemon=True)
        self._bridge_thread.start()

    def _get_whisper_model(self):
        """Lazily loads lightweight faster-whisper tiny.en model for incoming IVR prompts."""
        if self._whisper_model is None and not self._whisper_load_attempted:
            self._whisper_load_attempted = True
            try:
                from faster_whisper import WhisperModel
                self._whisper_model = WhisperModel("tiny.en", device="cpu", compute_type="int8")
                logger.info("Whisper model loaded for real-time IVR prompt transcription.")
            except Exception as e:
                logger.warning(f"Could not load faster-whisper model: {e}")
        return self._whisper_model

    def _audio_bridge_loop(self):
        """
        Background loop streaming incoming remote audio to local speakers,
        calculating RMS levels, and detecting/transcribing remote prompts.
        """
        import sounddevice as sd

        try:
            # 8000 Hz, 16-bit PCM, 1 channel matches standard G.711 telephony audio
            self._monitor_stream = sd.RawOutputStream(
                samplerate=8000,
                channels=1,
                dtype="int16",
                blocksize=160
            )
            self._monitor_stream.start()
            logger.info("Local audio monitor stream started (8kHz mono PCM16).")
        except Exception as e:
            logger.warning(f"Could not open local audio monitor stream: {e}")
            self._monitor_stream = None

        speech_buffer = []
        is_in_speech = False
        silence_frames = 0
        speech_frames = 0

        while not self._stop_bridge:
            has_activity = False

            # 1. Read incoming audio from telephone call
            if self._active_call and hasattr(self._active_call, "read_audio"):
                try:
                    raw_ulaw = self._active_call.read_audio(160, blocking=False)
                    if raw_ulaw and len(raw_ulaw) == 160:
                        has_activity = True
                        # Convert G.711 u-law to 16-bit linear PCM
                        pcm16 = audioop.ulaw2lin(raw_ulaw, 2)
                        rms = audioop.rms(pcm16, 2)

                        # Emit audio level for VU meter
                        self._emit_activity("remote", min(1.0, rms / 15000.0))

                        # Play incoming remote audio through PC speakers if monitoring is active
                        if self.listen_in_real_time and self._monitor_stream:
                            try:
                                self._monitor_stream.write(pcm16)
                            except Exception:
                                pass

                        # Speech energy detection (> 1200 RMS indicates remote speaking)
                        if rms > 1200:
                            speech_frames += 1
                            silence_frames = 0
                            speech_buffer.append(pcm16)
                            if not is_in_speech and speech_frames >= 4:
                                is_in_speech = True
                                self._emit_status("🔊 [Remote Line] Audio prompt playing...")
                        else:
                            if is_in_speech:
                                silence_frames += 1
                                speech_buffer.append(pcm16)
                                # End of prompt detected (> 0.5s silence)
                                if silence_frames >= 25:
                                    is_in_speech = False
                                    speech_frames = 0
                                    total_speech = b"".join(speech_buffer)
                                    speech_buffer = []
                                    self._emit_status("⏸️ [Remote Line] Listening for clinician input.")
                                    # Transcribe remote prompt in background
                                    threading.Thread(
                                        target=self._transcribe_remote_speech,
                                        args=(total_speech,),
                                        daemon=True
                                    ).start()
                            else:
                                speech_frames = 0
                except Exception as e:
                    logger.debug(f"Bridge read error: {e}")

            # 2. Check for outbound audio to play locally in monitor stream
            try:
                out_chunk = self._outbound_audio_queue.get_nowait()
                if self.listen_in_real_time and self._monitor_stream:
                    self._monitor_stream.write(out_chunk)
                has_activity = True
            except queue.Empty:
                pass

            if not has_activity:
                time.sleep(0.01)

        # Cleanup monitor stream
        if self._monitor_stream:
            try:
                self._monitor_stream.stop()
                self._monitor_stream.close()
            except Exception:
                pass
            self._monitor_stream = None
        logger.info("Local audio monitor bridge terminated.")

    def _transcribe_remote_speech(self, pcm_bytes: bytes):
        """Transcribes incoming remote audio snippet and emits to transcript."""
        if not pcm_bytes or len(pcm_bytes) < 8000 * 2 * 0.4:  # at least 400ms
            return

        model = self._get_whisper_model()
        if not model:
            self._emit_transcript("Hospital Line", "(Spoken voice prompt received)")
            return

        try:
            # Convert 16-bit PCM bytes (8000Hz) to float32 numpy array
            audio_int16 = np.frombuffer(pcm_bytes, dtype=np.int16)
            audio_float = audio_int16.astype(np.float32) / 32768.0

            # Resample 8000Hz -> 16000Hz for Whisper
            audio_16k = scipy.signal.resample(audio_float, len(audio_float) * 2).astype(np.float32)

            segments, _ = model.transcribe(audio_16k, beam_size=1, language="en")
            text = " ".join(seg.text for seg in segments).strip()
            if text:
                self._emit_transcript("Hospital Line", f'"{text}"')
            else:
                self._emit_transcript("Hospital Line", "(Voice prompt received)")
        except Exception as e:
            logger.debug(f"Transcription error: {e}")
            self._emit_transcript("Hospital Line", "(Voice prompt received)")

    def send_dtmf(self, tones: str) -> None:
        """
        Sends DTMF touch-tones over the active SIP session,
        plays tone to local monitor stream, and emits transcript.
        """
        tones = (tones or "").strip()
        if not tones:
            return

        self._emit_status(f"🔢 Transmitting DTMF: {tones}")
        self._emit_transcript("Outbound DTMF", f"Tones: {tones}")

        from tts.dtmf import generate_dtmf_tone

        # 1. Send via SIP signaling if supported
        if self._active_call and self._is_connected:
            try:
                for char in tones:
                    if hasattr(self._active_call, "send_dtmf"):
                        self._active_call.send_dtmf(char)
                    time.sleep(0.12)
            except Exception as e:
                logger.warning(f"SIP DTMF signaling error: {e}")

        # 2. Transmit in-band G.711 RTP audio for robust DTMF detection on all IVR switches
        for char in tones:
            # Generate 120ms tone at 8kHz telephony rate
            tone_audio = generate_dtmf_tone(char, duration_sec=0.12, sample_rate=8000)
            tone_pcm16 = (tone_audio * 28000.0).astype(np.int16).tobytes()

            # Play to local monitor stream so user hears DTMF
            if self.listen_in_real_time:
                self._outbound_audio_queue.put(tone_pcm16)

            # Send over RTP if call is active
            if self._active_call and self._is_connected and hasattr(self._active_call, "write_audio"):
                try:
                    ulaw_tone = audioop.lin2ulaw(tone_pcm16, 2)
                    for i in range(len(ulaw_tone) // 160):
                        self._active_call.write_audio(ulaw_tone[i * 160 : (i + 1) * 160])
                except Exception as e:
                    logger.debug(f"Error streaming in-band DTMF: {e}")

            time.sleep(0.08)  # Inter-digit pause

    def stream_audio(
        self,
        audio_data: np.ndarray,
        sample_rate: int = 24000,
        stop_check: Optional[Callable[[], bool]] = None
    ) -> None:
        """
        Resamples oral dictation to 8000Hz G.711 telephony audio,
        streams RTP packets to active call, and simultaneously plays
        audio to local monitor stream so clinician hears both sides.
        """
        if audio_data is None or len(audio_data) == 0:
            return

        self._emit_status("🎙️ Streaming oral clinical dictation to telephone call...")
        self._emit_transcript("Outbound Dictation", "Dictation stream playing...")

        # Resample to 8000Hz telephony rate
        target_sr = 8000
        target_len = int(len(audio_data) * target_sr / sample_rate)
        audio_8k = scipy.signal.resample(audio_data, target_len).astype(np.float32)

        # Normalize audio
        max_val = np.max(np.abs(audio_8k))
        if max_val > 1.0:
            audio_8k = audio_8k / max_val

        # Convert to 16-bit PCM and G.711 u-law bytes
        pcm16 = (audio_8k * 32767.0).astype(np.int16).tobytes()
        try:
            ulaw_bytes = audioop.lin2ulaw(pcm16, 2)
        except Exception:
            ulaw_bytes = pcm16

        # Standard 20ms chunks (160 bytes at 8kHz)
        chunk_size_ulaw = 160
        chunk_size_pcm = 320
        num_chunks = len(ulaw_bytes) // chunk_size_ulaw

        logger.info(f"Streaming {len(audio_8k)/target_sr:.2f}s audio ({num_chunks} RTP packets) to call...")

        for i in range(num_chunks):
            if stop_check and stop_check():
                break

            ulaw_chunk = ulaw_bytes[i * chunk_size_ulaw : (i + 1) * chunk_size_ulaw]
            pcm_chunk = pcm16[i * chunk_size_pcm : (i + 1) * chunk_size_pcm]

            # 1. Write RTP packet to telephone call
            if self._active_call and self._is_connected and hasattr(self._active_call, "write_audio"):
                try:
                    self._active_call.write_audio(ulaw_chunk)
                except Exception as e:
                    logger.warning(f"Error writing RTP packet: {e}")

            # 2. Queue for local PC monitor stream so clinician hears it
            if self.listen_in_real_time:
                self._outbound_audio_queue.put(pcm_chunk)

            # Compute outbound activity level
            rms = audioop.rms(pcm_chunk, 2)
            self._emit_activity("outbound", min(1.0, rms / 20000.0))

            # Pace transmission at real-time rate (20ms)
            time.sleep(0.019)

        self._emit_status("✓ Dictation stream completed.")

    def hangup(self) -> None:
        """Terminates active telephone call and stops local audio monitor."""
        self._stop_bridge = True
        if self._bridge_thread and self._bridge_thread.is_alive():
            self._bridge_thread.join(timeout=1.0)
            self._bridge_thread = None

        if self._active_call:
            try:
                self._active_call.hangup()
                self._emit_status("📴 Call concluded.")
                self._emit_transcript("System", "Call ended.")
            except Exception as e:
                logger.warning(f"Error hanging up call: {e}")
            finally:
                self._active_call = None

    def disconnect(self) -> None:
        """Shuts down VoIP phone client and deregisters SIP session."""
        self.hangup()
        if self._phone:
            try:
                self._phone.stop()
                logger.info("VoIP.ms SIP client stopped.")
            except Exception as e:
                logger.warning(f"Error stopping VoIP phone: {e}")
            finally:
                self._phone = None
                self._is_connected = False
