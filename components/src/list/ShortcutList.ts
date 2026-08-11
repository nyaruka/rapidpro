import { css, html, PropertyValueMap, TemplateResult } from 'lit';
import { property } from 'lit/decorators.js';
import { CustomEventType, Shortcut } from '../interfaces';
import { StoreMonitorElement } from '../store/StoreMonitorElement';
import { Options } from '../display/Options';

export class ShortcutList extends StoreMonitorElement {
  static get styles() {
    return css`
      temba-options {
        display: block;
        width: 100%;
        flex-grow: 1;
      }

      .options-empty {
        height: 0;
        overflow: hidden;
      }

      .no-match {
        margin: 5px 10px;
        padding: 10px;
      }

      .filter {
        background: #f3f3f3;
        padding: 0.1em 0.3em;
        border-radius: var(--curvature);
      }

      .search-box {
        padding: 6px 8px;
        border-bottom: 1px solid var(--color-widget-border, #e6e6e6);
      }

      .search-box input {
        width: 100%;
        border: none;
        outline: none;
        font-size: 0.9em;
        padding: 4px 0;
        background: transparent;
        font-family: inherit;
      }
    `;
  }

  @property({ type: String })
  filter: string;

  @property({ type: Boolean })
  showSearch = false;

  @property({ type: Array })
  filteredShortcuts = [];

  @property({ type: Number })
  cursorIndex = 0;

  constructor() {
    super();
  }

  protected firstUpdated(
    changes: PropertyValueMap<any> | Map<PropertyKey, unknown>
  ): void {
    super.firstUpdated(changes);
  }

  public storeUpdated(): void {
    this.filteredShortcuts = this.store.getShortcuts();
  }

  public updated(
    changes: PropertyValueMap<any> | Map<PropertyKey, unknown>
  ): void {
    super.updated(changes);

    if (changes.has('filter')) {
      if (!this.filter) {
        this.filteredShortcuts = this.store.getShortcuts();
      } else {
        this.filteredShortcuts = this.store
          .getShortcuts()
          .filter((shortcut: Shortcut) =>
            shortcut.name.toLowerCase().includes(this.filter.toLowerCase())
          );
      }
      this.cursorIndex = 0;
    }
  }

  public renderShortcut(shortcut: Shortcut): TemplateResult {
    return html`<div style="display:flex;align-items: center;min-width:0">
      <div
        style="
          overflow: hidden;
          text-overflow: ellipsis;
          width:175px; 
          padding-right: 10px;
          white-space: nowrap;"
      >
        ${shortcut.name}
      </div>
      <div
        style=" 
          font-size: 0.9em;
          color: rgba(0, 0, 0, 0.4);
          flex:1;
          overflow: hidden;
          text-overflow: ellipsis;

          display: -webkit-box;
          line-height: 16px;
          max-height: 16px;
          -webkit-line-clamp: 1;
          -webkit-box-orient: vertical;
        "
      >
        ${shortcut.text}
      </div>
    </div>`;
  }

  public getShortcut() {
    const options = this.shadowRoot.querySelector('temba-options') as Options;
    return options.getSelection();
  }

  private handleSearchInput(evt: Event) {
    this.filter = (evt.target as HTMLInputElement).value;
  }

  private handleSearchKeyDown(evt: KeyboardEvent) {
    if (evt.key === 'ArrowDown') {
      evt.preventDefault();
      this.cursorIndex = Math.min(
        this.cursorIndex + 1,
        this.filteredShortcuts.length - 1
      );
    } else if (evt.key === 'ArrowUp') {
      evt.preventDefault();
      this.cursorIndex = Math.max(this.cursorIndex - 1, 0);
    } else if (evt.key === 'Enter') {
      evt.preventDefault();
      evt.stopPropagation();
      if (this.filteredShortcuts.length > 0) {
        const selected = this.filteredShortcuts[this.cursorIndex];
        this.fireCustomEvent(CustomEventType.Selection, { selected });
      }
    }
  }

  public focusSearch() {
    const input = this.shadowRoot?.querySelector(
      '.search-box input'
    ) as HTMLInputElement;
    if (input) {
      input.focus();
    }
  }

  public render(): TemplateResult {
    return html`
      ${this.showSearch
        ? html`<div class="search-box">
            <input
              type="text"
              placeholder="Search shortcuts..."
              @input=${this.handleSearchInput}
              @keydown=${this.handleSearchKeyDown}
            />
          </div>`
        : null}
      ${this.filteredShortcuts.length === 0
        ? html`<div class="no-match">
            ${this.filter
              ? html`No matches for <span class="filter">${this.filter}</span>.`
              : html`No shortcuts yet, create some to quickly include them in
                your messages.`}
          </div>`
        : null}

      <temba-options
        class="options-${this.filteredShortcuts.length === 0
          ? 'empty'
          : 'full'}"
        block
        cursorHover
        visible
        .renderOption=${this.renderShortcut}
        .cursorIndex=${this.cursorIndex}
        .options=${this.filteredShortcuts}
      ></temba-options>
    `;
  }
}
