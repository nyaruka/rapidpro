import { PropertyValueMap, css, html } from 'lit';
import { getClasses } from '../utils';
import { property } from 'lit/decorators.js';
import { CustomEventType } from '../interfaces';
import { ResizeElement } from '../ResizeElement';

export class Resizer extends ResizeElement {
  static styles = css`
    :host {
      display: block;
      position: relative;
      width: var(--box-width, 200px);
      /* hold the drag-clamp floor against flex compression too, so
         shrinking the browser can't squeeze us below minWidth */
      min-width: var(--box-min-width, 200px);
      --resizer-handle-size: 15px;
    }

    .resizer {
      position: absolute;
      right: calc(var(--resizer-handle-size) * -1);
      height: 100%;
      cursor: col-resize;
      padding: 0 calc(var(--resizer-handle-size) / 2);
      z-index: 1;
    }

    .resizer-handle {
      position: relative;
      width: 4px;
      background: rgba(0, 0, 0, 0);
      height: 100%;
    }

    .resizer:hover .resizer-handle {
      background: rgba(0, 0, 0, 0.05);
      width: 3px;
      margin-right: -1px;
    }

    .resizing .resizer-handle {
      background: rgba(0, 0, 0, 0.1) !important;
      width: 3px;
      margin-right: -1px;
    }

    slot {
      margin-right: var(--resizer-handle-size);
      background: red;
    }
  `;

  initialX: number;
  boxWidth: number;

  @property({ type: Number })
  minWidth = 200;

  @property({ type: Number })
  maxWidth = 2000;

  @property({ type: Boolean })
  resizing = false;

  @property({ type: Number })
  currentWidth: number;

  constructor() {
    super();
    this.startResize = this.startResize.bind(this);
    this.resize = this.resize.bind(this);
    this.stopResize = this.stopResize.bind(this);
  }

  protected willUpdate(
    changes: PropertyValueMap<any> | Map<PropertyKey, unknown>
  ): void {
    super.willUpdate(changes);
    // clamp programmatic width sets (e.g. a stored width restored on
    // load) the same way drags are clamped
    if (changes.has('currentWidth') && this.currentWidth != null) {
      this.currentWidth = Math.min(
        Math.max(this.currentWidth, this.minWidth),
        this.maxWidth
      );
    }
  }

  protected updated(
    _changedProperties: PropertyValueMap<any> | Map<PropertyKey, unknown>
  ): void {
    super.updated(_changedProperties);
    if (_changedProperties.has('currentWidth')) {
      this.style.setProperty('--box-width', `${this.currentWidth}px`);
    }
    if (_changedProperties.has('minWidth')) {
      this.style.setProperty('--box-min-width', `${this.minWidth}px`);
    }
  }

  public setWidth(width: number) {
    const newWidth = Math.min(Math.max(width, this.minWidth), this.maxWidth);
    this.currentWidth = newWidth;
  }

  startResize(e: MouseEvent) {
    this.initialX = e.x;
    this.boxWidth = this.offsetWidth;
    document.body.style.userSelect = 'none';
    this.resizing = true;
    window.addEventListener('mousemove', this.resize);
    window.addEventListener('mouseup', this.stopResize);
    this.requestUpdate();
  }

  resize(event: MouseEvent) {
    const dx = event.x - this.initialX;
    this.setWidth(this.boxWidth + dx);
  }

  stopResize() {
    document.body.style.userSelect = 'initial';
    window.removeEventListener('mousemove', this.resize);
    window.removeEventListener('mouseup', this.stopResize);
    this.requestUpdate();
    this.resizing = false;

    this.fireCustomEvent(CustomEventType.Resized, { width: this.currentWidth });
  }

  render() {
    return html`
      <div
        class=${getClasses({ resizer: true, resizing: this.resizing })}
        @mousedown="${this.startResize}"
      >
        <div class=${getClasses({ 'resizer-handle': true })}></div>
      </div>
      <slot></slot>
    `;
  }
}
