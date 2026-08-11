import { css, html, PropertyValues, TemplateResult } from 'lit';
import { property, state } from 'lit/decorators.js';
import { Icon } from '../Icons';
import { Article } from '../interfaces';
import { postJSON } from '../utils';
import { ContentList, ContentListColumn } from './ContentList';

/** Pixels of indent per level of nesting. Also the horizontal travel a
 * drag needs to change the level it would land at, and the spacing of
 * the guide rails - all three are the same measure, so a row always
 * lands where its rail says it will. */
export const INDENT = 20;

/** How long a branch takes to fold open or shut. The removal of a
 * folded branch's rows waits on this, so the fold is seen to finish. */
export const FOLD_MS = 200;

/** An article annotated for display. The endpoint hands back the tree
 * already flattened into display order, and everything below is
 * derived from that order rather than from the parent links. */
export interface ArticleRow extends Article {
  /** Deepest descendant's depth relative to ours - 0 for a leaf. Taken
   * over the whole tree rather than the visible rows, so a collapsed
   * branch still counts against the depth cap when it's dragged. */
  height: number;
}

/** One entry of the ordering posted to the sort endpoint. */
export interface ArticleOrder {
  uuid: string;
  parent: string | null;
  sort_order: number;
}

/**
 * Annotates a flattened tree with each row's subtree height. Rows are
 * in depth-first order, so an article's descendants are exactly the
 * rows that follow it until one at its own depth or shallower.
 */
export function annotateTree(articles: Article[]): ArticleRow[] {
  return articles.map((article, index) => {
    const depth = article.depth || 0;
    let height = 0;
    for (
      let i = index + 1;
      i < articles.length && (articles[i].depth || 0) > depth;
      i++
    ) {
      height = Math.max(height, (articles[i].depth || 0) - depth);
    }
    return { ...article, depth, height };
  });
}

/** The rows a collapsed tree actually shows - everything except the
 * descendants of a collapsed article. */
export function visibleRows(
  rows: ArticleRow[],
  collapsed: Set<string>
): ArticleRow[] {
  const visible: ArticleRow[] = [];
  let hidingBelow = -1; // depth of the collapsed row we're inside, -1 when we aren't

  for (const row of rows) {
    if (hidingBelow >= 0 && row.depth > hidingBelow) {
      continue;
    }
    hidingBelow = collapsed.has(row.uuid) && row.height > 0 ? row.depth : -1;
    visible.push(row);
  }

  return visible;
}

/**
 * Moves the article at `from`, with its subtree, to flat position
 * `dropIndex` at `wantedDepth`, and returns the resulting order.
 * Returns null when the move isn't one that can be made - a subtree
 * can't be dropped inside itself.
 *
 * Nothing here is authoritative: the resulting order is posted whole
 * and the server re-derives the tree from it, rejecting cycles and
 * anything nested past the cap. The clamping is so that what the user
 * sees while dragging is what they'll get, not a validation step.
 */
export function moveSubtree(
  rows: ArticleRow[],
  from: number,
  dropIndex: number,
  wantedDepth: number,
  maxDepth: number
): ArticleRow[] | null {
  const dragged = rows[from];
  if (!dragged) {
    return null;
  }

  // the rows travelling with the drag: the dragged row and those below it that are deeper
  let size = 1;
  while (from + size < rows.length && rows[from + size].depth > dragged.depth) {
    size++;
  }

  if (dropIndex > from && dropIndex < from + size) {
    return null;
  }

  const moving = rows.slice(from, from + size);
  const rest = [...rows.slice(0, from), ...rows.slice(from + size)];
  const insertAt = dropIndex > from ? dropIndex - size : dropIndex;

  // the row we'd land under bounds how deep we can be - at most one level below it. Our descendants move by the same
  // delta we do, so the cap has to leave room for the tallest of them as well as for us.
  const above = rest[insertAt - 1];
  const depth = Math.max(
    0,
    Math.min(
      wantedDepth,
      above ? above.depth + 1 : 0,
      maxDepth - 1 - dragged.height
    )
  );

  const delta = depth - dragged.depth;
  const moved = moving.map((row) => ({ ...row, depth: row.depth + delta }));
  const result = [
    ...rest.slice(0, insertAt),
    ...moved,
    ...rest.slice(insertAt)
  ];

  // a gap would leave a row naming an ancestor that isn't above it, so depths are clamped to one more than the row
  // before - which is also how the parent of each row is read back out in toOrder
  let previous = -1;
  return result.map((row) => {
    const clamped = Math.min(row.depth, previous + 1);
    previous = clamped;
    return row.depth === clamped ? row : { ...row, depth: clamped };
  });
}

