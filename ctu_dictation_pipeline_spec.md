# CTU Clinical Documentation, Automated Dictation & EMR Ingestion Pipeline
*System Architecture, Engineering Specifications, and Clinical Workflow Implementation Guide*

---

## 1. Executive Summary & Clinical Context

In a hybrid/paper hospital environment (such as Thunder Bay Regional Health Sciences Centre - TBRHSC), clinical consults (e.g., CTU Internal Medicine consults) frequently require double documentation:
1. **Official Medical Record:** Dictated via telephone PBX or mobile dictation app into Meditech (which has a 12–48 hour human transcription lag).
2. **Immediate Ward Operational Record:** Hand-filed into the physical patient chart binder on 50/50 split NCR (No-Carbon-Required) Doctor's Order / Progress Note sheets to provide an immediate operational bridge for ward nursing, allied health, and cross-covering teams.

### The Objective
Build a privacy-preserving, local-first web interface and background pipeline that:
- **Speech-to-Text & Live Templating:** Captures local microphone dictation in real time with custom medical "Power Phrases" / dot-phrase macro expansions and placeholder navigation (`[ ]` jumping), replicating Dragon Medical without subscriptions.
- **Single-Click Dual Submission:**
  - **Path A (Physical Chart):** Formats a clean, high-density `@media print` note on standard 8.5×11 bond paper for the physical chart, requiring only quick handwritten active admission orders on the 2-part NCR order sheet.
  - **Path B (Telephony/Dictation Backend):** Runs a local Neural Text-to-Speech (TTS) engine, connects to the hospital dictation phone line (via automated SIP/VoIP or mobile audio injection), handles IVR prompts via RFC 2833 DTMF tones, and streams the dictation automatically.
- **Meditech Screen Ingestion:** Uses local offline OCR (e.g., Tesseract) to snip data from legacy Meditech Client/Server (purple terminal UI running inside remote Citrix sessions) without clipboard barriers.
- **100% PHIPA Compliance:** Operates strictly on `localhost` with zero third-party cloud data leakage of Patient Health Information (PHI).

---

## 2. Clinical Workflow & Physical Charting Strategy

