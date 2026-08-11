import { css, html, TemplateResult } from 'lit';
import { customElement } from 'lit/decorators.js';
import { RapidElement } from '../src/RapidElement';

@customElement('mouse-helper')
export default class MouseHelper extends RapidElement {
  static get styles() {
    return css`
      :host {
        position: absolute;
      }

      .pointer {
        position: absolute;
        width: 6px;
        height: 6px;
        z-index: 1000;
        background: rgba(0, 250, 0, 0.3);
        border-radius: 20px;
        margin-left: -3px;
        margin-top: -3px;
        pointer-events: none;
      }
    `;
  }

  connectedCallback(): void {
    super.connectedCallback();
    this.updateCursor = this.updateCursor.bind(this);
    document.addEventListener('mousemove', this.updateCursor);
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    document.removeEventListener('mousemove', this.updateCursor);
  }

  public updateCursor(event: MouseEvent) {
    const pointer = this.shadowRoot.querySelector('.pointer') as HTMLDivElement;
    pointer.style.left = event.offsetX + 'px';
    pointer.style.top = event.offsetY + 'px';
  }

  public render(): TemplateResult {
    return html`<div class="pointer"></div>`;
  }
}
