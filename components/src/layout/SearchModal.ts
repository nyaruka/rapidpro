import { html, css, CSSResultGroup, TemplateResult } from 'lit';
import { property, state, query } from 'lit/decorators.js';
import { styleMap } from 'lit/directives/style-map.js';
import { Icon } from '../Icons';
import { RapidElement } from '../RapidElement';

export interface ModalSearchResult {
  // The label shown in the result's badge (e.g. "Send Message", a contact name)
  typeName: string;
  // Color for the badge background
  color: string;
  // Optional border color for the badge
  borderColor?: string;
  // Optional text color override for the badge
  textColor?: string;
  // The full text that was searched
  fullText: string;
  // The index of the match start in fullText
  matchStart: number;
  // The length of the match (0 renders the text as an unhighlighted preview)
  matchLength: number;
}

/**
 * Base class for modal search windows — a centered overlay with a search
 * input, keyboard-navigable result list and match highlighting. Subclasses
 * implement performSearch() to supply results, either synchronously as the
 * user types (the default) or asynchronously when the user hits Enter (set
 * searchOnEnter for searches that hit an endpoint).
 */
export abstract class SearchModal<
  T extends ModalSearchResult = ModalSearchResult
> extends RapidElement {
  static styles: CSSResultGroup = css`
    :host {
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      z-index: 100000;
      display: none;
      font-family: var(--font-family, sans-serif);
    }

    :host([open]) {
      display: flex;
      align-items: flex-start;
      justify-content: center;
    }

    .backdrop {
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(0, 0, 0, 0.3);
    }

    .search-container {
      position: relative;
      margin-top: 80px;
      width: 560px;
      max-height: calc(100vh - 160px);
      background: white;
      border-radius: 14px;
      box-shadow:
        0 24px 80px rgba(0, 0, 0, 0.2),
        0 0 0 1px rgba(0, 0, 0, 0.05);
      display: flex;
      flex-direction: column;
      overflow: hidden;
      animation: searchSlideIn 0.15s ease-out;
    }

    @keyframes searchSlideIn {
      from {
        opacity: 0;
        transform: scale(0.98) translateY(-8px);
      }
      to {
        opacity: 1;
        transform: scale(1) translateY(0);
      }
    }

    .search-input-row {
      display: flex;
      align-items: center;
      padding: 14px 18px;
      border-bottom: 1px solid #e5e7eb;
      gap: 10px;
    }

    .search-icon {
      color: #9ca3af;
      flex-shrink: 0;
    }

    .search-icon temba-icon {
      --icon-color: #9ca3af;
      display: block;
    }

    input {
      flex: 1;
      border: none;
      outline: none;
      font-size: 16px;
      background: transparent;
      color: #111;
      font-family: inherit;
    }

    input::placeholder {
      color: #9ca3af;
    }

    .results {
      overflow-y: auto;
      max-height: 400px;
    }

    .result-item {
      display: flex;
      align-items: center;
      padding: 10px 18px;
      gap: 12px;
      cursor: pointer;
      border-bottom: 1px solid #f3f4f6;
      transition: background 0.08s;
    }

    .result-item:last-child {
      border-bottom: none;
    }

    .result-item:hover,
    .result-item.highlighted {
      background: #f0f4ff;
    }

    .result-type-badge {
      flex-shrink: 0;
      font-size: 11px;
      font-weight: 600;
      color: white;
      padding: 2px 10px;
      border-radius: 8px;
      border: 2px solid transparent;
      white-space: nowrap;
      text-align: center;
      box-sizing: border-box;
    }

    .result-text {
      min-width: 0;
      font-size: 14px;
      color: #374151;
      line-height: 1.4;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .result-text mark {
      background: #fef08a;
      color: inherit;
      border-radius: 2px;
      padding: 0 1px;
    }

    .no-results {
      padding: 24px 18px;
      text-align: center;
      color: #9ca3af;
      font-size: 14px;
    }

    .loading {
      display: flex;
      justify-content: center;
      padding: 24px 18px;
    }

    .result-count {
      padding: 8px 18px;
      font-size: 12px;
      color: #9ca3af;
      border-top: 1px solid #e5e7eb;
      text-align: right;
      flex-shrink: 0;
    }

    .hint {
      padding: 10px 18px;
      font-size: 12px;
      color: #9ca3af;
      text-align: center;
    }

    kbd {
      background: #f3f4f6;
      border: 1px solid #d1d5db;
      border-radius: 4px;
      padding: 1px 5px;
      font-size: 11px;
      font-family: inherit;
    }
  `;

  @property({ type: Boolean, reflect: true })
  open = false;

  // When set, searching waits for Enter instead of running as the user types.
  // Use for searches that hit an endpoint and shouldn't fire on every keystroke.
  @property({ type: Boolean })
  searchOnEnter = false;

  @state()
  protected searchQuery = '';

  @state()
  protected results: T[] = [];

  @state()
  protected highlightedIndex = 0;

  @state()
  protected loading = false;

  // In searchOnEnter mode, whether the query has changed since the last search
  @state()
  protected dirty = false;

  // Set when an async performSearch rejects, so a failed lookup reads as a
  // failure rather than as an empty result set
  @state()
  protected error = false;

  // Bumped on each search (and on query edits in searchOnEnter mode) so
  // in-flight async results that are no longer wanted get dropped
  private searchGeneration = 0;

  @query('input')
  private inputEl!: HTMLInputElement;

  /**
   * Produce results for the given query. Synchronous implementations run on
   * every keystroke; async implementations should be paired with searchOnEnter.
   */
  protected abstract performSearch(query: string): T[] | Promise<T[]>;

  /**
   * The label used for the dialog, placeholder and aria attributes.
   */
  protected abstract getSearchLabel(): string;

  /**
   * Called when a search is abandoned - the modal closed, or the query
   * edited out from under it. Subclasses with an in-flight request should
   * cancel it here.
   */
  protected cancelSearch(): void {
    // nothing to do for synchronous searches
  }

  public show(): void {
    this.open = true;
    this.searchQuery = '';
    this.results = [];
    this.highlightedIndex = 0;
    this.loading = false;
    this.dirty = false;
    this.error = false;
    this.searchGeneration++;
    this.updateComplete.then(() => {
      this.inputEl?.focus();
      this.inputEl?.select();
    });
  }

  public hide(): void {
    this.cancelSearch();
    this.open = false;
    this.searchQuery = '';
    this.results = [];
    this.loading = false;
    this.dirty = false;
    this.error = false;
    this.searchGeneration++;
  }

  private handleInput(e: InputEvent): void {
    const input = e.target as HTMLInputElement;
    this.searchQuery = input.value;
    this.highlightedIndex = 0;
    this.error = false;
    // whatever was in flight was for the old query
    this.cancelSearch();
    if (this.searchOnEnter) {
      // invalidate any in-flight search and wait for Enter
      this.searchGeneration++;
      this.results = [];
      this.loading = false;
      this.dirty = true;
    } else {
      this.runSearch();
    }
  }

  private handleKeyDown(e: KeyboardEvent): void {
    if (e.key === 'Escape') {
      e.preventDefault();
      this.hide();
      return;
    }
    if (e.key === 'ArrowDown' || (e.ctrlKey && e.key === 'n')) {
      e.preventDefault();
      if (this.results.length > 0) {
        this.highlightedIndex =
          (this.highlightedIndex + 1) % this.results.length;
      }
      return;
    }
    if (e.key === 'ArrowUp' || (e.ctrlKey && e.key === 'p')) {
      e.preventDefault();
      if (this.results.length > 0) {
        this.highlightedIndex =
          (this.highlightedIndex - 1 + this.results.length) %
          this.results.length;
      }
      return;
    }
    if (e.key === 'Enter') {
      e.preventDefault();
      if (this.searchOnEnter && this.dirty) {
        this.runSearch();
        return;
      }
      if (this.results.length > 0) {
        this.selectResult(this.results[this.highlightedIndex]);
      }
      return;
    }
  }

  private runSearch(): void {
    const generation = ++this.searchGeneration;
    this.dirty = false;
    this.highlightedIndex = 0;
    this.error = false;

    if (!this.searchQuery.trim()) {
      this.results = [];
      this.loading = false;
      return;
    }

    const outcome = this.performSearch(this.searchQuery);
    if (outcome instanceof Promise) {
      this.results = [];
      this.loading = true;
      outcome
        .then((results) => {
          if (generation === this.searchGeneration) {
            this.results = results;
            this.loading = false;
          }
        })
        .catch((error) => {
          // a superseded search has already been replaced by whatever
          // superseded it - that includes searches we aborted ourselves,
          // so those never surface as failures
          if (generation === this.searchGeneration) {
            console.error(
              'search failed',
              error instanceof Response
                ? `${error.status} ${error.url || ''}`.trim()
                : error
            );
            this.results = [];
            this.loading = false;
            this.error = true;
            // the query is still the one that failed, so leaving it dirty
            // lets Enter run it again
            this.dirty = this.searchOnEnter;
          }
        });
    } else {
      this.results = outcome;
    }
  }

  private handleBackdropClick(): void {
    this.hide();
  }

  protected selectResult(result: T): void {
    this.hide();
    this.dispatchEvent(
      new CustomEvent('temba-search-result-selected', {
        detail: result,
        bubbles: true,
        composed: true
      })
    );
  }

  protected renderMatchText(result: T): TemplateResult {
    const { matchStart, matchLength } = result;
    const matchEnd = matchStart + matchLength;

    // Replace newlines with spaces for single-line display
    const text = result.fullText.replace(/\n/g, ' ');

    // Zero-length matches show an unhighlighted content preview
    if (matchLength === 0) {
      return html`${text}`;
    }

    // Show leading context before the match, then the match, then trailing.
    // CSS text-overflow:ellipsis clips the trailing text, so we keep the match
    // near the start. When the match is near the end of the text, show more
    // leading context since there's less trailing text to display.
    const afterMatch = text.length - matchEnd;
    const contextBefore = afterMatch < 30 ? 50 : 20;
    const start = Math.max(0, matchStart - contextBefore);
    const prefix = start > 0 ? '…' : '';

    const before = text.slice(start, matchStart);
    const match = text.slice(matchStart, matchEnd);
    const after = text.slice(matchEnd);

    return html`${prefix}${before}<mark>${match}</mark>${after}`;
  }

  /**
   * The content of a single result row. Subclasses can override to customize.
   */
  protected renderResultContent(result: T): TemplateResult {
    const badgeStyles: { [key: string]: string } = {
      background: result.color,
      borderColor: result.borderColor || result.color
    };
    if (result.textColor) {
      badgeStyles.color = result.textColor;
    }

    return html`
      <div class="result-type-badge" style=${styleMap(badgeStyles)}>
        ${result.typeName}
      </div>
      <div class="result-text">${this.renderMatchText(result)}</div>
    `;
  }

  /**
   * The message shown when a completed search produced no results. Subclasses
   * can override to explain why the result set came back empty.
   */
  protected getNoResultsMessage(): string {
    return 'No matches found';
  }

  /**
   * The hint shown before any query has been entered.
   */
  protected renderHint(): TemplateResult {
    return html`<div class="hint">
      <kbd>↑</kbd> <kbd>↓</kbd> to navigate &nbsp; <kbd>Enter</kbd> to open
      &nbsp; <kbd>Esc</kbd> to close
    </div>`;
  }

  private renderBody(): TemplateResult {
    if (!this.searchQuery.trim()) {
      return this.renderHint();
    }

    // a failed search leaves the query dirty so Enter retries it, so the
    // failure has to be reported ahead of the "Enter to search" hint
    if (this.error) {
      return html`<div class="no-results">Search failed - try again</div>`;
    }

    if (this.searchOnEnter && this.dirty) {
      return html`<div class="hint"><kbd>Enter</kbd> to search</div>`;
    }

    if (this.loading) {
      return html`<div class="loading">
        <temba-loading units="6" size="8"></temba-loading>
      </div>`;
    }

    if (this.results.length === 0) {
      return html`<div class="no-results">${this.getNoResultsMessage()}</div>`;
    }

    return html`
      <div class="results">
        ${this.results.map(
          (result, index) => html`
            <div
              class="result-item ${index === this.highlightedIndex
                ? 'highlighted'
                : ''}"
              @click=${() => this.selectResult(result)}
              @mouseenter=${() => {
                this.highlightedIndex = index;
              }}
            >
              ${this.renderResultContent(result)}
            </div>
          `
        )}
      </div>
      <div class="result-count">
        ${this.results.length} result${this.results.length !== 1 ? 's' : ''}
      </div>
    `;
  }

  updated(changedProps: Map<string, unknown>): void {
    if (changedProps.has('highlightedIndex')) {
      const highlighted = this.shadowRoot?.querySelector(
        '.result-item.highlighted'
      );
      highlighted?.scrollIntoView({ block: 'nearest' });
    }
  }

  render(): TemplateResult {
    const searchLabel = this.getSearchLabel();

    return html`
      <div class="backdrop" @click=${this.handleBackdropClick}></div>
      <div
        class="search-container"
        role="dialog"
        aria-modal="true"
        aria-label=${searchLabel}
        @click=${(e: Event) => e.stopPropagation()}
      >
        <div class="search-input-row">
          <div class="search-icon">
            <temba-icon name=${Icon.search} size="1.5"></temba-icon>
          </div>
          <input
            type="text"
            placeholder="${searchLabel}..."
            aria-label=${searchLabel}
            .value=${this.searchQuery}
            @input=${this.handleInput}
            @keydown=${this.handleKeyDown}
          />
        </div>
        ${this.renderBody()}
      </div>
    `;
  }
}
