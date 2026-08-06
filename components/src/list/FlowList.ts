import { css, html, TemplateResult } from 'lit';
import { ContentList, ContentListColumn } from './ContentList';
import { Icon } from '../Icons';
import { CustomEventType, Flow, ObjectReference } from '../interfaces';
import { getStore, StoreAsset, StoreAssetChangedEvent } from '../store/Store';
import { RealtimeSubscription } from '../live/Realtime';

/**
 * Flow CRUDL list — drop-in replacement for the rapidpro
 * `flows/flow_list.html` table. Rows of the unusual flow types
 * (voice / background / surveyor) carry a leading type icon;
 * message flows don't. Columns: name, runs, ongoing, completion
 * bar, activity sparkline.
 */
export class FlowList extends ContentList<Flow> {
  private assetWatch: RealtimeSubscription = null;

  static get styles() {
    return css`
      ${ContentList.styles}
      /* The name cell is a flex row (name text, issue icon, label
         chips) that fills the grow column. When space runs out the
         text spans ellipsize — the flex items shrink instead of the
         cell hard-clipping them mid-glyph, which is what happens to
         an inline-flex atomic inline under .cell-inner's ellipsis. */
      .flow-name {
        color: inherit;
        font-weight: var(--w-medium);
        display: flex;
        align-items: center;
        gap: 6px;
        min-width: 0;
      }
      .flow-name .name {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .flow-labels {
        display: flex;
        align-items: center;
        gap: 4px;
        min-width: 0;
      }
      /* Chips shrink with the row and ellipsize internally (the
         label's own slot handles that) rather than being clipped
         mid-chip at the column edge. */
      .flow-labels temba-label {
        min-width: 0;
      }
      .issue-icon {
        flex: none;
        --icon-color: var(--warning);
      }
      .num {
        font-variant-numeric: tabular-nums;
        color: inherit;
      }
      .completion-bar {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        justify-content: flex-end;
      }
      .completion-bar .bar {
        width: 50px;
        height: 6px;
        border-radius: 999px;
        background: var(--sunken);
        overflow: hidden;
      }
      .completion-bar .fill {
        height: 100%;
        background: var(--success);
        border-radius: 999px;
      }
      .completion-bar .pct {
        font-variant-numeric: tabular-nums;
        color: var(--text-2);
        min-width: 36px;
        text-align: right;
      }
      .sparkline {
        display: inline-block;
        vertical-align: middle;
      }
      .sparkline .line {
        fill: none;
        stroke: var(--accent-600);
        stroke-width: 1.25;
        stroke-linejoin: round;
        stroke-linecap: round;
      }
      .sparkline .area {
        fill: var(--accent-100);
        opacity: 0.7;
      }
    `;
  }

  constructor() {
    super();
    this.valueKey = 'uuid';
    this.emptyMessage = 'No flows';
    this.searchPlaceholder = 'Search flows';
    // The name column is a `grow` column — it pools the table's
    // leftover width so long names (and their label chips) get all
    // available space before truncating, instead of clipping against
    // a fixed cap while slack sits in the spacer. minTableWidth arms
    // a horizontal scroll once the container is too narrow to keep
    // the columns usable, rather than clipping anything.
    this.minTableWidth = '640px';
    this.columns = [
      {
        key: 'name',
        label: 'Name',
        sortable: true,
        minWidth: '160px',
        grow: true,
        pinned: true
      },
      {
        key: 'runs',
        label: 'Runs',
        sortable: true,
        minWidth: '64px',
        align: 'right'
      },
      {
        key: 'ongoing',
        label: 'Ongoing',
        sortable: true,
        minWidth: '64px',
        align: 'right'
      },
      {
        key: 'completion',
        label: 'Completion',
        minWidth: '110px',
        align: 'right'
      },
      { key: 'activity', label: 'Activity', width: '120px', align: 'right' }
    ];
    this.bulkActions = [
      {
        key: 'label',
        label: 'Label',
        icon: Icon.label,
        labelsEndpoint: '/api/v2/flow-labels.json'
      },
      { key: 'export', label: 'Export results', icon: Icon.export },
      { key: 'archive', label: 'Archive', icon: Icon.archive }
    ];
  }

  public connectedCallback(): void {
    super.connectedCallback();
    // rows we already have (if any) - each load re-syncs from prepareItems
    this.syncAssetWatch();
  }

  public disconnectedCallback(): void {
    super.disconnectedCallback();
    if (this.assetWatch) {
      this.assetWatch.unsubscribe();
      this.assetWatch = null;
    }
  }

  private syncAssetWatch(): void {
    if (!this.isConnected) {
      return;
    }
    const store = getStore();
    if (!store) {
      return;
    }
    if (this.assetWatch) {
      this.assetWatch.unsubscribe();
    }
    this.assetWatch = store.watchAssets(
      (this.items || []).map((flow) => ({ type: 'flow', uuid: flow.uuid })),
      (event: StoreAssetChangedEvent | null) => this.syncFlowNames(event?.asset)
    );
  }

  private syncFlowNames(changed?: StoreAsset): void {
    const items = this.withCanonicalFlowNames(this.items, changed);
    if (items !== this.items) {
      this.items = items;
    }
  }

