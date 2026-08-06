import { css, html, TemplateResult } from 'lit';
import { property, state } from 'lit/decorators.js';
import { RapidElement } from '../RapidElement';
import { CustomEventType } from '../interfaces';
import { NODE_CONFIG, ACTION_CONFIG } from './config';
import {
  NodeConfig,
  ActionConfig,
  ACTION_GROUPS,
  SPLIT_GROUPS,
  ACTION_GROUP_METADATA,
  SPLIT_GROUP_METADATA
} from './types';

/**
 * Event detail for node type selection
 */
export interface NodeTypeSelection {
  nodeType: string;
  position: { x: number; y: number };
}

/**
 * An item in the node type selector
 */
interface NodeItem {
  type: string;
  config: NodeConfig | ActionConfig;
  branching: boolean;
  color: string;
}

/**
 * Categorizes node types for display
 */
interface NodeCategory {
  name: string;
  description: string;
  color: string;
  items: NodeItem[];
}

/**
 * NodeTypeSelector - A unified dialog for selecting which type of node to create.
 * Shows promoted items (Send Message, Wait for Response) at the top,
 * then categorized actions, then splits.
 */
export class NodeTypeSelector extends RapidElement {
  static get styles() {
    return css`
      :host {
        --dialog-top-offset: clamp(16px, 6vh, 64px);
        --dialog-bottom-offset: clamp(24px, 5vh, 56px);
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        z-index: 10001;
        display: none;
      }

      :host([open]) {
        display: flex;
        align-items: flex-start;
        justify-content: center;
        padding-top: var(--dialog-top-offset);
        box-sizing: border-box;
      }

      .overlay {
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.5);
      }

      .dialog {
        position: relative;
        background: white;
        border-radius: var(--curvature);
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
        max-width: 740px;
        max-height: calc(
          100vh - var(--dialog-top-offset) - var(--dialog-bottom-offset)
        );
        width: 90%;
        display: flex;
        flex-direction: column;
      }

      .header {
        padding: 1.5em;
        border-bottom: 1px solid rgba(0, 0, 0, 0.1);
        background: rgba(0, 0, 0, 0.03);
        border-radius: var(--curvature) var(--curvature) 0 0;
      }

      .search-input {
        width: 100%;
        padding: 0.6em 0.8em;
        border: 1px solid rgba(0, 0, 0, 0.15);
        border-radius: calc(var(--curvature) * 0.75);
        font-size: 1rem;
        outline: none;
        box-sizing: border-box;
      }

      .search-input:focus {
        border-color: var(--color-focus);
        box-shadow: var(--widget-box-shadow-focused);
      }

      .content {
        overflow-y: auto;
        overflow-x: hidden;
        flex: 1;
        min-height: 0;
        padding: 1.5em;
      }

      .promoted-section {
        margin-bottom: 1.5em;
      }

      .category {
        margin-bottom: 2em;
      }

      .category:last-child {
        margin-bottom: 0;
      }

      .category-title {
        font-weight: 600;
        color: var(--color-text-dark);
        margin-bottom: 0.5em;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-size: 0.9rem;
        opacity: 0.7;
      }

      .category-description {
        font-size: 0.85rem;
        color: var(--color-text);
        opacity: 0.6;
        margin-bottom: 0.75em;
        line-height: 1.4;
      }

      .items-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(158px, 1fr));
        gap: 0.75em;
      }

      .node-item {
        padding: 0.5em;
        padding-left: 1em;
        border: 1px solid rgba(0, 0, 0, 0.1);
        border-radius: calc(var(--curvature) * 0.75);
        cursor: pointer;
        transition: all 0.15s ease;
        background: white;
        position: relative;
        overflow: hidden;
      }

      .node-item::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        width: 4px;
        height: 100%;
        background: var(--item-color, rgba(0, 0, 0, 0.1));
      }

      .node-item:hover,
      .node-item.highlighted {
        border-color: var(--item-color, var(--color-primary));
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        transform: translateY(-1px);
      }

      .node-item:hover::before,
      .node-item.highlighted::before {
        width: 6px;
      }

      .node-item-title {
        font-weight: 500;
        font-size: 1rem;
        color: var(--color-text-dark);
        white-space: nowrap;
      }

      .no-results {
        text-align: center;
        padding: 2em;
        color: var(--color-text);
        opacity: 0.6;
      }

      .footer {
        padding: 1em 1.5em;
        border-top: 1px solid rgba(0, 0, 0, 0.1);
        display: flex;
        justify-content: flex-end;
        background: rgba(0, 0, 0, 0.03);
        border-radius: 0 0 var(--curvature) var(--curvature);
      }
    `;
  }

