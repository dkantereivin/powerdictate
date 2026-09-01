"""
FastAPI Server & WebSocket Dictation Daemon
===========================================
Hosts the local-first clinical documentation UI, real-time WebSocket STT
streaming, neural TTS synthesis with multi-sink dispatch, and Meditech OCR ingestion.
"""

import io
import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from pydantic import BaseModel
import soundfile as sf
import numpy as np

from src.tts.synthesizer import MedicalTTSSynthesizer, DEFAULT_VOICE
from src.tts.normalizer import NormalizationMode
from src.tts.sinks import (
    LocalSpeakerSink,
    FileAudioSink,
    TelephonyAudioSink,
    MultiSink,
)
from src.stt.transcriber import MedicalTranscriber
from src.stt.lexer import PowerPhraseLexer
from src.stt.templates import CLINICAL_MACROS, MacroTemplate
from src.telephony.dtmf import DTMFGenerator
from src.telephony.smartphone_sink import SmartphoneAudioSink
from src.telephony.sip_dialer import SipVoipSink, SipConfig
from src.telephony.fluency_drop import FluencyDropSink
from src.ocr.snip_daemon import MeditechOCRService
from src.ocr.meditech_parser import MeditechOCRParser

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("powerdictate.server")

app = FastAPI(title="PowerDictate CTU Clinical Documentation Engine", version="0.1.0")

# Lazy-loaded singletons for memory efficiency
_tts_engine: Optional[MedicalTTSSynthesizer] = None
_stt_engine: Optional[MedicalTranscriber] = None
_ocr_service: Optional[MeditechOCRService] = None


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


# ------------------ REST Request Models ------------------

class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = DEFAULT_VOICE
    mode: str = "dictation"  # "dictation" or "ward_review"
    sink: str = "speaker"    # "speaker", "telephony_8k", "smartphone", "sip", "fluency"
    provider_id: Optional[str] = "12345"
    work_type: Optional[str] = "01"
    mrn: Optional[str] = ""
    patient_name: Optional[str] = ""
    target_phone: Optional[str] = ""


class MacroCreateRequest(BaseModel):
    id: str
    name: str
    description: str
    trigger_patterns: List[str]
    replacement: str


# ------------------ REST Endpoints ------------------

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "app": "PowerDictate", "gpu_cuda": True}


@app.get("/api/macros")
async def list_macros():
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
    return {"macros": macros_data}


@app.post("/api/macros")
async def add_macro(req: MacroCreateRequest):
    """Registers a new personal dot-phrase macro."""
    macro = MacroTemplate(
        id=req.id,
        name=req.name,
        description=req.description,
        trigger_patterns=req.trigger_patterns,
        replacement=req.replacement
    )
    CLINICAL_MACROS[req.id] = macro
    stt = get_stt_engine()
    if stt.lexer:
        stt.lexer.register_macro(macro)
    return {"status": "success", "macro_id": req.id}


@app.post("/api/tts/speak")
async def synthesize_speech(req: TTSRequest):
    """Synthesizes note text and dispatches to the requested sink."""
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty.")

    tts = get_tts_engine()
    mode_enum = NormalizationMode.DICTATION if req.mode == "dictation" else NormalizationMode.WARD_REVIEW
    metadata = {
        "provider_id": req.provider_id or "",
        "work_type": req.work_type or "01",
        "mrn": req.mrn or "",
        "patient_name": req.patient_name or "",
        "phone_number": req.target_phone or ""
    }

    # Dispatch based on chosen sink
    if req.sink == "speaker":
        audio, sr = tts.synthesize(req.text, voice=req.voice, mode=mode_enum)
        speaker = LocalSpeakerSink(blocking=False)
        speaker.emit(audio, sr, metadata)
        return {"status": "success", "sink": "speaker", "duration": len(audio) / sr}

    elif req.sink == "telephony_8k":
        out_dir = Path("output")
        out_dir.mkdir(parents=True, exist_ok=True)
        file_path = out_dir / f"dictation_{req.mrn or 'note'}_8k.wav"
        sink = TelephonyAudioSink(output_path=file_path)
        audio, sr = tts.synthesize(req.text, voice=req.voice, mode=mode_enum, sink=sink)
        return {
            "status": "success",
            "sink": "telephony_8k",
            "file_path": str(file_path),
            "duration": len(audio) / 8000
        }

    elif req.sink == "smartphone":
        phone_sink = SmartphoneAudioSink()
        audio, sr = tts.synthesize(req.text, voice=req.voice, mode=mode_enum)
        phone_sink.emit(audio, sr, metadata)
        return {"status": "success", "sink": "smartphone", "message": "Streamed to connected smartphone"}

    elif req.sink == "sip":
        sip_sink = SipVoipSink()
        audio, sr = tts.synthesize(req.text, voice=req.voice, mode=mode_enum)
        res = sip_sink.emit(audio, sr, metadata)
        return {"status": "success", "sink": "sip", "call_result": res}

    elif req.sink == "fluency":
        drop_sink = FluencyDropSink()
        audio, sr = tts.synthesize(req.text, voice=req.voice, mode=mode_enum)
        res = drop_sink.emit(audio, sr, metadata)
        return {"status": "success", "sink": "fluency", "job_package": res}

    else:
        raise HTTPException(status_code=400, detail=f"Unknown sink type: {req.sink}")


