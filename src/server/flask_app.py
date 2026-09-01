"""
Lightweight Flask Backend Server for AI Pipeline & SvelteKit Integration
========================================================================
Exposes REST and WebSocket endpoints for GPU Faster-Whisper transcription,
Kokoro neural TTS with multi-sink submission, and Meditech OCR ingestion.
"""

import json
import logging
from pathlib import Path
from typing import Optional

from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sock import Sock
import numpy as np

from src.tts.synthesizer import MedicalTTSSynthesizer, DEFAULT_VOICE
from src.tts.normalizer import NormalizationMode
from src.tts.sinks import (
    LocalSpeakerSink,
    FileAudioSink,
    TelephonyAudioSink,
)
from src.stt.transcriber import MedicalTranscriber
from src.stt.lexer import PowerPhraseLexer
from src.stt.stream_vad import StreamingAudioProcessor
from src.stt.templates import CLINICAL_MACROS, MacroTemplate
from src.telephony.smartphone_sink import SmartphoneAudioSink
from src.telephony.sip_dialer import SipVoipSink, SipConfig
from src.telephony.fluency_drop import FluencyDropSink
from src.ocr.snip_daemon import MeditechOCRService
from src.utils.template_loader import TemplateManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("powerdictate.flask")

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})
sock = Sock(app)

# Singletons
_tts_engine: Optional[MedicalTTSSynthesizer] = None
_stt_engine: Optional[MedicalTranscriber] = None
_ocr_service: Optional[MeditechOCRService] = None
template_mgr = TemplateManager()


def get_tts_engine() -> MedicalTTSSynthesizer:
    global _tts_engine
    if _tts_engine is None:
        logger.info("Initializing Medical TTS Synthesizer...")
        _tts_engine = MedicalTTSSynthesizer()
    return _tts_engine


def get_stt_engine() -> MedicalTranscriber:
    global _stt_engine
    if _stt_engine is None:
        logger.info("Initializing Medical STT Transcriber...")
        _stt_engine = MedicalTranscriber()
    return _stt_engine


def get_ocr_service() -> MeditechOCRService:
    global _ocr_service
    if _ocr_service is None:
        _ocr_service = MeditechOCRService()
    return _ocr_service


# ------------------ REST Endpoints ------------------

@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok", "app": "PowerDictate", "backend": "flask", "gpu_cuda": True})


@app.route("/api/macros", methods=["GET"])
def list_macros():
    """Returns all registered dot-phrases and macros."""
    macros_data = []
    for m in CLINICAL_MACROS.values():
        macros_data.append({
            "id": m.id,
            "name": m.name,
            "description": m.description,
            "triggers": m.trigger_patterns,
            "replacement": m.replacement
        })
    return jsonify({"macros": macros_data})


@app.route("/api/macros", methods=["POST"])
def add_macro():
    """Registers a new personal dot-phrase macro."""
    data = request.get_json(force=True)
    macro_id = data.get("id")
    name = data.get("name", macro_id)
    description = data.get("description", "")
    triggers = data.get("trigger_patterns", [macro_id])
    replacement = data.get("replacement", "")

    macro = MacroTemplate(
        id=macro_id,
        name=name,
        description=description,
        trigger_patterns=triggers,
        replacement=replacement
    )
    CLINICAL_MACROS[macro_id] = macro
    stt = get_stt_engine()
    if stt.lexer:
        stt.lexer.register_macro(macro)
    return jsonify({"status": "success", "macro_id": macro_id})


@app.route("/api/templates", methods=["GET"])
def list_templates():
    """Returns list of all available YAML templates."""
    templates = template_mgr.list_templates()
    return jsonify({"templates": templates})


@app.route("/api/templates/<template_id>", methods=["GET"])
def get_template(template_id):
    """Loads a specific template by ID."""
    data = template_mgr.get_template(template_id)
    if not data:
        return jsonify({"error": f"Template {template_id} not found"}), 404
    return jsonify(data)


