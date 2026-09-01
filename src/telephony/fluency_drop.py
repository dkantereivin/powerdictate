"""
Option C: 3M M*Modal / Fluency Mobile & Drop Folder Exporter
============================================================
Generates structured metadata packages (XML/JSON envelopes) and 16kHz WAV audio
for ingestion into hospital dictation queues (3M Fluency, Winscribe, Philips SpeechLive).
"""

import json
import uuid
import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Union
import numpy as np
import soundfile as sf

from src.tts.sinks import AudioSink


class FluencyDropSink(AudioSink):
    """
    Exports dictation audio and metadata in the standard XML/JSON drop format
    expected by enterprise hospital dictation servers.
    """

    def __init__(
        self,
        drop_directory: Union[str, Path] = "exports/fluency",
        facility_id: str = "CTU_HOSPITAL",
        target_sample_rate: int = 16000
    ):
        self.drop_dir = Path(drop_directory)
        self.facility_id = facility_id
        self.target_sample_rate = target_sample_rate

    def emit(self, audio: np.ndarray, sample_rate: int, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if audio is None or len(audio) == 0:
            raise ValueError("No audio provided to FluencyDropSink.")

        meta = metadata or {}
        job_id = meta.get("job_id", f"JOB-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}")
        provider_id = meta.get("provider_id", "UNKNOWN_MD")
        work_type = meta.get("work_type", "01")
        mrn = meta.get("mrn", "UNKNOWN_MRN")
        patient_name = meta.get("patient_name", "UNKNOWN, PATIENT")
        timestamp = datetime.datetime.now().isoformat()

        # Resample to 16kHz for enterprise dictation standard
        if sample_rate != self.target_sample_rate:
            from scipy.signal import resample_poly
            import math
            gcd = math.gcd(sample_rate, self.target_sample_rate)
            audio_16k = resample_poly(audio, self.target_sample_rate // gcd, sample_rate // gcd).astype(np.float32)
        else:
            audio_16k = audio.astype(np.float32)

        self.drop_dir.mkdir(parents=True, exist_ok=True)

        audio_filename = f"{job_id}.wav"
        audio_filepath = self.drop_dir / audio_filename
        sf.write(str(audio_filepath), audio_16k, self.target_sample_rate, subtype="PCM_16")

        duration_sec = len(audio_16k) / float(self.target_sample_rate)

        # 1. Generate JSON Metadata Envelope
        job_dict = {
            "job_id": job_id,
            "facility_id": self.facility_id,
            "provider_id": provider_id,
            "work_type": work_type,
            "mrn": mrn,
            "patient_name": patient_name,
            "timestamp": timestamp,
            "duration_seconds": round(duration_sec, 2),
            "audio_file": audio_filename,
            "audio_format": "PCM_16BIT_16KHZ",
            "channels": 1
        }
        json_filepath = self.drop_dir / f"{job_id}.json"
        with open(json_filepath, "w", encoding="utf-8") as f:
            json.dump(job_dict, f, indent=2)

        # 2. Generate XML Metadata Envelope (HL7/Winscribe/Fluency compatible)
        xml_content = f"""<?xml version="1.0" encoding="utf-8"?>
<DictationJob Version="2.0">
  <JobID>{job_id}</JobID>
  <FacilityID>{self.facility_id}</FacilityID>
  <ProviderID>{provider_id}</ProviderID>
  <WorkType>{work_type}</WorkType>
  <PatientMRN>{mrn}</PatientMRN>
  <PatientName>{patient_name}</PatientName>
  <CreatedDateTime>{timestamp}</CreatedDateTime>
  <DurationSeconds>{duration_sec:.2f}</DurationSeconds>
  <AudioFileName>{audio_filename}</AudioFileName>
  <AudioFormat>WAV_16KHZ_MONO</AudioFormat>
</DictationJob>"""
        xml_filepath = self.drop_dir / f"{job_id}.xml"
        with open(xml_filepath, "w", encoding="utf-8") as f:
            f.write(xml_content)

        return {
            "job_id": job_id,
            "audio_file": str(audio_filepath),
            "xml_file": str(xml_filepath),
            "json_file": str(json_filepath),
            "duration_seconds": duration_sec
        }