  /**
   * A freshly fetched page is authoritative, so it seeds the store cache
   * rather than being overwritten by it - a cached name can predate this
   * response (e.g. a rename missed while another page was on screen), and
   * writing it back would make the stale name self-reinforcing. Cached names
   * only ever move rows through syncFlowNames, driven by socket changes and
   * the reconnect refresh, which are the paths that are actually newer.
   */
  protected prepareItems(items: Flow[]): Flow[] {
    getStore()?.cacheAssets(
      items
        .filter((item) => !!item.uuid && typeof item.name === 'string')
        .map((item) => ({
          type: 'flow',
          uuid: item.uuid,
          name: item.name
        }))
    );
    Promise.resolve().then(() => this.syncAssetWatch());
    return items;
  }

  private withCanonicalFlowNames(items: Flow[], changed?: StoreAsset): Flow[] {
    const store = getStore();
    let updated = false;
    const canonical = items.map((item) => {
      const asset = changed
        ? changed.uuid === item.uuid
          ? changed
          : null
        : store?.getAsset('flow', item.uuid);
      if (asset && asset.name !== item.name) {
        updated = true;
        return { ...item, name: asset.name };
      }
      return item;
    });
    return updated ? canonical : items;
  }

  protected getRowIcon(item: Flow): string | null {
    switch (item?.type) {
      case 'voice':
      case 'ivr':
        return Icon.flow_ivr;
      case 'background':
        return Icon.flow_background;
      case 'survey':
        return Icon.flow_surveyor;
      default:
        // message flows are the common case and carry no icon — only
        // the unusual types get flagged, matching the legacy table
        return null;
    }
  }

  protected getRowHref(item: Flow): string | null {
    return item?.uuid ? `/flow/editor/${item.uuid}/` : null;
  }

  /** Clicking a label chip opens that label's filtered flow list rather
   * than falling through to the row click (which opens the flow editor). */
  private handleLabelClick(label: ObjectReference, event: MouseEvent): void {
    // Stop the click from bubbling to the row's navigation handler.
    event.stopPropagation();
    if (!label?.uuid) return;
    const href = `/flow/filter/${label.uuid}/`;
    // Guard the JSON-driven href against open-redirect, same as the
    // row-click path in ContentList.handleRowClick.
    if (!this.isSafeHref(href)) return;
    // Meta/ctrl-click opens a new tab, matching ordinary links and the
    // row-click behavior.
    if (event.metaKey || event.ctrlKey) {
      window.open(href, '_blank');
      return;
    }
    this.fireCustomEvent(CustomEventType.Redirected, { url: href });
  }

  protected renderCell(
    item: Flow,
    column: ContentListColumn
  ): TemplateResult | string {
    switch (column.key) {
      case 'name': {
        const labels = item.labels || [];
        return html`<span class="flow-name"
          ><span class="name" title="${item.name || ''}"
            >${item.name || ''}</span
          >
          ${item.has_issues
            ? html`<temba-icon
                class="issue-icon"
                name=${Icon.issue}
                size="0.9"
              ></temba-icon>`
            : null}
          ${labels.length > 0
            ? html`<span class="flow-labels">
                ${labels.map(
                  (l: ObjectReference) =>
                    html`<temba-label
                      type="label"
                      icon=${Icon.label}
                      clickable
                      @click=${(e: MouseEvent) => this.handleLabelClick(l, e)}
                      >${l.name}</temba-label
                    >`
                )}
              </span>`
            : null}
        </span>`;
      }
      case 'runs':
        return html`<span class="num"
          >${(item.runs ?? 0).toLocaleString()}</span
        >`;
      case 'ongoing':
        return html`<span class="num">${item.ongoing ?? 0}</span>`;
      case 'completion':
        return this.renderCompletion(item);
      case 'activity':
        return this.renderSparkline(item.activity || []);
      default:
        return super.renderCell(item, column);
    }
  }

  private renderCompletion(item: Flow): TemplateResult {
    const value = typeof item.completion === 'number' ? item.completion : 0;
    const pct = Math.round(value * 100);
    return html`
      <div class="completion-bar">
        <div class="bar">
          <div class="fill" style="width: ${pct}%"></div>
        </div>
        <span class="pct">${pct}%</span>
      </div>
    `;
  }

  /** Render a tiny line+area sparkline from a numeric array.
   * Values are normalized to the column's pixel viewBox; absolute
   * magnitude isn't preserved — the goal is shape, not scale. */
  private renderSparkline(values: number[]): TemplateResult {
    if (!values || values.length < 2) return html``;
    const w = 90;
    const h = 22;
    const max = Math.max(...values, 1);
    const step = w / (values.length - 1);
    const pts = values.map((v, i) => {
      const x = i * step;
      const y = h - (v / max) * (h - 2) - 1;
      return [x.toFixed(1), y.toFixed(1)] as const;
    });
    const line = pts.map(([x, y]) => `${x},${y}`).join(' ');
    const areaCmds = pts
      .map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x},${y}`)
      .join(' ');
    const area = `${areaCmds} L${w},${h} L0,${h} Z`;
    return html`
      <svg
        class="sparkline"
        width=${w}
        height=${h}
        viewBox="0 0 ${w} ${h}"
        preserveAspectRatio="none"
      >
        <path class="area" d=${area}></path>
        <polyline class="line" points=${line}></polyline>
      </svg>
    `;
  }
}
