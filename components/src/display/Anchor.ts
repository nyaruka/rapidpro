import { LitElement, TemplateResult, html, css } from 'lit';
import { property } from 'lit/decorators.js';

export class Anchor extends LitElement {
  static get styles() {
    return css`
      :host {
        color: var(--color-link-primary);
        display: inline-block;
      }

      slot:hover {
        cursor: pointer;
        text-decoration: underline;
      }
    `;
  }

  @property({ type: String })
  href: string;

  private handleClick(evt: MouseEvent) {
    // TODO: fire event instead to be handled upstream
    (window as any).goto(evt);
  }

  public render(): TemplateResult {
    return html`<slot href="${this.href}" @click="${this.handleClick}"></slot>`;
  }
}
