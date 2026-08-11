import { css, html, PropertyValueMap, TemplateResult } from 'lit';
import { property, state } from 'lit/decorators.js';
import { RapidElement } from '../RapidElement';
import { CustomEventType } from '../interfaces';
import { ContextMenuShortcut } from './types';

/**
 * Event detail for canvas menu selection. `action` is either one of the
 * built-in menu actions ('sticky', 'other', 'reflow') or the `type` of a
 * configured shortcut (e.g. 'send_msg', 'say_msg', 'set_contact_field').
 */
export interface CanvasMenuSelection {
  action: string;
  position: { x: number; y: number };
}

/**
 * CanvasMenu - A popup menu for adding items to the flow canvas
 * Displayed when double-clicking on empty canvas space
 */
export class CanvasMenu extends RapidElement {
  static get styles() {
    return css`
      :host {
        position: fixed;
        z-index: 10000;
        display: block;
        pointer-events: none;
      }

      .menu {
        position: fixed;
        background: white;
        border-radius: var(--curvature);
        box-shadow: var(--dropdown-shadow);
        padding: 0.5em 0;
        width: 265px;
        pointer-events: auto;
      }

      .menu-item {
        padding: 0.75em 1.5em;
        cursor: pointer;
        display: flex;
        align-items: flex-start;
        gap: 0.75em;
        transition: background-color 0.15s ease;
      }

      .menu-item:hover {
        background-color: rgba(0, 0, 0, 0.05);
      }

      .menu-item temba-icon {
        --icon-color: var(--color-text);
      }

      .menu-item-title {
        font-weight: 500;
        font-size: 1rem;
        color: var(--color-text-dark);
      }

      .divider {
        height: 1px;
        background: rgba(0, 0, 0, 0.1);
        margin: 0.5em 0;
      }
    `;
  }

  @property({ type: Number })
  public x = 0;

  @property({ type: Number })
  public y = 0;

  @property({ type: Boolean })
  public open = false;

  @property({ type: Boolean })
  public showStickyNote = true;

  @property({ type: Array })
  public shortcuts: ContextMenuShortcut[] = [];

  @property({ type: Boolean })
  public showReflow = false;

  @state()
  private clickPosition = { x: 0, y: 0 };

  protected firstUpdated(
    _changedProperties: PropertyValueMap<any> | Map<PropertyKey, unknown>
  ): void {
    super.firstUpdated(_changedProperties);

    // Close menu when clicking/tapping outside — use mousedown instead of
    // click to avoid being triggered by the click synthesized from a
    // drag-and-drop (mousedown on exit + mouseup on canvas = click on
    // common ancestor). Also listen for touchstart for touch devices.
    const handleClickOutside = (e: MouseEvent | TouchEvent) => {
      if (this.open && !this.contains(e.target as Node)) {
        this.close();
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('touchstart', handleClickOutside, {
      passive: true
    });

    // Store cleanup function
    (this as any)._clickOutsideHandler = handleClickOutside;
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    if ((this as any)._clickOutsideHandler) {
      document.removeEventListener(
        'mousedown',
        (this as any)._clickOutsideHandler
      );
      document.removeEventListener(
        'touchstart',
        (this as any)._clickOutsideHandler
      );
    }
  }

  public show(
    x: number,
    y: number,
    clickPosition: { x: number; y: number },
    showStickyNote: boolean = true,
    showReflow: boolean = false,
    shortcuts: ContextMenuShortcut[] = []
  ) {
    this.x = x;
    this.y = y;
    this.clickPosition = clickPosition;
    this.showStickyNote = showStickyNote;
    this.showReflow = showReflow;
    this.shortcuts = shortcuts;
    this.open = true;

    // Adjust position after menu renders to ensure it fits on screen
    requestAnimationFrame(() => {
      this.adjustPosition();
    });
  }

  private adjustPosition(): void {
    const menuElement = this.shadowRoot?.querySelector('.menu') as HTMLElement;
    if (!menuElement) return;

    const menuRect = menuElement.getBoundingClientRect();
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    const margin = 10; // margin from viewport edges

    let adjustedX = this.x;
    let adjustedY = this.y;

    // Check if menu goes off the right edge
    if (this.x + menuRect.width + margin > viewportWidth) {
      adjustedX = viewportWidth - menuRect.width - margin;
    }

    // Check if menu goes off the bottom edge
    if (this.y + menuRect.height + margin > viewportHeight) {
      adjustedY = viewportHeight - menuRect.height - margin;
    }

    // Update position if needed
    if (adjustedX !== this.x || adjustedY !== this.y) {
      this.x = adjustedX;
      this.y = adjustedY;
    }
  }

  public close(fireCanceledEvent: boolean = true) {
    if (this.open) {
      this.open = false;
      // Fire close event so parent can clean up, but only if not from a selection
      if (fireCanceledEvent) {
        this.fireCustomEvent(CustomEventType.Canceled, {});
      }
    }
  }

  private handleMenuItemClick(action: CanvasMenuSelection['action']) {
    this.fireCustomEvent(CustomEventType.Selection, {
      action,
      position: this.clickPosition
    } as CanvasMenuSelection);
    // Close without firing canceled event since we made a selection
    this.close(false);
  }

  public render(): TemplateResult {
    if (!this.open) {
      return html``;
    }

    return html`
      <div class="menu" style="left: ${this.x}px; top: ${this.y}px;">
        ${this.shortcuts.map(
          (shortcut) => html`
            <div
              class="menu-item"
              @click=${() => this.handleMenuItemClick(shortcut.type)}
            >
              <temba-icon name="${shortcut.icon}" size="1.25"></temba-icon>
              <div class="menu-item-title">${shortcut.name}</div>
            </div>
          `
        )}

        <div
          class="menu-item"
          @click=${() => this.handleMenuItemClick('other')}
        >
          <temba-icon name="plus" size="1.25"></temba-icon>
          <div class="menu-item-title">Add Other</div>
        </div>

        ${this.showStickyNote
          ? html`
              <div class="divider"></div>

              <div
                class="menu-item"
                @click=${() => this.handleMenuItemClick('sticky')}
              >
                <temba-icon name="note" size="1.25"></temba-icon>
                <div class="menu-item-title">Add Sticky Note</div>
              </div>
            `
          : ''}
        ${this.showReflow
          ? html`
              <div class="divider"></div>

              <div
                class="menu-item"
                @click=${() => this.handleMenuItemClick('reflow')}
              >
                <temba-icon name="flow" size="1.25"></temba-icon>
                <div class="menu-item-title">Reflow</div>
              </div>
            `
          : ''}
      </div>
    `;
  }
}
