import { html, TemplateResult } from 'lit-html';
import { css } from 'lit';
import { property } from 'lit/decorators.js';
import { RapidElement } from '../RapidElement';
import { CustomEventType } from '../interfaces';
import { FlowIssue } from '../store/AppState';
import { formatIssueMessage } from './utils';

export class IssuesWindow extends RapidElement {
  static get styles() {
    return css`
      :host {
        display: contents;
      }

      .issue-list-item {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px;
        border-radius: 4px;
        cursor: pointer;
      }

      .issue-list-item:hover {
        background: #fff1f0;
      }
    `;
  }

  @property({ type: Array })
  issues: FlowIssue[] = [];

  @property({ type: Boolean })
  hidden = true;

  private handleItemClick(issue: FlowIssue): void {
    this.fireCustomEvent(CustomEventType.IssueSelected, { issue });
  }

  public render(): TemplateResult | string {
    if (!this.issues?.length) return '';
    return html`
      <temba-floating-window
        id="issues-window"
        name="issues"
        header="Flow Issues"
        icon="alert_warning"
        .width=${360}
        .maxHeight=${600}
        .top=${120}
        color="tomato"
        .hidden=${this.hidden}
        @temba-dialog-hidden=${() =>
          this.fireCustomEvent(CustomEventType.IssuesClosed)}
      >
        <div style="display:flex; flex-direction:column; gap:2px;">
          ${this.issues.map(
            (issue) => html`
              <div
                class="issue-list-item"
                @click=${() => this.handleItemClick(issue)}
              >
                <temba-icon name="alert_warning" size="1.2"></temba-icon>
                <span>${formatIssueMessage(issue)}</span>
              </div>
            `
          )}
        </div>
      </temba-floating-window>
    `;
  }
}
