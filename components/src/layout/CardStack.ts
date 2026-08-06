import { css, html, TemplateResult } from 'lit';
import { property } from 'lit/decorators.js';
import { RapidElement } from '../RapidElement';
import { CustomEventType } from '../interfaces';

/**
 * A vertical stack of temba-cards that can be reordered by dragging their
 * headers. Owns the DOM move on drop and re-emits temba-order-changed with
 * the full id list so hosts only deal in ids. An initial order can be
 * passed via the `order` attribute (JSON array of child ids).
 */
export class CardStack extends RapidElement {
  static get styles() {
    return css`
      :host {
        display: block;
      }
    `;
  }

  @property({ type: Array })
  order: string[] = [];

  /** Vertical gap between cards — the layout's one spacing unit, so
   * card-to-card spacing matches the gap between the main view and the
   * card column. */
  @property({ type: String })
  gap = 'var(--layout-spacing, 8px)';

  private getAssigned(): Element[] {
    // resolve through the shadow slot so cards forwarded from a wrapper
    // component's slot (e.g. temba-card-layout) are seen too
    const slot = this.shadowRoot?.querySelector('slot');
    return slot
      ? slot.assignedElements({ flatten: true })
      : Array.from(this.children);
  }

  private getCards(): HTMLElement[] {
    return this.getAssigned().filter(
      (ele) => ele.classList.contains('sortable') && ele.id
    ) as HTMLElement[];
  }

  public getIds(): string[] {
    return this.getCards().map((ele) => ele.id);
  }

  private handleSlotChange() {
    // cards are expected to carry .sortable for SortableList; add it so
    // consumers don't have to remember. Only actual cards — an incidental
    // id'd element passing through the slot shouldn't become draggable.
    this.getAssigned().forEach((ele) => {
      if (ele.tagName === 'TEMBA-CARD' && ele.id) {
        ele.classList.add('sortable');
      }
    });
    this.applyOrder();
  }

  protected updated(changes: Map<PropertyKey, unknown>): void {
    super.updated(changes);
    if (changes.has('order')) {
      this.applyOrder();
    }
  }

  private applyOrder() {
    if (!this.order || this.order.length === 0) {
      return;
    }

    const cards = this.getCards();
    const listed = this.order
      .map((id) => cards.find((card) => card.id === id))
      .filter(Boolean) as HTMLElement[];
    const unlisted = cards.filter((card) => !listed.includes(card));
    const desired = [...listed, ...unlisted];

    if (desired.every((card, idx) => card === cards[idx])) {
      return;
    }

    // move within whatever parent actually holds the cards (this element,
    // or the wrapper host when cards arrive through a forwarded slot)
    desired.forEach((card) => card.parentElement?.appendChild(card));
  }

  private handleOrderChanged(event: CustomEvent) {
    // the inner sortable list reports a swap but leaves the DOM alone;
    // perform the move here and surface the resulting id order instead
    event.stopPropagation();

    const [fromIdx, toIdx] = event.detail.swap;
    const cards = this.getCards();
    const moving = cards[fromIdx];
    const target = cards[toIdx];
    if (!moving || !target || moving === target) {
      return;
    }

    if (fromIdx < toIdx) {
      target.insertAdjacentElement('afterend', moving);
    } else {
      target.insertAdjacentElement('beforebegin', moving);
    }

    this.order = this.getIds();
    this.fireCustomEvent(CustomEventType.OrderChanged, { ids: this.order });
  }

  /**
   * The ghost is a deep clone appended to document.body, sized to the
   * original card — so an open card drags as an open card. Cloned panels
   * re-render from the store's cache; clip anything still settling.
   */
  private prepareGhost = (ghost: HTMLElement) => {
    ghost.removeAttribute('id');
    ghost.style.overflow = 'hidden';
  };

  public render(): TemplateResult {
    return html`
      <temba-sortable-list
        dragHandle="card-header"
        gap=${this.gap}
        .prepareGhost=${this.prepareGhost}
        @temba-order-changed=${this.handleOrderChanged}
      >
        <slot @slotchange=${this.handleSlotChange}></slot>
      </temba-sortable-list>
    `;
  }
}