@app.post("/api/ocr/clipboard")
async def ocr_clipboard():
    """Extracts demographics and labs from clipboard image."""
    ocr = get_ocr_service()
    data = ocr.process_clipboard()
    if data is None:
        raise HTTPException(status_code=404, detail="No valid image found on system clipboard.")
    return {
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
    }


# ------------------ WebSocket STT Endpoint ------------------

@app.websocket("/ws/dictate")
async def websocket_dictate(websocket: WebSocket):
    """
    Bidirectional streaming WebSocket for real-time microphone dictation.
    Accepts raw audio chunks, passes to Faster-Whisper, applies Power-Phrase Lexer,
    and returns token events and navigation commands.
    """
    await websocket.accept()
    stt = get_stt_engine()
    lexer = PowerPhraseLexer()
    logger.info("WebSocket dictation client connected.")

    audio_buffer = bytearray()

    try:
        while True:
            data = await websocket.receive()
            
            if "bytes" in data and data["bytes"]:
                chunk = data["bytes"]
                audio_buffer.extend(chunk)

                # Process every ~1.0-1.5 seconds of 16kHz 16-bit mono audio (32000 bytes)
                if len(audio_buffer) >= 32000:
                    raw_bytes = bytes(audio_buffer)
                    audio_buffer.clear()

                    # Convert 16-bit PCM bytes to float32 numpy array
                    pcm_16 = np.frombuffer(raw_bytes, dtype=np.int16)
                    float_audio = pcm_16.astype(np.float32) / 32768.0

                    # Transcribe chunk
                    raw_text, _ = stt.transcribe_audio(float_audio, apply_lexer=False)
                    
                    if raw_text.strip():
                        # Process through Power Phrase Lexer
                        res = lexer.process(raw_text)
                        
                        if res.is_navigation_command:
                            await websocket.send_json({
                                "type": "navigation",
                                "command": res.command_type
                            })
                        else:
                            await websocket.send_json({
                                "type": "transcript",
                                "text": res.text,
                                "is_macro": res.expanded,
                                "macro_id": res.macro_id,
                                "placeholders_count": res.placeholders_count
                            })

            elif "text" in data and data["text"]:
                msg = json.loads(data["text"])
                if msg.get("action") == "flush" and len(audio_buffer) > 0:
                    raw_bytes = bytes(audio_buffer)
                    audio_buffer.clear()
                    pcm_16 = np.frombuffer(raw_bytes, dtype=np.int16)
                    float_audio = pcm_16.astype(np.float32) / 32768.0
                    raw_text, _ = stt.transcribe_audio(float_audio, apply_lexer=False)
                    if raw_text.strip():
                        res = lexer.process(raw_text)
                        if res.is_navigation_command:
                            await websocket.send_json({"type": "navigation", "command": res.command_type})
                        else:
                            await websocket.send_json({
                                "type": "transcript",
                                "text": res.text,
                                "is_macro": res.expanded,
                                "macro_id": res.macro_id,
                                "placeholders_count": res.placeholders_count
                            })

    except WebSocketDisconnect:
        logger.info("WebSocket dictation client disconnected.")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")


# ------------------ Static Frontend Mounting ------------------

frontend_path = Path(__file__).resolve().parent.parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path / "src")), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def serve_index():
        index_file = frontend_path / "index.html"
        if index_file.exists():
            return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
        return HTMLResponse("<h1>PowerDictate UI</h1><p>index.html not found.</p>")
