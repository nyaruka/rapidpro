import { css, html, LitElement, TemplateResult } from 'lit';
import { property } from 'lit/decorators.js';

export class Alert extends LitElement {
  static get styles() {
    return css`
      :host {
        display: block;
      }

      .temba-alert {
        color: rgba(0, 0, 0, 0.8);
        padding: 0.65rem 1rem;
        border: 1px solid rgba(0, 0, 0, 0.35);
        border-left: 10px solid rgba(0, 0, 0, 0.35);
        border-radius: var(--curvature-widget);
        box-shadow: var(--shadow);
      }

      .temba-info {
        background: var(--color-info);
        border-color: var(--color-info-border);
      }

      .temba-warning {
        background: var(--color-warning);
        border-color: var(--color-warning-border);
      }

      .temba-error {
        border-color: var(--color-error);
        background: #fff;
        border: 1px solid var(--color-error);
        border-left: 10px solid var(--color-error);
      }
    `;
  }

  @property({ type: String })
  level = 'info';

  public render(): TemplateResult {
    return html`
      <div class="temba-alert temba-${this.level}"><slot></slot></div>
    `;
  }
}
