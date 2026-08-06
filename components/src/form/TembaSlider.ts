import { css, html, PropertyValues, TemplateResult } from 'lit';
import { styleMap } from 'lit-html/directives/style-map.js';
import { property } from 'lit/decorators.js';
import { FieldElement } from './FieldElement';
import { getClasses } from '../utils';

export class TembaSlider extends FieldElement {
  static get styles() {
    return css`
      :host {
        display: block;
      }

      .track {
        height: 2px;
        border-top: 0.5em solid var(--surface);
        border-bottom: 0.5em solid var(--surface);
        background: var(--border-strong);
        flex-grow: 1;
      }

      .circle {
        margin-bottom: -1.05em;
        margin-left: -0.5em;
        width: 0.75em;
        height: 0.75em;
        border: 2px solid var(--border-strong);
        border-radius: 999px;
        position: relative;
        background: var(--surface);
        box-shadow: 0 0 0 4px var(--surface);
        transition: transform 200ms ease-in-out;
      }

      .grabbed .track {
        cursor: pointer;
      }

      :hover .circle {
        border-color: var(--text-2);
        cursor: pointer;
      }

      .grabbed .circle {
        border-color: var(--accent);
        background: var(--surface);
      }

      .grabbed .circle {
        transform: scale(1.2);
      }

      .wrapper {
        display: flex;
        align-items: center;
      }

      .pre,
      .post {
        font-size: 0.9em;
        color: var(--text-3);
        padding: 0em 1em;
      }
    `;
  }

  @property({ type: Boolean })
  range = false;

  @property({ type: Number })
  min = 0;

  @property({ type: Number })
  max = 100;

  circleX = 0;
  grabbed = false;

  public firstUpdated(changes: Map<string, any>) {
    super.firstUpdated(changes);
    this.handleMouseMove = this.handleMouseMove.bind(this);
    this.handleMouseUp = this.handleMouseUp.bind(this);
  }

  public willUpdate(changedProperties: PropertyValues): void {
    super.willUpdate(changedProperties);
    if (changedProperties.has('value')) {
      // Normalize value to min/max bounds
      let cValue = parseInt(this.value);
      if (!cValue || cValue < this.min) {
        cValue = this.min;
      } else if (cValue > this.max) {
        cValue = this.max;
      }
      this.value = '' + cValue;
    }
  }

  public updated(changedProperties: Map<string, any>): void {
    if (changedProperties.has('value')) {
      this.updateCircle();
    }
  }

  public updateValue(evt: MouseEvent) {
    const track = this.shadowRoot.querySelector('.track') as HTMLDivElement;
    const left = evt.pageX - track.offsetLeft;
    const pct = left / track.offsetWidth;

    const range = this.max - this.min;
    const pctAsValue = range * pct + this.min;
    this.value =
      '' + Math.max(this.min, Math.min(Math.round(pctAsValue), this.max));
  }

  public handleMouseMove(evt: MouseEvent) {
    if (this.grabbed) {
      this.updateValue(evt);
    }
  }

  public handleTrackDown(evt: MouseEvent) {
    this.grabbed = true;
    document.addEventListener('mousemove', this.handleMouseMove);
    document.addEventListener('mouseup', this.handleMouseUp);
    document.querySelector('html').classList.add('dragging');
    this.updateValue(evt);
    this.requestUpdate();
  }

  public handleMouseUp(evt: MouseEvent) {
    this.grabbed = false;
    this.updateValue(evt);
    this.requestUpdate();

    document.removeEventListener('mousemove', this.handleMouseMove);
    document.removeEventListener('mouseup', this.handleMouseUp);
    document.querySelector('html').classList.remove('dragging');
  }

  public updateCircle() {
    const track = this.shadowRoot.querySelector('.track') as HTMLDivElement;
    const pre = this.shadowRoot.querySelector('.pre') as HTMLDivElement;
    const circle = this.shadowRoot.querySelector('.circle') as HTMLDivElement;
    const range = this.max - this.min;
    const cValue = parseInt(this.value) || this.min;
    const pct = (cValue - this.min) / range;
    const pctAsPixels = track.offsetWidth * pct;

    this.circleX = Math.round(pctAsPixels + (pre ? pre.offsetWidth : 0));
    // directly update DOM to avoid scheduling another update
    circle.style.left = this.circleX + 'px';
  }

  public renderWidget(): TemplateResult {
    return html` <div class="${getClasses({ grabbed: this.grabbed })}">
      <div
        style=${styleMap({ left: this.circleX + 'px' })}
        class="circle"
        @mousedown=${this.handleTrackDown}
      ></div>
      <div class="wrapper">
        ${this.range ? html`<div class="pre">${this.min}</div>` : null}
        <div class="track" @mousedown=${this.handleTrackDown}></div>
        ${this.range ? html`<div class="post">${this.max}</div>` : null}
      </div>
    </div>`;
  }
}
