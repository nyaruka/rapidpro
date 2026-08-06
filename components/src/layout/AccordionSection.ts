import { LitElement, TemplateResult, css, html } from 'lit';
import { property } from 'lit/decorators.js';

export class AccordionSection extends LitElement {
  static get styles() {
    return css`
      :host {
        display: block;
        border-bottom: 1px solid #e0e0e0;
      }

      :host(:last-child) {
        border-bottom: none;
      }

      .accordion-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 6px 10px;
        cursor: pointer;
        user-select: none;
        background: #f8f9fa;
        transition: background 0.15s ease;
      }

      .accordion-header:hover {
        background: #f0f1f2;
      }

      :host(.expanded) > .accordion-header {
        border-bottom: 1px solid #e0e0e0;
      }

      .accordion-title {
        display: flex;
        align-items: center;
        font-weight: 500;
        font-size: 13px;
        color: var(--color-label, #777);
      }

      .toggle-container {
        position: relative;
        display: flex;
        align-items: center;
      }

      .toggle-icon {
        color: #999;
        transition:
          transform 0.2s ease,
          opacity 0.3s ease;
      }

      .toggle-icon.expanded {
        transform: rotate(90deg);
      }

      .toggle-icon.faded {
        opacity: 0;
      }

      .count-bubble {
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 10px;
        font-weight: 600;
        padding: 3px;
        min-width: 10px;
        min-height: 10px;
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        line-height: 0px;
        opacity: 1;
        transition: opacity 0.3s ease;
        background: var(--color-bubble-bg, #fff);
        border: 1px solid var(--color-bubble-border, #777);
        color: var(--color-bubble-text, #000);
      }

      .count-bubble.hidden {
        opacity: 0;
        pointer-events: none;
      }

      .checkmark-icon {
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        opacity: 1;
        transition: opacity 0.3s ease;
        border-radius: 50%;
        color: var(--color-bubble-text, #000);
        background: var(--color-bubble-bg, #fff);
        border: 1px solid var(--color-bubble-border, #777);
        padding: 0.15em;
      }

      .checkmark-icon.hidden {
        opacity: 0;
        pointer-events: none;
      }

      .accordion-content {
        padding: 8px 10px;
        display: flex;
        flex-direction: column;
        gap: 8px;
        overflow: hidden;
        transition: all 0.2s ease-in-out;
        opacity: 1;
      }

      .accordion-content.collapsed {
        max-height: 0;
        padding-top: 0;
        padding-bottom: 0;
        opacity: 0;
      }

      .error-icon {
        color: var(--color-error, tomato);
        margin-right: 6px;
      }
    `;
  }

  @property({ type: String })
  label = '';

  @property({ type: String })
  icon = '';

  @property({ type: Number })
  count: number;

  @property({ type: Boolean })
  checked = false;

  @property({ type: Boolean, reflect: true })
  collapsed = true;

  @property({ type: Boolean })
  hasError = false;

  private hovered = false;

  private handleClick() {
    this.collapsed = !this.collapsed;
    this.dispatchEvent(
      new CustomEvent('toggle', {
        bubbles: true,
        composed: true,
        detail: { collapsed: this.collapsed, label: this.label }
      })
    );
  }

  private handleMouseEnter() {
    this.hovered = true;
    this.requestUpdate();
  }

  private handleMouseLeave() {
    this.hovered = false;
    this.requestUpdate();
  }

  public updated() {
    if (this.collapsed) {
      this.classList.remove('expanded');
      this.classList.add('collapsed');
    } else {
      this.classList.remove('collapsed');
      this.classList.add('expanded');
    }
  }

  public render(): TemplateResult {
    const hasCount = typeof this.count === 'number' && this.count > 0;
    const showBubble = hasCount && this.collapsed && !this.hovered;
    const showCheckmark = this.checked && this.collapsed && !this.hovered;

    return html`
      <div
        class="accordion-header"
        @click=${this.handleClick}
        @mouseenter=${this.handleMouseEnter}
        @mouseleave=${this.handleMouseLeave}
      >
        <div class="accordion-title">
          ${this.icon
            ? html`<temba-icon
                name=${this.icon}
                size="1"
                style="margin-right:6px;color:#999;"
              ></temba-icon>`
            : ''}${this.label}
        </div>
        ${this.hasError
          ? html`<temba-icon
              name="alert_warning"
              class="error-icon"
              size="1.2"
            ></temba-icon>`
          : html`<div class="toggle-container">
              <temba-icon
                name="arrow_right"
                size="1.2"
                class="toggle-icon ${this.collapsed
                  ? 'collapsed'
                  : 'expanded'} ${showBubble || showCheckmark ? 'faded' : ''}"
              ></temba-icon>
              ${showCheckmark
                ? html`<temba-icon
                    name="check"
                    size="0.8"
                    class="checkmark-icon"
                  ></temba-icon>`
                : showBubble
                  ? html`<div class="count-bubble">${this.count}</div>`
                  : ''}
            </div>`}
      </div>
      <div class="accordion-content ${this.collapsed ? 'collapsed' : ''}">
        <slot></slot>
      </div>
    `;
  }
}
