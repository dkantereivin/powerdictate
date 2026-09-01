"""
Generate High-Fidelity Medical Consult TTS Audio Samples
"""

from pathlib import Path
from src.tts.synthesizer import MedicalTTSSynthesizer
from src.tts.normalizer import NormalizationMode
from src.tts.sinks import FileAudioSink, TelephonyAudioSink, MultiSink


SAMPLE_CARDIOLOGY_CONSULT = """
CONSULT NOTE — CARDIOLOGY

Patient: Eleanor McPherson, 68-year-old female
Referring physician: Dr. Jonathan R. Patel
Consultant: Dr. Miriam O'Connor
Date: September 1, 2026

Reason for consultation: Evaluation of progressive exertional dyspnea and intermittent palpitations.

History: Ms. McPherson reports approximately six weeks of worsening shortness of breath when climbing stairs, associated with occasional fluttering sensations lasting 30 to 60 seconds. She denies syncope, orthopnea, paroxysmal nocturnal dyspnea, or pleuritic chest pain. ECG obtained demonstrated sinus rhythm with occasional premature atrial complexes.

Past medical history: Hypertension, type 2 diabetes mellitus, hyperlipidemia, and stage 3a chronic kidney disease.

Medications: amlodipine 5mg PO daily, metformin 1,000mg PO with supper, atorvastatin 40mg PO nightly, empagliflozin 10mg PO daily, ramipril 10mg PO daily, and pantoprazole 40mg PO PRN.

Examination: BP 138/74, HR 82, regular. No jugular venous distention. Normal S1 and S2 without murmur. Lungs clear bilaterally. No peripheral edema.

Assessment and plan: Exertional dyspnea of unclear etiology, with intermittent palpitations and multiple cardiovascular risk factors. I recommend transthoracic echocardiography, a 14-day ambulatory Zio monitor, CBC, CMP, TSH, and BNP. Continue current medications pending results.
"""

SAMPLE_CTU_ADMISSION = """
CTU INTERNAL MEDICINE ADMISSION NOTE

Patient: 74-year-old male presenting from Emergency Department.
Attending: Dr. Robert Harrison

History of Present Illness:
Patient presents with 4 days of progressive productive cough with purulent sputum, fever, and dyspnea on minimal exertion. Chest X-ray demonstrates right lower lobe consolidation consistent with community acquired pneumonia.

Past Medical History: COPD Gold Stage 2, HFrEF with baseline LVEF 35%, atrial fibrillation on apixaban.

Medications on Admission:
1. Tazocin 3.375g IV q8h
2. Azithromycin 500mg IV q24h
3. Lasix 40mg IV BID for mild volume overload
4. Apixaban 5mg PO BID
5. Bisoprolol 5mg PO daily
6. Spiriva 1 puff inhaled daily

Physical Examination:
Vitals: BP 118/68, HR 88 irregular, SpO2 94% on 2L nasal prongs, T 38.4 C, RR 22.
General: Mild respiratory distress, speaking in full sentences.
Cardiovascular: Irregularly irregular rhythm, S1/S2 present, no murmurs. JVP 3cm above sternal angle.
Respiratory: Bronchial breath sounds and inspiratory crackles over right lung base.
Abdomen: Soft, non-tender, no organomegaly.

Labs:
WBC 16.4 with left shift, Hgb 132, Plt 210.
Sodium 136, Potassium 4.1, Creatinine 112, BUN 7.8, eGFR 58.
hs-cTn 18, BNP 420.

Impression & Plan:
1. Community Acquired Pneumonia: continue IV Tazocin and Azithromycin, monitor sputum cultures.
2. Acute Decompensated Heart Failure secondary to infection: Lasix 40mg IV BID, fluid restrict 1.5 L/day, strict input and output, daily weights.
3. Atrial Fibrillation: rate controlled on bisoprolol, therapeutic on apixaban.
"""


def generate_all_samples(output_dir: str = "output"):
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    
    synthesizer = MedicalTTSSynthesizer()
    print("Synthesizing Cardiology Consult (Dictation Mode for Telephony/PBX)...")
    
    # 1. Cardiology Consult in PBX Dictation Mode (spoken punctuation)
    cardio_master = out_path / "cardiology_consult_pbx_master_24k.wav"
    cardio_telephony = out_path / "cardiology_consult_pbx_telephony_8k.wav"
    
    sink = MultiSink([
        FileAudioSink(cardio_master),
        TelephonyAudioSink(cardio_telephony, target_sample_rate=8000)
    ])
    synthesizer.synthesize(SAMPLE_CARDIOLOGY_CONSULT, mode=NormalizationMode.DICTATION, sink=sink)
    print(f"  -> Generated {cardio_master}")
    print(f"  -> Generated {cardio_telephony}")
    
    # 2. CTU Admission in Ward Review Mode (natural prosody for room/doctor listening)
    print("Synthesizing CTU Admission (Ward Review Mode)...")
    ctu_ward = out_path / "ctu_admission_ward_review_24k.wav"
    ctu_telephony = out_path / "ctu_admission_telephony_8k.wav"
    
    sink_ctu = MultiSink([
        FileAudioSink(ctu_ward),
        TelephonyAudioSink(ctu_telephony, target_sample_rate=8000)
    ])
    synthesizer.synthesize(SAMPLE_CTU_ADMISSION, mode=NormalizationMode.WARD_REVIEW, sink=sink_ctu)
    print(f"  -> Generated {ctu_ward}")
    print(f"  -> Generated {ctu_telephony}")
    
    print("\nAll sample generation complete!")


if __name__ == "__main__":
    generate_all_samples()