  @property({ type: Boolean, reflect: true })
  public open = false;

  @property({ type: String })
  public mode: 'all' | 'action-no-branching' = 'all';

  @property({ type: String })
  public flowType: string = 'message';

  @property({ type: Array })
  public features: string[] = [];

  @state()
  private clickPosition = { x: 0, y: 0 };

  @state()
  private searchQuery = '';

  @state()
  private highlightedIndex = 0;

  private boundHandleEscape = (e: KeyboardEvent) => {
    if (e.key === 'Escape') {
      this.close();
    }
  };

  public show(
    mode: 'all' | 'action-no-branching',
    position: { x: number; y: number }
  ) {
    this.mode = mode;
    this.clickPosition = position;
    this.searchQuery = '';
    this.highlightedIndex = 0;
    this.open = true;
    document.addEventListener('keydown', this.boundHandleEscape);
    this.updateComplete.then(() => {
      const input = this.shadowRoot?.querySelector(
        '.search-input'
      ) as HTMLInputElement;
      input?.focus();
    });
  }

  public close(fireCanceledEvent: boolean = true) {
    if (this.open) {
      this.open = false;
      document.removeEventListener('keydown', this.boundHandleEscape);
      if (fireCanceledEvent) {
        this.fireCustomEvent(CustomEventType.Canceled, {});
      }
    }
  }

  /**
   * Check if a config is available for the current flow type and features
   */
  private isConfigAvailable(config: NodeConfig | ActionConfig): boolean {
    // Check flow type filter
    if (config.flowTypes !== undefined) {
      // Empty array means not available for any flow type in selector
      if (config.flowTypes.length === 0) {
        return false;
      }
      // Non-empty array means check if current flow type is included
      if (!config.flowTypes.includes(this.flowType as any)) {
        return false;
      }
    }
    // undefined/null flowTypes means available for all flow types

    // Check features filter - all required features must be present
    if (config.features && config.features.length > 0) {
      for (const requiredFeature of config.features) {
        if (!this.features.includes(requiredFeature)) {
          return false;
        }
      }
    }

    return true;
  }

  private handleNodeTypeClick(nodeType: string) {
    this.fireCustomEvent(CustomEventType.Selection, {
      nodeType,
      position: this.clickPosition
    } as NodeTypeSelection);
    // Close without firing canceled event since we made a selection
    this.close(false);
  }

  private handleOverlayClick() {
    this.close();
  }

  private handleSearchInput(e: InputEvent) {
    this.searchQuery = (e.target as HTMLInputElement).value;
    this.highlightedIndex = 0;
  }

  private handleKeyDown(e: KeyboardEvent) {
    if (e.key === 'Enter') {
      const allVisible = this.getVisibleItems();
      if (allVisible.length > 0) {
        const idx = Math.min(this.highlightedIndex, allVisible.length - 1);
        this.handleNodeTypeClick(allVisible[idx].type);
      }
    } else if (e.key === 'ArrowDown' || (e.key === 'n' && e.ctrlKey)) {
      e.preventDefault();
      const allVisible = this.getVisibleItems();
      if (allVisible.length > 0) {
        this.highlightedIndex = (this.highlightedIndex + 1) % allVisible.length;
      }
    } else if (e.key === 'ArrowUp' || (e.key === 'p' && e.ctrlKey)) {
      e.preventDefault();
      const allVisible = this.getVisibleItems();
      if (allVisible.length > 0) {
        this.highlightedIndex =
          (this.highlightedIndex - 1 + allVisible.length) % allVisible.length;
      }
    } else if (e.key === 'Escape') {
      this.close();
    }
  }

  /**
   * Get promoted items shown at the top of the selector
   */
  private getPromotedItems(): NodeItem[] {
    const items: NodeItem[] = [];

    const sendMsgConfig = ACTION_CONFIG['send_msg'];
    if (sendMsgConfig && this.isConfigAvailable(sendMsgConfig)) {
      items.push({
        type: 'send_msg',
        config: sendMsgConfig,
        branching: false,
        color: ACTION_GROUP_METADATA[sendMsgConfig.group].color
      });
    }

    const waitConfig = NODE_CONFIG['wait_for_response'];
    if (waitConfig && this.isConfigAvailable(waitConfig)) {
      items.push({
        type: 'wait_for_response',
        config: waitConfig,
        branching: true,
        color: SPLIT_GROUP_METADATA[SPLIT_GROUPS.wait].color
      });
    }

    return items;
  }

