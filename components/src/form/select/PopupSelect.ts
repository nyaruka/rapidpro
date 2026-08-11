import { css, html } from 'lit';
import { RapidElement } from '../../RapidElement';
import { property } from 'lit/decorators.js';

export class PopupSelect extends RapidElement {
  public static styles = css`
    :host {
    }

    .dropdown {
      background: #fff;
      border-radius: 0.5em;
      padding: 0.15em;
      border-radius: var(--curvature);
    }

    temba-select {
      width: 250px;
      display: block;
      --color-widget-border: transparent;
      --widget-box-shadow: none;
    }
  `;

  @property({ type: String })
  placeholder: string = '';

  @property({ type: String })
  endpoint: string = '';

  private handleChange() {
    this.blur();
  }

  public render() {
    return html`
      <div>
        <temba-dropdown>
          <div slot="toggle"><slot name="toggle"></slot></div>
          <div class="dropdown" slot="dropdown">
            <temba-select
              placeholder=${this.placeholder}
              endpoint=${this.endpoint}
              clearable
              searchable
              @change=${this.handleChange}
            ></temba-select>
          </div>
        </temba-dropdown>
      </div>
    `;
  }
}
