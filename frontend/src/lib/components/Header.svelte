<script>
  export let templates = [];
  export let selectedTemplateId = "ctu_admission";
  export let onSelectTemplate = (id) => {};
  export let onPrint = () => {};
  export let onSubmitDictation = () => {};
  export let onCopyBridge = () => {};
  export let onOpenSpellTool = () => {};
</script>

<header class="app-header">
  <div class="brand">
    <span style="font-size: 24px;">⚡</span>
    <span class="brand-title">PowerDictate</span>
    <span class="badge-gpu">RTX A2000 (CUDA)</span>
  </div>

  <div class="header-center" style="display: flex; align-items: center; gap: 8px;">
    <span style="font-size: 12px; color: #94a3b8; font-weight: 600;">TEMPLATE:</span>
    <select
      class="template-select"
      bind:value={selectedTemplateId}
      on:change={() => onSelectTemplate(selectedTemplateId)}
    >
      {#each templates as t}
        <option value={t.id}>{t.name} ({t.category})</option>
      {/each}
    </select>
  </div>

  <div class="header-actions">
    <button class="btn btn-secondary" on:click={onOpenSpellTool} title="Spell names or phonetic terms letter-by-letter">
      🔤 Spell Tool
    </button>
    <button class="btn btn-secondary" on:click={onCopyBridge} title="Copy 1-line reference for physical NCR paper order sheet">
      📋 Copy NCR Bridge
    </button>
    <button class="btn btn-secondary" on:click={onPrint} title="Print 8.5x11 Chart Note (Ctrl+P)">
      🖨️ Print
    </button>
    <button class="btn btn-primary" on:click={onSubmitDictation} title="Submit to Telephony / Phone / PBX / WAV">
      🎙️ Submit Audio
    </button>
  </div>
</header>

<style lang="scss">
  .template-select {
    padding: 6px 12px;
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 6px;
    color: #f8fafc;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;

    &:focus {
      border-color: #0284c7;
      outline: none;
    }
  }
</style>
