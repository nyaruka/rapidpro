import {
  css,
  html,
  PropertyValueMap,
  PropertyValues,
  TemplateResult
} from 'lit';
import { property } from 'lit/decorators.js';
import { RapidElement } from '../RapidElement';
import { CustomEventType } from '../interfaces';
import { getClasses, getCookie, setCookie } from '../utils';

export class FloatingWindow extends RapidElement {
  static get styles() {
    return css`
      .window.hidden {
        transform: translateX(100%);
        opacity: 0;
        pointer-events: none;
      }

      .window {
        transition:
          transform var(--transition-duration, 300ms) ease-in-out,
          opacity var(--transition-duration, 300ms) ease-in-out;
        position: fixed;
        z-index: 5000;
        top: 100px;
        background: white;
        border-radius: 8px;
        box-shadow: -4px 4px 20px rgba(0, 0, 0, 0.3);
        display: flex;
        flex-direction: column;
        overflow: hidden;
      }

      .window.chromeless {
        background: transparent;
        border-radius: 0;
        box-shadow: none;
        pointer-events: none;
      }

      .window.chromeless .body {
        pointer-events: none;
      }

      .window.dragging {
        user-select: none;
        cursor: move;
      }

      .header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 6px 6px;
        background: var(--header-color, var(--color-primary-light, #f3f4f6));
        border-bottom: 1px solid rgba(0, 0, 0, 0.1);
        cursor: move;
        user-select: none;
      }

      .title-group {
        display: flex;
        align-items: center;
        gap: 8px;
        min-width: 0;
        padding-left: 8px;
      }

      .title-icon {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 16px;
        height: 16px;
        flex-shrink: 0;
      }

      .title-icon temba-icon {
        --icon-color: white;
      }

      .title {
        font-weight: 600;
        font-size: 16px;
        color: white;
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .close-button {
        background: none;
        border: none;
        cursor: pointer;
        padding: 4px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 4px;
        transition: background-color calc(var(--transition-duration, 150ms) / 2)
          ease-in-out;
      }

      .close-button:hover {
        background-color: rgba(255, 255, 255, 0.2);
      }

      .close-button temba-icon {
        --icon-color: white;
      }

      @keyframes spin {
        0% {
          transform: rotate(0deg);
        }
        100% {
          transform: rotate(360deg);
        }
      }

      .title-icon.saving {
        animation: spin 1s linear infinite;
      }

      .body {
        flex: 1;
        overflow-y: auto;
        padding: 16px;
      }

      .window.chromeless .body {
        padding: 0;
      }

      ::slotted(.drag-handle) {
        cursor: move;
        user-select: none;
        border: 1px solid red;
      }
    `;
  }

  @property({ type: String })
  name = '';

  @property({ type: String })
  header = '';

  @property({ type: String })
  icon = '';

  @property({ type: Number })
  width = 500;

  @property({ type: Number })
  minHeight = 200;

  @property({ type: Number })
  maxHeight = 800;

  @property({ type: Number })
  top = 100;

  @property({ type: Number })
  left = -1; // -1 means calculate from right side

  @property({ type: Boolean })
  hidden = true;

  @property({ type: Boolean })
  dragging = false;

  @property({ type: Boolean })
  chromeless = false;

  @property({ type: String })
  color = '#6B7280';

  @property({ type: Boolean })
  saving = false;

  @property({ type: Number })
  leftBoundaryMargin = 0;

  @property({ type: Number })
  rightBoundaryMargin = 0;

  @property({ type: Number })
  topBoundaryMargin = 0;

  @property({ type: Number })
  bottomBoundaryMargin = 0;

  private dragStartX = 0;
  private dragStartY = 0;
  private dragOffsetX = 0;
  private dragOffsetY = 0;
  private positionFromRight = false;
  private defaultTop = 100;
  private defaultLeft = -1;

  private savePosition(): void {
    if (!this.name) return;
    try {
      const all = JSON.parse(getCookie('window-positions') || '{}');
      all[this.name] = { top: this.top, left: this.left };
      setCookie('window-positions', JSON.stringify(all));
    } catch {
      // ignore
    }
  }

