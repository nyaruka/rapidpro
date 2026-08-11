import { css, html, PropertyValueMap, TemplateResult } from 'lit';
import { property } from 'lit/decorators.js';
import { RapidElement } from '../RapidElement';
import { getClasses } from '../utils';

export class Tab extends RapidElement {
  static get styles() {
    return css`
      :host {
        display: none;
        flex-direction: column;
        min-height: 0;
        pointer-events: none;
      }

      :host(.selected) {
        display: flex;
        flex-grow: 1;
        pointer-events: auto;
      }
    `;
  }

  @property({ type: String })
  name: string;

  @property({ type: String })
  icon: string;

  @property({ type: Boolean })
  selected = false;

  @property({ type: Boolean })
  alert = false;

  @property({ type: Boolean })
  hidden = false;

  @property({ type: Boolean })
  hideEmpty = false;

  // show just that there is activity instead of count
  @property({ type: Boolean })
  activity = false;

  @property({ type: Number })
  count = 0;

  @property({ type: Boolean })
  checked = false;

  @property({ type: Boolean })
  dirty = false;

  public updated(
    changes: PropertyValueMap<any> | Map<PropertyKey, unknown>
  ): void {
    super.updated(changes);
    if (changes.has('selected')) {
      this.classList.toggle('selected', this.selected);
    }
  }

  public hasBadge() {
    return this.count > 0;
  }

  public handleDetailsChanged(event: CustomEvent) {
    if ('dirty' in event.detail) {
      this.dirty = event.detail.dirty;
    }
    if ('count' in event.detail) {
      this.count = event.detail.count;
      if (this.hideEmpty) {
        this.hidden = this.count === 0;
      }
    }
  }

  public render(): TemplateResult {
    return html`<slot
      @temba-details-changed=${this.handleDetailsChanged}
      class="${getClasses({ selected: this.selected })}"
    ></slot> `;
  }
}