/**
 * Reads a flat order back out as the (uuid, parent, sort_order) triples
 * the server validates. A row's parent is the nearest row above it one
 * level shallower.
 *
 * Only the rows given are described, which is what lets a collapsed
 * branch be dragged without being listed: the server starts from the
 * tree as it stands, so a hidden article keeps the parent it already
 * has - and therefore travels with it.
 */
export function toOrder(rows: ArticleRow[]): ArticleOrder[] {
  const ancestors: string[] = [];

  return rows.map((row, index) => {
    ancestors[row.depth] = row.uuid;
    return {
      uuid: row.uuid,
      parent: row.depth > 0 ? ancestors[row.depth - 1] : null,
      sort_order: index
    };
  });
}

/**
 * The helpdesk's article tree. Unlike the other content lists this one
 * is a hierarchy rather than a flat page of rows: articles arrive
 * already flattened into display order and are rendered with an indent,
 * a guide rail per level of nesting and a disclosure chevron on
 * anything with children.
 *
 * Rows are dragged by their handle to reorder and reparent them, and
 * the whole resulting order is posted to `sort-endpoint`. The tree the
 * client builds is never trusted - the server re-derives it.
 */
export class ArticleList extends ContentList<ArticleRow> {
  static get styles() {
    return css`
      ${ContentList.styles}

      :host {
        /* the drop marker is positioned against the list */
        position: relative;
      }

      /* The guide rails bleed a pixel past the row border so they read
         as continuous lines, which the cell wrapper would otherwise
         clip - so every cell in this list truncates its own content
         instead of relying on the wrapper to do it. */
      .cell-inner {
        overflow: visible;
      }

      .tree-cell {
        align-items: center;
        display: flex;
        gap: 6px;
        min-height: 38px;
        position: relative;
      }

      /* one muted vertical line per level of ancestry, centered under
         the chevron of the level it belongs to */
      .rail {
        border-left: 1px solid var(--border);
        bottom: -1px;
        position: absolute;
        top: 0;
        width: 0;
      }

      .disclosure {
        align-items: center;
        border-radius: var(--r-sm);
        color: var(--text-3);
        cursor: pointer;
        display: inline-flex;
        flex: 0 0 16px;
        height: 16px;
        justify-content: center;
        width: 16px;
      }

      .disclosure temba-icon {
        --icon-color: currentColor;
      }

      .disclosure:hover {
        background: var(--sunken);
        color: var(--text-1);
      }

      .title {
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      /* an article with children reads as a heading for the ones under it */
      .title.branch {
        font-weight: var(--w-medium);
      }

      /* faint at rest so the column doesn't read as empty, and solid
         under the pointer that's about to use it */
      .drag-handle {
        --icon-color: var(--text-3);
        cursor: grab;
        opacity: 0.35;
      }

      tr.row:hover .drag-handle {
        opacity: 1;
      }

      /* the dragged row stays in place, dimmed, until the drop lands */
      tr.row:has(.tree-cell.dragging) {
        opacity: 0.4;
      }

      /* a control rather than text, so it centers on the row instead of sitting on the text baseline */
      .publish {
        vertical-align: middle;
      }

      /* where the dragged row would land, indented to the level it
         would land at */
      .drop-marker {
        background: var(--accent-400);
        height: 2px;
        pointer-events: none;
        position: absolute;
        z-index: 10;
      }

      /* Folding a branch open or shut. The branch has to move as one
         block - as if a single container around it were collapsing and
         its clip edge swept up through the rows - but the rows are
         table rows with no such container to animate. So each row
         plays its own slice of the fold instead: the block's height
         collapses bottom row first (and grows back top row first), one
         row per slice, which is exactly the order a container's clip
         edge would cross them. getRowStyle deals each row its delay
         and duration; the timing is linear because the slices tile the
         fold end to end - an eased slice would read as a stutter.

         Each cell clips its content while its height plays, and the
         row's height has to follow for the rows below to ride up with
         the fold rather than jump when it lands. Two things on the
         cells would otherwise hold that height: the base list's fixed
         38px cell height - a floor, in table layout - is lifted while
         the row is mid-fold, and the row divider, a cell border that
         keeps its pixel even over no content at all, plays the same
         slice down to zero width. The cells carry no vertical padding,
         so with those gone the row really does start and end at
         nothing. The rails bleed outside the row, so they're clipped
         only while the fold is in flight. */
      tr.row.entering td,
      tr.row.leaving td {
        height: 0;
      }

      tr.row.entering td {
        animation: divider-open var(--fold-duration) linear var(--fold-delay)
          backwards;
      }

      tr.row.leaving td {
        animation: divider-shut var(--fold-duration) linear var(--fold-delay)
          both;
      }

      @keyframes divider-open {
        from {
          border-bottom-width: 0;
        }
      }

      @keyframes divider-shut {
        to {
          border-bottom-width: 0;
        }
      }

      tr.row.entering .cell-inner {
        animation: fold-open var(--fold-duration) linear var(--fold-delay)
          backwards;
        overflow: hidden;
      }

      tr.row.leaving .cell-inner {
        animation: fold-shut var(--fold-duration) linear var(--fold-delay) both;
        overflow: hidden;
      }

      @keyframes fold-open {
        from {
          max-height: 0;
          opacity: 0;
        }
        to {
          max-height: 38px;
          opacity: 1;
        }
      }

      @keyframes fold-shut {
        from {
          max-height: 38px;
          opacity: 1;
        }
        to {
          max-height: 0;
          opacity: 0;
        }
      }

      @media (prefers-reduced-motion: reduce) {
        tr.row.entering td,
        tr.row.leaving td,
        tr.row.entering .cell-inner,
        tr.row.leaving .cell-inner {
          animation: none;
        }
      }
    `;
  }

