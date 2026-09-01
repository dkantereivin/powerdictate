<script>
  export let isRecording = false;
  export let vuLevel = 0;
  export let macros = [];
  export let onToggleRecord = () => {};
  export let onInsertMacro = (macro) => {};
  export let onOcrSnip = () => {};
</script>

<aside class="sidebar">
  <!-- Live Microphone Capture Card -->
  <div class="card">
    <div class="card-title">
      <span>Live Dictation</span>
      <span style="font-size: 10px; color: #94a3b8;">{isRecording ? "STREAMING" : "OFF"}</span>
    </div>
    <div class="mic-box">
      <button
        class="mic-button"
        class:recording={isRecording}
        on:click={onToggleRecord}
        title="Toggle Microphone Dictation"
      >
        {#if isRecording}⏹️{:else}🎙️{/if}
      </button>
      <div class="vu-meter-bar">
        <div class="vu-fill" style="width: {vuLevel}%;"></div>
      </div>
      <div style="font-size: 11px; color: #94a3b8; text-align: center;">
        {#if isRecording}
          Speaking... (Say "next field" or "macro...")
        {:else}
          Click mic or speak to dictate
        {/if}
      </div>
    </div>
  </div>

  <!-- Meditech Screen Ingestion (OCR) Card -->
  <div class="card">
    <div class="card-title">
      <span>Meditech Ingestion</span>
      <span>📷</span>
    </div>
    <p style="font-size: 12px; color: #94a3b8; margin-bottom: 10px;">
      Snips terminal demographics & labs from clipboard (Ctrl+Shift+S).
    </p>
    <button class="btn btn-secondary" style="width: 100%; justify-content: center;" on:click={onOcrSnip}>
      Snip & Extract Meditech
    </button>
  </div>

  <!-- Dot-Phrases / Macro Library Card -->
  <div class="card" style="flex: 1; display: flex; flex-direction: column;">
    <div class="card-title">
      <span>Dot-Phrases & Macros</span>
      <span>⚡</span>
    </div>
    <div class="macro-list">
      {#each macros as m}
        <button type="button" class="macro-chip" on:click={() => onInsertMacro(m)}>
          <span>{m.name}</span>
          <span class="trigger-tag">.{m.id}</span>
        </button>
      {/each}
    </div>
  </div>
</aside>
