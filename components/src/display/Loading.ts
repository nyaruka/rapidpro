import { html, TemplateResult, css, LitElement } from 'lit';
import { property } from 'lit/decorators.js';
import { styleMap } from 'lit-html/directives/style-map.js';
import { range } from '../utils';

export class Loading extends LitElement {
  static get styles() {
    return css`
      :host {
        display: block;
      }

      .loading-unit {
        border: 1px inset rgba(0, 0, 0, 0.05);
        animation: loading-pulse 0.9s cubic-bezier(0.3, 0, 0.7, 1) infinite;
      }

      .loading-container {
        display: flex;
      }

      @keyframes loading-pulse {
        0% {
          transform: scale(0.2);
          opacity: 0.1;
        }
        20% {
          transform: scale(1);
          opacity: 1;
        }
        100% {
          transform: scale(0.2);
          opacity: 0.1;
        }
      }
    `;
  }

  @property({ type: String })
  color = 'var(--color-primary-dark)';

  @property({ type: Number })
  size = 5;

  @property({ type: Number })
  units = 5;

  @property({ type: Boolean })
  square?: boolean;

  @property({ type: String })
  direction = 'row';

  public render(): TemplateResult {
    const margin = this.size / 2;

    return html`
      <div class="loading-container" style="flex-direction:${this.direction}">
        ${range(0, this.units).map((num: number) => {
          const ballStyle = {
            'border-radius': this.square ? '0' : '50%',
            width: this.size + 'px',
            height: this.size + 'px',
            margin: margin + 'px',
            animationDelay: `-${1 - num * (1 / this.units)}s`,
            background: this.color
          };
          return html`
            <div class="loading-unit" style=${styleMap(ballStyle)}></div>
          `;
        })}
      </div>
    `;
  }
}