  /** Endpoint the reordered tree is posted to. Drag is only offered
   * when this is set, so a viewer without the permission simply can't
   * start one. */
  @property({ type: String, attribute: 'sort-endpoint' })
  sortEndpoint = '';

  /** How deep the helpdesk allows articles to nest, mirroring the
   * server's cap so a drag can't aim somewhere the server would then
   * reject. */
  @property({ type: Number, attribute: 'max-depth' })
  maxDepth = 3;

  /** Endpoint a row's publish switch posts `{uuid, status}` to. Like
   * the sort endpoint, the switch is only offered when this is set, so
   * a viewer without the permission simply doesn't get one. */
  @property({ type: String, attribute: 'publish-endpoint' })
  publishEndpoint = '';

  /** The whole tree, including the rows a collapsed branch hides. */
  @state()
  private tree: ArticleRow[] = [];

  @state()
  private collapsed: Set<string> = new Set();

  /** The rows of a branch mid-fold: entering plays them open, leaving
   * plays them shut before they go. */
  @state()
  private entering: Set<string> = new Set();

  @state()
  private leaving: Set<string> = new Set();

  /** Each mid-fold row's position within the folding block, top first.
   * The fold plays one row per slice of FOLD_MS - see the styles - and
   * this is what deals each row its slice. */
  private foldIndex: Map<string, number> = new Map();

  private foldTimeout: number = null;

  @state()
  private dragUuid = '';

  /** Where the marker sits while dragging, in pixels from the list's
   * top left. -1 marks a drag that currently has nowhere to land. */
  @state()
  private dropTop = -1;

  @state()
  private dropLeft = 0;

  /** The order a drop would produce, recomputed as the pointer moves so
   * the marker and the eventual post can never disagree. */
  private preview: ArticleRow[] = null;

  private dragStartX = 0;
  private clickBlocker: (event: MouseEvent) => void = null;

