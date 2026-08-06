import { html, css, PropertyValues } from 'lit';
import { FieldElement } from './FieldElement';
import { property } from 'lit/decorators.js';
import { getClasses, hslToHex } from '../utils';
import { TextInput } from './TextInput';

export class ColorPicker extends FieldElement {
  @property({ type: Boolean })
  expanded = false;

  @property({ type: String })
  previewColor = '#ffffff';

  @property({ type: String })
  labelColor = '#ffffffee';

  @property({ type: Boolean })
  selecting = false;

  @property({ type: Number }) hue: number;
  @property({ type: Number }) saturation = 100;
  @property({ type: Number }) lightness = 50;
  @property({ type: String }) hex = '';

  static get styles() {
    return css`
      ${super.styles}

      :host {
        color: var(--color-text);
        display: inline-block;
        width: 100%;

        --temba-textinput-padding: 0.4em;
      }

      temba-textinput {
        margin-left: 0.3em;
        width: 7em;
        --temba-textinput-min-height: 0;
        --temba-textinput-padding: 4px 8px;
        --temba-textinput-font-size: 12.5px;
      }

      .wrapper {
        border: 1px solid var(--color-widget-border);
        padding: calc(var(--curvature) / 2);
        border-radius: var(--curvature);
        transition: all calc(var(--transition-speed) * 2) var(--bounce);

        display: flex;
        flex-grow: 0;
      }

      .picker-wrapper {
        display: flex;
        flex-direction: row;
        align-items: stretch;
        transition: all calc(var(--transition-speed) * 2) var(--bounce);
        flex-grow: 0;
      }

      .preview {
        width: initial;
        border-radius: var(--curvature);
        padding: 0.2em 0.5em;
        font-weight: 400;
        border: 2px solid rgba(0, 0, 0, 0.1);
        white-space: nowrap;
        cursor: pointer;
        transition: transform calc(var(--transition-speed) * 0.5) var(--bounce);
      }

      .preview.selecting {
        transform: scale(1.05);
      }

      .wrapper.expanded {
        flex-grow: 1 !important;
      }

      .wrapper.expanded .picker-wrapper {
        flex-grow: 1 !important;
      }

      .wrapper.expanded .preview {
        pointer-events: none;
      }

      .wrapper.expanded .color-picker {
        margin-left: calc(var(--curvature) / 2);
      }

      .wrapper.expanded temba-textinput {
        display: block;
      }

      .color-picker {
        border-radius: var(--curvature);
        cursor: pointer;
        transition: all calc(var(--transition-speed) * 2) var(--bounce);
        flex-grow: 1;
        position: relative;
        width: 100%;
        height: 100%;
        background-image:
          linear-gradient(
            to bottom,
            rgba(0, 0, 0, 0) 60%,
            rgba(0, 0, 0, 0.5) 90%,
            rgba(0, 0, 0, 1)
          ),
          linear-gradient(
            to top,
            rgba(255, 255, 255, 0) 60%,
            rgba(255, 255, 255, 0.8) 90%,
            rgba(255, 255, 255, 1)
          ),
          linear-gradient(
            to right,
            hsla(0, 100%, 50%, 1),
            hsla(60, 100%, 50%, 1),
            hsla(120, 100%, 50%, 1),
            hsla(180, 100%, 50%, 1),
            hsla(240, 100%, 50%, 1),
            hsla(300, 100%, 50%, 1),
            hsla(360, 100%, 50%, 1)
          );
        mix-blend-mode: multiply;
      }

      .color-picker:focus {
        outline: none;
      }
    `;
  }

  protected willUpdate(changed: PropertyValues): void {
    super.willUpdate(changed);

    if (changed.has('value')) {
      this.previewColor = this.value || '#9c9c9c';
      this.hex = this.value;
    }
  }

  public updated(changed: Map<string, any>): void {
    super.updated(changed);

    if (changed.has('selecting')) {
      if (this.selecting) {
        window.setTimeout(() => {
          this.selecting = false;
        }, 100);
      }
    }
  }

  private handleBlur() {
    if (this.expanded) {
      this.expanded = false;
    }
  }

  private handleMouseOut() {
    this.previewColor = this.value;
    this.hex = this.value;
  }

  private handleMouseMove(event: MouseEvent) {
    if (this.expanded) {
      const rect = (event.target as HTMLElement).getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      this.hue = (x / rect.width) * 360;
      this.lightness = 100 - (y / rect.height) * 100;
      this.previewColor = `hsla(${this.hue}, ${this.saturation}%, ${this.lightness}%, 1)`;
      this.hex = hslToHex(this.hue, this.saturation, this.lightness);
    }
  }

  private handlePreviewClick() {
    this.expanded = !this.expanded;
    this.selecting = true;
    (this.shadowRoot.querySelector('.color-picker') as HTMLDivElement).focus();
  }

  private handleColorClick(event: MouseEvent) {
    if (this.expanded) {
      const rect = (event.target as HTMLElement).getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      this.hue = (x / rect.width) * 360;
      this.lightness = 100 - (y / rect.height) * 100;
      this.previewColor = `hsla(${this.hue}, ${this.saturation}%, ${this.lightness}%, 1)`;
      this.value = this.hex;
      this.selecting = true;
      this.expanded = false;
    }

    if (!this.expanded) {
      //
    }
  }

  private handleHexInput(event: InputEvent) {
    const hex = (event.target as TextInput).value;
    if (hex.startsWith('#')) {
      this.previewColor = hex;
      this.value = hex;
    }
  }

  public serializeValue(value: any): string {
    return value;
  }

  protected renderWidget() {
    return html`
      <div style="display:flex" tabindex="0">
        <div class=${getClasses({ wrapper: true, expanded: this.expanded })}>
          <div class=${getClasses({ 'picker-wrapper': true })}>
            <div
              class=${getClasses({
                preview: true,
                selecting: this.selecting
              })}
              style="color:${this.labelColor};background:${this.previewColor}"
              @click=${this.handlePreviewClick}
            >
              ${this.label}
            </div>
            <div
              class="color-picker"
              tabindex="0"
              @blur=${this.handleBlur}
              @mousemove=${this.handleMouseMove}
              @mouseout=${this.handleMouseOut}
              @click=${this.handleColorClick}
            ></div>
          </div>
          <temba-textinput
            value=${this.hex}
            @input=${this.handleHexInput}
            placeholder="#000000"
          ></temba-textinput>
        </div>
      </div>
    `;
  }
}
