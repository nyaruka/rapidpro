import { PropertyValues, TemplateResult, html } from 'lit';
import { property } from 'lit/decorators.js';
import { styleMap } from 'lit-html/directives/style-map.js';
import { Select, SelectOption } from './Select';
import { Icon } from '../../Icons';

enum OmniType {
  Group = 'group',
  Contact = 'contact'
}

export interface OmniOption extends SelectOption {
  id: string;
  name: string;
  type: OmniType;
  urn?: string;
  count?: number;
  contact?: string;
  scheme?: string;
}

const postNameStyle = {
  color: 'var(--color-text-dark)',
  padding: '0px 6px',
  fontSize: '12px'
};

export class Omnibox extends Select<OmniOption> {
  @property({ type: String })
  valueKey = 'uuid';

  @property({ type: Boolean })
  groups = false;

  @property({ type: Boolean })
  contacts = false;

  @property({ type: String })
  placeholder = 'Select recipients';

  @property({ type: Boolean })
  multi = true;

  @property({ type: Boolean })
  jsonValue = true;

  @property({ type: Boolean })
  searchable = true;

  @property({ type: Boolean })
  searchOnFocus = true;

  @property({ type: Boolean })
  queryParam = 'search';

  public willUpdate(changes: PropertyValues): void {
    if (
      (changes.has('groups') || changes.has('contacts')) &&
      (this.groups || this.contacts)
    ) {
      let types = '&types=';
      if (this.groups) {
        types += 'g';
      }

      if (this.contacts) {
        types += 'c';
      }

      this.endpoint = this.endpoint + types;
    }
    super.willUpdate(changes);
  }

  /** An option in the drop down */
  public renderOptionDefault(option: OmniOption): TemplateResult {
    return html`
      <div style="display:flex;">
        <div style="margin-right: 8px">${this.getIcon(option)}</div>
        <div style="flex: 1">${option.name}</div>
        <div
          style="background: rgba(50, 50, 50, 0.15); margin-left: 5px; display: flex; align-items: center; border-radius: 4px"
        >
          ${this.getPostName(option)}
        </div>
      </div>
    `;
  }

  private getPostName(option: OmniOption): TemplateResult {
    const style = { ...postNameStyle };

    if (option.urn && option.type === OmniType.Contact) {
      if (option.urn !== option.name) {
        return html`<div style=${styleMap(style)}>${option.urn}</div>`;
      }
    }

    if (option.type === OmniType.Group) {
      return html`
        <div style=${styleMap(style)}>${option.count.toLocaleString()}</div>
      `;
    }

    return null;
  }

  /**
   * Chip rendering — icon + name, plus the group count when the option
   * is a Group. Counts are intentionally suppressed in the base Select
   * chip (noise for action editors like Add to Group), but Omnibox is
   * the start-flow recipients picker where group size is a key part
   * of the chip's identity. Contacts skip the post-name URN that the
   * dropdown shows — chips already have a tight footprint.
   */
  public renderSelectedItemDefault(option: OmniOption): TemplateResult {
    const base = super.renderOptionDefault(option);
    if (
      option.type === OmniType.Group &&
      option.count !== undefined &&
      option.count !== null
    ) {
      return html`<div style="display:flex; align-items:center; gap:6px;">
        ${base}<span
          style="opacity:0.7; font-size:11px; font-variant-numeric: tabular-nums; font-weight: var(--w-medium);"
          >${option.count.toLocaleString()}</span
        >
      </div>`;
    }
    return base;
  }

  private getIcon(option: OmniOption): TemplateResult {
    if (option.type === OmniType.Group) {
      return html`<temba-icon name="${Icon.group}"></temba-icon>`;
    }

    if (option.type === OmniType.Contact) {
      return html`<temba-icon name="${Icon.contact}"></temba-icon>`;
    }
  }
}
