import { css, html, PropertyValueMap, TemplateResult } from 'lit';
import { property } from 'lit/decorators.js';
import { CustomEventType } from '../interfaces';
import { RapidElement } from '../RapidElement';
import { getClasses } from '../utils';
import { Tab } from './Tab';

export class TabPane extends RapidElement {
  static get styles() {
    return css`
      :host {
        display: flex;
        flex-direction: column;
        min-height: 0;
        flex-grow: 1;
      }

      .options {
        display: flex;
        align-items: stretch;
        gap: 4px;
        border-bottom: 1px solid var(--border);
      }

      .option {
        user-select: none;
        display: flex;
        align-items: center;
        cursor: pointer;
        padding: 8px 14px 10px;
        margin-bottom: -1px;
        background: transparent;
        color: var(--text-2);
        --icon-color: var(--text-2);
        font-size: 13px;
        font-weight: var(--w-medium);
        border-bottom: 2px solid transparent;
        white-space: nowrap;
        transition:
          color 100ms linear,
          border-color 100ms linear;
      }

      .option:hover {
        color: var(--text-1);
        --icon-color: var(--text-1);
      }

      .option.selected,
      .option.selected:hover {
        cursor: default;
        color: var(--accent-700);
        --icon-color: var(--accent-700);
        border-bottom-color: var(--accent-600);
      }

      .unselect .option.selected {
        cursor: pointer;
      }

      .option.hidden {
        display: none;
      }

      .option .name {
        margin-left: 0.4em;
        max-width: 200px;
        overflow: hidden;
        transition:
          max-width 500ms ease-in-out,
          margin 500ms ease-in-out;
        white-space: nowrap;
        text-overflow: ellipsis;
      }

      .option .badge {
        margin-left: 0.4em;
        margin-right: -6px;
        display: inline-flex;
        align-items: center;
      }

      @media (max-width: 900px) {
        .collapses .option .name {
          max-width: 0px;
          margin: 0;
        }
      }

      @media (max-width: 600px) {
        .collapses .option .badge {
          display: none;
        }
      }

      .focusedname .option .name {
        max-width: 0px;
        margin: 0;
        transition:
          max-width 200ms linear,
          margin 200ms linear;
      }

      .focusedname .option.selected .name {
        margin-left: 0.4em;
        max-width: 200px;
      }

      .focusedname .option .name {
        transition: all 0s linear !important;
      }

      .focusedname .option.selected .name {
        transition: all 200ms linear !important;
      }

      .option.dirty {
        font-weight: var(--w-semibold);
      }

      .option.alert {
        color: var(--danger);
        --icon-color: var(--danger);
      }

      .pane {
        display: flex;
        flex-direction: column;
        flex-grow: 1;
        min-height: 0;
        overflow: hidden;
      }

      .count {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        height: 16px;
        padding: 0 2px;
        color: inherit;
        opacity: 0.6;
        font-size: 11px;
        font-weight: var(--w-medium);
        font-variant-numeric: tabular-nums;
      }

      .option.selected .count,
      .option.alert .count {
        min-width: 16px;
        padding: 0 4px;
        border-radius: 999px;
        opacity: 1;
      }

      .option.selected .count {
        background: var(--accent-100);
        color: var(--accent-700);
        font-weight: var(--w-semibold);
      }

      .option.alert .count {
        background: var(--danger-bg);
        color: var(--danger);
      }

      .dot {
        height: 0.5em;
        width: 0.5em;
        margin-left: 0.2em;
        background: var(--accent-600);
        border-radius: 99px;
      }

      .option.selected .dot {
        display: none;
      }

      .check {
        margin-left: 0.4em;
      }
    `;
  }

  @property({ type: Boolean })
  collapses = false;

  // do we allow unselecting the current tab
  @property({ type: Boolean })
  unselect = false;

  // Only shows the name if the tab is focused
  @property({ type: Boolean })
  focusedName = false;

  @property({ type: Number })
  index = -1;

  @property({ type: String })
  refresh = '';

  @property({ type: Array, attribute: false })
  options: Tab[] = [];

