<script>
  export let isOpen = false;
  export let onClose = () => {};
  export let onInsertSpelling = (spelledText) => {};

  let inputWord = "";
  let formattedResult = "";

  $: {
    if (inputWord.trim()) {
      // Split into individual letters or uppercase
      formattedResult = inputWord.trim().toUpperCase().replace(/[^A-Z0-9]/g, '');
    } else {
      formattedResult = "";
    }
  }

  function handleInsert() {
    if (formattedResult) {
      onInsertSpelling(formattedResult);
      inputWord = "";
      onClose();
    }
  }
</script>

{#if isOpen}
  <div class="modal-backdrop">
    <div class="modal-dialog">
      <div class="modal-title">🔤 Spell Out Names & Medical Terms</div>
      <p style="font-size: 12px; color: #94a3b8; margin-bottom: 14px;">
        Type or speak to spell out patient surnames or unlisted drug names letter-by-letter.
        (You can also say <em>"spell P-A-T-E-L"</em> during live dictation).
      </p>

      <div class="form-group">
        <label for="spell-input">Enter Name or Letters (e.g. "McPherson" or "M C P H E R S O N")</label>
        <input
          id="spell-input"
          type="text"
          bind:value={inputWord}
          placeholder="e.g. M C P H E R S O N"
        />
      </div>

      {#if formattedResult}
        <div class="preview-box">
          <span style="font-size: 11px; color: #94a3b8;">Formatted Result:</span>
          <div class="preview-text">{formattedResult}</div>
        </div>
      {/if}

      <div class="modal-actions">
        <button class="btn btn-secondary" on:click={onClose}>Cancel</button>
        <button class="btn btn-primary" on:click={handleInsert} disabled={!formattedResult}>
          Insert into Note
        </button>
      </div>
    </div>
  </div>
{/if}

<style lang="scss">
  .preview-box {
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 10px 14px;
    margin-bottom: 14px;
  }
  .preview-text {
    font-size: 16px;
    font-weight: 700;
    color: #38bdf8;
    letter-spacing: 1px;
    margin-top: 4px;
  }
</style>
