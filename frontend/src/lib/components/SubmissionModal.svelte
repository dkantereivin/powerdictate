<script>
  export let isOpen = false;
  export let noteText = "";
  export let onClose = () => {};
  export let onSubmit = (payload) => {};

  let sinkType = "wav_file";
  let voice = "af_heart";
  let mode = "dictation";
  let providerId = "12345";
  let mrn = "9876543";
  let workType = "01";
  let phone = "8076846000";

  // SIP VoIP Configuration Details
  let sipServer = "toronto.voip.ms";
  let sipUsername = "";
  let sipPassword = "";
  let sipCallerId = "";

  function handleConfirm() {
    onSubmit({
      sink: sinkType,
      voice,
      mode,
      provider_id: providerId,
      mrn,
      work_type: workType,
      target_phone: phone,
      sip_server: sipServer,
      sip_username: sipUsername,
      sip_password: sipPassword,
      sip_caller_id: sipCallerId,
      text: noteText
    });
  }
</script>

{#if isOpen}
  <div class="modal-backdrop">
    <div class="modal-dialog">
      <div class="modal-title">🎙️ Audio Submission & Export Sinks</div>

      <!-- Sink Selector -->
      <div class="form-group">
        <label for="sink-select">Destination / Audio Modality</label>
        <select id="sink-select" bind:value={sinkType}>
          <option value="wav_file">💾 Export to Master .WAV Audio File (24kHz Studio Quality)</option>
          <option value="telephony_8k">💾 Export to 8kHz Mono PCM WAV (Hospital Telephony Standard)</option>
          <option value="smartphone">📱 Option A: Smartphone Audio Injection (Bluetooth HFP / TRRS + DTMF)</option>
          <option value="sip">📞 Option B: Automated SIP / VoIP PBX Caller (VoIP.ms / Telnyx)</option>
          <option value="fluency">📂 Option C: 3M M*Modal / Fluency Drop Package (XML + 16k WAV)</option>
          <option value="speaker">🔊 Room Speaker / Headphone Playback</option>
        </select>
      </div>

      <!-- Voice Selection -->
      <div class="form-group">
        <label for="voice-select">Neural Voice Profile (Kokoro-82M)</label>
        <select id="voice-select" bind:value={voice}>
          <option value="af_heart">af_heart (Female, Clear & Articulate - Recommended)</option>
          <option value="af_bella">af_bella (Female, Professional)</option>
          <option value="am_adam">am_adam (Male, Authoritative)</option>
          <option value="am_michael">am_michael (Male, Standard)</option>
          <option value="bm_george">bm_george (British Male)</option>
          <option value="bf_emma">bf_emma (British Female)</option>
        </select>
      </div>

      <!-- Dictation Mode -->
      <div class="form-group">
        <label for="mode-select">Dictation Grammar Mode</label>
        <select id="mode-select" bind:value={mode}>
          <option value="dictation">Dictation Mode (Spoken punctuation: "period", "comma", "new line" for hospital PBX)</option>
          <option value="ward_review">Ward Review Mode (Natural human pauses and inflections)</option>
        </select>
      </div>

      <!-- Provider ID & MRN for IVR -->
      <div style="display: flex; gap: 12px;">
        <div class="form-group" style="flex: 1;">
          <label for="provider-id">Provider ID (Doctor #)</label>
          <input id="provider-id" type="text" bind:value={providerId} placeholder="e.g. 12345" />
        </div>
        <div class="form-group" style="flex: 1;">
          <label for="mrn-input">Patient MRN</label>
          <input id="mrn-input" type="text" bind:value={mrn} placeholder="e.g. 9876543" />
        </div>
      </div>

      <!-- Option B: SIP Details & Provider Recommendation -->
      {#if sinkType === 'sip'}
        <div class="sip-config-box">
          <div class="sip-banner">
            ℹ️ Recommended SIP Provider: <strong>VoIP.ms</strong> (~$0.005/min, Canadian POPs, SIP-TLS 5061 + SRTP, custom Caller ID).
          </div>
          <div style="display: flex; gap: 8px;">
            <div class="form-group" style="flex: 1;">
              <label for="sip-user">VoIP Account / Sub-account</label>
              <input id="sip-user" type="text" bind:value={sipUsername} placeholder="e.g. 100001_md" />
            </div>
            <div class="form-group" style="flex: 1;">
              <label for="sip-pass">SIP Password</label>
              <input id="sip-pass" type="password" bind:value={sipPassword} placeholder="••••••••" />
            </div>
          </div>
          <div style="font-size: 11px; color: #94a3b8;">
            *If unconfigured, PowerDictate executes an offline dry-run IVR simulation.
          </div>
        </div>
      {/if}

      <!-- Option A: Smartphone Guidance -->
      {#if sinkType === 'smartphone'}
        <div class="sip-banner" style="background: rgba(14, 165, 233, 0.15); border-color: #0284c7;">
          📱 <strong>Option A (Zero-Cost Cellular):</strong> Pair your laptop to your smartphone via Bluetooth Headset (HFP) or connect a 3.5mm TRRS audio cable / USB-C DAC. Call the hospital line and press Confirm.
        </div>
      {/if}

      <div class="modal-actions">
        <button class="btn btn-secondary" on:click={onClose}>Cancel</button>
        <button class="btn btn-primary" on:click={handleConfirm}>
          {#if sinkType.startsWith('wav') || sinkType.startsWith('telephony')}
            💾 Generate & Save WAV
          {:else}
            🎙️ Confirm & Transmit
          {/if}
        </button>
      </div>
    </div>
  </div>
{/if}

<style lang="scss">
  .sip-config-box {
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 12px;
    margin-bottom: 14px;
  }

  .sip-banner {
    background: rgba(245, 158, 11, 0.15);
    border: 1px solid #f59e0b;
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 12px;
    color: #f8fafc;
    margin-bottom: 10px;
    line-height: 1.4;
  }
</style>
