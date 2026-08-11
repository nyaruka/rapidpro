import { css, html, PropertyValues, TemplateResult } from 'lit';
import { property } from 'lit/decorators.js';
import { ContactField, CustomEventType } from '../interfaces';

import { SortableList } from '../list/SortableList';
import { EndpointMonitorElement } from '../store/EndpointMonitorElement';
import { postJSON } from '../utils';

const TYPE_NAMES = {
  text: 'Text',
  numeric: 'Number',
  number: 'Number',
  datetime: 'Date & Time',
  state: 'State',
  ward: 'Ward',
  district: 'District'
};

const matches = (field: ContactField, query: string): boolean => {
  if (!query) {
    return true;
  }
  const search = (
    field.label +
    field.key +
    TYPE_NAMES[field.value_type]
  ).toLowerCase();
  if (search.toLowerCase().indexOf(query) > -1) {
    return true;
  }
  return false;
};

export class FieldManager extends EndpointMonitorElement {
  static get styles() {
    return css`
      :host {
        display: flex;
        flex-grow: 1;
        flex-direction: column;
        min-height: 0px;
      }

      .featured,
      .other-fields {
        background: #fff;
        border-radius: var(--curvature);
        box-shadow: var(--shadow);
        margin-bottom: 1em;
        display: flex;
        flex-direction: column;
      }

      .featured {
        max-height: 40%;
      }

      .other-fields {
        flex-grow: 2;
        min-height: 0px;
        margin-bottom: 0px;
      }

      temba-textinput {
        margin-bottom: 1em;
      }

      .scroll-box {
        overflow-y: auto;
        flex-grow: 1;
        flex-direction: column;
        display: flex;
      }

      .header temba-icon {
        margin-right: 0.5em;
      }

      .label {
        flex-grow: 1;
      }

      .header {
        padding: 0.5em 1em;
        display: flex;
        align-items: flex-start;
        border-bottom: 1px solid var(--color-widget-border);
      }

      .featured-field {
        user-select: none;
      }

      temba-sortable-list {
        padding: 0.5em 0em;
        width: 100%;
        overflow-y: auto;
      }

      .scroll-box {
        padding: 0.5em 0em;
      }

      temba-icon[name='usages']:hover {
        --icon-color: var(--color-link-primary);
      }

      .field:hover temba-icon[name='delete_small'] {
        opacity: 1 !important;
        cursor: pointer !important;
        pointer-events: all !important;
      }

      temba-icon[name='delete_small']:hover {
        --icon-color: var(--color-link-primary);
      }

      .field {
        border: 1px solid transparent;
        margin: 0 0.5em;
        border-radius: var(--curvature);
      }

      .featured:not(.dragging) temba-sortable-list .field:hover {
        cursor: move;
        border-color: #e6e6e6;
        background: #fcfcfc;
      }
    `;
  }

  @property({ type: String, attribute: 'priority-endpoint' })
  priorityEndpoint: string;

  @property({ type: Object, attribute: false })
  featuredFields: ContactField[];

  @property({ type: Object, attribute: false })
  otherFieldKeys: string[] = [];

  @property({ type: String })
  query = '';

  connectedCallback(): void {
    super.connectedCallback();
    if (this.store?.fieldsEndpoint) {
      this.url = this.store.fieldsEndpoint;
    }
  }

  public willUpdate(changed: PropertyValues): void {
    super.willUpdate(changed);
    if (changed.has('data') || changed.has('query')) {
      this.filterFields();
    }
  }

  private filterFields() {
    const filteredKeys = this.store.getFieldKeys().filter((key) => {
      const field = this.store.getContactField(key);
      if (field.featured) {
        return false;
      }
      return matches(field, this.query);
    });

    // sort by the label instead of the key
    filteredKeys.sort((a, b) => {
      return this.store
        .getContactField(a)
        .label.localeCompare(this.store.getContactField(b).label);
    });

    const featured: ContactField[] = [];
    this.store.getFeaturedFields().forEach((field) => {
      if (matches(field, this.query)) {
        featured.push(field);
      }
    });

    this.otherFieldKeys = filteredKeys;
    this.featuredFields = featured;
  }