### The 50/50 Split NCR Paper Bottleneck
* **The Problem:** 2-part carbonless paper (Doctor's Orders on left, Progress Notes on right) cannot be fed into standard hospital laser printers due to fuser heat (180°C–200°C) bursting micro-encapsulated dye, causing smudging and mechanical jams.
* **The Clinical Solution:**
  1. **Handwritten Orders Column (Left):** Write a 30-second bulleted admission order list on the 2-part NCR sheet (*"1. Admit CTU under Dr. X. 2. Vitals q4h. 3. Meds/details as per typed admission note in chart."*). Nursing tears off the yellow duplicate copy for immediate pharmacy/ward execution.
  2. **Handwritten Progress Notes Column (Right):** Write a 1-line bridge reference:  
     `"CTU Consult — See attached typed note. Dictated / Meditech pending (Job #[XXX])."`
  3. **Printed Consult Note:** Print the full, typed consult note from the local app onto plain copy paper, affix the patient addressograph sticker, date/time, sign with CPSO number, and hole-punch directly into the chart behind the order sheet.

---

## 3. High-Level System Architecture

```
                                      ┌─────────────────────────────────────────────────────────┐
                                      │                 LOCAL HOST ENVIRONMENT                  │
                                      │                                                         │
┌───────────────────────┐             │  ┌─────────────────────────┐   ┌─────────────────────┐  │             ┌─────────────────────────┐
│    Citrix Meditech    │──(Screen)───┼─▶│   Offline Screen OCR    │──▶│   Context Parser    │  │             │   Hospital Dictation    │
│  (Remote Pixel Feed)  │             │  │       (Tesseract)       │   │  (Demographics/Labs)│  │             │      PBX / Server       │
└───────────────────────┘             │  └─────────────────────────┘   └──────────┬──────────┘  │             └───────────▲─────────────┘
                                      │                                           │             │                         │
                                      │  ┌────────────────────────────────────────▼──────────┐  │                         │ (RTP Stream +
                                      │  │               Web Application UI                   │  │                         │  RFC 2833 DTMF)
                                      │  │  • TipTap Rich-Text Editor + Dot-Phrases           │  │                         │
                                      │  │  • Real-Time STT (Faster-Whisper / WebGPU)         │  │                         │
                                      │  │  • Live Power Phrase Lexer ("No PE", etc.)         │  │                         │
                                      │  └──────────┬─────────────────────────────┬───────────┘  │                         │
                                      │             │                             │              │                         │
                                      │     (Ctrl+P / Print)             (Submit & Dictate)      │                         │
                                      │             ▼                             ▼              │                         │
                                      │  ┌────────────────────┐          ┌────────────────────┐  │   ┌────────────────┐    │
                                      │  │ @media print Engine│          │ Text Normalizer    │──┼──▶│ Headless SIP   │────┘
                                      │  │ (Chart Printout)   │          │ + Piper TTS (ONNX) │  │   │ Client (pjsua) │
                                      │  └────────────────────┘          └────────────────────┘  │   └────────────────┘
                                      │                                                         │
                                      └─────────────────────────────────────────────────────────┘
```

---

## 4. Subsystem Deep Dives & Implementation Plans

### Module 1: In-Browser STT & Live Power Phrase Lexer (Dragon Alternative)

#### A. STT Engine Options
1. **Local Backend WebSocket (Recommended for low latency):**
   * Python daemon running `faster-whisper` (`whisper-base.en` or `small.en`) on CPU/GPU.
   * Exposes a local WebSocket at `ws://127.0.0.1:8765/stt`.
   * Client streams 250ms PCM chunks from `navigator.mediaDevices.getUserMedia`.
2. **In-Browser WebGPU:**
   * Uses `@xenova/transformers` (Transformers.js) running Whisper directly in browser VRAM.

#### B. Vocabulary Priming
Pass an `initial_prompt` to the model containing hospital-specific clinical terminology:
```python
INITIAL_PROMPT = (
    "Patient presents with dyspnea, orthopnea, JVP, troponin, HFrEF, HFpEF, "
    "ceftriaxone, piperacillin-tazobactam, CT head, CBC, lytes, BUN, Cr, "
    "Wells score, PERC rule, CTA chest, GCS, bibasilar crackles."
)
```

#### C. Power Phrase Lexer & Dynamic Placeholder Expansion
Intercept speech tokens before appending to the editor. Support both explicit voice triggers (*"macro"*, *"insert"*, *"dot"*) and standalone utterance matches:

```typescript
interface MacroTemplate {
  triggerPatterns: RegExp[];
  replacement: string;
}

const POWER_PHRASES: Record<string, MacroTemplate> = {
  no_pe: {
    triggerPatterns: [
      /(?:macro|insert|dot)?\s*(?:no\s*p\s*e|negative\s*p\s*e)/i
    ],
    replacement:
      `• [No] cough / hemoptysis
` +
      `• [No] recent travel or immobilization
` +
      `• [No] history of VTE / DVT / PE
` +
      `• [No] unilateral leg swelling / erythema
` +
      `--> Wells score: [ # ], PERC: [ +/- ]`
  },
  norm_card: {
    triggerPatterns: [
      /(?:macro|insert|dot)?\s*(?:normal\s*cardiac|norm\s*card)/i
    ],
    replacement: `S1/S2 normal, regular rate and rhythm. No murmurs, rubs, or gallops. Peripheral pulses 2+ bilaterally, JVP [ flat / <3cm ].`
  },
  hfref_plan: {
    triggerPatterns: [
      /(?:macro|insert|dot)?\s*(?:hfref\s*plan|heart\s*failure\s*plan)/i
    ],
    replacement:
      `# Acute Decompensated Heart Failure (HFrEF)
` +
      `- Lasix [ 40 ] mg IV [ BID / daily ]
` +
      `- Fluid restrict to [ 1.5 ] L/day, strict I/O, daily weights
` +
      `- Target euvolemia; hold ACEi/ARB/ARNI if SBP < [ 100 ]
` +
      `- Echocardiogram ordered / pending`
  }
};