  constructor() {
    super();
    this.valueKey = 'uuid';
    this.emptyMessage = 'No articles';
    // the tree is the order, so there's nothing to sort or search by
    this.searchable = false;
    this.selectable = false;
    this.columns = this.buildColumns();
  }

  private buildColumns(): ContentListColumn[] {
    const columns: ContentListColumn[] = [];

    // the drag column is an affordance rather than data, so it heads up blank
    if (this.sortEndpoint) {
      columns.push({ key: 'drag', label: '', width: '28px' });
    }

    columns.push({
      key: 'title',
      label: 'Article',
      minWidth: '200px',
      grow: true
    });

    // The switch says what the status is as well as changing it, so a reader of a row shouldn't have to take in both
    // it and a pill saying the same thing. Without the permission to publish there's no switch, and then the pill is
    // the only thing left that can say.
    if (!this.publishEndpoint) {
      columns.push({ key: 'status', label: 'Status', width: '100px' });
    }

    columns.push({
      key: 'modified_on',
      label: 'Updated',
      width: '130px',
      align: 'right'
    });

    if (this.publishEndpoint) {
      columns.push({
        key: 'publish',
        label: 'Published',
        width: '96px',
        align: 'right'
      });
    }

    return columns;
  }

  protected willUpdate(changes: PropertyValues): void {
    // rebuilt before the base class runs so its width bookkeeping sees the columns this render will use
    if (changes.has('sortEndpoint') || changes.has('publishEndpoint')) {
      this.columns = this.buildColumns();
    }
    super.willUpdate(changes);
  }

  public disconnectedCallback(): void {
    this.endDrag();
    window.clearTimeout(this.foldTimeout);
    super.disconnectedCallback();
  }

  protected prepareItems(items: ArticleRow[]): ArticleRow[] {
    this.tree = annotateTree(items);

    // an article that's gone shouldn't hold a collapsed branch open forever
    const present = new Set(this.tree.map((row) => row.uuid));
    this.collapsed = new Set(
      [...this.collapsed].filter((uuid) => present.has(uuid))
    );

    // fresh data is the tree as it stands, so any fold in flight is over
    window.clearTimeout(this.foldTimeout);
    this.entering = new Set();
    this.leaving = new Set();
    this.foldIndex = new Map();

    return visibleRows(this.tree, this.collapsed);
  }

  /** An article has no page of its own to link to - it's opened by the
   * host from the row-click event, in a dialog over the list. */
  protected getRowHref(): string | null {
    return null;
  }

  protected getRowClass(item: ArticleRow): string {
    if (this.entering.has(item.uuid)) {
      return 'entering';
    }
    if (this.leaving.has(item.uuid)) {
      return 'leaving';
    }
    return '';
  }

  /** A mid-fold row's slice of the fold: FOLD_MS divided evenly over
   * the block, played top-down opening and bottom-up closing, so the
   * block's edge sweeps through the rows the way a single collapsing
   * container's clip edge would. */
  protected getRowStyle(item: ArticleRow): string {
    const index = this.foldIndex.get(item.uuid);
    if (index === undefined) {
      return '';
    }

    const slice = FOLD_MS / this.foldIndex.size;
    const place = this.entering.has(item.uuid)
      ? index
      : this.foldIndex.size - 1 - index;
    return `--fold-delay: ${place * slice}ms; --fold-duration: ${slice}ms`;
  }

  protected isRowClickable(): boolean {
    return true;
  }

  /**
   * Puts an article in or out of the agents' reach. Shown straight away and then reconciled against the server's
   * tree either way, the same as a reorder - it's the authority on what the status is, and a rejected change has to
   * snap back rather than leave the row lying about it.
   */
  private handlePublishChanged(row: ArticleRow, event: Event): void {
    // the switch is a control on the row rather than part of it, so using one isn't opening the article
    event.stopPropagation();

    const status = (event.target as any).checked ? 'published' : 'draft';

    this.items = this.items.map((item) =>
      item.uuid === row.uuid ? { ...item, status } : item
    );

    postJSON(this.publishEndpoint, { uuid: row.uuid, status })
      .catch((error) => {
        console.warn('Failed to change article status', error);
      })
      .finally(() => this.refresh());
  }