  private handleOrderChanged(event) {
    // Apply the reordering immediately - the SortableList now provides accurate indexes
    const [fromIdx, toIdx] = event.detail.swap;

    const temp = this.featuredFields[fromIdx];
    this.featuredFields.splice(fromIdx, 1);
    this.featuredFields.splice(toIdx, 0, temp);
    this.requestUpdate();

    // Save the new order to the server
    const list = event.currentTarget as SortableList;
    setTimeout(() => {
      postJSON(
        this.priorityEndpoint,
        list
          .getIds()
          .reverse()
          .reduce((map, key, idx) => {
            map[key] = idx;
            return map;
          }, {})
      ).then(() => {
        this.store.refreshFields();
      });
    }, 0);
  }

  private handleFieldAction(event: MouseEvent) {
    const ele = event.target as HTMLDivElement;
    const key = ele.dataset.key;
    const action = ele.dataset.action;
    this.fireCustomEvent(CustomEventType.Selection, { key, action });
  }

  private handleSearch(event) {
    this.query = (event.target.value || '').trim();
  }

  private hasUsages(field: ContactField): boolean {
    return (
      field.usages.campaign_events + field.usages.flows + field.usages.groups >
      0
    );
  }

  private renderField(field: ContactField) {
    return html`
      <div
        class="field sortable"
        id="${field.key}"
        style="
            display: flex; 
            flex-direction: row; 
            align-items: center;
            padding: 0.25em 1em;"
        @click=${(e: MouseEvent) => {
          const ele = e.currentTarget as HTMLDivElement;
          const key = ele.dataset.key;
          const action = ele.dataset.action;
          this.fireCustomEvent(CustomEventType.Selection, { key, action });
        }}
      >
        <div
          style="display: flex; min-width: 200px; width: 200px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-right: 2em"
        >
          <temba-label
            type="field"
            clickable
            @click=${this.handleFieldAction}
            data-key=${field.key}
            data-action="update"
            >${field.label}</temba-label
          >
          ${this.hasUsages(field)
            ? html`
                <temba-icon
                  size="0.8"
                  style="color: #ccc; margin-left: 0.7em;"
                  name="usages"
                  data-key=${field.key}
                  data-action="usages"
                  @click=${this.handleFieldAction}
                  clickable
                ></temba-icon>
              `
            : null}
          <div class="flex-grow:1"></div>
        </div>
        <div
          style="flex-grow:1; font-family: Roboto Mono, monospace; font-size:0.8em;"
        >
          @fields.${field.key}
        </div>
        <div>${TYPE_NAMES[field.value_type]}</div>
        <temba-icon
          style="pointer-events:none;color:#ccc;margin-left:0.3em;margin-right:-0.5em;opacity:0"
          name="delete_small"
          data-key=${field.key}
          data-action="delete"
          @click=${this.handleFieldAction}
        ></temba-icon>
      </div>
    `;
  }

  public render(): TemplateResult {
    if (!this.featuredFields) {
      return null;
    }

    return html`
      <temba-textinput
        id="search"
        placeholder="Search"
        @change=${this.handleSearch}
        clearable
        value=${this.query}
      ></temba-textinput>

      ${this.featuredFields.length > 0
        ? html`
            <div class="featured">
              <div class="header">
                <temba-icon name="featured"></temba-icon>
                <div class="label">Featured</div>
              </div>
              ${this.query
                ? html`
                    <div class="scroll-box">
                      ${this.featuredFields.map((field) =>
                        this.renderField(field)
                      )}
                    </div>
                  `
                : html`
                    <temba-sortable-list
                      @temba-order-changed=${this.handleOrderChanged}
                    >
                      ${this.featuredFields.map((field) =>
                        this.renderField(field)
                      )}
                    </temba-sortable-list>
                  `}
            </div>
          `
        : null}

      <div class="other-fields">
        <div class="header">
          <temba-icon name="fields"></temba-icon>
          <div class="label">Everything Else</div>
        </div>
        <div class="scroll-box">
          ${this.otherFieldKeys.map((field) =>
            this.renderField(this.store.getContactField(field))
          )}
        </div>
      </div>
    `;
  }
}