function processIncomingSTT(rawText: string, editor: any): void {
  // 1. Voice Navigation Commands
  if (/^(?:next\s*field|tab)$/i.test(rawText.trim())) {
    selectNextPlaceholder(editor);
    return;
  }

  // 2. Power Phrase Expansions
  let transformed = rawText;
  let expanded = false;
  for (const [_, macro] of Object.entries(POWER_PHRASES)) {
    for (const pattern of macro.triggerPatterns) {
      if (pattern.test(transformed)) {
        transformed = transformed.replace(pattern, macro.replacement);
        expanded = true;
      }
    }
  }

  // 3. Punctuation Mapping
  transformed = transformed
    .replace(/period/gi, '.')
    .replace(/comma/gi, ',')
    .replace(/new\s*paragraph/gi, '

')
    .replace(/new\s*line/gi, '
')
    .replace(/colon/gi, ':');

  editor.commands.insertContent(transformed);

  if (expanded) {
    selectNextPlaceholder(editor);
  }
}

function selectNextPlaceholder(editor: any): void {
  const content = editor.getText();
  const match = /\[(.*?)\]/.exec(content);
  if (match) {
    // Set selection range to the matched brackets for instant overwrite
    const start = match.index;
    const end = start + match[0].length;
    editor.commands.setTextSelection({ from: start + 1, to: end + 1 });
  }
}
```

---

### Module 2: Medical Text Normalization & Local Neural TTS Engine

Human transcriptionists and automated dictation listeners expect spoken punctuation tokens and accurately articulated drug dosages.

```
Raw Note ──▶ [Normalizer: Punctuation & Rx Expansion] ──▶ [Phonemizer / Lexicon] ──▶ [Piper TTS] ──▶ 8kHz Mono PCM
```

#### A. Text Normalization Rules
1. **Punctuation Injection:** Pre-process text to insert explicit punctuation words if dictating to a human transcriptionist (e.g., `.` $ightarrow$ `", period, "`, `

` $ightarrow$ `", new paragraph, "`).
2. **Pharmacology / Acronym Expansions:**
   - `"Tazocin 3.375g IV q8h"` $ightarrow$ `"Tazocin three point three seven five grams intravenously every eight hours"`
   - `"Lasix 40mg PO daily"` $ightarrow$ `"Lasix forty milligrams by mouth daily"`
   - `"HFrEF"` $ightarrow$ `"Heart Failure with reduced Ejection Fraction"`

#### B. Local TTS Synthesis via Piper
- **Model:** `en_US-lessac-medium` or `en_US-libritts-high` running locally via ONNX Runtime.
- **Audio Output:** Resampled to **16-bit Mono PCM at 8000 Hz** (standard telephony sampling rate for G.711u).

```python
import subprocess
import wave

def synthesize_clinical_audio(normalized_text: str, output_wav: str):
    # Piper TTS CLI execution
    cmd = [
        "piper",
        "--model", "models/en_US-lessac-medium.onnx",
        "--output_file", output_wav
    ]
    process = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    process.communicate(input=normalized_text.encode('utf-8'))
    
    # Ensure audio format is resampled to 8kHz mono PCM for PBX streaming
    resample_cmd = [
        "ffmpeg", "-y", "-i", output_wav,
        "-ar", "8000", "-ac", "1", "-c:a", "pcm_s16le",
        "telephony_" + output_wav
    ]
    subprocess.run(resample_cmd, check=True)
```

---

### Module 3: Automated Telephony & IVR PBX Traversal

#### A. The Telephony State Machine
```
[INIT SIP CALL to Dictation Number]
               │
               ▼
[WAIT: Connection Established (ACK)]
               │
               ▼
[DTMF: Send Provider ID + '#'] ──▶ [PAUSE: 2.5s]
                                         │
                                         ▼
[DTMF: Send Work Type + '#']   ──▶ [PAUSE: 2.0s]
                                         │
                                         ▼
[DTMF: Send Patient MRN + '#'] ──▶ [PAUSE: 3.0s (Wait for tone)]
                                         │
                                         ▼
[STREAM: Transmit 8kHz PCM Audio (RTP Payload)]
                                         │
                                         ▼
[DTMF: Send Disconnect / Save Key (e.g., '8')] ──▶ [TERMINATE CALL]
```

#### B. Headless PJSIP (`pjsua`) Automation Script
```python
import pjsua2 as pj
import time

class DictationCall(pj.Call):
    def __init__(self, acc, peer_uri, audio_file, dtmf_sequence):
        super().__init__(acc)
        self.audio_file = audio_file
        self.dtmf_sequence = dtmf_sequence  # e.g., [("1234#", 2.5), ("01#", 2.0), ("9876543#", 3.0)]

    def onCallState(self, prm):
        ci = self.getInfo()
        if ci.state == pj.PJSIP_INV_STATE_CONFIRMED:
            print("Call connected. Executing IVR state sequence...")
            self.execute_ivr()

    def execute_ivr(self):
        for dtmf_digits, delay in self.dtmf_sequence:
            for digit in dtmf_digits:
                self.dialDtmf(digit)
            time.sleep(delay)
        
        print("IVR navigation complete. Streaming TTS audio payload...")
        # Stream WAV file to audio conference bridge
        # (Connect local player to call audio media)
```

---

### Module 4: Meditech Client/Server Data Ingestion (Citrix OCR)

Because legacy Meditech (purple terminal UI) inside Citrix Workspace disables native text selection and restricts clipboard sync, use an offline local screen snip + OCR pipeline.

```
User triggers Global Hotkey (e.g., Ctrl+Shift+S)
               │
               ▼
Capture Citrix Window Bounding Box
               │
               ▼
Local Tesseract OCR Engine (Engine Mode: Monospace/Table)
               │
               ▼
Regex Extraction: Demographics, Vitals, Labs (CBC, Lytes, BUN, Cr)
               │
               ▼
Auto-populate Context Object in Local Editor UI
```

#### Python Local OCR Daemon (`ocr_daemon.py`):
```python
import pytesseract
from PIL import ImageGrab
import re

def capture_and_parse_meditech():
    # Grab clipboard image or bounding box screenshot
    img = ImageGrab.grabclipboard()
    if img is None:
        return None

    raw_text = pytesseract.image_to_string(img, config='--psm 6')
    
    # Monospace parsing for standard Meditech lab layouts
    parsed_data = {
        "mrn": None,
        "hemoglobin": None,
        "wbc": None,
        "platelets": None,
        "creatinine": None
    }
    
    mrn_match = re.search(r'MRN[:\s]+(\d{6,8})', raw_text, re.IGNORECASE)
    if mrn_match:
        parsed_data["mrn"] = mrn_match.group(1)

    hgb_match = re.search(r'HGB[:\s]+(\d+)', raw_text)
    if hgb_match:
        parsed_data["hemoglobin"] = hgb_match.group(1)

    return parsed_data
```

---

### Module 5: Print-to-Chart Engine (`@media print`)

The application must include a high-density, professional print stylesheet that formats the consult note perfectly onto standard 8.5×11 bond paper.

```css
@media print {
  @page {
    size: letter portrait;
    margin: 15mm 15mm 15mm 15mm;
  }

  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    font-size: 10pt;
    line-height: 1.35;
    color: #000;
    background: #fff;
  }

  .no-print {
    display: none !important;
  }

  .chart-header {
    border-bottom: 2px solid #000;
    padding-bottom: 4px;
    margin-bottom: 8px;
    display: table;
    width: 100%;
  }

  .chart-header-left {
    display: table-cell;
    vertical-align: top;
  }

  .chart-header-right {
    display: table-cell;
    vertical-align: top;
    text-align: right;
  }

  .section-title {
    font-size: 11pt;
    font-weight: bold;
    text-transform: uppercase;
    border-bottom: 1px solid #ccc;
    margin-top: 8px;
    margin-bottom: 4px;
  }

  .signature-block {
    margin-top: 20px;
    page-break-inside: avoid;
    display: table;
    width: 100%;
  }
}
```

---

## 5. Development Roadmap & Execution Checklist

| Phase | Component | Deliverable | Key Validation |
| :--- | :--- | :--- | :--- |
| **1** | **Local STT & Power Phrases** | WebSocket STT daemon + TipTap editor with dot-phrases & `[ ]` field jumping. | Test expansion latency (<100ms) and accuracy on `"No PE"` and `"Normal Cardiac"`. |
| **2** | **Print Engine** | Formatted web view with `@media print` CSS for standard 8.5×11 chart printout. | Verify 1-page/2-page layouts print cleanly without clipping margins or orphan headings. |
| **3** | **OCR Ingestion Tool** | Global shortcut screen grabber + Tesseract parser for legacy Meditech screens. | Extract patient demographics and lab values from Citrix window without clipboard sync. |
| **4** | **TTS & Text Normalizer** | Regex normalizer + Piper TTS (ONNX) rendering 8kHz mono PCM WAV files. | Validate pronunciation of complex pharmacology terms (e.g., *Piperacillin-Tazobactam*). |
| **5** | **SIP/VoIP Caller** | `pjsua` / VoIP.ms / Telnyx script with DTMF state machine and RTP audio streaming. | Successfully authenticate and dictate a complete dummy note into hospital test extension. |

---

## 6. PHIPA Compliance & Security Architecture

1. **Local-Only Processing:** All inference (Faster-Whisper, Tesseract OCR, Piper TTS) executes exclusively on `127.0.0.1`. No data leaves the laptop over WAN/cloud APIs.
2. **Ephemeral Storage:** Patient records and transcripts reside in-memory or inside a temporary `SQLCipher` database that purges upon application exit or window reload.
3. **VoIP Security:** If using an external SIP trunk (e.g., VoIP.ms or Telnyx) over cellular/hospital Wi-Fi:
   - Enforce TLS signaling (SIP-TLS) and Secure RTP (SRTP).
   - Disable remote cloud-side call recording and audio logging in the provider dashboard.
