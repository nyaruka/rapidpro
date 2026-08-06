import { html, TemplateResult } from 'lit-html';

// SVG paths for play and pause icons
const PLAY_SVG = html`<svg
  viewBox="0 0 24 24"
  width="16"
  height="16"
  fill="currentColor"
>
  <polygon points="6,3 20,12 6,21" />
</svg>`;

// Track active audio so only one plays at a time
let activeAudio: HTMLAudioElement | null = null;
let activeContainer: HTMLElement | null = null;

function stopActive() {
  if (activeAudio) {
    activeAudio.pause();
    activeAudio.currentTime = 0;
    if (activeContainer) {
      resetPlayer(activeContainer);
    }
    activeAudio = null;
    activeContainer = null;
  }
}

function resetPlayer(container: HTMLElement) {
  const btn = container.querySelector('.audio-play-btn') as HTMLElement;
  const progress = container.querySelector('.audio-progress') as HTMLElement;
  if (btn)
    btn.innerHTML =
      '<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><polygon points="6,3 20,12 6,21"/></svg>';
  if (progress) progress.style.width = '0%';
}

function handlePlayClick(e: MouseEvent) {
  e.stopPropagation();
  e.preventDefault();

  const container = (e.currentTarget as HTMLElement).closest(
    '.audio-player'
  ) as HTMLElement;
  if (!container) return;

  const url = container.dataset.url;
  if (!url) return;

  const btn = container.querySelector('.audio-play-btn') as HTMLElement;
  const progress = container.querySelector('.audio-progress') as HTMLElement;

  // If this is already playing, pause it
  if (activeAudio && activeContainer === container && !activeAudio.paused) {
    activeAudio.pause();
    btn.innerHTML =
      '<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><polygon points="6,3 20,12 6,21"/></svg>';
    return;
  }

  // Stop any other playing audio
  stopActive();

  const audio = new Audio(url);
  activeAudio = audio;
  activeContainer = container;

  btn.innerHTML =
    '<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><rect x="5" y="3" width="4" height="18"/><rect x="15" y="3" width="4" height="18"/></svg>';

  audio.addEventListener('timeupdate', () => {
    if (audio.duration && progress) {
      const pct = (audio.currentTime / audio.duration) * 100;
      progress.style.width = `${pct}%`;
    }
  });

  audio.addEventListener('ended', () => {
    resetPlayer(container);
    activeAudio = null;
    activeContainer = null;
  });

  audio.addEventListener('error', () => {
    resetPlayer(container);
    activeAudio = null;
    activeContainer = null;
  });

  audio.play().catch(() => {
    resetPlayer(container);
    activeAudio = null;
    activeContainer = null;
  });
}

/**
 * Renders an inline audio player with play/pause button and progress bar.
 * Used on canvas nodes for play_audio and say_msg actions.
 */
export function renderAudioPlayer(audioUrl: string): TemplateResult {
  return html`
    <div
      class="audio-player"
      data-url="${audioUrl}"
      style="display: flex; align-items: center; gap: 0.4em; cursor: default;"
      @mousedown=${(e: MouseEvent) => e.stopPropagation()}
      @mouseup=${(e: MouseEvent) => e.stopPropagation()}
    >
      <div
        class="audio-play-btn"
        @click=${handlePlayClick}
        style="cursor: pointer; color: #666; display: flex; align-items: center; flex-shrink: 0;"
      >
        ${PLAY_SVG}
      </div>
      <div
        style="flex: 1; height: 4px; background: #e0e0e0; border-radius: 2px; overflow: hidden; min-width: 40px;"
      >
        <div
          class="audio-progress"
          style="width: 0%; height: 100%; background: var(--color-primary, #2387ca); border-radius: 2px; transition: width 0.2s linear;"
        ></div>
      </div>
    </div>
  `;
}