  private getSavedPosition(): { top: number; left: number } | null {
    if (!this.name) return null;
    try {
      const all = JSON.parse(getCookie('window-positions') || '{}');
      const pos = all[this.name];
      if (pos && typeof pos.top === 'number' && typeof pos.left === 'number') {
        return pos;
      }
    } catch {
      // ignore
    }
    return null;
  }

  private clampPosition(): void {
    const padding = 20;
    const windowElement = this.shadowRoot?.querySelector(
      '.window'
    ) as HTMLElement;
    const currentHeight =
      windowElement?.offsetHeight || this.maxHeight || window.innerHeight;

    this.left = Math.max(
      padding - this.leftBoundaryMargin,
      Math.min(
        this.left,
        window.innerWidth - this.width - padding + this.rightBoundaryMargin
      )
    );

    const maxTop = Math.max(
      padding - this.topBoundaryMargin,
      window.innerHeight - currentHeight - padding + this.bottomBoundaryMargin
    );
    this.top = Math.max(
      padding - this.topBoundaryMargin,
      Math.min(this.top, maxTop)
    );
  }

  public firstUpdated(
    changes: PropertyValueMap<any> | Map<PropertyKey, unknown>
  ): void {
    super.firstUpdated(changes);

    // store the default position from properties
    this.defaultTop = this.top;
    this.defaultLeft = this.left;

    // determine if we should position from right side
    if (this.left === -1) {
      this.positionFromRight = true;
    }

    // set up drag handle listeners for chromeless windows
    if (this.chromeless) {
      this.setupDragHandles();
    }

    // listen for window resize to keep window in bounds
    window.addEventListener('resize', this.handleResize);
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    window.removeEventListener('resize', this.handleResize);
  }

  private setupDragHandles() {
    // listen for mousedown on slotted content
    this.addEventListener('mousedown', this.handleSlotMouseDown);
  }

  private handleSlotMouseDown = (event: MouseEvent) => {
    // check if the target or any parent has the drag-handle class
    const target = event.target as HTMLElement;
    const dragHandle = target.closest('.drag-handle');

    if (!dragHandle) {
      return;
    }

    this.dragging = true;
    this.dragStartX = event.clientX;
    this.dragStartY = event.clientY;
    this.dragOffsetX = this.left;
    this.dragOffsetY = this.top;

    document.addEventListener('mousemove', this.handleMouseMove);
    document.addEventListener('mouseup', this.handleMouseUp);

    event.preventDefault();
  };

  public willUpdate(changes: PropertyValues): void {
    super.willUpdate(changes);
    if (this.hasUpdated && changes.has('hidden')) {
      // when hiding, reset positioning behavior to original
      if (this.hidden && changes.get('hidden') === false) {
        if (this.defaultLeft === -1) {
          this.positionFromRight = true;
        }
      }

      // restore position when showing
      if (!this.hidden && changes.get('hidden') === true) {
        const saved = this.getSavedPosition();
        if (saved) {
          this.top = saved.top;
          this.left = saved.left;
          this.positionFromRight = false;
          this.clampPosition();
        } else {
          // no saved position — use defaults
          this.top = this.defaultTop;
          if (this.positionFromRight) {
            this.left = window.innerWidth - this.width - 80;
          } else {
            this.left = this.defaultLeft;
          }
        }
      }
    }
  }

  public updated(
    changes: PropertyValueMap<any> | Map<PropertyKey, unknown>
  ): void {
    super.updated(changes);

    // setup drag handles if chromeless changed to true
    if (changes.has('chromeless') && this.chromeless) {
      this.setupDragHandles();
    }
  }

  public handleClose() {
    this.hidden = true;
    this.fireCustomEvent(CustomEventType.DialogHidden);
  }

  private handleHeaderMouseDown(event: MouseEvent) {
    // don't start drag if clicking on close button
    if ((event.target as HTMLElement).closest('.close-button')) {
      return;
    }

    this.dragging = true;
    this.dragStartX = event.clientX;
    this.dragStartY = event.clientY;
    this.dragOffsetX = this.left;
    this.dragOffsetY = this.top;

    document.addEventListener('mousemove', this.handleMouseMove);
    document.addEventListener('mouseup', this.handleMouseUp);

    event.preventDefault();
  }

