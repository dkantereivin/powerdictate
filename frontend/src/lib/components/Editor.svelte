<script>
  import { onMount } from 'svelte';
  import EpicFieldPicker from './EpicFieldPicker.svelte';

  export let textContent = "";
  export let activeBracket = "";

  let textareaElement;
  let activeStart = -1;
  let activeEnd = -1;

  export function insertTextAtCursor(text) {
    if (!textareaElement) return;
    textareaElement.focus();

    const start = textareaElement.selectionStart;
    const end = textareaElement.selectionEnd;
    const before = textContent.substring(0, start);
    const after = textContent.substring(end);

    textContent = before + text + " " + after;

    // Place cursor right after inserted text
    const newPos = start + text.length + 1;
    setTimeout(() => {
      if (textareaElement) {
        textareaElement.focus();
        textareaElement.setSelectionRange(newPos, newPos);
      }
    }, 10);
  }

  export function jumpNextPlaceholder() {
    if (!textareaElement) return;
    const startPos = textareaElement.selectionEnd || 0;
    const textAfter = textContent.substring(startPos);

    // Search for [ ... ] or ***
    const match = /\[(.*?)\]|\*\*\*/.exec(textAfter);
    if (match) {
      const matchStart = startPos + match.index;
      const matchEnd = matchStart + match[0].length;
      selectRange(matchStart, matchEnd, match[0]);
    } else {
      // Wrap around to start of note
      const wrapMatch = /\[(.*?)\]|\*\*\*/.exec(textContent);
      if (wrapMatch) {
        selectRange(wrapMatch.index, wrapMatch.index + wrapMatch[0].length, wrapMatch[0]);
      }
    }
  }

  export function jumpPreviousPlaceholder() {
    if (!textareaElement) return;
    const currentStart = textareaElement.selectionStart || 0;
    const textBefore = textContent.substring(0, currentStart);

    const matches = Array.from(textBefore.matchAll(/\[(.*?)\]|\*\*\*/g));
    if (matches.length > 0) {
      const last = matches[matches.length - 1];
      selectRange(last.index, last.index + last[0].length, last[0]);
    }
  }

  function selectRange(start, end, targetText) {
    activeStart = start;
    activeEnd = end;
    activeBracket = targetText;

    if (textareaElement) {
      textareaElement.focus();
      textareaElement.setSelectionRange(start, end);
    }
  }

  export function replaceActiveOption(chosenOption) {
    if (activeStart >= 0 && activeEnd >= activeStart && textareaElement) {
      const before = textContent.substring(0, activeStart);
      const after = textContent.substring(activeEnd);
      textContent = before + chosenOption + after;

      const newPos = activeStart + chosenOption.length;
      activeBracket = "";
      setTimeout(() => {
        if (textareaElement) {
          textareaElement.focus();
          textareaElement.setSelectionRange(newPos, newPos);
          // Automatically advance to the next placeholder
          jumpNextPlaceholder();
        }
      }, 10);
    }
  }

  function handleKeydown(e) {
    if (e.key === "Tab") {
      e.preventDefault();
      if (e.shiftKey) {
        jumpPreviousPlaceholder();
      } else {
        jumpNextPlaceholder();
      }
    } else if (e.key === "F4") {
      e.preventDefault();
      jumpNextPlaceholder();
    }
  }

  function handleSelectionChange() {
    if (textareaElement) {
      const start = textareaElement.selectionStart;
      const end = textareaElement.selectionEnd;
      if (start !== end) {
        const selected = textContent.substring(start, end);
        if (selected.startsWith("[") && selected.endsWith("]")) {
          activeBracket = selected;
          activeStart = start;
          activeEnd = end;
          return;
        }
      }
    }
  }
</script>

<main class="main-canvas">
  <!-- Epic-style Picklist Helper Bar -->
  {#if activeBracket && activeBracket.includes("/")}
    <EpicFieldPicker
      activeBracketText={activeBracket}
      onSelectOption={replaceActiveOption}
      onClose={() => activeBracket = ""}
    />
  {/if}

  <div class="editor-container">
    <textarea
      bind:this={textareaElement}
      bind:value={textContent}
      class="editor-paper-textarea"
      placeholder="Type or dictate clinical note here..."
      spellcheck="false"
      on:keydown={handleKeydown}
      on:select={handleSelectionChange}
      on:click={handleSelectionChange}
    ></textarea>
  </div>
</main>

<style lang="scss">
  .editor-container {
    width: 100%;
    max-width: 850px;
    display: flex;
    flex-direction: column;
  }

  .editor-paper-textarea {
    width: 100%;
    min-height: 850px;
    background: #ffffff;
    color: #000000;
    border-radius: 8px;
    padding: 40px 48px;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
    outline: none;
    border: 1px solid #cbd5e1;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Inter", monospace;
    font-size: 13.5px;
    line-height: 1.6;
    resize: vertical;
    white-space: pre-wrap;

    &:focus {
      border-color: #0284c7;
      box-shadow: 0 0 0 3px rgba(2, 132, 199, 0.25);
    }
  }

  @media print {
    .editor-container {
      width: 100% !important;
      max-width: 100% !important;
    }
    .editor-paper-textarea {
      box-shadow: none !important;
      border: none !important;
      padding: 0 !important;
      font-size: 10pt !important;
      min-height: auto !important;
      resize: none !important;
    }
  }
</style>