  /**
   * Get categorized items: action groups followed by split groups
   */
  private getCategories(): NodeCategory[] {
    const categories: NodeCategory[] = [];
    const noBranching = this.mode === 'action-no-branching';

    // --- Action categories ---
    const actionsByGroup = new Map<string, NodeItem[]>();

    // Regular actions (excluding hideFromActions)
    Object.entries(ACTION_CONFIG)
      .filter(([type, config]) => {
        const isAlias = config.aliases && config.aliases.includes(type);
        return (
          !isAlias &&
          config.name &&
          !config.hideFromActions &&
          config.group &&
          this.isConfigAvailable(config)
        );
      })
      .forEach(([type, config]) => {
        const metadata = ACTION_GROUP_METADATA[config.group];
        if (!actionsByGroup.has(config.group))
          actionsByGroup.set(config.group, []);
        actionsByGroup
          .get(config.group)!
          .push({ type, config, branching: false, color: metadata.color });
      });

    // Nodes with showAsAction mixed into their action groups
    if (!noBranching) {
      Object.entries(NODE_CONFIG)
        .filter(([type, config]) => {
          return (
            type !== 'execute_actions' &&
            type === config.type &&
            config.name &&
            config.showAsAction &&
            config.group &&
            this.isConfigAvailable(config)
          );
        })
        .forEach(([type, config]) => {
          const group = config.group!;
          const metadata =
            ACTION_GROUP_METADATA[group] || SPLIT_GROUP_METADATA[group];
          if (!actionsByGroup.has(group)) actionsByGroup.set(group, []);
          actionsByGroup
            .get(group)!
            .push({ type, config, branching: true, color: metadata.color });
        });
    }

    const actionGroupOrder = Object.keys(ACTION_GROUPS);
    const actionConfigOrder = Object.keys(ACTION_CONFIG);
    const nodeConfigOrder = Object.keys(NODE_CONFIG);

    Array.from(actionsByGroup.entries())
      .sort(([a], [b]) => {
        const oa = actionGroupOrder.indexOf(a);
        const ob = actionGroupOrder.indexOf(b);
        return (oa === -1 ? 999 : oa) - (ob === -1 ? 999 : ob);
      })
      .forEach(([group, items]) => {
        // Sort: actions by ACTION_CONFIG order, then nodes by NODE_CONFIG order
        const sortedItems = items.sort((a, b) => {
          const oaA = actionConfigOrder.indexOf(a.type);
          const obA = actionConfigOrder.indexOf(b.type);
          const oaN = nodeConfigOrder.indexOf(a.type);
          const obN = nodeConfigOrder.indexOf(b.type);
          const oa = oaA !== -1 ? oaA : oaN !== -1 ? 1000 + oaN : 2000;
          const ob = obA !== -1 ? obA : obN !== -1 ? 1000 + obN : 2000;
          return oa - ob;
        });
        const metadata = ACTION_GROUP_METADATA[group];
        categories.push({
          name: metadata.title,
          description: metadata.description,
          color: metadata.color,
          items: sortedItems
        });
      });

    // --- Split categories (only in 'all' mode) ---
    if (!noBranching) {
      const splitsByGroup = new Map<string, NodeItem[]>();

      Object.entries(NODE_CONFIG)
        .filter(([type, config]) => {
          return (
            type !== 'execute_actions' &&
            type === config.type &&
            config.name &&
            !config.showAsAction &&
            !config.hideFromSplits &&
            type !== 'wait_for_response' &&
            this.isConfigAvailable(config)
          );
        })
        .forEach(([type, config]) => {
          const group = config.group || SPLIT_GROUPS.split;
          const metadata =
            SPLIT_GROUP_METADATA[group] || ACTION_GROUP_METADATA[group];
          if (!splitsByGroup.has(group)) splitsByGroup.set(group, []);
          splitsByGroup
            .get(group)!
            .push({ type, config, branching: true, color: metadata.color });
        });

      const splitGroupOrder = Object.keys(SPLIT_GROUPS);

      Array.from(splitsByGroup.entries())
        .sort(([a], [b]) => {
          const oa = splitGroupOrder.indexOf(a);
          const ob = splitGroupOrder.indexOf(b);
          return (oa === -1 ? 999 : oa) - (ob === -1 ? 999 : ob);
        })
        .forEach(([group, items]) => {
          const sortedItems = items.sort((a, b) => {
            const oa = nodeConfigOrder.indexOf(a.type);
            const ob = nodeConfigOrder.indexOf(b.type);
            return (oa === -1 ? 999 : oa) - (ob === -1 ? 999 : ob);
          });
          const metadata =
            SPLIT_GROUP_METADATA[group] || ACTION_GROUP_METADATA[group];
          categories.push({
            name: metadata.title,
            description: metadata.description,
            color: metadata.color,
            items: sortedItems
          });
        });
    }

    return categories;
  }

