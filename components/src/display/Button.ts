import { LitElement, TemplateResult, html, css } from 'lit';
import { getClasses } from '../utils';

import { property } from 'lit/decorators.js';

export class Button extends LitElement {
  static get styles() {
    return css`
      :host {
        display: inline-flex;
        align-self: stretch;
        font-family: var(--font);
        /* Match the styleguide's .ds Inter rendering — the stylistic
           sets (ss01/cv11) and the "tnum 0" off-switch — so glyph
           shapes line up with the design-system buttons. */
        font-feature-settings:
          'ss01',
          'cv11',
          'tnum' 0;
      }

      /* DS .btn-sm — sizing, type, transition, shape */
      .button-container {
        display: inline-flex;
        align-items: center;
        justify-content: var(--button-justify, center);
        gap: 6px;
        flex-grow: 1;
        height: var(--button-height, 28px);
        padding: 0 10px;
        border: 1px solid transparent;
        border-radius: var(--r-sm);
        font-size: 12.5px;
        font-weight: var(--w-regular);
        letter-spacing: -0.005em;
        line-height: 1;
        white-space: nowrap;
        cursor: pointer;
        user-select: none;
        -webkit-user-select: none;
        outline: none;
        box-sizing: border-box;
        transition:
          background 120ms,
          border-color 120ms,
          color 120ms,
          box-shadow 120ms;
      }

      .button-mask {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        line-height: 1;
      }

      .button-name {
        white-space: nowrap;
      }

      /* even smaller variant (compact lists, list-row actions, etc.).
         The vars let dense consumers (e.g. slim status rows) compact
         it further without another named size. */
      .small {
        height: var(--button-small-height, 24px);
        padding: 0 var(--button-small-x-pad, 8px);
        font-size: var(--button-small-font-size, 12px);
      }

      /* DS .btn-primary — solid accent fill with a faint top
         highlight and a ground shadow so it sits a touch above the
         surface. The base 1px transparent border stays in the box
         model so the primary's footprint matches the secondary's. */
      .primary-button {
        background: var(--accent-600);
        color: #fff;
        box-shadow:
          inset 0 1px 0 rgba(255, 255, 255, 0.18),
          0 1px 1px rgba(15, 22, 36, 0.1);
      }
      .primary-button:hover {
        background: var(--accent-700);
      }

      /* Ghost-style secondary — transparent fill so it blends into
         any surface (the dialog gutter's grey, a white card, etc.),
         no border, with a semi-transparent wash on hover that shows
         up regardless of the underlying colour. */
      .secondary-button {
        background: transparent;
        color: var(--text-1);
      }
      .secondary-button:hover {
        background: rgba(0, 0, 0, 0.05);
      }

      /* Flat success fill — mirrors the DS .btn-danger chrome (no
         lift), tinted green for go-ahead CTAs. */
      .attention-button,
      .affirmative {
        background: var(--success, #16a34a);
        color: #fff;
      }
      /* Hover darkening: static pre-mixed values first for browsers
         without color-mix(), re-derived from the token below. */
      .attention-button:hover,
      .affirmative:hover {
        background: #138f41;
      }

      /* DS .btn-danger — flat danger fill (no lift). */
      .destructive-button {
        background: var(--danger, #d03f3f);
        color: #fff;
      }
      .destructive-button:hover {
        background: #b73737;
      }

      @supports (color: color-mix(in srgb, red, red)) {
        .attention-button:hover,
        .affirmative:hover {
          background: color-mix(in srgb, var(--success, #16a34a) 88%, black);
        }
        .destructive-button:hover {
          background: color-mix(in srgb, var(--danger, #d03f3f) 88%, black);
        }
      }

      /* DS .btn-ghost — text-only, hover fills with sunken */
      .light-button,
      .lined-button {
        background: var(--surface);
        border-color: var(--border-strong);
        color: var(--text-1);
      }
      .light-button:hover,
      .lined-button:hover {
        background: var(--sunken);
      }

      /* icon-only button — square footprint, ghost chrome */
      .icon-button {
        width: var(--button-height, 28px);
        padding: 0;
        background: transparent;
        border-color: transparent;
        color: var(--text-2);
      }
      .icon-button:hover {
        background: var(--sunken);
        color: var(--text-1);
      }
      .icon-button.small {
        width: 24px;
      }

      /* active = pressed-down look — slightly inset */
      .button-container.active-button {
        box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.12);
      }
      .secondary-button.active-button {
        background: rgba(0, 0, 0, 0.08);
      }

      /* disabled */
      .button-container.disabled-button {
        opacity: 0.45;
        cursor: not-allowed;
        pointer-events: none;
      }

      /* focus ring — keyboard nav only */
      .button-container:focus-visible {
        box-shadow: var(--widget-box-shadow-focused);
      }

      .submit-animation {
        padding: 1px 4px;
      }

      .submit-animation temba-loading {
        margin-bottom: -3px;
        line-height: normal;
      }
    `;
  }