  private toggleCollapsed(row: ArticleRow, event: Event): void {
    // folding a branch isn't opening the article
    event.stopPropagation();

    // a fold started mid-fold takes over from the one in flight
    window.clearTimeout(this.foldTimeout);

    const collapsed = new Set(this.collapsed);
    const opening = collapsed.has(row.uuid);
    if (opening) {
      collapsed.delete(row.uuid);
    } else {
      collapsed.add(row.uuid);
    }

    this.collapsed = collapsed;

    const after = visibleRows(this.tree, collapsed);

    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) {
      this.entering = new Set();
      this.leaving = new Set();
      this.foldIndex = new Map();
      this.items = after;
      return;
    }

    // the rows only one side of the fold shows are the ones that play
    // it, in display order so each knows its place in the block
    const other = new Set((opening ? this.items : after).map((r) => r.uuid));
    const folding = (opening ? after : this.items).filter(
      (r) => !other.has(r.uuid)
    );

    this.foldIndex = new Map(folding.map((r, index) => [r.uuid, index]));

    if (opening) {
      this.entering = new Set(this.foldIndex.keys());
      this.leaving = new Set();
      this.items = after;
    } else {
      // a closing branch stays in the list while it folds shut, and leaves when the fold lands
      this.entering = new Set();
      this.leaving = new Set(this.foldIndex.keys());
    }

