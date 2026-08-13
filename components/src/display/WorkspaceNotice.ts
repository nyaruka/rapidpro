import { TemplateResult, css, html } from 'lit';
import { property } from 'lit/decorators.js';
import { msg, str } from '@lit/localize';
import { RapidElement } from '../RapidElement';
import { getStore } from '../store/Store';
import { isWorkspaceStale, onWorkspaceStale } from '../workspace';

/**
 * Tells the user that this page is showing a workspace they have since
 * switched away from. Deliberately a banner rather than a reload - the page
 * may be holding work that isn't saved yet, so leaving is the user's call.
 */
export class WorkspaceNotice extends RapidElement {
  static styles = css`
    :host {
      position: fixed;
      display: flex;
      justify-content: center;
      width: 100%;
      top: 0;
      z-index: 10000;
      pointer-events: none;
    }

    temba-alert {
      pointer-events: all;
      max-width: 40em;
      margin: 0.75em;
    }

    .banner {
      display: flex;
      align-items: center;
      gap: 1em;
    }

    .message {
      flex-grow: 1;
    }
  `;

  @property({ type: Boolean })
  stale = false;

  private unsubscribe: () => void;

  public connectedCallback(): void {
    super.connectedCallback();
    this.stale = isWorkspaceStale();
    this.unsubscribe = onWorkspaceStale(() => {
      this.stale = true;
    });
  }

  public disconnectedCallback(): void {
    if (this.unsubscribe) {
      this.unsubscribe();
      this.unsubscribe = null;
    }
    super.disconnectedCallback();
  }

  private handleRefresh(): void {
    window.location.reload();
  }

  /** The workspace this page rendered, which is the one it is stuck showing. */
  private getWorkspaceName(): string {
    return getStore()?.getWorkspace()?.name;
  }

  public render(): TemplateResult {
    if (!this.stale) {
      return html``;
    }

    const name = this.getWorkspaceName();
    const message = name
      ? msg(
          str`This page is showing ${name}. You've since switched workspaces, so refresh to catch up.`
        )
      : msg(
          `This page is showing a workspace you've since switched away from, so refresh to catch up.`
        );

    return html`
      <temba-alert level="warning">
        <div class="banner" role="status">
          <div class="message">${message}</div>
          <temba-button
            name=${msg('Refresh')}
            @click=${this.handleRefresh}
          ></temba-button>
        </div>
      </temba-alert>
    `;
  }
}