@app.route("/api/templates", methods=["POST"])
def save_template():
    """Saves or updates a template."""
    data = request.get_json(force=True)
    try:
        tmpl_id = template_mgr.save_template(data)
        return jsonify({"status": "success", "id": tmpl_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/tts/speak", methods=["POST"])
def synthesize_speech():
    """Synthesizes note text and dispatches to the selected audio sink."""
    data = request.get_json(force=True)
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "Text cannot be empty"}), 400

    voice = data.get("voice", DEFAULT_VOICE)
    mode_str = data.get("mode", "dictation")
    sink_type = data.get("sink", "speaker")
    provider_id = data.get("provider_id", "12345")
    work_type = data.get("work_type", "01")
    mrn = data.get("mrn", "")
    patient_name = data.get("patient_name", "")
    target_phone = data.get("target_phone", "")

    tts = get_tts_engine()
    mode_enum = NormalizationMode.DICTATION if mode_str == "dictation" else NormalizationMode.WARD_REVIEW
    metadata = {
        "provider_id": provider_id,
        "work_type": work_type,
        "mrn": mrn,
        "patient_name": patient_name,
        "phone_number": target_phone
    }

    if sink_type == "speaker":
        audio, sr = tts.synthesize(text, voice=voice, mode=mode_enum)
        speaker = LocalSpeakerSink(blocking=False)
        speaker.emit(audio, sr, metadata)
        return jsonify({"status": "success", "sink": "speaker", "duration": len(audio) / sr})

    elif sink_type == "wav_file":
        out_dir = Path("output")
        out_dir.mkdir(parents=True, exist_ok=True)
        file_path = out_dir / f"consult_{mrn or 'note'}_24k.wav"
        sink = FileAudioSink(output_path=file_path)
        audio, sr = tts.synthesize(text, voice=voice, mode=mode_enum, sink=sink)
        return jsonify({
            "status": "success",
            "sink": "wav_file",
            "file_path": str(file_path),
            "sample_rate": 24000,
            "duration": len(audio) / 24000
        })

    elif sink_type == "telephony_8k":
        out_dir = Path("output")
        out_dir.mkdir(parents=True, exist_ok=True)
        file_path = out_dir / f"dictation_{mrn or 'note'}_8k.wav"
        sink = TelephonyAudioSink(output_path=file_path)
        audio, sr = tts.synthesize(text, voice=voice, mode=mode_enum, sink=sink)
        return jsonify({
            "status": "success",
            "sink": "telephony_8k",
            "file_path": str(file_path),
            "duration": len(audio) / 8000
        })

    elif sink_type == "smartphone":
        phone_sink = SmartphoneAudioSink()
        audio, sr = tts.synthesize(text, voice=voice, mode=mode_enum)
        phone_sink.emit(audio, sr, metadata)
        return jsonify({"status": "success", "sink": "smartphone", "message": "Streamed to connected phone"})

    elif sink_type == "sip":
        sip_sink = SipVoipSink()
        audio, sr = tts.synthesize(text, voice=voice, mode=mode_enum)
        res = sip_sink.emit(audio, sr, metadata)
        return jsonify({"status": "success", "sink": "sip", "call_result": res})

    elif sink_type == "fluency":
        drop_sink = FluencyDropSink()
        audio, sr = tts.synthesize(text, voice=voice, mode=mode_enum)
        res = drop_sink.emit(audio, sr, metadata)
        return jsonify({"status": "success", "sink": "fluency", "job_package": res})

    else:
        return jsonify({"error": f"Unknown sink type: {sink_type}"}), 400


@app.route("/api/ocr/clipboard", methods=["POST"])
def ocr_clipboard():
    """Extracts demographics and labs from clipboard image."""
    ocr = get_ocr_service()
    data = ocr.process_clipboard()
    if data is None:
        return jsonify({"error": "No valid image found on system clipboard"}), 404
    return jsonify({
        "mrn": data.mrn,
        "patient_name": data.patient_name,
        "age": data.age,
        "sex": data.sex,
        "vitals": data.vitals,
        "cbc": data.cbc,
        "chem": data.chem,
        "cardiac": data.cardiac,
        "coag": data.coag,
        "snippet": data.to_formatted_note_snippet()
    })


# ------------------ WebSocket Streaming with VAD ------------------

@sock.route("/ws/dictate")
def ws_dictate(ws):
    """
    WebSocket endpoint for real-time microphone stream transcription & macro lexing.
    Uses StreamingAudioProcessor with silence gating to eliminate word repetitions.
    """
    stt = get_stt_engine()
    lexer = PowerPhraseLexer()
    stream_processor = StreamingAudioProcessor(sample_rate=16000)
    logger.info("WebSocket client connected to Flask Sock with VAD gating.")

    try:
        while True:
            msg = ws.receive()
            if msg is None:
                break

            if isinstance(msg, bytes):
                # Feed raw PCM16 bytes through VAD stream processor
                utterance_audio = stream_processor.process_chunk(msg)

                if utterance_audio is not None and len(utterance_audio) > 0:
                    raw_text, _ = stt.transcribe_audio(utterance_audio, apply_lexer=False)
                    if raw_text.strip():
                        res = lexer.process(raw_text)
                        if res.is_navigation_command:
                            ws.send(json.dumps({"type": "navigation", "command": res.command_type}))
                        else:
                            ws.send(json.dumps({
                                "type": "transcript",
                                "text": res.text,
                                "is_macro": res.expanded,
                                "macro_id": res.macro_id,
                                "placeholders_count": res.placeholders_count
                            }))

            elif isinstance(msg, str):
                try:
                    payload = json.loads(msg)
                    if payload.get("action") == "flush":
                        utterance_audio = stream_processor.flush()
                        if utterance_audio is not None and len(utterance_audio) > 0:
                            raw_text, _ = stt.transcribe_audio(utterance_audio, apply_lexer=False)
                            if raw_text.strip():
                                res = lexer.process(raw_text)
                                if res.is_navigation_command:
                                    ws.send(json.dumps({"type": "navigation", "command": res.command_type}))
                                else:
                                    ws.send(json.dumps({
                                        "type": "transcript",
                                        "text": res.text,
                                        "is_macro": res.expanded,
                                        "macro_id": res.macro_id,
                                        "placeholders_count": res.placeholders_count
                                    }))
                except Exception:
                    pass

    except Exception as e:
        logger.error(f"WebSocket session ended: {e}")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