  private handleTabClick(event: MouseEvent): void {
    const newIndex = parseInt(
      (event.currentTarget as HTMLDivElement).dataset.index
    );

    if (this.unselect && this.index === newIndex) {
      this.index = -1;
    } else {
      this.index = newIndex;
    }

    event.preventDefault();
    event.stopPropagation();
    this.requestUpdate('index');
  }

  public handleSlotChange() {
    const tabs: Tab[] = [];
    for (const t of this.children) {
      if (t.tagName === 'TEMBA-TAB') {
        const tab = t as Tab;
        tabs.push(tab);
      }
    }
    this.options = tabs;
    if (this.index < 0 || this.index >= tabs.length) {
      this.index = 0;
    }
  }

  public firstUpdated(
    changes: PropertyValueMap<any> | Map<PropertyKey, unknown>
  ): void {
    super.firstUpdated(changes);
    this.shadowRoot.addEventListener(
      'slotchange',
      this.handleSlotChange.bind(this)
    );
  }

  public updated(changedProperties: Map<string, any>) {
    super.updated(changedProperties);

    if (changedProperties.has('options')) {
      this.options.forEach((tab, index) => {
        tab.selected = index == this.index;
      });
    }

    if (changedProperties.has('index')) {
      if (this.options.length >= 0) {
        if (this.index !== changedProperties.get('index')) {
          this.options.forEach((tab, index) => {
            tab.selected = index == this.index;
          });
          this.fireEvent(CustomEventType.ContextChanged);
        }
      }
    }

    // if our current tab is hidden, select the first visible one
    if (this.index > this.options.length) {
      const tab = this.options[this.index];
      if (tab && tab.hidden) {
        for (let i = 0; i < this.options.length; i++) {
          const other = this.options[i];
          if (other && !other.hidden) {
            this.index = i;
            return;
          }
        }
      }
    }
  }

  public focusTab(name: string): Tab {
    const index = this.options.findIndex((tab) => tab.name === name);
    if (index >= 0) {
      this.index = index;
      return this.getTab(index);
    }
  }

  public setTabDetails(
    index: number,
    details: { count: number; hidden: boolean }
  ) {
    if (index < this.options.length) {
      const tab = this.options[index];
      tab.count = details.count;
      tab.hidden = details.hidden;
      this.requestUpdate();
    } else {
      // not ready yet, set the tab details later
      setTimeout(() => {
        this.setTabDetails(index, details);
      }, 100);
    }
  }

  public getCurrentTab(): Tab {
    return this.options[this.index];
  }

  public getTab(index: number): Tab {
    return this.options[index];
  }

  public handleTabContentChanged() {
    this.requestUpdate();
  }

  public handleTabDetailsChanged() {
    this.requestUpdate();
  }

  public render(): TemplateResult {
    return html`
      <div
        class="${getClasses({
          options: true,
          collapses: this.collapses,
          focusedname: this.focusedName,
          unselect: this.unselect
        })}"
      >
        ${this.options.map(
          (tab, index) => html`
            <div
              @click=${this.handleTabClick}
              data-index=${index}
              class="${getClasses({
                option: true,
                first: index == 0,
                selected: index == this.index,
                hidden: tab.hidden,
                alert: tab.alert,
                dirty: tab.dirty
              })}"
            >
              ${tab.icon ? html`<temba-icon name=${tab.icon} />` : null}
              <div class="name">${tab.name} ${tab.dirty ? ` *` : ``}</div>
              ${tab.hasBadge()
                ? html`
                    <div class="badge">
                      ${tab.count > 0 && !tab.activity
                        ? html`<div class="count">
                            ${tab.count.toLocaleString()}
                          </div>`
                        : null}
                      ${tab.activity && tab.count > 0 && !tab.dirty
                        ? html`<div class="dot"></div>`
                        : null}
                    </div>
                  `
                : null}
              ${tab.checked && !tab.alert
                ? html`<temba-icon class="check" name="check"></temba-icon>`
                : null}
            </div>
          `
        )}

        <div style="flex-grow:1"></div>
        <div style="display:flex; align-items:center">
          <slot name="tab-right"></slot>
        </div>
      </div>
      <div @temba-details-changed=${this.handleTabDetailsChanged} class="pane">
        <slot></slot>
        <slot name="pane-bottom"></slot>
      </div>
    `;
  }
}
