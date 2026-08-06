import { css, html, PropertyValueMap } from 'lit';
import { property, state } from 'lit/decorators.js';
import { RapidElement } from '../RapidElement';
import { getClasses } from '../utils';

/**
 * A full-screen viewer for an image attachment. `showElement` is handed the
 * element that was clicked (a raw <img> or a temba-thumbnail exposing a `url`),
 * and we present that image centered and contained within the viewport with a
 * short fade / scale-in. Clicking anywhere dismisses it.
 */
export class Lightbox extends RapidElement {
  static get styles() {
    return css`
      :host {
        position: fixed;
        top: 0;
        left: 0;
        z-index: 10000;
      }

      /* a full-viewport layer that centers the image, catches the dismiss
         click, and lays a light translucent mask over the page behind */
      .backdrop {
        position: fixed;
        inset: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        background: rgba(0, 0, 0, 0.5);
        opacity: 0;
        pointer-events: none;
        transition: opacity var(--anim) ease;
      }

      .backdrop.zoom {
        opacity: 1;
        pointer-events: auto;
      }

      img {
        /* contain the image within the viewport at any aspect ratio, on
           its own solid backing (so transparent images aren't see-through) */
        box-sizing: border-box;
        max-width: 90vw;
        max-height: 90vh;
        object-fit: contain;
        background: #fff;
        padding: 6px;
        border-radius: calc(var(--curvature) * 1.5);
        box-shadow: 0 0 24px 6px rgba(0, 0, 0, 0.4);
        transform: scale(0.85);
        opacity: 0;
        transition:
          transform var(--anim) ease,
          opacity var(--anim) ease;
      }

      .zoom img {
        transform: scale(1);
        opacity: 1;
      }
    `;
  }

  @property({ type: Number })
  animationTime = 300;

  @property({ type: Boolean })
  show = false;

  @property({ type: Boolean })
  zoom = false;

  @state()
  private url = '';

  protected updated(
    changed: PropertyValueMap<any> | Map<PropertyKey, unknown>
  ): void {
    // mount first (opacity 0 / scaled down), then flip to zoom on the next
    // tick so the transition to the visible state actually animates
    if (changed.has('show') && this.show) {
      window.setTimeout(() => {
        this.zoom = true;
      }, 0);
    }

    // once zoomed out, wait for the fade to finish before unmounting the image
    if (changed.has('zoom') && !this.zoom && this.show) {
      window.setTimeout(() => {
        // unless a re-open during the fade-out already zoomed us back in
        if (!this.zoom) {
          this.show = false;
        }
      }, this.animationTime);
    }
  }

  public showElement(ele: HTMLElement) {
    // the clicked element is either a raw <img> or a temba-thumbnail that
    // exposes the attachment url; take whichever gives us an image source
    this.url = (ele as HTMLImageElement).src || (ele as any).url || '';
    if (this.show) {
      // already mounted (e.g. re-opened mid-dismissal) — re-zoom in place
      this.zoom = true;
    } else {
      this.show = true; // updated() flips zoom on the next tick
    }
  }

  public handleClick() {
    this.zoom = false;
  }

  public render() {
    return html`
      <div
        class=${getClasses({ backdrop: true, zoom: this.zoom })}
        style="--anim: ${this.animationTime}ms"
        @click=${this.handleClick}
      >
        ${this.show && this.url
          ? html`<img src=${this.url} alt="attachment" />`
          : null}
      </div>
    `;
  }
}