  private filterBySearch(items: NodeItem[]): NodeItem[] {
    if (!this.searchQuery) return items;
    const query = this.searchQuery.toLowerCase();
    return items.filter((item) =>
      item.config.name?.toLowerCase().includes(query)
    );
  }

  /**
   * Get all visible items in order (promoted + categories), after filtering
   */
  private getVisibleItems(): NodeItem[] {
    const promotedItems = this.getPromotedItems();
    const categories = this.getCategories();
    const noBranching = this.mode === 'action-no-branching';

    const filteredPromoted = this.filterBySearch(
      noBranching ? promotedItems.filter((i) => !i.branching) : promotedItems
    );
    const filteredCategories = categories
      .map((cat) => ({ ...cat, items: this.filterBySearch(cat.items) }))
      .filter((cat) => cat.items.length > 0);

    return [
      ...filteredPromoted,
      ...filteredCategories.flatMap((cat) => cat.items)
    ];
  }

  private renderItem(item: NodeItem, index: number): TemplateResult {
    return html`
      <div
        class="node-item ${item.branching ? 'branching' : ''} ${index ===
        this.highlightedIndex
          ? 'highlighted'
          : ''}"
        style="--item-color: ${item.color}"
        @click=${() => this.handleNodeTypeClick(item.type)}
      >
        <div class="node-item-title">${item.config.name}</div>
      </div>
    `;
  }

  public render(): TemplateResult {
    if (!this.open) {
      return html``;
    }

    const promotedItems = this.getPromotedItems();
    const categories = this.getCategories();
    const noBranching = this.mode === 'action-no-branching';

    // Apply search and branching filters
    const filteredPromoted = this.filterBySearch(
      noBranching ? promotedItems.filter((i) => !i.branching) : promotedItems
    );
    const filteredCategories = categories
      .map((cat) => ({ ...cat, items: this.filterBySearch(cat.items) }))
      .filter((cat) => cat.items.length > 0);

    // Build a running index for highlight tracking
    let itemIndex = 0;

    const hasResults =
      filteredPromoted.length > 0 || filteredCategories.length > 0;

    return html`
      <div class="overlay" @click=${this.handleOverlayClick}></div>
      <div class="dialog" @click=${(e: Event) => e.stopPropagation()}>
        <div class="header">
          <input
            class="search-input"
            type="text"
            placeholder="Search..."
            .value=${this.searchQuery}
            @input=${this.handleSearchInput}
            @keydown=${this.handleKeyDown}
          />
        </div>
        <div class="content">
          ${filteredPromoted.length > 0
            ? html`
                <div class="promoted-section">
                  <div class="items-grid">
                    ${filteredPromoted.map((item) =>
                      this.renderItem(item, itemIndex++)
                    )}
                  </div>
                </div>
              `
            : ''}
          ${filteredCategories.map(
            (category) => html`
              <div class="category">
                <div class="category-title">${category.name}</div>
                <div class="category-description">${category.description}</div>
                <div class="items-grid">
                  ${category.items.map((item) =>
                    this.renderItem(item, itemIndex++)
                  )}
                </div>
              </div>
            `
          )}
          ${!hasResults
            ? html`<div class="no-results">No matching items found</div>`
            : ''}
        </div>
        <div class="footer">
          <temba-button
            name="Cancel"
            @click=${this.close}
            secondary
          ></temba-button>
        </div>
      </div>
    `;
  }
}
