import { LitElement, css, html } from 'lit';
import { property } from 'lit/decorators.js';

export class Mask extends LitElement {
  static styles = css`
    .mask {
      position: fixed;
      top: 0;
      left: 0;
      z-index: 100;
      width: 100vw;
      height: 100vh;
      background: rgba(0, 0, 0, 0.6);
      display: none;
      align-items: center;
      justify-content: center;
    }

    .show {
      display: flex;
    }
  `;

  @property({ type: Boolean })
  show = false;

  render() {
    return html` <div class="mask  ${this.show ? 'show' : ''}">
      <slot></slot>
    </div>`;
  }
}
