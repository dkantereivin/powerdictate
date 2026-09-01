<script>
  import { onMount } from 'svelte';
  import Header from './lib/components/Header.svelte';
  import Sidebar from './lib/components/Sidebar.svelte';
  import Editor from './lib/components/Editor.svelte';
  import SubmissionModal from './lib/components/SubmissionModal.svelte';
  import SpellToolModal from './lib/components/SpellToolModal.svelte';

  let textContent = "";
  let activeBracket = "";
  let editorComp;

  let isRecording = false;
  let vuLevel = 0;
  let statusMessage = "Ready";
  let macros = [];
  let templates = [];
  let selectedTemplateId = "ctu_admission";

  let isSubmissionModalOpen = false;
  let isSpellModalOpen = false;

  let ws = null;
  let audioContext = null;
  let mediaStream = null;
  let processor = null;

  onMount(async () => {
    await fetchTemplates();
    await fetchMacros();
  });

  async function fetchTemplates() {
    try {
      const res = await fetch("/api/templates");
      const data = await res.json();
      templates = data.templates || [];
      if (templates.length > 0) {
        await loadTemplateById(selectedTemplateId);
      }
    } catch (err) {
      console.error("Failed to load templates:", err);
    }
  }

  async function loadTemplateById(templateId) {
    try {
      const res = await fetch(`/api/templates/${templateId}`);
      if (res.ok) {
        const data = await res.json();
        textContent = data.content || "";
        selectedTemplateId = templateId;
      }
    } catch (err) {
      console.error(`Failed to fetch template ${templateId}:`, err);
    }
  }

  async function fetchMacros() {
    try {
      const res = await fetch("/api/macros");
      const data = await res.json();
      macros = data.macros || [];
    } catch (err) {
      console.error("Failed to load macros:", err);
    }
  }

  async function toggleRecording() {
    if (isRecording) {
      stopRecording();
    } else {
      await startRecording();
    }
  }

  async function startRecording() {
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: { sampleRate: 16000, channelCount: 1, echoCancellation: true, noiseSuppression: true }
      });

      audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
      const source = audioContext.createMediaStreamSource(mediaStream);
      processor = audioContext.createScriptProcessor(4096, 1, 1);

      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const wsUrl = `${protocol}//${window.location.host}/ws/dictate`;
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        isRecording = true;
        statusMessage = "🔴 Live Dictation Active (GPU Faster-Whisper)";
      };

      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.type === "transcript") {
          if (editorComp && msg.text.trim()) {
            editorComp.insertTextAtCursor(msg.text.trim());
            if (msg.is_macro) {
              editorComp.jumpNextPlaceholder();
            }
          }
        } else if (msg.type === "navigation") {
          if (msg.command === "next_field" && editorComp) {
            editorComp.jumpNextPlaceholder();
          } else if (msg.command === "prev_field" && editorComp) {
            editorComp.jumpPreviousPlaceholder();
          }
        }
      };

      ws.onclose = () => {
        stopRecording();
      };

      processor.onaudioprocess = (e) => {
        if (!isRecording || !ws || ws.readyState !== WebSocket.OPEN) return;
        const inputData = e.inputBuffer.getChannelData(0);

        let sum = 0;
        for (let i = 0; i < inputData.length; i++) {
          sum += inputData[i] * inputData[i];
        }
        const rms = Math.sqrt(sum / inputData.length);
        vuLevel = Math.min(100, Math.round(rms * 400));

        const pcm16 = new Int16Array(inputData.length);
        for (let i = 0; i < inputData.length; i++) {
          const s = Math.max(-1, Math.min(1, inputData[i]));
          pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
        }
        ws.send(pcm16.buffer);
      };

      source.connect(processor);
      processor.connect(audioContext.destination);

    } catch (err) {
      console.error("Microphone capture error:", err);
      alert("Could not access microphone.");
    }
  }

  function stopRecording() {
    isRecording = false;
    statusMessage = "Ready";
    vuLevel = 0;
    if (processor) { processor.disconnect(); processor = null; }
    if (mediaStream) { mediaStream.getTracks().forEach(t => t.stop()); mediaStream = null; }
    if (audioContext) { audioContext.close(); audioContext = null; }
    if (ws) {
      // Send flush message before closing
      try { ws.send(JSON.stringify({ action: "flush" })); } catch (e) {}
      ws.close();
      ws = null;
    }
  }

  function handleInsertMacro(macro) {
    if (editorComp) {
      editorComp.insertTextAtCursor("\n" + macro.replacement + "\n");
      editorComp.jumpNextPlaceholder();
    }
  }

  async function handleOcrSnip() {
    statusMessage = "Snapping Meditech terminal OCR from clipboard...";
    try {
      const res = await fetch("/api/ocr/clipboard", { method: "POST" });
      if (!res.ok) throw new Error("Clipboard OCR failed.");
      const data = await res.json();
      if (data.snippet && editorComp) {
        editorComp.insertTextAtCursor("\n" + data.snippet + "\n\n");
        editorComp.jumpNextPlaceholder();
        statusMessage = "Meditech Data Extracted!";
      }
    } catch (err) {
      alert("Could not extract Meditech terminal data from clipboard. Please take a screenshot (Ctrl+Shift+S / PrtScn) of the Citrix terminal screen first.");
      statusMessage = "Ready";
    }
  }

  function handlePrint() {
    window.print();
  }

  function handleCopyBridge() {
    const bridge = "CTU Consult — See attached typed note. Dictated / Meditech pending (Job #[XXX]).";
    navigator.clipboard.writeText(bridge).then(() => {
      alert("Copied 1-line NCR Order Bridge reference to clipboard!\n\n" + bridge);
    });
  }

  async function handleSubmitPayload(payload) {
    isSubmissionModalOpen = false;
    statusMessage = `Processing submission via ${payload.sink}...`;

    try {
      const res = await fetch("/api/tts/speak", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (res.ok) {
        if (payload.sink === "wav_file" || payload.sink === "telephony_8k") {
          alert(`WAV Export Success!\nSaved to: ${data.file_path}\nDuration: ${data.duration.toFixed(1)}s`);
        } else if (payload.sink === "sip") {
          if (data.call_result && data.call_result.mode === "dry_run") {
            alert(`SIP IVR Simulation (Dry-Run):\n${data.call_result.message}\n(Configure VoIP.ms account in Submission dialog for live dialing)`);
          } else {
            alert(`SIP Call Connected: ${data.call_result.message}`);
          }
        } else {
          alert(`Submission Success!\nSink: ${payload.sink}\nStatus: ${data.status || 'OK'}`);
        }
      } else {
        alert(`Submission error: ${data.error || JSON.stringify(data)}`);
      }
    } catch (err) {
      alert("Error submitting to backend server.");
    } finally {
      statusMessage = "Ready";
    }
  }

  $: wordCount = textContent ? textContent.trim().split(/\s+/).filter(Boolean).length : 0;
</script>

<div class="app-container">
  <Header
    {templates}
    {selectedTemplateId}
    onSelectTemplate={loadTemplateById}
    onPrint={handlePrint}
    onSubmitDictation={() => isSubmissionModalOpen = true}
    onCopyBridge={handleCopyBridge}
    onOpenSpellTool={() => isSpellModalOpen = true}
  />

  <div class="main-body">
    <Sidebar
      {isRecording}
      {vuLevel}
      {macros}
      onToggleRecord={toggleRecording}
      onInsertMacro={handleInsertMacro}
      onOcrSnip={handleOcrSnip}
    />

    <Editor
      bind:this={editorComp}
      bind:textContent
      bind:activeBracket
    />
  </div>

  <footer class="status-bar">
    <div class="status-left">
      <span>Status: <strong>{statusMessage}</strong></span>
      <span>|</span>
      <span>Audio: 16kHz Stream (VAD-Gated)</span>
      <span>|</span>
      <span>Desktop Companion: <strong>python -m src.desktop_widget.desktop_app</strong></span>
    </div>
    <div class="status-right">
      <span>{wordCount} words</span>
      <span>|</span>
      <span>Press <strong>Tab</strong> or <strong>F4</strong> for next [ field ]</span>
    </div>
  </footer>

  <SubmissionModal
    isOpen={isSubmissionModalOpen}
    noteText={textContent}
    onClose={() => isSubmissionModalOpen = false}
    onSubmit={handleSubmitPayload}
  />

  <SpellToolModal
    isOpen={isSpellModalOpen}
    onClose={() => isSpellModalOpen = false}
    onInsertSpelling={(spelled) => editorComp && editorComp.insertTextAtCursor(spelled)}
  />
</div>
