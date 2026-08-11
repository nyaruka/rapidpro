import { TemplateResult, html, css } from 'lit';
import { property } from 'lit/decorators.js';
import { FieldElement } from './FieldElement';
import { renderMarkdownInline } from '../markdown';

/**
 * A two state switch - the same contract as temba-checkbox, shown as a slider rather than a box, and standing the
 * height of a standard button so it can sit level in a row of them. That's where a state you flip usually belongs:
 * a checkbox reads as something you're filling in and will submit later, a switch as something that takes effect.
 */
export class Toggle extends FieldElement {
  static get styles() {
    return css`
      ${super.styles}

      :host {
        display: inline-block;
        color: var(--color-text);
      }

      .wrapper {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        /* the height of a standard button, so the switch lines up with any button beside it rather than sitting
           proud of the row */
        height: var(--button-height, 28px);
        padding: 0 2px;
        border-radius: var(--r-sm);
        cursor: pointer;
        user-select: none;
        -webkit-user-select: none;
        outline: none;
      }

      .wrapper:focus-visible {
        box-shadow: var(--focus-halo);
      }

      .track {
        position: relative;
        flex: 0 0 auto;
        width: 30px;
        height: 18px;
        border-radius: 999px;
        background: var(--sunken);
        /* an inset shadow rather than a border, so the track's size doesn't change with its state */
        box-shadow: inset 0 0 0 1px var(--border-strong);
        transition:
          background 140ms ease,
          box-shadow 140ms ease;
      }

      .knob {
        position: absolute;
        top: 2px;
        left: 2px;
        width: 14px;
        height: 14px;
        border-radius: 50%;
        background: #fff;
        box-shadow: 0 1px 2px rgba(15, 22, 36, 0.28);
        transition: transform 140ms ease;
      }

      .on .track {
        background: var(--accent-600);
        box-shadow: inset 0 0 0 1px var(--accent-600);
      }

      .on .knob {
        transform: translateX(12px);
      }

      .toggle-label {
        font-size: 12.5px;
        line-height: 1;
        white-space: nowrap;
      }

      .toggle-help-text {
        font-size: var(--help-text-size, 0.85em);
        line-height: normal;
        color: var(--color-text-help);
        margin-top: 4px;
      }

      .disabled {
        cursor: not-allowed;
        opacity: var(--disabled-opacity);
      }
    `;
  }

  @property({ type: Boolean })
  checked = false;

  private initialized = false;

  public updated(changes: Map<string, any>): void {
    super.updated(changes);

    if (changes.has('checked') || changes.has('value')) {
      // the same form value a checkbox posts - present when on, absent when off
      this.internals.setFormValue(this.checked ? this.value || '1' : undefined);

      // the first render is the state we were given, not a change to it
      if (this.initialized) {
        this.fireEvent('change');
      }
    }

    this.initialized = true;
  }

  public serializeValue(value: any): string {
    return value;
  }

  private toggle(): void {
    if (!this.disabled) {
      this.checked = !this.checked;
    }
  }

  public click(): void {
    this.toggle();
    super.click();
  }

  private handleKeyDown(event: KeyboardEvent): void {
    if (event.key === ' ' || event.key === 'Enter') {
      // space would otherwise scroll whatever holds the switch
      event.preventDefault();
      this.toggle();
    }
  }

  protected renderWidget(): TemplateResult {
    return html`
      <div
        class="wrapper ${this.checked ? 'on' : ''} ${this.disabled
          ? 'disabled'
          : ''}"
        role="switch"
        aria-checked=${this.checked}
        aria-label=${this.label || this.name || 'Toggle'}
        aria-disabled=${!!this.disabled}
        tabindex=${this.disabled ? -1 : 0}
        @click=${this.toggle}
        @keydown=${this.handleKeyDown}
      >
        <div class="track"><div class="knob"></div></div>
        ${!this.hideLabel && (this.label || this.helpText)
          ? html`<div class="label-and-help">
              ${this.label
                ? html`<div class="toggle-label">${this.label}</div>`
                : null}
              ${this.helpText && this.helpText !== 'None'
                ? html`<div class="toggle-help-text">${this.helpText}</div>`
                : null}
            </div>`
          : null}
      </div>
    `;
  }

  protected renderField(): TemplateResult {
    // FieldElement.renderField without the field label, which the switch renders inline itself
    const hasErrors = !this.hideErrors && this.errors && this.errors.length > 0;
    const errors = hasErrors
      ? this.errors.map(
          (error: string) =>
            html`<div class="alert-error">${renderMarkdownInline(error)}</div>`
        )
      : [];

    if (this.widgetOnly) {
      return html`${this.renderWidget()}${errors}`;
    }

    return html`
      <div class="field ${hasErrors ? 'has-error' : ''}">
        <div class="widget">${this.renderWidget()} ${errors}</div>
      </div>
    `;
  }
}