  private handleMouseMove = (event: MouseEvent) => {
    if (!this.dragging) return;

    const deltaX = event.clientX - this.dragStartX;
    const deltaY = event.clientY - this.dragStartY;

    this.left = this.dragOffsetX + deltaX;
    this.top = this.dragOffsetY + deltaY;

    // keep window within viewport bounds with 20px padding
    const padding = 20;
    this.left = Math.max(
      padding - this.leftBoundaryMargin,
      Math.min(
        this.left,
        window.innerWidth - this.width - padding + this.rightBoundaryMargin
      )
    );

    // get the actual rendered height of the window element
    const windowElement = this.shadowRoot?.querySelector(
      '.window'
    ) as HTMLElement;
    const currentHeight =
      windowElement?.offsetHeight || this.maxHeight || window.innerHeight;
    const maxTop = Math.max(
      padding - this.topBoundaryMargin,
      window.innerHeight - currentHeight - padding + this.bottomBoundaryMargin
    );
    this.top = Math.max(
      padding - this.topBoundaryMargin,
      Math.min(this.top, maxTop)
    );
  };

  private handleMouseUp = () => {
    this.dragging = false;
    document.removeEventListener('mousemove', this.handleMouseMove);
    document.removeEventListener('mouseup', this.handleMouseUp);

    // once user drags the window, stop auto-positioning from right
    this.positionFromRight = false;
    this.savePosition();
  };

  private handleResize = () => {
    // only constrain position if window is visible
    if (this.hidden) return;

    const padding = 20;
    const windowElement = this.shadowRoot?.querySelector(
      '.window'
    ) as HTMLElement;
    const currentHeight =
      windowElement?.offsetHeight || this.maxHeight || window.innerHeight;

    // if positioned from right, always recalculate from right edge
    if (this.positionFromRight) {
      this.left =
        window.innerWidth - this.width - padding + this.rightBoundaryMargin;
    } else {
      // only adjust left if out of bounds
      const minLeft = padding - this.leftBoundaryMargin;
      const maxLeft =
        window.innerWidth - this.width - padding + this.rightBoundaryMargin;

      if (this.left < minLeft) {
        this.left = minLeft;
      } else if (this.left > maxLeft) {
        this.left = maxLeft;
      }
    }

    // only adjust top if out of bounds
    const minTop = padding - this.topBoundaryMargin;
    const maxTop = Math.max(
      padding - this.topBoundaryMargin,
      window.innerHeight - currentHeight - padding + this.bottomBoundaryMargin
    );

    if (this.top < minTop) {
      this.top = minTop;
    } else if (this.top > maxTop) {
      this.top = maxTop;
    }
  };

  public show() {
    this.hidden = false;
  }

  public hide() {
    this.hidden = true;
  }

  public close() {
    this.hidden = true;
    this.fireCustomEvent(CustomEventType.DialogHidden);
  }

  public render(): TemplateResult {
    const minHeightStyle = this.minHeight
      ? `min-height: ${this.minHeight}px;`
      : '';
    const maxHeightStyle = this.maxHeight
      ? `max-height: ${this.maxHeight}px;`
      : '';

    const windowStyle = `
      width: ${this.width}px;
      ${minHeightStyle}
      ${maxHeightStyle}
      top: ${this.top}px;
      left: ${this.left}px;
      --header-color: ${this.color};
    `;

    const windowClasses = getClasses({
      window: true,
      dragging: this.dragging,
      hidden: this.hidden,
      chromeless: this.chromeless
    });
    const iconName = this.saving ? 'progress_spinner' : this.icon;

    return html`
      <div class="${windowClasses}" style="${windowStyle}">
        ${!this.chromeless
          ? html`
              <div class="header" @mousedown=${this.handleHeaderMouseDown}>
                <div class="title-group">
                  ${iconName
                    ? html`
                        <div class="title-icon ${this.saving ? 'saving' : ''}">
                          <temba-icon
                            size="1.3"
                            name="${iconName}"
                          ></temba-icon>
                        </div>
                      `
                    : ''}
                  <div class="title">${this.header}</div>
                </div>
                <button class="close-button" @click=${this.handleClose}>
                  <temba-icon name="close" size="1.5"></temba-icon>
                </button>
              </div>
            `
          : ''}
        <div class="body">
          <slot></slot>
        </div>
      </div>
    `;
  }
}