    this.foldTimeout = window.setTimeout(() => {
      this.entering = new Set();
      this.leaving = new Set();
      this.foldIndex = new Map();
      this.items = visibleRows(this.tree, this.collapsed);
    }, FOLD_MS);
  }

  // ==========================================================
  // Dragging
  // ==========================================================

  private handleDragStart(row: ArticleRow, event: MouseEvent): void {
    if (!this.sortEndpoint || event.button !== 0) {
      return;
    }

    // keep the drag from selecting text as it crosses rows
    event.preventDefault();
    event.stopPropagation();

    this.dragUuid = row.uuid;
    this.dragStartX = event.clientX;
    this.preview = null;
    this.dropTop = -1;

    document.addEventListener('mousemove', this.handleDragMove);
    document.addEventListener('mouseup', this.handleDragEnd);
  }

  private handleDragMove = (event: MouseEvent): void => {
    const from = this.items.findIndex((row) => row.uuid === this.dragUuid);
    if (from < 0) {
      return;
    }

    const rows = Array.from(
      this.shadowRoot.querySelectorAll('tr.row')
    ) as HTMLElement[];
    if (!rows.length) {
      return;
    }

    // the row we'd land above - the first whose midpoint the pointer is above
    let dropIndex = rows.length;
    for (let i = 0; i < rows.length; i++) {
      const box = rows[i].getBoundingClientRect();
      if (event.clientY < box.top + box.height / 2) {
        dropIndex = i;
        break;
      }
    }

    const wantedDepth =
      this.items[from].depth +
      Math.round((event.clientX - this.dragStartX) / INDENT);

    this.preview = moveSubtree(
      this.items,
      from,
      dropIndex,
      wantedDepth,
      this.maxDepth
    );

    if (!this.preview) {
      this.dropTop = -1;
      return;
    }

    // once the click blocker is armed this is a drag rather than a click, so the mouseup can't also open the article
    this.armClickBlocker();

    const host = this.getBoundingClientRect();
    const edge = rows[Math.min(dropIndex, rows.length - 1)];
    const box = edge.getBoundingClientRect();
    const cell = edge.querySelector('.tree-cell');
    const landed = this.preview.find((row) => row.uuid === this.dragUuid);

    this.dropTop =
      (dropIndex < rows.length ? box.top : box.bottom) - host.top - 1;
    this.dropLeft =
      (cell ? cell.getBoundingClientRect().left - host.left : 0) +
      landed.depth * INDENT;
  };

  private handleDragEnd = (): void => {
    const order = this.preview;
    const moved =
      order &&
      order.some(
        (row, index) =>
          row.uuid !== this.items[index].uuid ||
          row.depth !== this.items[index].depth
      );
    this.endDrag();

    if (moved) {
      // shown straight away, then reconciled against the server's tree either way - it's the authority on what the
      // hierarchy is, and a rejected ordering has to snap back
      this.items = order;
      postJSON(this.sortEndpoint, toOrder(order))
        .catch((error) => {
          console.warn('Failed to save article order', error);
        })
        .finally(() => this.refresh());
    }
  };

  private endDrag(): void {
    document.removeEventListener('mousemove', this.handleDragMove);
    document.removeEventListener('mouseup', this.handleDragEnd);

    this.dragUuid = '';
    this.dropTop = -1;
    this.preview = null;
    this.releaseClickBlocker();
  }

  /** Swallows the click the drop's mouseup synthesizes, which would
   * otherwise fall through to the row and navigate. */
  private armClickBlocker(): void {
    if (this.clickBlocker) {
      return;
    }
    this.clickBlocker = (event: MouseEvent) => {
      event.preventDefault();
      event.stopPropagation();
    };
    document.addEventListener('click', this.clickBlocker, true);
  }

  private releaseClickBlocker(): void {
    if (!this.clickBlocker) {
      return;
    }
    const blocker = this.clickBlocker;
    this.clickBlocker = null;
    // the drop's own click is dispatched after mouseup, so the blocker has to outlive this task to catch it
    window.setTimeout(
      () => document.removeEventListener('click', blocker, true),
      0
    );
  }

  // ==========================================================
  // Rendering
  // ==========================================================

  private renderTitle(row: ArticleRow): TemplateResult {
    const rails = [];
    for (let level = 0; level < row.depth; level++) {
      rails.push(
        html`<span class="rail" style="left: ${level * INDENT + 8}px"></span>`
      );
    }

    const branch = row.height > 0;
    const open = branch && !this.collapsed.has(row.uuid);

    return html`
      <div
        class="tree-cell ${row.uuid === this.dragUuid ? 'dragging' : ''}"
        style="padding-left: ${row.depth * INDENT}px"
      >
        ${rails}
        ${branch
          ? html`<span
              class="disclosure"
              role="button"
              tabindex="0"
              aria-expanded=${open}
              aria-label=${open ? 'Collapse' : 'Expand'}
              @click=${(event: MouseEvent) => this.toggleCollapsed(row, event)}
              @keydown=${(event: KeyboardEvent) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault();
                  this.toggleCollapsed(row, event);
                }
              }}
              ><temba-icon
                name=${open ? Icon.down : Icon.arrow_right}
                size="1"
              ></temba-icon
            ></span>`
          : html`<span class="disclosure" aria-hidden="true"></span>`}
        <span class="title ${branch ? 'branch' : ''}" title=${row.title || ''}
          >${row.title || ''}</span
        >
      </div>
    `;
  }

  protected renderCell(
    item: ArticleRow,
    column: ContentListColumn
  ): TemplateResult | string {
    switch (column.key) {
      case 'drag':
        return html`<temba-icon
          class="drag-handle"
          name=${Icon.drag}
          size="1"
          @mousedown=${(event: MouseEvent) => this.handleDragStart(item, event)}
          @click=${(event: MouseEvent) => event.stopPropagation()}
        ></temba-icon>`;
      case 'title':
        return this.renderTitle(item);
      case 'status':
        // only a draft is worth calling out - published is what an article is for
        return item.status === 'draft'
          ? this.renderStatusPill('neutral', 'Draft')
          : '';
      case 'modified_on':
        return item.modified_on
          ? html`<temba-date
              value=${item.modified_on}
              display="timedate"
            ></temba-date>`
          : '';
      case 'publish':
        return html`<temba-toggle
          class="publish"
          label="Published"
          hide_label
          ?checked=${item.status === 'published'}
          @click=${(event: MouseEvent) => event.stopPropagation()}
          @change=${(event: Event) => this.handlePublishChanged(item, event)}
        ></temba-toggle>`;
      default:
        return super.renderCell(item, column);
    }
  }

  public render(): TemplateResult {
    return html`${super.render()}${this.dropTop >= 0
      ? html`<div
          class="drop-marker"
          style="top: ${this.dropTop}px; left: ${this.dropLeft}px; right: 0"
        ></div>`
      : null}`;
  }
}
