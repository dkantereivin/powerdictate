<script>
  export let activeBracketText = "";
  export let onSelectOption = (option) => {};
  export let onClose = () => {};

  $: options = parsePicklistOptions(activeBracketText);

  function parsePicklistOptions(bracketStr) {
    if (!bracketStr) return [];
    // Clean outer brackets [ ... ]
    let inner = bracketStr.trim();
    if (inner.startsWith("[") && inner.endsWith("]")) {
      inner = inner.substring(1, inner.length - 1).trim();
    }
    // Check if contains slash separator /
    if (inner.includes("/")) {
      return inner.split("/").map(s => s.trim()).filter(Boolean);
    }
    return [];
  }
</script>

{#if options.length > 0}
  <div class="epic-picker-bar">
    <span class="picker-label">📋 Choose Option:</span>
    {#each options as opt, idx}
      <button
        type="button"
        class="picker-chip"
        on:click={() => onSelectOption(opt)}
        title="Select {opt}"
      >
        <span class="chip-num">{idx + 1}</span>
        <span>{opt}</span>
      </button>
    {/each}
    <button type="button" class="picker-close" on:click={onClose} title="Dismiss">✕</button>
  </div>
{/if}

<style lang="scss">
  .epic-picker-bar {
    display: flex;
    align-items: center;
    gap: 8px;
    background: #1e293b;
    border: 1px solid #0284c7;
    border-radius: 8px;
    padding: 6px 12px;
    margin-bottom: 12px;
    box-shadow: 0 4px 12px rgba(2, 132, 199, 0.25);
    animation: slideDown 0.15s ease-out;

    .picker-label {
      font-size: 11px;
      font-weight: 700;
      color: #38bdf8;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    .picker-chip {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 10px;
      background: #0f172a;
      border: 1px solid #334155;
      border-radius: 6px;
      color: #f8fafc;
      font-size: 12px;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.15s ease;

      &:hover {
        background: #0284c7;
        border-color: #38bdf8;
        color: #fff;
      }

      .chip-num {
        background: #334155;
        color: #94a3b8;
        font-size: 10px;
        font-weight: 700;
        padding: 1px 5px;
        border-radius: 4px;
      }
    }

    .picker-close {
      background: none;
      border: none;
      color: #94a3b8;
      cursor: pointer;
      font-size: 12px;
      margin-left: auto;
      padding: 2px 6px;

      &:hover {
        color: #ef4444;
      }
    }
  }

  @keyframes slideDown {
    from { opacity: 0; transform: translateY(-6px); }
    to { opacity: 1; transform: translateY(0); }
  }
</style>