  @property({ type: Boolean })
  primary: boolean;

  @property({ type: Boolean })
  secondary: boolean;

  @property({ type: Boolean })
  attention: boolean;

  @property({ type: Number })
  v = 1;

  @property({ type: Boolean })
  destructive: boolean;

  @property({ type: Boolean })
  light: boolean;

  @property()
  name: string;

  @property({ type: Boolean })
  disabled: boolean;

  @property({ type: Boolean })
  submitting: boolean;

  @property({ type: Boolean })
  active: boolean;

  @property({ type: Boolean })
  small: boolean;

  @property({ type: Boolean })
  lined: boolean;

  @property({ type: String })
  href: string;

  @property({ type: Number })
  index?: number;

  @property({ type: String })
  icon?: string;

  private handleClick(evt: MouseEvent) {
    if (this.disabled) {
      evt.preventDefault();
      evt.stopPropagation();
    }

    if (this.href && !this.disabled) {
      this.ownerDocument.location.href = this.href;
      evt.preventDefault();
      evt.stopPropagation();
    }
  }

  private handleKeyUp(event: KeyboardEvent): void {
    this.active = false;
    if (event.key === 'Enter') {
      this.click();
    }
  }

  private handleMouseDown(): void {
    if (!this.disabled && !this.submitting) {
      this.active = true;
      this.classList.add('active');
    }
  }

  private handleMouseUp(): void {
    this.active = false;
    this.classList.remove('active');
  }

  public render(): TemplateResult {
    const buttonName = this.submitting
      ? html`<div class="submit-animation">
          <temba-loading units="3" size="8" color="#eee"></temba-loading>
        </div>`
      : this.name;

    return html`
      <div
        class="button-container 
          v-${this.v}
          ${getClasses({
          'primary-button':
            this.primary ||
            (!this.primary &&
              !this.secondary &&
              !this.attention &&
              !this.destructive &&
              !this.lined &&
              !this.light &&
              this.v == 1),
          'secondary-button': this.secondary,
          'disabled-button': this.disabled,
          'active-button': this.active,
          'attention-button': this.attention,
          'destructive-button': this.destructive,
          'light-button': this.light,
          'lined-button': this.lined,
          'icon-button': !!this.icon && !this.name,
          small: this.small
        })}"
        tabindex="0"
        @mousedown=${this.handleMouseDown}
        @mouseup=${this.handleMouseUp}
        @mouseleave=${this.handleMouseUp}
        @keyup=${this.handleKeyUp}
        @click=${this.handleClick}
      >
        <div class="button-mask">
          ${this.icon
            ? html`<temba-icon name="${this.icon}"></temba-icon>`
            : null}
          <div class="button-name"><slot name="name">${buttonName}</slot></div>
        </div>
      </div>
    `;
  }
}
